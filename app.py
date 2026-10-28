from flask import Flask, jsonify, request
from database import get_connection, init_db

app = Flask(__name__)


@app.route("/", methods=["GET"])
def inicio():
    return """
    <h1>Sistema de Segurança</h1>
    <p>API de controle de acesso RFID.</p>
    <ul>
        <li><a href="/health">Verificar funcionamento</a></li>
        <li><a href="/colaboradores">Listar colaboradores</a></li>
        <li><a href="/acessos">Consultar registros de acesso</a></li>
        <li><a href="/monitoramento">Monitoramento</a></li>
    </ul>
    """


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "servico": "Sistema de Seguranca RFID"
    }), 200


@app.route("/colaboradores", methods=["GET"])
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

        return jsonify({
            "colaboradores_ativos": total_colaboradores,
            "colaboradores_autorizados": total_autorizados,
            "registros_de_acesso": total_acessos,
            "acessos_negados": total_negados
        })

    finally:
        connection.close()

@app.route("/cartoes", methods=["POST"])
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
                resultado
            )
            VALUES (?, ?, ?, ?)
        """, (
            colaborador_id,
            uid.strip(),
            evento,
            resultado
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

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
