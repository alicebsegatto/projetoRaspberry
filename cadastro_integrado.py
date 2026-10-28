
import json
import os
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Troque pelo IPv4 do computador onde o Flask está rodando.
API_BASE = "http://IP_DO_COMPUTADOR:5000"

# Tempo máximo, em segundos, para aguardar uma resposta da API
TEMPO_LIMITE = 3

# Caminho do arquivo que armazena localmente os dados de colaboradores já consultados
ARQUIVO_CACHE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "cache_rfid.json"
)

# Caminho do arquivo que mantém os registros de acesso que ainda não foram enviados  API
ARQUIVO_PENDENTES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "acessos_pendentes.json"
)

def carregar_cache():
    # Carrega os dados locais dos cartões
    if not os.path.exists(ARQUIVO_CACHE):
        return {}

    try:
        with open(ARQUIVO_CACHE, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except (OSError, ValueError):
        # Retorna um cache vazio caso o arquivo não esteja disponível
        return {}


def salvar_cache(uid, colaborador):
    # Atualiza os dados armazenados para o UID informado
    cache = carregar_cache()

    cache[str(uid)] = colaborador

    with open(ARQUIVO_CACHE, "w", encoding="utf-8") as arquivo:
        json.dump(cache, arquivo, indent=4, ensure_ascii=False)

def salvar_acesso_pendente(uid, evento, resultado):
    # Mantém os acessos que precisam ser enviados posteriormente
    pendentes = []

    if os.path.exists(ARQUIVO_PENDENTES):
        try:
            with open(ARQUIVO_PENDENTES, "r", encoding="utf-8") as arquivo:
                pendentes = json.load(arquivo)
                # Verifica se o arquivo contém uma lista de registros
                if not isinstance(pendentes, list):
                    pendentes = []
        except (OSError, ValueError):
            pendentes = []

    # Inicia uma lista vazia se não for possível carregar os registros.
    pendentes.append({
        "evento_id": str(uuid.uuid4()),
        "uid": str(uid),
        "evento": evento,
        "resultado": resultado,
        "data_hora": datetime.now().astimezone().isoformat()
    })

    with open(ARQUIVO_PENDENTES, "w", encoding="utf-8") as arquivo:
        json.dump(pendentes, arquivo, indent=4, ensure_ascii=False)

def sincronizar_acessos_pendentes():
    # Reenvia os registros armazenados durante períodos sem conexão.
    if not os.path.exists(ARQUIVO_PENDENTES):
        return

    try:
        with open(ARQUIVO_PENDENTES, "r", encoding="utf-8") as arquivo:
            pendentes = json.load(arquivo)
        # Confere o formato dos registros pendentes.
        if not isinstance(pendentes, list):
            return

    except (OSError, ValueError):
         # Interrompe a sincronização se o arquivo não puder ser lido
        return

    restantes = []

    for indice, acesso in enumerate(pendentes):
        resposta = _requisicao_api("/acessos/registrar", acesso)
        # Mantém os registros restantes caso ocorra uma falha no envio
        if resposta.get("erro_conexao") or resposta.get("erro_http"):
            restantes = pendentes[indice:]
            break

    with open(ARQUIVO_PENDENTES, "w", encoding="utf-8") as arquivo:
        json.dump(restantes, arquivo, indent=4, ensure_ascii=False)

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
            "erro_http": True,
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

    if resposta.get("erro_http"):
        return {
            "autorizado": False,
            "nome": "Desconhecido",
            "motivo": "erro_api"
        }

    if resposta.get("erro_conexao"):
        cache = carregar_cache()
        colaborador_cache = cache.get(str(id_cracha))

        if colaborador_cache is not None:
            print("API indisponivel. Utilizando cache local.")

            return {
                **colaborador_cache,
                "origem": "cache"
            }

        return resposta

    colaborador = resposta.get("colaborador") or {}
    permitido = resposta.get("permitido", False)

    resultado = {
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

    salvar_cache(id_cracha, resultado)

    return resultado


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

        salvar_acesso_pendente(
            id_cracha,
            evento_api,
            "permitido" if permitido else "negado"
        )

        print("Acesso salvo para sincronizacao posterior.")
        return False

    if resposta.get("erro_http"):
        print("Erro da API:", resposta.get("detalhe"))
        return False

    sincronizar_acessos_pendentes()

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
