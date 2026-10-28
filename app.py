from flask import Flask, jsonify, request, session
from functools import wraps
import os
import hmac
from datetime import datetime
from database import get_connection, init_db

app = Flask(__name__)


app.config["SECRET_KEY"] = os.environ["FLASK_SECRET_KEY"]

USUARIO_ADMIN = os.environ["ADMIN_USUARIO"]
SENHA_ADMIN = os.environ["ADMIN_SENHA"]


def login_obrigatorio(func):
    @wraps(func)
    def verificar_login(*args, **kwargs):
        if not session.get("autenticado"):
            return jsonify({
                "erro": "Autenticacao necessaria."
            }), 401

        return func(*args, **kwargs)

    return verificar_login


@app.route("/login", methods=["POST"])
def login():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "erro": "Envie usuario e senha em JSON."
        }), 400

    usuario = dados.get("usuario")
    senha = dados.get("senha")

    if (
        isinstance(usuario, str)
        and isinstance(senha, str)
        and hmac.compare_digest(usuario, USUARIO_ADMIN)
        and hmac.compare_digest(senha, SENHA_ADMIN)
    ):
        session.clear()
        session["autenticado"] = True

        return jsonify({
            "mensagem": "Login realizado com sucesso."
        }), 200

    return jsonify({
        "erro": "Usuario ou senha incorretos."
    }), 401


@app.route("/logout", methods=["POST"])
@login_obrigatorio
def logout():
    session.clear()

    return jsonify({
        "mensagem": "Logout realizado com sucesso."
    }), 200

@app.route("/", methods=["GET"])
def inicio():
    return """
    <h1>Sistema de Segurança RFID</h1>
    <p>API de controle de acesso RFID.</p>

    <h2>Funcionamento</h2>
    <ul>
        <li>GET /health - Verificar funcionamento</li>
    </ul>

    <h2>Colaboradores</h2>
    <ul>
        <li>GET /colaboradores - Listar colaboradores</li>
        <li>POST /colaboradores - Cadastrar colaborador</li>
        <li>PUT/PATCH /colaboradores/&lt;int:id&gt; - Editar colaborador</li>
        <li>DELETE /colaboradores/&lt;int:id&gt; - Desativar colaborador</li>
    </ul>

    <h2>Cartões RFID</h2>
    <ul>
        <li>POST /cartoes - Cadastrar cartão</li>
        <li>PUT/PATCH /colaboradores/&lt;int:id&gt;/cartao - Atualizar cartão</li>
        <li>POST /rfid/validar - Validar cartão</li>
    </ul>

    <h2>Acessos</h2>
    <ul>
        <li>GET /acessos - Consultar registros</li>
        <li>POST /acessos/registrar - Registrar acesso</li>
    </ul>

    <h2>Monitoramento</h2>
    <ul>
        <li>GET /monitoramento - Consultar indicadores</li>
    </ul>
    """



@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "servico": "Sistema de Seguranca RFID"
    }), 200


@app.route("/colaboradores", methods=["GET"])
@login_obrigatorio
def listar_colaboradores():
    connection = get_connection()

    try:
        colaboradores = connection.execute("""
            SELECT
                c.id,
                c.matricula,
                c.nome,
                c.funcao,
                c.autorizado,
                c.ativo,
                cr.uid AS cartao_rfid
            FROM colaboradores c
            LEFT JOIN cartoes_rfid cr
                ON cr.colaborador_id = c.id
            ORDER BY c.nome
        """).fetchall()

        return jsonify([
            dict(colaborador)
            for colaborador in colaboradores
        ])

    finally:
        connection.close()


