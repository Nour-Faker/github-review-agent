import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from app.logger import get_logger
logger = get_logger("database")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    """Crée la table reviews si elle n'existe pas."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id          SERIAL PRIMARY KEY,
            pr_number   INTEGER NOT NULL,
            repo        VARCHAR(255) NOT NULL,
            status      VARCHAR(50) DEFAULT 'processing',
            bugs        INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("DB — table reviews prête")


def save_review(pr_number: int, repo: str, status: str = "processing", bugs: int = 0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reviews (pr_number, repo, status, bugs) VALUES (%s, %s, %s, %s)",
        (pr_number, repo, status, bugs)
    )
    conn.commit()
    cur.close()
    conn.close()


def update_review(pr_number: int, repo: str, status: str, bugs: int = 0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE reviews SET status=%s, bugs=%s WHERE pr_number=%s AND repo=%s",
        (status, bugs, pr_number, repo)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_all_reviews():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM reviews ORDER BY created_at DESC LIMIT 50")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_metrics():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) as total_prs,
            COUNT(*) FILTER (WHERE status = 'analysed') as analysed,
            COUNT(*) FILTER (WHERE status = 'oversized') as oversized,
            COALESCE(SUM(bugs), 0) as bugs_detected
        FROM reviews
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row)