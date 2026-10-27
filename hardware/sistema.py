
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
from cadastro import colaboradores

import time
import csv
import json
import os

from datetime import datetime


# ==========================================
# CONFIGURACAO DOS PINOS - BCM
# ==========================================

LED_VERDE = 11
LED_VERMELHO = 13
BUZZER = 15

ARQUIVO_LOG = "logs_acesso.csv"
ARQUIVO_ESTADO = "estado_sistema.json"


# ==========================================
# CARREGAR ESTADO SALVO
# ==========================================

def carregar_estado():
    if os.path.exists(ARQUIVO_ESTADO):
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)

    return {
        "colaboradores": {},
        "tentativas_negadas": {},
        "tags_desconhecidas": {}
    }


estado = carregar_estado()

estado.setdefault("colaboradores", {})
estado.setdefault("tentativas_negadas", {})
estado.setdefault("tags_desconhecidas", {})

for id_cracha in colaboradores:
    estado["colaboradores"].setdefault(
        id_cracha,
        {
            "dentro": False,
            "entrada_epoch": None,
            "data_entrada": None,
            "primeira_entrada_data": None,
            "tempo_por_dia": {}
        }
    )


# ==========================================
# INICIALIZAR GPIO E LEITOR RFID
# ==========================================

GPIO.setwarnings(False)

# SimpleMFRC522 configura o modo GPIO internamente.
# Nao chamar GPIO.setmode() novamente.

leitorRfid = SimpleMFRC522()

