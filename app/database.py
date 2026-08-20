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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id              SERIAL PRIMARY KEY,
            pr_number       INTEGER NOT NULL,
            repo            VARCHAR(255) NOT NULL,
            status          VARCHAR(50) DEFAULT 'processing',
            bugs            INTEGER DEFAULT 0,
            critical_count  INTEGER DEFAULT 0,
            warning_count   INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key   VARCHAR(100) PRIMARY KEY,
        value VARCHAR(255) NOT NULL
    );
    """)

    # Valeur par défaut si la table est vide
    cur.execute("""
        INSERT INTO settings (key, value)
        VALUES ('max_diff_lines', '500')
        ON CONFLICT (key) DO NOTHING;
    """)
    cur.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS critical_count INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS warning_count INTEGER DEFAULT 0")
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

def update_review(pr_number: int, repo: str, status: str, bugs: int = 0,
                  critical_count: int = 0, warning_count: int = 0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE reviews
           SET status=%s, bugs=%s, critical_count=%s, warning_count=%s
           WHERE pr_number=%s AND repo=%s""",
        (status, bugs, critical_count, warning_count, pr_number, repo)
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
            COALESCE(SUM(bugs), 0) as bugs_detected,
            COALESCE(SUM(critical_count), 0) as critical_total,
            COALESCE(SUM(warning_count), 0) as warning_total
        FROM reviews
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row)

def get_setting(key: str, default: str = None) -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["value"] if row else default

def save_setting(key: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings (key, value)
        VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, (key, value))
    conn.commit()
    cur.close()
    conn.close()