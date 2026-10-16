from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    dsn: str
    max_rows: int = 100

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        maximum = int(os.getenv("LOGLENS_MAX_ROWS", "100"))
        if not 1 <= maximum <= 500:
            raise ValueError("LOGLENS_MAX_ROWS must be between 1 and 500")
        return cls(
            dsn=os.getenv(
                "SERENEDB_DSN",
                "host=localhost port=7890 dbname=postgres user=postgres",
            ),
            max_rows=maximum,
        )