GPIO.setup(LED_VERDE, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(LED_VERMELHO, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(BUZZER, GPIO.OUT, initial=GPIO.LOW)


# ==========================================
# SALVAR ESTADO
# ==========================================

def salvar_estado():
    with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as arquivo:
        json.dump(estado, arquivo, indent=4, ensure_ascii=False)


# ==========================================
# REGISTRAR EVENTOS EM CSV
# ==========================================

def registrar_evento(evento, id_cracha, nome, detalhe=""):
    arquivo_vazio = (
        not os.path.exists(ARQUIVO_LOG)
        or os.path.getsize(ARQUIVO_LOG) == 0
    )

    with open(
        ARQUIVO_LOG,
        "a",
        newline="",
        encoding="utf-8"
    ) as arquivo:
        campos = [
            "data_hora",
            "evento",
            "id_cracha",
            "nome",
            "detalhe"
        ]

        escritor = csv.DictWriter(arquivo, fieldnames=campos)

        if arquivo_vazio:
            escritor.writeheader()

        escritor.writerow({
            "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "evento": evento,
            "id_cracha": id_cracha,
            "nome": nome,
            "detalhe": detalhe
        })


# ==========================================
# BUZZER
# ==========================================

def bip(duracao=0.2):
    GPIO.output(BUZZER, GPIO.HIGH)
    time.sleep(duracao)
    GPIO.output(BUZZER, GPIO.LOW)


def alerta_sonoro(quantidade, duracao=0.15, pausa=0.15):
    for _ in range(quantidade):
        bip(duracao)
        time.sleep(pausa)


# ==========================================
# SINAIS DOS LEDS E BUZZER
# ==========================================

def sinal_acesso_liberado():
    GPIO.output(LED_VERDE, GPIO.HIGH)
    bip(0.2)
    time.sleep(2)
    GPIO.output(LED_VERDE, GPIO.LOW)


def sinal_acesso_negado():
    GPIO.output(LED_VERMELHO, GPIO.HIGH)
    alerta_sonoro(3)
    time.sleep(0.5)
    GPIO.output(LED_VERMELHO, GPIO.LOW)


def sinal_tag_desconhecida():
    print("ALERTA: possivel tentativa de invasao!")

    for _ in range(10):
        GPIO.output(LED_VERMELHO, GPIO.HIGH)
        bip(0.2)
        time.sleep(0.1)
        GPIO.output(LED_VERMELHO, GPIO.LOW)
        time.sleep(0.1)


# ==========================================
# FORMATAR TEMPO
# ==========================================

def formatar_tempo(segundos):
    segundos = max(0, int(segundos))
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segundos = segundos % 60

    return f"{horas}h {minutos}min {segundos}s"


# ==========================================
# PROCESSAR COLABORADOR
# ==========================================

def processar_colaborador(id_cracha, colaborador):
    hoje = datetime.now().strftime("%Y-%m-%d")
    nome = colaborador["nome"]
    dados = estado["colaboradores"][id_cracha]

    # Colaborador cadastrado sem autorizacao
    if not colaborador["autorizado"]:
        print(f"Voce nao tem acesso a este projeto, {nome}!")

        estado["tentativas_negadas"].setdefault(hoje, {})
        estado["tentativas_negadas"][hoje][nome] = (
            estado["tentativas_negadas"][hoje].get(nome, 0) + 1
        )

        registrar_evento(
            "ACESSO_NEGADO",
            id_cracha,
            nome,
            "Colaborador sem autorizacao"
        )

        salvar_estado()
        sinal_acesso_negado()
        return

    # Se estiver dentro, registrar a saida
    if dados["dentro"]:
        agora = time.time()
        data_entrada = dados["data_entrada"]
        entrada_epoch = dados["entrada_epoch"]

        if entrada_epoch is not None and data_entrada is not None:
            permanencia = agora - entrada_epoch

            dados["tempo_por_dia"][data_entrada] = (
                dados["tempo_por_dia"].get(data_entrada, 0)
                + permanencia
            )

        print(f"Saida registrada: {nome}.")

        registrar_evento(
            "SAIDA",
            id_cracha,
            nome,
            "Saida registrada pelo RFID"
        )

        dados["dentro"] = False
        dados["entrada_epoch"] = None
        dados["data_entrada"] = None

        salvar_estado()
        sinal_acesso_liberado()
        return

    # Nova entrada
    if dados["primeira_entrada_data"] != hoje:
        print(f"Bem-vindo, {nome}!")
        dados["primeira_entrada_data"] = hoje
    else:
        print(f"Bem-vindo de volta, {nome}!")

    dados["dentro"] = True
    dados["entrada_epoch"] = time.time()
    dados["data_entrada"] = hoje

    registrar_evento(
        "ENTRADA",
        id_cracha,
        nome,
        "Entrada autorizada"
    )

    salvar_estado()
    sinal_acesso_liberado()


# ==========================================
# RELATORIO FINAL
# ==========================================

def gerar_relatorio():
    hoje = datetime.now().strftime("%Y-%m-%d")

    print("\n" + "=" * 45)
    print("RELATORIO FINAL DE ACESSO")
    print("=" * 45)

    print("\nTEMPO DE PERMANENCIA HOJE:")

    for id_cracha, colaborador in colaboradores.items():
        nome = colaborador["nome"]
        dados = estado["colaboradores"][id_cracha]

        total = dados["tempo_por_dia"].get(hoje, 0)

        if (
            dados["dentro"]
            and dados["data_entrada"] == hoje
            and dados["entrada_epoch"] is not None
        ):
            total += time.time() - dados["entrada_epoch"]

        print(f"{nome}: {formatar_tempo(total)}")

        if dados["dentro"]:
            print("  Situacao: ainda consta dentro da sala.")

    print("\nTENTATIVAS DE ACESSO NEGADO:")

    negadas = estado["tentativas_negadas"].get(hoje, {})

    if negadas:
        for nome, quantidade in negadas.items():
            print(f"{nome}: {quantidade} tentativa(s)")
    else:
        print("Nenhuma tentativa registrada.")

    desconhecidas = estado["tags_desconhecidas"].get(hoje, 0)
    print("\nTAGS DESCONHECIDAS:")
    print(f"Total de tentativas hoje: {desconhecidas}")

    print(f"\nEventos registrados em: {ARQUIVO_LOG}")
    print("=" * 45)


# ==========================================
# EXECUCAO PRINCIPAL
# ==========================================

try:
    print("=" * 45)
    print("SISTEMA DE CONTROLE DE ACESSO RFID")
    print("=" * 45)
    print("Aproxime um cracha do leitor.")
    print("Retire o cracha apos cada leitura.")
    print("Pressione Ctrl+C para encerrar.\n")

    while True:
        id_cracha, texto = leitorRfid.read()
        id_cracha = str(id_cracha)

        print(f"\nID do cartao: {id_cracha}")

        colaborador = colaboradores.get(id_cracha)

        if colaborador is None:
            print("Identificacao nao encontrada!")

            hoje = datetime.now().strftime("%Y-%m-%d")

            estado["tags_desconhecidas"][hoje] = (
                estado["tags_desconhecidas"].get(hoje, 0) + 1
            )

            registrar_evento(
                "TAG_DESCONHECIDA",
                id_cracha,
                "Desconhecido",
                "Possivel tentativa de invasao"
            )

            salvar_estado()
            sinal_tag_desconhecida()

        else:
            processar_colaborador(id_cracha, colaborador)

        print("\nAproxime outro cracha.")
        time.sleep(1)

except KeyboardInterrupt:
    print("\nEncerrando o sistema...")

finally:
    try:
        gerar_relatorio()
    finally:
        GPIO.cleanup()
        print("\nGPIO liberado. Sistema finalizado.")
