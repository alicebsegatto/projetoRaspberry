import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = "http://127.0.0.1:5000"
TEMPO_LIMITE = 3


def _requisicao_api(caminho, dados=None):
    """Faz uma requisicao JSON para a API local."""
    corpo = json.dumps(dados).encode("utf-8") if dados is not None else None
    requisicao = Request(
        f"{API_BASE}{caminho}", data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST" if corpo is not None else "GET"
    )
    try:
        with urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except (URLError, HTTPError, TimeoutError, OSError, ValueError) as erro:
        return {"erro_conexao": True, "detalhe": str(erro)}


def buscar_colaborador(id_cracha):
    """Consulta o UID e sua autorizacao no backend."""
    resposta = _requisicao_api("/rfid/validar", {"uid": str(id_cracha)})
    if resposta.get("erro_conexao"):
        return resposta

    colaborador = resposta.get("colaborador")
    if not resposta.get("permitido", False):
        return {
            "nome": (colaborador or {}).get("nome", "Desconhecido"),
            "autorizado": False,
            "motivo": resposta.get("motivo", "acesso_negado")
        }

    return {
        "id": colaborador.get("id"),
        "matricula": colaborador.get("matricula"),
        "nome": colaborador.get("nome", "Colaborador"),
        "funcao": colaborador.get("funcao", ""),
        "autorizado": True,
        "motivo": resposta.get("motivo", "autorizado")
    }


def registrar_acesso_api(id_cracha, evento, permitido):
    """Envia um evento para o banco da API."""
    eventos = {
        "ENTRADA": "entrada", "SAIDA": "saida",
        "ACESSO_NEGADO": "negado", "TAG_DESCONHECIDA": "desconhecido"
    }
    evento_api = eventos.get(evento)
    if evento_api is None:
        return False
    resposta = _requisicao_api("/acessos/registrar", {
        "uid": str(id_cracha), "evento": evento_api,
        "resultado": "permitido" if permitido else "negado"
    })
    return not resposta.get("erro_conexao") and "erro" not in resposta


if __name__ == "__main__":
    uid = input("Digite o UID do cartao para consultar: ")
    resultado = buscar_colaborador(uid)
    if resultado.get("erro_conexao"):
        print("Nao foi possivel conectar a API:", resultado.get("detalhe"))
    else:
        print("Nome:", resultado["nome"])
        print("Autorizado:", resultado["autorizado"])
