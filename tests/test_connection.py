from __future__ import annotations

import unittest

from pg_memory_diagnostics.connection import build_cloudsql_proxy_dsn, build_url_dsn


class CloudSqlProxyDsnTest(unittest.TestCase):
    def test_tcp_mode_builds_localhost_dsn_with_sslmode_disable(self) -> None:
        dsn = build_cloudsql_proxy_dsn(
            user="reporter",
            password="s3cret",
            dbname="appdb",
            mode="tcp",
        )
        self.assertIn("host=127.0.0.1", dsn)
        self.assertIn("port=5432", dsn)
        self.assertIn("dbname=appdb", dsn)
        self.assertIn("user=reporter", dsn)
        # The proxy encrypts the hop, so sslmode is disabled for the local link.
        self.assertIn("sslmode=disable", dsn)

    def test_unix_mode_uses_instance_socket_directory(self) -> None:
        dsn = build_cloudsql_proxy_dsn(
            user="reporter",
            password=None,
            dbname="appdb",
            mode="unix",
            instance_connection_name="my-proj:us-central1:pg-main",
        )
        self.assertIn("host=/cloudsql/my-proj:us-central1:pg-main", dsn)
        self.assertIn("sslmode=disable", dsn)
        self.assertNotIn("password=", dsn)

    def test_unix_mode_requires_instance_connection_name(self) -> None:
        with self.assertRaises(ValueError):
            build_cloudsql_proxy_dsn(user="u", password=None, dbname="d", mode="unix")

    def test_missing_required_fields_raise(self) -> None:
        with self.assertRaises(ValueError):
            build_cloudsql_proxy_dsn(user=None, password=None, dbname="d")
        with self.assertRaises(ValueError):
            build_cloudsql_proxy_dsn(user="u", password=None, dbname=None)

    def test_unknown_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_cloudsql_proxy_dsn(user="u", password=None, dbname="d", mode="bogus")

    def test_url_dsn_percent_encodes_credentials(self) -> None:
        dsn = build_url_dsn(
            user="user@example",
            password="p@ss/word",
            host="db.internal",
            port=5432,
            dbname="appdb",
        )
        self.assertTrue(dsn.startswith("postgresql://user%40example:p%40ss%2Fword@db.internal:5432/appdb"))
        self.assertIn("sslmode=require", dsn)


if __name__ == "__main__":
    unittest.main()
