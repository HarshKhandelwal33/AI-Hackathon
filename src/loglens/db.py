from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
import sys
from threading import Lock
from typing import Any, Iterator, Protocol

from psycopg_pool import ConnectionPool
import psycopg
from psycopg.rows import dict_row


class QueryRunner(Protocol):
    def fetch_all(self, query: str, parameters: list[Any]) -> list[dict[str, Any]]: ...


class SereneDB:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._lock = Lock()
        self._failure = None
        self._pool = None

    def _ready(self):
        # Probe once synchronously: background pool retries hide authentication failures.
        with self._lock:
            if self._failure:
                raise RuntimeError(self._failure)
            if self._pool is not None:
                return
            try:
                with psycopg.connect(self._dsn, connect_timeout=3):
                    pass
            except psycopg.Error as error:
                detail = str(error).lower()
                reason = ("authentication failed or password missing" if any(
                    term in detail for term in ("password", "authentication", "pg_hba"))
                    else "server unreachable or connection configuration invalid")
                self._failure = "SereneDB unavailable: " + reason + ". Check SERENEDB_DSN and restart LogLens after correcting it. No query ran."
                raise RuntimeError(self._failure) from None
            self._pool = ConnectionPool(self._dsn, min_size=0, max_size=4, timeout=5,
                                        kwargs={"row_factory": dict_row, "connect_timeout": 3})

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        self._ready()
        with self._pool.connection() as connection:
            yield connection

    def fetch_all(self, query: str, parameters: list[Any]) -> list[dict[str, Any]]:
        started = perf_counter()
        try:
            with self.connection() as connection, connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return list(cursor.fetchall())
        finally:
            print(f"[database] elapsed_ms={(perf_counter()-started)*1000:.1f}", file=sys.stderr)


    def close(self):
        if self._pool is not None:
            self._pool.close()
