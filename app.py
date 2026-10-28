```python
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

        return jsonify([dict(c) for c in colaboradores])

    finally:
        connection.close()


@app.route("/colaboradores", methods=["POST"])
def cadastrar_colaborador():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({"erro": "Envie os dados em formato JSON."}), 400

    for campo in ["matricula", "nome", "funcao"]:
        if not isinstance(dados.get(campo), str) or not dados[campo].strip():
            return jsonify({
                "erro": f"O campo '{campo}' e obrigatorio."
            }), 400

    autorizado = dados.get("autorizado", False)

    if not isinstance(autorizado, bool):
        return jsonify({
            "erro": "O campo 'autorizado' deve ser true ou false."
        }), 400

    connection = get_connection()

    try:
        cursor = connection.execute("""
            INSERT INTO colaboradores
                (matricula, nome, funcao, autorizado)
            VALUES (?, ?, ?, ?)
        """, (
            dados["matricula"].strip(),
            dados["nome"].strip(),
            dados["funcao"].strip(),
            int(autorizado)
        ))

        connection.commit()

        return jsonify({
            "mensagem": "Colaborador cadastrado com sucesso.",
            "id": cursor.lastrowid
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
                r.colaborador_id,
                r.uid,
                r.evento,
                r.resultado,
                r.registrado_em,
                c.matricula,
                c.nome,
                c.autorizado
            FROM registros_acesso r
            LEFT JOIN colaboradores c
                ON c.id = r.colaborador_id
            ORDER BY r.id DESC
            LIMIT 100
        """).fetchall()

        return jsonify([dict(r) for r in registros])

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
        return jsonify({"erro": "Envie os dados em formato JSON."}), 400

    uid = dados.get("uid")
    colaborador_id = dados.get("colaborador_id")

    if not isinstance(uid, str) or not uid.strip():
        return jsonify({"erro": "O UID do cartao e obrigatorio."}), 400

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
        return jsonify({"erro": "Envie os dados em formato JSON."}), 400

    uid = dados.get("uid")

    if not isinstance(uid, str) or not uid.strip():
        return jsonify({"erro": "O UID do cartao e obrigatorio."}), 400

