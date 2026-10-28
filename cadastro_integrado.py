
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Troque pelo IPv4 do computador onde o Flask está rodando.
# Exemplo: API_BASE = "http://192.168.0.10:5001"
API_BASE = "http://IP_DO_COMPUTADOR:5001"

TEMPO_LIMITE = 3


def _requisicao_api(caminho, dados=None):
    """Faz uma requisição JSON para a API."""
    corpo = (
        json.dumps(dados).encode("utf-8")
        if dados is not None
        else None
    )

    requisicao = Request(
        f"{API_BASE}{caminho}",
        data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST" if corpo is not None else "GET"
    )

    try:
        with urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            conteudo = resposta.read().decode("utf-8")
            return json.loads(conteudo) if conteudo else {}

    except HTTPError as erro:
        detalhe = erro.read().decode("utf-8", errors="replace")
        return {
            "erro_conexao": True,
            "detalhe": f"HTTP {erro.code}: {detalhe}"
        }

    except (URLError, TimeoutError, OSError, ValueError) as erro:
        return {
            "erro_conexao": True,
            "detalhe": str(erro)
        }


def buscar_colaborador(id_cracha):
    """Consulta o UID do cartão e sua autorização."""
    resposta = _requisicao_api(
        "/rfid/validar",
        {"uid": str(id_cracha)}
    )

    if resposta.get("erro_conexao"):
        return resposta

    colaborador = resposta.get("colaborador") or {}
    permitido = resposta.get("permitido", False)

    return {
        "id": colaborador.get("id"),
        "matricula": colaborador.get("matricula"),
        "nome": colaborador.get("nome", "Desconhecido"),
        "funcao": colaborador.get("funcao", ""),
        "autorizado": permitido,
        "motivo": resposta.get(
            "motivo",
            "autorizado" if permitido else "acesso_negado"
        )
    }


def registrar_acesso_api(id_cracha, evento, permitido):
    """Envia o evento de acesso para o banco de dados da API."""
    eventos = {
        "ENTRADA": "entrada",
        "SAIDA": "saida",
        "ACESSO_NEGADO": "negado",
        "TAG_DESCONHECIDA": "desconhecido"
    }

    evento_api = eventos.get(str(evento).upper())

    if evento_api is None:
        print(f"Evento inválido: {evento}")
        return False

    resposta = _requisicao_api(
        "/acessos/registrar",
        {
            "uid": str(id_cracha),
            "evento": evento_api,
            "resultado": "permitido" if permitido else "negado"
        }
    )

    if resposta.get("erro_conexao"):
        print("Erro ao registrar acesso:", resposta.get("detalhe"))
        return False

    return True


if __name__ == "__main__":
    uid = input("Digite o UID do cartão para consultar: ").strip()

    resultado = buscar_colaborador(uid)

    if resultado.get("erro_conexao"):
        print("Não foi possível conectar à API:")
        print(resultado.get("detalhe"))
    else:
        print("Nome:", resultado["nome"])
        print("Autorizado:", resultado["autorizado"])
        print("Motivo:", resultado["motivo"])