@app.route("/colaboradores", methods=["POST"])
@login_obrigatorio
def cadastrar_colaborador():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "erro": "Envie os dados em formato JSON."
        }), 400

    campos_obrigatorios = [
        "matricula",
        "nome",
        "funcao"
    ]

    for campo in campos_obrigatorios:
        if not isinstance(dados.get(campo), str) or not dados[campo].strip():
            return jsonify({
                "erro": f"O campo '{campo}' e obrigatorio."
            }), 400

    autorizado = dados.get("autorizado", False)

    if not isinstance(autorizado, bool):
        return jsonify({
            "erro": "O campo 'autorizado' deve ser true ou false."
        }), 400

    matricula = dados["matricula"].strip()
    nome = dados["nome"].strip()
    funcao = dados["funcao"].strip()

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO colaboradores (
                matricula,
                nome,
                funcao,
                autorizado
            )
            VALUES (?, ?, ?, ?)
        """, (
            matricula,
            nome,
            funcao,
            int(autorizado)
        ))

        connection.commit()

        return jsonify({
            "mensagem": "Colaborador cadastrado com sucesso.",
            "id": cursor.lastrowid,
            "matricula": matricula,
            "nome": nome,
            "funcao": funcao,
            "autorizado": autorizado
        }), 201

    except Exception as erro:
        connection.rollback()

        if "UNIQUE constraint failed" in str(erro):
            return jsonify({
                "erro": "Essa matricula ja esta cadastrada."
            }), 409

        app.logger.exception("Erro ao cadastrar colaborador")

        return jsonify({
            "erro": "Nao foi possivel cadastrar o colaborador."
        }), 500

    finally:
        connection.close()


@app.route("/acessos", methods=["GET"])
@login_obrigatorio
def listar_acessos():
    connection = get_connection()

    try:
        registros = connection.execute("""
            SELECT
                r.id,
                r.uid,
                r.evento,
                r.resultado,
                r.registrado_em,
                c.matricula,
                c.nome
            FROM registros_acesso r
            LEFT JOIN colaboradores c
                ON c.id = r.colaborador_id
            ORDER BY r.id DESC
            LIMIT 100
        """).fetchall()

        return jsonify([
            dict(registro)
            for registro in registros
        ])

    finally:
        connection.close()


@app.route("/monitoramento", methods=["GET"])
@login_obrigatorio
def monitoramento():
    connection = get_connection()

    try:
        total_colaboradores = connection.execute("""
            SELECT COUNT(*) AS total
            FROM colaboradores
            WHERE ativo = 1
        """).fetchone()["total"]

        total_autorizados = connection.execute("""
            SELECT COUNT(*) AS total
            FROM colaboradores
            WHERE ativo = 1 AND autorizado = 1
        """).fetchone()["total"]

        total_acessos = connection.execute("""
            SELECT COUNT(*) AS total
            FROM registros_acesso
        """).fetchone()["total"]

        total_negados = connection.execute("""
            SELECT COUNT(*) AS total
            FROM registros_acesso
            WHERE resultado = 'negado'
        """).fetchone()["total"]

        
        ultimos_acessos = connection.execute("""
            SELECT
                r.id,
                r.uid,
                r.evento,
                r.resultado,
                r.registrado_em,
                c.nome,
                c.matricula
            FROM registros_acesso r
            LEFT JOIN colaboradores c
                ON c.id = r.colaborador_id
            ORDER BY r.id DESC
            LIMIT 20
        """).fetchall()

        
        colaboradores_na_sala = connection.execute("""
            SELECT
                c.id,
                c.nome,
                c.matricula,
                r.registrado_em AS entrada_em
            FROM registros_acesso r
            INNER JOIN colaboradores c
                ON c.id = r.colaborador_id
            WHERE r.id = (
                SELECT MAX(r2.id)
                FROM registros_acesso r2
                WHERE r2.colaborador_id = c.id
                  AND r2.evento IN ('entrada', 'saida')
                  AND r2.resultado = 'permitido'
            )
            AND r.evento = 'entrada'
            AND r.resultado = 'permitido'
        """).fetchall()

        
        alertas_recentes = connection.execute("""
            SELECT
                r.id,
                r.uid,
                r.evento,
                r.resultado,
                r.registrado_em,
                c.nome,
                c.matricula
            FROM registros_acesso r
            LEFT JOIN colaboradores c
                ON c.id = r.colaborador_id
            WHERE r.resultado = 'negado'
               OR r.evento = 'desconhecido'
            ORDER BY r.id DESC
            LIMIT 20
        """).fetchall()

        return jsonify({
            "colaboradores_ativos": total_colaboradores,
            "colaboradores_autorizados": total_autorizados,
            "registros_de_acesso": total_acessos,
            "acessos_negados": total_negados,
            "ultimos_acessos": [
                dict(acesso) for acesso in ultimos_acessos
            ],
            "colaboradores_na_sala": [
                dict(colaborador)
                for colaborador in colaboradores_na_sala
            ],
            "alertas_recentes": [
                dict(alerta)
                for alerta in alertas_recentes
            ]
        })

    finally:
        connection.close()

@app.route("/cartoes", methods=["POST"])
@login_obrigatorio
def cadastrar_cartao():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "erro": "Envie os dados em formato JSON."
        }), 400

    uid = dados.get("uid")
    colaborador_id = dados.get("colaborador_id")

    if not isinstance(uid, str) or not uid.strip():
        return jsonify({
            "erro": "O UID do cartao e obrigatorio."
        }), 400

    if (
        isinstance(colaborador_id, bool)
        or not isinstance(colaborador_id, int)
        or colaborador_id <= 0
    ):
        return jsonify({
            "erro": "Informe um ID de colaborador valido."
        }), 400

    connection = get_connection()

    try:
        colaborador = connection.execute("""
            SELECT id
            FROM colaboradores
            WHERE id = ? AND ativo = 1
        """, (colaborador_id,)).fetchone()

        if colaborador is None:
            return jsonify({
                "erro": "Colaborador nao encontrado ou inativo."
            }), 404

        cursor = connection.execute("""
            INSERT INTO cartoes_rfid (uid, colaborador_id)
            VALUES (?, ?)
        """, (uid.strip(), colaborador_id))

        connection.commit()

        return jsonify({
            "mensagem": "Cartao cadastrado com sucesso.",
            "id": cursor.lastrowid,
            "uid": uid.strip(),
            "colaborador_id": colaborador_id
        }), 201

    except Exception as erro:
        connection.rollback()

        if "UNIQUE constraint failed" in str(erro):
            return jsonify({
                "erro": (
                    "Este cartao ja esta cadastrado "
                    "ou o colaborador ja possui um cartao."
                )
            }), 409

        app.logger.exception("Erro ao cadastrar cartao RFID")

        return jsonify({
            "erro": "Nao foi possivel cadastrar o cartao."
        }), 500

    finally:
        connection.close()

@app.route("/rfid/validar", methods=["POST"])
def validar_rfid():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "erro": "Envie os dados em formato JSON."
        }), 400

    uid = dados.get("uid")

    if not isinstance(uid, str) or not uid.strip():
        return jsonify({
            "erro": "O UID do cartao e obrigatorio."
        }), 400

    uid = uid.strip()

    connection = get_connection()

    try:
        registro = connection.execute("""
            SELECT
                c.id AS colaborador_id,
                c.matricula,
                c.nome,
                c.funcao,
                c.autorizado,
                c.ativo,
                cr.uid
            FROM cartoes_rfid cr
            INNER JOIN colaboradores c
                ON c.id = cr.colaborador_id
            WHERE cr.uid = ?
              AND cr.ativo = 1
        """, (uid,)).fetchone()

        if registro is None:
            return jsonify({
                "permitido": False,
                "motivo": "cartao_desconhecido",
                "mensagem": "Cartao nao cadastrado."
            }), 200

        colaborador = dict(registro)

        if not colaborador["ativo"]:
            return jsonify({
                "permitido": False,
                "motivo": "colaborador_inativo",
                "mensagem": "Colaborador inativo."
            }), 200

        if not colaborador["autorizado"]:
            return jsonify({
                "permitido": False,
                "motivo": "acesso_nao_autorizado",
                "mensagem": "Acesso negado.",
                "colaborador": {
                    "matricula": colaborador["matricula"],
                    "nome": colaborador["nome"]
                }
            }), 200

        return jsonify({
            "permitido": True,
            "motivo": "autorizado",
            "mensagem": "Acesso permitido.",
            "colaborador": {
                "id": colaborador["colaborador_id"],
                "matricula": colaborador["matricula"],
                "nome": colaborador["nome"],
                "funcao": colaborador["funcao"]
            }
        }), 200

    finally:
        connection.close()

@app.route("/acessos/registrar", methods=["POST"])
def registrar_acesso():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({
            "erro": "Envie os dados em formato JSON."
        }), 400

    uid = dados.get("uid")
    evento = dados.get("evento")
    resultado = dados.get("resultado")
    data_hora = dados.get("data_hora")
    evento_id = dados.get("evento_id")

    if evento_id is not None and (
    not isinstance(evento_id, str) or not evento_id.strip()
    ):
        return jsonify({
            "erro": "Identificador do evento invalido."
        }), 400

    if data_hora is not None:
        if not isinstance(data_hora, str):
            return jsonify({
                "erro": "Data e hora invalidas."
            }), 400

        try:
            data_hora = datetime.fromisoformat(data_hora)
            data_hora = data_hora.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OverflowError):
            return jsonify({
                "erro": "Formato de data e hora invalido."
            }), 400

    eventos_validos = [
        "entrada",
        "saida",
        "negado",
        "desconhecido"
    ]

    resultados_validos = [
        "permitido",
        "negado"
    ]

    if not isinstance(uid, str) or not uid.strip():
        return jsonify({
            "erro": "O UID do cartao e obrigatorio."
        }), 400

    if evento not in eventos_validos:
        return jsonify({
            "erro": "Evento invalido."
        }), 400

    if resultado not in resultados_validos:
        return jsonify({
            "erro": "Resultado invalido."
        }), 400

    connection = get_connection()

    try:
        cartao = connection.execute("""
            SELECT c.id
            FROM cartoes_rfid cr
            INNER JOIN colaboradores c
                ON c.id = cr.colaborador_id
            WHERE cr.uid = ?
        """, (uid.strip(),)).fetchone()

        colaborador_id = (
            cartao["id"] if cartao is not None else None
        )

        connection.execute("""
            INSERT INTO registros_acesso (
                colaborador_id,
                uid,
                evento,
                resultado,
                registrado_em,
                evento_id
            )
            VALUES (?, ?, ?, ?, COALESCE(?, datetime('now', 'localtime')), ?)
            ON CONFLICT(evento_id) DO NOTHING
        """, (
            colaborador_id,
            uid.strip(),
            evento,
            resultado,
            data_hora,
            evento_id
        ))

        connection.commit()

        return jsonify({
            "mensagem": "Registro de acesso salvo com sucesso.",
            "uid": uid.strip(),
            "evento": evento,
            "resultado": resultado
        }), 201

    except Exception:
        connection.rollback()
        app.logger.exception("Erro ao registrar acesso")

        return jsonify({
            "erro": "Nao foi possivel registrar o acesso."
        }), 500

    finally:
        connection.close()

@app.route("/colaboradores/<int:colaborador_id>", methods=["PUT", "PATCH"])
@login_obrigatorio
def editar_colaborador(colaborador_id):
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict) or not dados:
        return jsonify({"erro": "Envie os dados em formato JSON."}), 400

    campos_permitidos = {
        "matricula": str,
        "nome": str,
        "funcao": str,
        "autorizado": bool,
        "ativo": bool
    }

    for campo, valor in dados.items():
        if campo not in campos_permitidos:
            return jsonify({"erro": f"Campo '{campo}' não permitido."}), 400

        if not isinstance(valor, campos_permitidos[campo]):
            return jsonify({"erro": f"Valor inválido para '{campo}'."}), 400

        if isinstance(valor, str) and not valor.strip():
            return jsonify({"erro": f"O campo '{campo}' não pode ficar vazio."}), 400

    campos = []
    valores = []

    for campo, valor in dados.items():
        campos.append(f"{campo} = ?")
        valores.append(int(valor) if isinstance(valor, bool) else valor.strip()
                       if isinstance(valor, str) else valor)

    connection = get_connection()

    try:
        colaborador = connection.execute(
            "SELECT id FROM colaboradores WHERE id = ?",
            (colaborador_id,)
        ).fetchone()

        if colaborador is None:
            return jsonify({"erro": "Colaborador não encontrado."}), 404

        valores.append(colaborador_id)

        connection.execute(
            f"UPDATE colaboradores SET {', '.join(campos)} WHERE id = ?",
            valores
        )

        connection.commit()

        return jsonify({
            "mensagem": "Colaborador atualizado com sucesso."
        }), 200

    except Exception as erro:
        connection.rollback()

        if "UNIQUE constraint failed" in str(erro):
            return jsonify({"erro": "Essa matrícula já está cadastrada."}), 409

        app.logger.exception("Erro ao editar colaborador")
        return jsonify({"erro": "Não foi possível editar o colaborador."}), 500

    finally:
        connection.close()

@app.route("/colaboradores/<int:colaborador_id>", methods=["DELETE"])
@login_obrigatorio
def excluir_colaborador(colaborador_id):
    connection = get_connection()

    try:
        colaborador = connection.execute(
            "SELECT id FROM colaboradores WHERE id = ?",
            (colaborador_id,)
        ).fetchone()

        if colaborador is None:
            return jsonify({"erro": "Colaborador não encontrado."}), 404

        connection.execute(
            "UPDATE colaboradores SET ativo = 0 WHERE id = ?",
            (colaborador_id,)
        )

        connection.execute(
            "UPDATE cartoes_rfid SET ativo = 0 WHERE colaborador_id = ?",
            (colaborador_id,)
        )

        connection.commit()

        return jsonify({
            "mensagem": "Colaborador desativado com sucesso."
        }), 200

    except Exception:
        connection.rollback()
        app.logger.exception("Erro ao excluir colaborador")

        return jsonify({
            "erro": "Não foi possível excluir o colaborador."
        }), 500

    finally:
        connection.close()

@app.route(
    "/colaboradores/<int:colaborador_id>/cartao",
    methods=["PUT", "PATCH"]
)
@login_obrigatorio
def editar_cartao_colaborador(colaborador_id):
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({"erro": "Envie os dados em formato JSON."}), 400

    uid = dados.get("uid")

    if not isinstance(uid, str) or not uid.strip():
        return jsonify({"erro": "O UID do cartão é obrigatório."}), 400

    uid = uid.strip()
    connection = get_connection()

    try:
        colaborador = connection.execute(
            "SELECT id FROM colaboradores WHERE id = ? AND ativo = 1",
            (colaborador_id,)
        ).fetchone()

        if colaborador is None:
            return jsonify({
                "erro": "Colaborador não encontrado ou inativo."
            }), 404

        cartao_existente = connection.execute(
            "SELECT id FROM cartoes_rfid WHERE colaborador_id = ?",
            (colaborador_id,)
        ).fetchone()

        if cartao_existente:
            connection.execute(
                """
                UPDATE cartoes_rfid
                SET uid = ?, ativo = 1
                WHERE colaborador_id = ?
                """,
                (uid, colaborador_id)
            )
        else:
            connection.execute(
                """
                INSERT INTO cartoes_rfid (uid, colaborador_id)
                VALUES (?, ?)
                """,
                (uid, colaborador_id)
            )

        connection.commit()

        return jsonify({
            "mensagem": "Cartão RFID cadastrado ou atualizado com sucesso.",
            "uid": uid,
            "colaborador_id": colaborador_id
        }), 200

    except Exception as erro:
        connection.rollback()

        if "UNIQUE constraint failed" in str(erro):
            return jsonify({
                "erro": "Este UID já está associado a outro cartão."
            }), 409

        app.logger.exception("Erro ao atualizar cartão RFID")

        return jsonify({
            "erro": "Não foi possível atualizar o cartão RFID."
        }), 500

    finally:
        connection.close()

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
