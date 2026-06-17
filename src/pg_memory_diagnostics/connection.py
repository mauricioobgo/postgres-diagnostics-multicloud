"""Build PostgreSQL connection strings, including Cloud SQL Auth Proxy modes.

The Cloud SQL Auth Proxy gives applications a secure, IAM-authenticated tunnel
to a Cloud SQL instance without managing SSL certificates or allow-lists. It can
listen in two ways:

* **TCP** — the proxy listens on a local port (127.0.0.1:5432 by default) and
  you connect as if PostgreSQL were running locally. The proxy itself encrypts
  the connection, so ``sslmode=disable`` is the correct setting for the hop to
  the proxy.
* **Unix socket** — the proxy creates a socket directory (conventionally
  ``/cloudsql``) containing one directory per instance named after the
  ``INSTANCE_CONNECTION_NAME`` (``project:region:instance``). libpq/psycopg use
  the *directory* as the host and append the ``.s.PGSQL.<port>`` suffix
  automatically.

References:
- Connect using the Cloud SQL Auth Proxy:
  https://cloud.google.com/sql/docs/postgres/connect-auth-proxy
- About the Cloud SQL Auth Proxy:
  https://cloud.google.com/sql/docs/postgres/sql-proxy
"""

from __future__ import annotations

from urllib.parse import quote


DEFAULT_PROXY_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 5432
DEFAULT_SOCKET_DIR = "/cloudsql"


def _require(value: str | None, name: str) -> str:
    if not value:
        raise ValueError(f"{name} is required for this connection mode.")
    return value


def build_cloudsql_proxy_dsn(
    *,
    user: str | None,
    password: str | None,
    dbname: str | None,
    mode: str = "tcp",
    host: str = DEFAULT_PROXY_HOST,
    port: int = DEFAULT_PROXY_PORT,
    socket_dir: str = DEFAULT_SOCKET_DIR,
    instance_connection_name: str | None = None,
) -> str:
    """Return a libpq DSN that targets a locally running Cloud SQL Auth Proxy.

    ``mode`` is ``"tcp"`` (default) or ``"unix"``. The Auth Proxy encrypts the
    connection itself, so ``sslmode=disable`` is used for the local hop.
    """

    user = _require(user, "user")
    dbname = _require(dbname, "dbname")

    if mode == "tcp":
        return _build_keyvalue_dsn(
            user=user,
            password=password,
            dbname=dbname,
            host=host,
            port=str(port),
            sslmode="disable",
        )

    if mode == "unix":
        instance = _require(instance_connection_name, "instance_connection_name")
        # libpq treats a host that begins with "/" as a Unix socket directory and
        # appends ".s.PGSQL.<port>" itself, so we pass the per-instance directory.
        socket_path = f"{socket_dir.rstrip('/')}/{instance}"
        return _build_keyvalue_dsn(
            user=user,
            password=password,
            dbname=dbname,
            host=socket_path,
            port=str(port),
            sslmode="disable",
        )

    raise ValueError(f"Unknown Cloud SQL proxy mode: {mode!r} (expected 'tcp' or 'unix').")


def _build_keyvalue_dsn(
    *,
    user: str,
    password: str | None,
    dbname: str,
    host: str,
    port: str,
    sslmode: str,
) -> str:
    """Build a libpq key/value DSN, quoting values that need it.

    A key/value DSN avoids percent-encoding pitfalls with Unix socket paths
    (which contain ``/`` and ``:``) that a URL-style DSN would mangle.
    """

    parts: list[tuple[str, str]] = [
        ("host", host),
        ("port", port),
        ("dbname", dbname),
        ("user", user),
    ]
    if password:
        parts.append(("password", password))
    parts.append(("sslmode", sslmode))
    return " ".join(f"{key}={_quote_kv(value)}" for key, value in parts)


def _quote_kv(value: str) -> str:
    if value == "" or any(ch in value for ch in " '\\"):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    return value


def build_url_dsn(
    *,
    user: str,
    password: str | None,
    host: str,
    port: int,
    dbname: str,
    sslmode: str = "require",
) -> str:
    """Build a standard ``postgresql://`` URL DSN with safe percent-encoding."""

    auth = quote(user, safe="")
    if password:
        auth += ":" + quote(password, safe="")
    return f"postgresql://{auth}@{host}:{port}/{quote(dbname, safe='')}?sslmode={sslmode}"
