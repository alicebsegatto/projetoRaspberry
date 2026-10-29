<div align="center">

# Sistema de Segurança RFID

**Controle de acesso com Raspberry Pi, API Flask, dashboard web e análise de dados com Pandas.**

</div>

---

## Sumário

- [Visão geral](#visão-geral)
- [Como funciona](#como-funciona)
- [Tecnologias](#tecnologias)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Montagem do hardware](#montagem-do-hardware)
- [Instalação e execução](#instalação-e-execução)
- [Dashboard de monitoramento](#dashboard-de-monitoramento)
- [Front-end de gerenciamento](#front-end-de-gerenciamento)
- [Análise de dados (Jupyter)](#análise-de-dados-jupyter)
- [Banco de dados](#banco-de-dados)
- [Modo offline](#modo-offline)
- [Autores](#autores)

---

## Visão geral

Sistema de controle de acesso a uma sala (ou laboratório) por **crachás RFID**. Ao aproximar o crachá do leitor, a Raspberry Pi lê o identificador (UID), consulta a API para saber se o cartão está cadastrado e autorizado, e sinaliza o resultado com LEDs e buzzer. Todos os eventos ficam registrados em um banco SQLite, ficam visíveis em um dashboard web e podem ser analisados em um Jupyter Notebook.

O sistema é dividido em cinco componentes:

| Componente | O que faz | Arquivos principais |
|---|---|---|
| **Hardware** | Raspberry Pi com leitor RFID RC522, 2 LEDs e buzzer. Identifica o crachá e sinaliza o resultado. | `sistema_integrado.py`, `cadastro_integrado.py` |
| **Backend e banco de dados** | API Flask que valida credenciais, gerencia colaboradores e cartões e grava os registros no SQLite. | `app.py`, `database.py` |
| **Monitoramento web** | Dashboard com total de entradas, saídas, acessos negados, tags desconhecidas e últimos registros. | `dash.py`, `templates/index.html` |
| **Front-end de gerenciamento** | Interface web para cadastrar e consultar colaboradores, vincular cartões RFID e ver os eventos de acesso. | `frontend/front.py` |
| **Análise de dados** | Notebook com Pandas para calcular indicadores de acesso e permanência. | `analise_dados.ipynb` |

---

## Como funciona

```mermaid
flowchart LR
    A["Crachá RFID"] --> B["Raspberry Pi<br/>RC522 + LEDs + buzzer"]
    B -->|"POST /rfid/validar<br/>POST /acessos/registrar"| C["API Flask<br/>app.py :5000"]
    C --> D[("SQLite<br/>seguranca.db")]
    D --> E["Dashboard<br/>dash.py :5001"]
    D --> F["Jupyter Notebook<br/>via API /acessos"]
    G["Front-end de gerenciamento<br/>frontend/front.py"] <-->|"/colaboradores<br/>/cartoes<br/>/acessos"| C
```

Decisão tomada a cada leitura de crachá:

```mermaid
flowchart TD
    A["Crachá aproximado"] --> B["Pi lê o UID"]
    B --> C{"API responde?"}
    C -->|Sim| D{"Resposta da API"}
    C -->|Não| E{"UID no cache local?"}
    E -->|Sim| D
    E -->|Não| F["Acesso negado por segurança<br/>evento fica pendente"]
    D -->|"Cartão desconhecido"| G["Tag desconhecida<br/>LED vermelho piscando + buzzer"]
    D -->|"Sem autorização"| H["Acesso negado<br/>LED vermelho + 3 bipes"]
    D -->|"Autorizado"| I{"Já está dentro?"}
    I -->|Não| J["ENTRADA<br/>LED verde + bipe"]
    I -->|Sim| K["SAÍDA<br/>LED verde + bipe"]
```

## Tecnologias

- **Python 3.9+**
- **Flask**: API REST, dashboard e front-end de gerenciamento
- **HTML + CSS (Jinja2)**: telas do dashboard e do front-end
- **SQLite**: banco de dados local
- **Pandas + Requests + Jupyter**: análise de dados
- **RPi.GPIO + mfrc522**: leitura RFID e controle de LEDs e buzzer na Raspberry Pi

---

## Estrutura do projeto

```text
projetoRaspberry/
├── app.py                    # API Flask: login, colaboradores, cartões, validação RFID, registros e monitoramento
├── database.py               # Conexão com o SQLite e criação das tabelas (init_db)
├── dash.py                   # Dashboard web (porta 5001) que lê direto do banco
├── templates/
│   └── index.html            # Página do dashboard (cards de resumo + tabela dos últimos acessos)
├── frontend/                 # Front-end de gerenciamento (consome a API)
│   ├── front.py              # Servidor web: login, colaboradores, novo cadastro, eventos e status da API
│   ├── requirements.txt      # Dependências do front-end (Flask e Requests)
│   ├── templates_front/
│   │   ├── base.html         # Layout base: menu de navegação e mensagens
│   │   ├── login.html        # Tela de login
│   │   ├── index.html        # Lista e busca de colaboradores
│   │   ├── form.html         # Formulário de novo colaborador + cartão RFID
│   │   └── eventos.html      # Tabela de eventos de acesso com filtro
│   └── static/
│       └── style.css         # Estilos das telas
├── cadastro_integrado.py     # Cliente da API usado pela Raspberry: valida cartão, cache local e fila de pendentes
├── sistema_integrado.py      # Programa principal da Raspberry: lê o RFID, aciona LEDs/buzzer e registra eventos
├── hardware/                 # Versão standalone (sem API), mantida como referência
│   ├── cadastro.py           # Colaboradores fixos em um dicionário Python
│   └── sistema.py            # Mesma lógica do sistema integrado, porém consultando o dicionário local
├── analise_dados.ipynb       # Notebook com as perguntas respondidas
├── logs_acesso.csv           # Log local de eventos gerado pela Raspberry (dados de exemplo/teste)
├── requirements.txt          # Dependências Python do servidor (Flask e Pandas)
├── .gitignore                # Arquivos ignorados pelo Git
└── README.md                 # Este arquivo
```

---

## Montagem do hardware

### Materiais

- 1x Raspberry Pi (com Raspberry Pi OS e acesso à rede)
- 1x leitor RFID **RC522** (13,56 MHz) com crachás/tags Mifare
- 1x LED verde e 1x LED vermelho
- 2x resistores de 220 Ω (um para cada LED)
- 1x buzzer ativo
- Protoboard e jumpers

### Ligações

O código usa a **numeração física dos pinos** (modo BOARD, definido internamente pela biblioteca `mfrc522`).

**Leitor RC522**

| RC522 | Pino físico da Raspberry | GPIO |
|---|---|---|
| SDA (SS) | 24 | GPIO8 (CE0) |
| SCK | 23 | GPIO11 |
| MOSI | 19 | GPIO10 |
| MISO | 21 | GPIO9 |
| IRQ | não conectar | |
| GND | 6 | GND |
| RST | 22 | GPIO25 |
| 3.3V | 1 | 3V3 |

> O RC522 trabalha com **3,3 V**. Nunca ligue o pino 3.3V do módulo em 5 V.

**LEDs e buzzer**

| Componente | Pino físico | GPIO | Observação |
|---|---|---|---|
| LED verde (`LED_VERDE`) | 11 | GPIO17 | Ligar em série com resistor de 220 Ω |
| LED vermelho (`LED_VERMELHO`) | 13 | GPIO27 | Ligar em série com resistor de 220 Ω |
| Buzzer (`BUZZER`) | 15 | GPIO22 | Buzzer ativo |
| GND dos três | 9 ou 14 | GND | |

Se quiser mudar os pinos, edite as constantes no topo de `sistema_integrado.py`.

---

## Instalação e execução

O projeto roda em **dois lugares**:

- **Servidor** (seu computador ou a própria Raspberry): API, dashboard, front-end e notebook.
- **Raspberry Pi**: leitor RFID, LEDs e buzzer.

A API roda na porta **5000** e o dashboard na **5001**. A Raspberry só precisa alcançar a API pela rede.

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU_USUARIO/projetoRaspberry.git
cd projetoRaspberry
```

### 2. Servidor: ambiente Python e dependências

**Linux / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install requests notebook   # necessários para o notebook de análise
```

**Windows (PowerShell)**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install requests notebook
```

### 3. Servidor: variáveis de ambiente

A API **não inicia** sem estas três variáveis:

| Variável | Descrição |
|---|---|
| `FLASK_SECRET_KEY` | Chave secreta usada para assinar a sessão de login |
| `ADMIN_USUARIO` | Usuário do administrador da API |
| `ADMIN_SENHA` | Senha do administrador da API |

Gere uma chave secreta:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Linux / macOS**

```bash
export FLASK_SECRET_KEY="cole_a_chave_gerada_aqui"
export ADMIN_USUARIO="admin"
export ADMIN_SENHA="troque_esta_senha"
```

**Windows (PowerShell)**

```powershell
$env:FLASK_SECRET_KEY="cole_a_chave_gerada_aqui"
$env:ADMIN_USUARIO="admin"
$env:ADMIN_SENHA="troque_esta_senha"
```

> O notebook `analise_dados.ipynb` vem com `admin` / `admin123` escritos na primeira célula. Use esses valores em desenvolvimento ou altere a célula para refletir suas credenciais.

### 4. Servidor: iniciar a API

```bash
python app.py
```

O banco `seguranca.db` é criado automaticamente na primeira execução. Teste:

```bash
curl http://localhost:5000/health
# {"servico":"Sistema de Seguranca RFID","status":"online"}
```

### 5. Servidor: iniciar o dashboard (opcional)

Em **outro terminal**, com o ambiente virtual ativado, na mesma pasta do projeto:

```bash
python dash.py
```

Acesse `http://localhost:5001`.

> O dashboard lê o mesmo `seguranca.db` da API. Execute os dois a partir da pasta do projeto.

### 6. Raspberry Pi: preparar o sistema

Habilite a interface SPI (usada pelo RC522) e reinicie:

```bash
sudo raspi-config nonint do_spi 0
sudo reboot
```

Depois de reiniciar, confirme que o SPI está ativo (deve listar `/dev/spidev0.0`):

```bash
ls /dev/spidev*
```

### 7. Raspberry Pi: dependências

```bash
sudo apt update
sudo apt install -y git python3-venv python3-dev

git clone https://github.com/SEU_USUARIO/projetoRaspberry.git
cd projetoRaspberry

python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install mfrc522 RPi.GPIO spidev
```

> **Raspberry Pi 5:** a biblioteca `RPi.GPIO` original não funciona. Troque por `pip uninstall RPi.GPIO && pip install rpi-lgpio`.

A Raspberry **não precisa** instalar Flask nem Pandas. O cliente da API (`cadastro_integrado.py`) usa apenas a biblioteca padrão do Python.

### 8. Raspberry Pi: apontar para a API

Descubra o IP do computador que roda a API:

```bash
# Linux / macOS
hostname -I        # Linux
ipconfig getifaddr en0   # macOS

# Windows
ipconfig
```

Edite `cadastro_integrado.py` e troque a constante `API_BASE`:

```python
API_BASE = "http://192.168.0.10:5000"   # use o IP do SEU servidor, porta 5000
```

Se a API roda na própria Raspberry, use `http://127.0.0.1:5000`.

Verifique a conexão a partir da Raspberry:

```bash
curl http://IP_DO_SERVIDOR:5000/health
```

> Se não conectar, libere a porta 5000 no firewall do servidor e confirme que os dois dispositivos estão na mesma rede.

### 9. Raspberry Pi: iniciar o sistema

```bash
python3 sistema_integrado.py
```

Aproxime um crachá do leitor. Para encerrar, pressione `Ctrl+C`: o relatório do dia é exibido e os pinos GPIO são liberados.

<details>
<summary><b>Opcional: iniciar automaticamente com a Raspberry (systemd)</b></summary>

Crie o arquivo `/etc/systemd/system/rfid.service` (ajuste usuário e caminhos):

```ini
[Unit]
Description=Sistema de controle de acesso RFID
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/projetoRaspberry
ExecStart=/home/pi/projetoRaspberry/venv/bin/python sistema_integrado.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Ative:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rfid.service
sudo journalctl -u rfid.service -f   # acompanhar os logs
```

</details>

---

## Dashboard de monitoramento

Disponível em `http://IP_DO_SERVIDOR:5001` após executar `python dash.py`.

- **Cards:** total de **entradas**, **saídas**, **acessos negados** e **tags desconhecidas**.
- **Tabela:** os 10 últimos acessos (data e hora, colaborador, UID, evento e resultado).
- **Rota extra:** `GET /acessos` retorna os 100 últimos registros em JSON.

A página não atualiza sozinha. Recarregue o navegador para ver novos eventos.

---

## Front-end de gerenciamento

Interface web (Flask + Jinja2) para gerenciar colaboradores e cartões sem usar `curl`. Ela **não acessa o banco diretamente**: toda leitura e gravação passa pela API.

**Telas**

| Tela | O que faz |
|---|---|
| Login | Entra com o **nome** do colaborador e, como senha, o **UID do cartão RFID** cadastrado |
| Colaboradores | Lista com busca por nome, matrícula, função ou UID, e atalho para os eventos de cada pessoa |
| Novo colaborador | Cadastra nome, matrícula, função e permissão, e já vincula o UID do cartão |
| Eventos | Tabela dos últimos acessos (filtro por nome e matrícula) |
| Status da API | Verifica se a API está respondendo |

**Como executar**

Com a API já rodando, em outro terminal:

```bash
cd frontend
pip install -r requirements.txt   # Flask e Requests
python front.py
```

Acesse `http://127.0.0.1:5001`.

Se a API estiver em outro computador, informe o endereço antes de iniciar:

```bash
export API_BASE_URL="http://IP_DO_SERVIDOR:5000"   # Windows: $env:API_BASE_URL="..."
python front.py
```

| Variável | Padrão | Descrição |
|---|---|---|
| `API_BASE_URL` | `http://127.0.0.1:5000` | Endereço da API |
| `FLASK_SECRET_KEY` | `troque` | Chave da sessão do front. Defina uma própria |

> **Porta:** o `front.py` usa a porta **5001**, a mesma do `dash.py`. Para rodar os dois ao mesmo tempo, altere a porta no final de um dos arquivos (`app.run(..., port=...)`).

**Rotas da API usadas:** `GET /health`, `GET /colaboradores`, `POST /colaboradores`, `POST /cartoes` e `GET /acessos`.

---

## Análise de dados (Jupyter)

O notebook `analise_dados.ipynb` faz login na API, baixa os registros de `/acessos` para um DataFrame do Pandas e responde:

1. Quantas pessoas entraram na sala em determinado dia?
2. Quantas pessoas saíram da sala em determinado dia?
3. Quanto tempo um colaborador permaneceu na sala em determinado dia?
4. Quantas tentativas de acesso negado ocorreram?
5. Quantas tentativas com tags desconhecidas (possível invasão) ocorreram?
6. Quais colaboradores não autorizados mais tentaram acessar a sala?

Para executar:

```bash
jupyter notebook analise_dados.ipynb
```

Antes de rodar, ajuste na primeira célula e nas seguintes:

| O que | Onde | Padrão |
|---|---|---|
| Endereço da API | `url_base` | `http://127.0.0.1:5000` |
| Usuário e senha | `sessao.post(... json={...})` | `admin` / `admin123` |
| Dia analisado | `dia` | `"2026-10-28"` (formato `AAAA-MM-DD`) |
| Colaborador do tempo de permanência | `matricula` | `"MAT001"` |

A API precisa estar rodando para o notebook funcionar.

---

## Banco de dados

SQLite (`seguranca.db`), criado por `database.py`.

| Tabela | Campos principais | Descrição |
|---|---|---|
| `colaboradores` | `id`, `matricula` (única), `nome`, `funcao`, `autorizado`, `ativo`, `criado_em` | Pessoas cadastradas |
| `cartoes_rfid` | `id`, `uid` (único), `colaborador_id` (único), `ativo` | Um cartão por colaborador |
| `registros_acesso` | `id`, `colaborador_id`, `uid`, `evento`, `resultado`, `registrado_em`, `evento_id` (único) | Histórico de todos os eventos |

Para zerar tudo, pare a API e o dashboard e apague o arquivo `seguranca.db`. Ele será recriado na próxima execução.

---

## Modo offline

Se a Raspberry perder a conexão com a API:

1. **Cache local:** cada resposta da API é guardada em `cache_rfid.json`. Se a API estiver fora do ar e o cartão estiver no cache, o acesso é decidido com base nessa última resposta.
2. **Cartão fora do cache:** o acesso é **negado por segurança**.
3. **Fila de pendentes:** eventos que não puderam ser enviados ficam em `acessos_pendentes.json` e são reenviados quando a API voltar a responder.
4. **Sem duplicidade:** cada evento pendente carrega um `evento_id` único, então a API ignora reenvios repetidos.
5. **Log local:** todos os eventos também são gravados em `logs_acesso.csv`.

Esse funcionamento depende de o cartão já ter sido consultado com a API online ao menos uma vez, e da correta sincronização com a API. Alterações de permissão feitas no servidor só chegam à Raspberry quando ela voltar a se comunicar com a API.

---

## Autores

Desenvolvido por:
  - Thaise Zanin - Hardware e Raspberry Pi
  - Alice Segatto - Backend, API e banco de dados
  - Ana Amaral - Sistema web de gerenciamento
  - Aline Hoffmann - Monitoramento e análise de dados
  - Pedro Segatto - Testes e documentação
