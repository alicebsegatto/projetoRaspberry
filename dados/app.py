
import sqlite3
from flask import Flask, render_template
from database import DB_PATH, init_db

app = Flask(__name__)

init_db()


@app.route("/")
def inicio():
    with sqlite3.connect(DB_PATH) as conexao:
        conexao.row_factory = sqlite3.Row

        entradas = conexao.execute(
            "SELECT COUNT(*) FROM registros_acesso WHERE evento = 'entrada'"
        ).fetchone()[0]

        saidas = conexao.execute(
            "SELECT COUNT(*) FROM registros_acesso WHERE evento = 'saida'"
        ).fetchone()[0]

        negados = conexao.execute(
            "SELECT COUNT(*) FROM registros_acesso WHERE resultado = 'negado'"
        ).fetchone()[0]

        invasoes = conexao.execute(
            "SELECT COUNT(*) FROM registros_acesso WHERE evento = 'desconhecido'"
        ).fetchone()[0]

        registros = conexao.execute("""
            SELECT
                r.registrado_em,
                c.nome,
                r.uid,
                r.evento,
                r.resultado
            FROM registros_acesso r
            LEFT JOIN colaboradores c
                ON r.colaborador_id = c.id
            ORDER BY r.id DESC
            LIMIT 10
        """).fetchall()

    return render_template(
        "index.html",
        entradas=entradas,
        saidas=saidas,
        negados=negados,
        invasoes=invasoes,
        registros=registros
    )


if __name__ == "__main__":
    app.run(debug=True)
