from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Protocol

import psycopg
from psycopg.rows import dict_row


class QueryRunner(Protocol):
    def fetch_all(self, query: str, parameters: list[Any]) -> list[dict[str, Any]]: ...


class SereneDB:
    def __init__(self, dsn: str):
        self._dsn = dsn

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self._dsn, row_factory=dict_row) as connection:
            yield connection

    def fetch_all(self, query: str, parameters: list[Any]) -> list[dict[str, Any]]:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(query, parameters)
            return list(cursor.fetchall())

