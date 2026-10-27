
import pandas as pd
from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def inicio():
    # Lê os dados do CSV
    dados = pd.read_csv("logs_acesso.csv")

    # Conta os eventos
    entradas = (dados["event_type"] == "entrada").sum()
    saidas = (dados["event_type"] == "saida").sum()
    negados = (dados["event_type"] == "acesso_negado").sum()
    invasoes = (dados["event_type"] == "invasao").sum()

    # Pega os últimos 10 registros
    registros = dados.tail(10).to_dict("records")

    # Abre o dashboard com os dados
    return render_template(
        "index.html",
        entradas=entradas,
        saidas=saidas,
        negados=negados,
        invasoes=invasoes,
        registros=registros
    )

app.run(debug=True)
