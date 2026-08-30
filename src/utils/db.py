import os
from sqlalchemy import create_engine, text


def mysql_engine(echo: bool = False):
    """Create a SQLAlchemy engine for MySQL using env vars."""
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "olist")
    password = os.getenv("MYSQL_PASSWORD", "olist")
    db = os.getenv("MYSQL_DATABASE", "olist")

    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"
    return create_engine(url, echo=echo, pool_pre_ping=True)


def run_sql_file(engine, path: str):
    """Execute a .sql file (statements separated by ';')."""
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    # split on ';' but keep simple (good enough for this project's SQL)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
