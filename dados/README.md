
# Monitoramento RFID

## Arquivos

- `app.py`: inicia o dashboard.
- `templates/index.html`: página do dashboard.
- `logs_acesso.csv`: dados dos acessos.
- `analise_logs.ipynb`: análises dos dados com Pandas.
- `requirements.txt`: bibliotecas necessárias.

## Como usar

1. Abra o terminal na pasta do projeto.

2. Instale as bibliotecas:

   ```bash
   pip install flask pandas
   ```

3. Inicie o dashboard:

   ```bash
   python app.py
   ```

4. Abra no navegador: http://127.0.0.1:5000

## Notebook

Abra o arquivo `analise_logs.ipynb` no VS Code ou no Jupyter Notebook e execute as células.

O notebook utiliza o arquivo `logs_acesso.csv` para analisar os dados.



