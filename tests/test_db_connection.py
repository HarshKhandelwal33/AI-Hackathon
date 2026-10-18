import unittest
from unittest.mock import patch
import psycopg
from loglens.db import SereneDB

class ConnectionTests(unittest.TestCase):
    def test_auth_failure_is_cached_and_sanitized(self):
        db = SereneDB("password=secret")
        with patch("loglens.db.psycopg.connect", side_effect=psycopg.OperationalError("password secret rejected")) as connect:
            for _ in range(3):
                with self.assertRaisesRegex(RuntimeError, "authentication failed") as error:
                    db.fetch_all("SELECT 1", [])
                self.assertNotIn("secret", str(error.exception))
            self.assertEqual(connect.call_count, 1)
        db.close()
