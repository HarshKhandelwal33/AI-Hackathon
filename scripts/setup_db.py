"""Apply the LogLens schema and ownership mapping to a configured SereneDB."""

from __future__ import annotations

from pathlib import Path

import psycopg

from loglens.config import Settings


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    files = (root / "sql" / "001_schema.sql", root / "sql" / "002_sample_ownership.sql")
    dsn = Settings.from_env().dsn
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        for path in files:
            cursor.execute(path.read_text(encoding="utf-8"))
            print(f"applied {path.relative_to(root)}")
        connection.commit()
    print("database setup complete")


if __name__ == "__main__":
    main()
