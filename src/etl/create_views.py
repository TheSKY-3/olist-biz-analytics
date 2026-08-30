"""Create MySQL analytics views."""

from pathlib import Path

from src.utils.db import mysql_engine, run_sql_file


def main():
    engine = mysql_engine(echo=False)
    run_sql_file(engine, str(Path("sql") / "02_views.sql"))
    print("[OK] created analytics views")


if __name__ == "__main__":
    main()
