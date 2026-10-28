import os
from functools import wraps

import requests
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "troque-esta-chave-antes-de-publicar"
)

# API do integrante do back-end. É possível sobrescrever via variável de ambiente.
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
API_TIMEOUT = 5


def chamar_api(metodo, caminho, **kwargs):
    """Chama a API e retorna (dados_json, mensagem_de_erro)."""
    url = f"{API_BASE_URL}{caminho}"

    try:
        resposta = requests.request(
            method=metodo,
            url=url,
            timeout=API_TIMEOUT,
            **kwargs,
        )
    except requests.RequestException as erro:
        app.logger.warning("Falha ao chamar a API %s: %s", url, erro)
        return None, (
            f"Não foi possível conectar à API em {API_BASE_URL}. "
            "Confirme se o back-end está em execução e se o endereço está correto."
        )

    try:
        dados = resposta.json() if resposta.content else {}
    except ValueError:
        dados = {}

    if not resposta.ok:
        if isinstance(dados, dict):
            mensagem = dados.get("erro") or dados.get("mensagem")
        else:
            mensagem = None
        if not mensagem:
            mensagem = f"A API respondeu com status HTTP {resposta.status_code}."
        return None, mensagem

    return dados, None


def exigir_login(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if "colaborador_id" not in session:
            flash("Faça login para acessar o sistema.", "aviso")
            return redirect(url_for("login"))
        return funcao(*args, **kwargs)

    return wrapper


def buscar_colaboradores():
    dados, erro = chamar_api("GET", "/colaboradores")
    if erro:
        return None, erro
    if not isinstance(dados, list):
        return None, "A API retornou uma resposta inesperada ao listar colaboradores."
    return dados, None


def valor_verdadeiro(valor):
    """Normaliza valores booleanos/inteiros devolvidos pela API SQLite."""
    return valor is True or valor == 1 or str(valor).lower() in ("true", "1")


@app.route("/")
def inicio():
    if "colaborador_id" in session:
        return redirect(url_for("index"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "colaborador_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        nome_informado = request.form.get("nome", "").strip()
        rfid_informado = request.form.get("senha", "").strip()

        if not nome_informado or not rfid_informado:
            flash("Preencha o login e a senha.", "erro")
            return render_template("login.html")

        colaboradores, erro = buscar_colaboradores()
        if erro:
            flash(f"Não foi possível validar o login: {erro}", "erro")
            return render_template("login.html")

        nome_normalizado = nome_informado.casefold()
        pessoas_com_nome = [
            c for c in colaboradores
            if str(c.get("nome", "")).strip().casefold() == nome_normalizado
        ]

        if not pessoas_com_nome:
            flash("Esta pessoa não está cadastrada no sistema.", "erro")
            return render_template("login.html")

        colaborador = next(
            (
                c for c in pessoas_com_nome
                if str(c.get("cartao_rfid") or "").strip() == rfid_informado
            ),
            None,
        )

        if colaborador is None:
            flash("Senha incorreta. Informe o UID do cartão RFID cadastrado.", "erro")
            return render_template("login.html")

        if not valor_verdadeiro(colaborador.get("ativo", 1)):
            flash("Este cadastro está inativo. Entre em contato com o responsável.", "erro")
            return render_template("login.html")

        session.clear()
        session["colaborador_id"] = colaborador.get("id")
        session["colaborador_nome"] = colaborador.get("nome", nome_informado)
        session["colaborador_matricula"] = colaborador.get("matricula", "")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu do sistema.", "sucesso")
    return redirect(url_for("login"))


@app.route("/colaboradores")
@exigir_login
def index():
    busca = request.args.get("q", "").strip().casefold()
    colaboradores, erro = buscar_colaboradores()
    if erro:
        flash(f"Não foi possível carregar os colaboradores: {erro}", "erro")
        colaboradores = []

    if busca:
        colaboradores = [
            c for c in colaboradores
            if busca in str(c.get("nome", "")).casefold()
            or busca in str(c.get("matricula", "")).casefold()
            or busca in str(c.get("cartao_rfid") or "").casefold()
            or busca in str(c.get("funcao", "")).casefold()
        ]

    return render_template("index.html", colaboradores=colaboradores, busca=request.args.get("q", ""))


@app.route("/colaboradores/novo", methods=["GET", "POST"])
@exigir_login
def novo_colaborador():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        matricula = request.form.get("matricula", "").strip()
        funcao = request.form.get("funcao", "").strip()
        uid = request.form.get("tag_rfid", "").strip()
        autorizado = request.form.get("autorizado") == "1"

        if not nome or not matricula or not funcao or not uid:
            flash("Preencha nome, matrícula, função e ID do cartão RFID.", "erro")
            return render_template("form.html", colaborador=request.form, titulo="Novo colaborador")

        # A rota POST /colaboradores espera matricula, nome, funcao e autorizado (booleano).
        dados_colaborador, erro = chamar_api(
            "POST",
            "/colaboradores",
            json={
                "matricula": matricula,
                "nome": nome,
                "funcao": funcao,
                "autorizado": autorizado,
            },
        )
        if erro:
            flash(f"Não foi possível cadastrar o colaborador: {erro}", "erro")
            return render_template("form.html", colaborador=request.form, titulo="Novo colaborador")

        colaborador_id = dados_colaborador.get("id") if isinstance(dados_colaborador, dict) else None
        if not isinstance(colaborador_id, int):
            flash(
                "O colaborador foi enviado à API, mas ela não retornou um ID válido. "
                "Confira o cadastro no back-end antes de tentar novamente.",
                "erro",
            )
            return redirect(url_for("index"))

        # A API recebe o UID separadamente em POST /cartoes.
        _, erro_cartao = chamar_api(
            "POST",
            "/cartoes",
            json={"uid": uid, "colaborador_id": colaborador_id},
        )
        if erro_cartao:
            flash(
                "O colaborador foi cadastrado, mas não foi possível associar o cartão RFID: "
                f"{erro_cartao} Confira o cadastro e associe o cartão antes de tentar o login.",
                "aviso",
            )
        else:
            flash("Colaborador e cartão RFID cadastrados com sucesso.", "sucesso")
        return redirect(url_for("index"))

    return render_template("form.html", colaborador=None, titulo="Novo colaborador")


@app.route("/eventos")
@exigir_login
def eventos():
    dados, erro = chamar_api("GET", "/acessos")
    if erro:
        flash(f"Não foi possível carregar os eventos: {erro}", "erro")
        dados = []
    if not isinstance(dados, list):
        dados = []

    matricula_filtro = request.args.get("matricula", "").strip()
    nome_filtro = request.args.get("nome", "").strip()
    eventos_filtrados = dados
    if matricula_filtro:
        eventos_filtrados = [
            e for e in eventos_filtrados
            if str(e.get("matricula") or "") == matricula_filtro
        ]
    if nome_filtro:
        eventos_filtrados = [
            e for e in eventos_filtrados
            if str(e.get("nome") or "").casefold() == nome_filtro.casefold()
        ]

    return render_template(
        "eventos.html",
        eventos=eventos_filtrados,
        matricula_filtro=matricula_filtro,
        nome_filtro=nome_filtro,
    )


@app.route("/health")
@exigir_login
def verificar_api():
    dados, erro = chamar_api("GET", "/health")
    if erro:
        flash(f"A API não respondeu: {erro}", "erro")
    else:
        flash("API conectada e respondendo normalmente.", "sucesso")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # O back-end usa a porta 5000; o front-end usa 5001 para evitar conflito.
    app.run(host="127.0.0.1", port=5001, debug=False)
