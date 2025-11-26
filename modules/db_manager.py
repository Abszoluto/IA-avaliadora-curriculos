import sqlite3
import hashlib
import json
from datetime import datetime

DB_NAME = "users.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Tabela Usuários
    c.execute(
        """CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)"""
    )

    # Tabela Histórico (utlizada no Dashboard)
    c.execute(
        """CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT, 
                  job_title TEXT, 
                  score INTEGER, 
                  missing_skills TEXT, 
                  analysis_date DATETIME,
                  status TEXT DEFAULT 'Analisado',
                  job_link TEXT)"""
    )

    try:
        c.execute("PRAGMA table_info(history)")
        cols = [row[1] for row in c.fetchall()]
        if "job_link" not in cols:
            c.execute("ALTER TABLE history ADD COLUMN job_link TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()

def user_exists(username: str) -> bool:
    """
    Verifica se o usuário ainda existe no banco.
    Usado para evitar sessão 'fantasma' quando o banco foi apagado/recriado.
    """
    if not username:
        return False

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        exists = c.fetchone() is not None
    finally:
        conn.close()
    return exists
    
def create_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    c.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, hashed_pw),
    )
    result = c.fetchone()
    conn.close()
    return result is not None


# Funções do dashboard
def save_analysis(username, job_title, score, missing_skills, job_link=None):
    """
    Salva uma análise no histórico do usuário, incluindo o link da vaga (opcional).
    Agora guarda o título COMPLETO da vaga.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    title = (job_title or "").strip()
    skills_json = json.dumps(missing_skills or [])
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute(
        """
        INSERT INTO history 
            (username, job_title, score, missing_skills, analysis_date, status, job_link)
        VALUES 
            (?, ?, ?, ?, ?, ?, ?)
        """,
        (username, title, score, skills_json, date_now, "Analisado", job_link or ""),
    )
    conn.commit()
    conn.close()


def get_user_history(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT 
            id, job_title, score, missing_skills, analysis_date, status, job_link
        FROM history 
        WHERE username = ? 
        ORDER BY analysis_date DESC
        """,
        (username,),
    )
    data = c.fetchall()
    conn.close()
    return data