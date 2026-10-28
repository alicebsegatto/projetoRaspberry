from functools import wraps
import os
import requests

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FRONT_SECRET_KEY", "troque-esta-chave-por-uma-chave-secreta"
)

# API do integrante responsável pelo backend.
# Se a API estiver em outro computador, configure a variável API_BASE_URL.
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
API_TIMEOUT = 5


class ErroAPI(Exception):
    """Erro amigável recebido ao tentar conversar com a API do backend."""


def chamar_api(metodo, rota, **kwargs):
    """Chama a API e converte falhas de rede/HTTP em mensagens tratáveis."""
    url = f"{API_BASE_URL}{rota}"
    try:
        resposta = requests.requests(metodo, url, timeout=API_TIMEOUT, **kwargs)
    except requests.RequestException as erro:
        raise ErroAPI(
            f"Não foi possível conectar à API ({API_BASE_URL}). "
            "Verifique se o backend está em execução e se o endereço está correto."
        ) from erro

    try:
        dados = resposta.json()
    except ValueError:
        dados = {}

    if not resposta.ok:
        mensagem = dados.get("erro") or dados.get("mensagem") or (
            f"A API retornou o erro HTTP {resposta.status_code}."
        )
        raise ErroAPI(mensagem)

    return dados


def login_obrigatorio(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if "colaborador_id" not in session:
            flash("Faça login para acessar o sistema.", "aviso")
            return redirect(url_for("login"))
        return funcao(*args, **kwargs)
    return wrapper


def buscar_colaboradores():
    dados = chamar_api("GET", "/colaboradores")
    if not isinstance(dados, list):
        raise ErroAPI("A resposta da API em /colaboradores não veio no formato esperado.")
    return dados


@app.route("/")
def inicio():
    if "colaborador_id" in session:
        return redirect(url_for("index"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "colaborador_id" in session:
        return redirect(url_for("index"))

    if requests.method == "POST":
        nome = requests.form.get("nome", "").strip()
        senha_rfid = requests.form.get("senha", "").strip()

        if not nome or not senha_rfid:
            flash("Preencha o login e a senha.", "erro")
            return render_template("login.html")

        try:
            colaboradores = buscar_colaboradores()
        except ErroAPI as erro:
            flash(str(erro), "erro")
            return render_template("login.html")

        pessoa = next(
            (c for c in colaboradores if str(c.get("nome", "")).strip().casefold() == nome.casefold()),
            None,
        )
        if pessoa is None:
            flash("Esta pessoa não está cadastrada no sistema.", "erro")
            return render_template("login.html")

        if not pessoa.get("ativo", 1):
            flash("Este cadastro está inativo. Entre em contato com o responsável.", "erro")
            return render_template("login.html")

        uid_cadastrado = str(pessoa.get("cartao_rfid") or "").strip()
        if not uid_cadastrado:
            flash("Esta pessoa está cadastrada, mas não possui cartão RFID vinculado.", "erro")
            return render_template("login.html")

        if uid_cadastrado != senha_rfid:
            flash("Senha incorreta. Informe o UID do cartão RFID cadastrado.", "erro")
            return render_template("login.html")

        session.clear()
        session["colaborador_id"] = pessoa.get("id")
        session["colaborador_nome"] = pessoa.get("nome", nome)
        session["colaborador_matricula"] = pessoa.get("matricula", "")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu do sistema.", "sucesso")
    return redirect(url_for("login"))


@app.route("/colaboradores")
@login_obrigatorio
def index():
    busca = requests.args.get("q", "").strip().casefold()
    try:
        colaboradores = buscar_colaboradores()
    except ErroAPI as erro:
        flash(str(erro), "erro")
        colaboradores = []

    if busca:
        colaboradores = [
            c for c in colaboradores
            if any(busca in str(c.get(campo) or "").casefold()
                for campo in ("nome", "matricula", "funcao", "cartao_rfid"))
        ]

    return render_template("index.html", colaboradores=colaboradores, busca=requests.args.get("q", ""))


@app.route("/colaboradores/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo_colaborador():
    if requests.method == "POST":
        nome = requests.form.get("nome", "").strip()
        matricula = requests.form.get("matricula", "").strip()
        funcao = requests.form.get("funcao", "").strip()
        uid = requests.form.get("tag_rfid", "").strip()
        autorizado = requests.form.get("autorizado") == "1"
        dados_form = {
            "nome": nome,
            "matricula": matricula,
            "funcao": funcao,
            "tag_rfid": uid,
            "autorizado": "1" if autorizado else "0",
        }

        if not all((nome, matricula, funcao, uid)):
            flash("Preencha nome, matrícula, função e UID do cartão RFID.", "erro")
            return render_template("form.html", colaborador=dados_form, titulo="Novo colaborador")

        # A API possui dois endpoints separados: primeiro cria o colaborador,
        # depois associa o UID RFID ao ID retornado pela primeira chamada.
        try:
            resposta_colaborador = chamar_api(
                "POST",
                "/colaboradores",
                json={
                    "matricula": matricula,
                    "nome": nome,
                    "funcao": funcao,
                    "autorizado": autorizado,
                },
            )
            colaborador_id = resposta_colaborador.get("id")
            if not isinstance(colaborador_id, int):
                raise ErroAPI(
                    "A API cadastrou o colaborador, mas não devolveu um ID válido; "
                    "não foi possível associar o cartão automaticamente."
                )

            try:
                chamar_api(
                    "POST",
                    "/cartoes",
                    json={"uid": uid, "colaborador_id": colaborador_id},
                )
            except ErroAPI as erro_cartao:
                flash(
                    "O colaborador foi cadastrado, mas o cartão RFID não foi associado. "
                    f"Detalhe: {erro_cartao} Confira o cadastro antes de tentar novamente.",
                    "aviso",
                )
                return redirect(url_for("index"))

            flash("Colaborador e cartão RFID cadastrados com sucesso pela API.", "sucesso")
            return redirect(url_for("index"))

        except ErroAPI as erro:
            flash(str(erro), "erro")
            return render_template("form.html", colaborador=dados_form, titulo="Novo colaborador")

    return render_template("form.html", colaborador=None, titulo="Novo colaborador")


@app.route("/colaboradores/<int:colaborador_id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def editar_colaborador(colaborador_id):
    # O backend enviado não implementa PUT/PATCH para editar colaboradores.
    flash(
        "A API atual ainda não possui uma rota de edição (PUT/PATCH /colaboradores/<id>). "
        "Peça ao integrante do backend para disponibilizá-la antes de habilitar esta ação.",
        "aviso",
    )
    return redirect(url_for("index"))


@app.route("/colaboradores/<int:colaborador_id>/excluir", methods=["POST"])
@login_obrigatorio
def excluir_colaborador(colaborador_id):
    # O backend enviado não implementa DELETE /colaboradores/<id>.
    flash(
        "A API atual ainda não possui uma rota de exclusão (DELETE /colaboradores/<id>). "
        "Nenhum dado foi removido.",
        "aviso",
    )
    return redirect(url_for("index"))


@app.route("/eventos")
@login_obrigatorio
def eventos():
    matricula_filtro = requests.args.get("matricula", "").strip()
    nome_filtro = requests.args.get("nome", "").strip()
    try:
        registros = chamar_api("GET", "/acessos")
        if not isinstance(registros, list):
            raise ErroAPI("A resposta da API em /acessos não veio no formato esperado.")
    except ErroAPI as erro:
        flash(str(erro), "erro")
        registros = []

    if matricula_filtro:
        registros = [r for r in registros if str(r.get("matricula") or "") == matricula_filtro]
    elif nome_filtro:
        registros = [r for r in registros if str(r.get("nome") or "").casefold() == nome_filtro.casefold()]

    return render_template(
        "eventos.html",
        eventos=registros,
        matricula_filtro=matricula_filtro,
        nome_filtro=nome_filtro,
    )


@app.route("/colaboradores/<int:colaborador_id>/eventos")
@login_obrigatorio
def eventos_colaborador(colaborador_id):
    # /acessos retorna os últimos 100 registros com nome/matrícula quando conhecidos.
    # Buscamos o colaborador na API para obter matrícula/nome para aplicar o filtro.
    try:
        colaboradores = buscar_colaboradores()
        colaborador = next((c for c in colaboradores if c.get("id") == colaborador_id), None)
        if colaborador is None:
            abort(404)
        registros = chamar_api("GET", "/acessos")
        if not isinstance(registros, list):
            raise ErroAPI("A resposta da API em /acessos não veio no formato esperado.")
        eventos_filtrados = [
            r for r in registros
            if str(r.get("matricula") or "") == str(colaborador.get("matricula") or "")
        ]
    except ErroAPI as erro:
        flash(str(erro), "erro")
        colaborador = {"nome": "Colaborador", "matricula": ""}
        eventos_filtrados = []

    return render_template(
        "eventos.html",
        eventos=eventos_filtrados,
        matricula_filtro=colaborador.get("matricula", ""),
        nome_filtro=colaborador.get("nome", ""),
    )


@app.route("/health-api")
@login_obrigatorio
def health_api():
    try:
        resposta = chamar_api("GET", "/health")
        flash(f"API conectada: {resposta.get('status', 'resposta recebida')}.", "sucesso")
    except ErroAPI as erro:
        flash(str(erro), "erro")
    return redirect(url_for("index"))


if __name__ == "__main__":
    # A API do backend já utiliza a porta 5000; o front fica na porta 5001.
    app.run(host="127.0.0.1", port=5001, debug=False)
