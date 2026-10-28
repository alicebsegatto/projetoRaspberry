# Front-end CRUD RFID conectado à API

## Requisitos
- O backend/API do integrante precisa estar executando.
- Por padrão, o front espera a API em `http://127.0.0.1:5000`.
- O front executa em `http://127.0.0.1:5001` para não conflitar com a API.

## Instalação no Ubuntu
Na pasta deste projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python front.py
```

Abra `http://127.0.0.1:5001`.

## Se a API estiver em outro computador
Configure o endereço IP do computador do backend (não use localhost nesse caso):

```bash
export API_BASE_URL="http://IP_DO_COMPUTADOR_BACK:5000"
python front.py
```

Substitua `IP_DO_COMPUTADOR_BACK` pelo IP real. O computador precisa estar acessível na mesma rede.

## Rotas da API usadas pelo front
- `GET /health`: verificar API.
- `GET /colaboradores`: listagem e validação do login.
- `POST /colaboradores`: cadastro principal (matrícula, nome, função, autorizado).
- `POST /cartoes`: associação do UID ao ID retornado no cadastro.
- `GET /acessos`: consulta dos últimos registros de acesso.

## Limitações da API recebida
O backend enviado não contém rotas para editar ou excluir colaboradores. Por isso, esses botões estão desabilitados e a interface avisa o motivo. Para habilitá-los, o backend precisa implementar, por exemplo:
- `PUT /colaboradores/<id>` para atualização;
- `DELETE /colaboradores/<id>` para exclusão.

Também não existe uma rota de login. O front consulta `GET /colaboradores` e confere localmente se o nome e o UID RFID correspondem. Para um sistema real, o ideal é que o backend forneça uma rota própria de autenticação.

## Observações
- O cadastro utiliza duas requisições sequenciais: cria o colaborador e depois associa o cartão. Como a API atual não oferece uma operação transacional única para ambas, pode ocorrer cadastro do colaborador sem cartão se a segunda chamada falhar.
- O front não abre o banco `seguranca.db` diretamente: toda leitura/gravação passa pela API.
- O login por UID RFID é apenas o comportamento de protótipo solicitado, não uma forma forte de autenticação para produção.
