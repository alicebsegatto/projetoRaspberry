import sqlite3
from pathlib import Path


# Caminho do banco de dados
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "seguranca.db"

# Abre uma conexão com o banco de dados
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# Cria as tabelas necessárias para o sistema.
def init_db():
    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS colaboradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                funcao TEXT NOT NULL,
                autorizado INTEGER NOT NULL DEFAULT 0
                    CHECK (autorizado IN (0, 1)),
                ativo INTEGER NOT NULL DEFAULT 1
                    CHECK (ativo IN (0, 1)),
                criado_em TEXT NOT NULL DEFAULT
                    (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS cartoes_rfid (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL UNIQUE,
                colaborador_id INTEGER NOT NULL UNIQUE,
                ativo INTEGER NOT NULL DEFAULT 1
                    CHECK (ativo IN (0, 1)),
                FOREIGN KEY (colaborador_id)
                    REFERENCES colaboradores(id)
            );

            CREATE TABLE IF NOT EXISTS registros_acesso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                colaborador_id INTEGER,
                uid TEXT NOT NULL,
                evento TEXT NOT NULL
                    CHECK (
                        evento IN (
                            'entrada',
                            'saida',
                            'negado',
                            'desconhecido'
                        )
                    ),
                resultado TEXT NOT NULL
                    CHECK (
                        resultado IN ('permitido', 'negado')
                    ),
                registrado_em TEXT NOT NULL DEFAULT
                    (datetime('now', 'localtime')),
                FOREIGN KEY (colaborador_id)
                    REFERENCES colaboradores(id)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_registros_data
            ON registros_acesso(registrado_em);

            CREATE INDEX IF NOT EXISTS idx_registros_colaborador
            ON registros_acesso(colaborador_id);

            CREATE INDEX IF NOT EXISTS idx_cartoes_uid
            ON cartoes_rfid(uid);
        """)

    print(f"Banco de dados inicializado em: {DB_PATH}")


if __name__ == "__main__":
    init_db()