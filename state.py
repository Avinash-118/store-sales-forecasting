"""
state.py - all external state for the Store Sales app lives behind this module.

- Secrets (DB host/user/password) come from Azure Key Vault
- Database is Azure Database for PostgreSQL (private network only)
- File uploads go to Azure Blob Storage
- All Azure access uses the container app's managed identity (no keys, no .env)

Non-secret configuration comes from environment variables:
    KEY_VAULT_URL      e.g. https://kv-storesales-667.vault.azure.net/
    STORAGE_ACCOUNT    e.g. storesales28606
    BLOB_CONTAINER     e.g. uploads   (default)
    PG_DATABASE        default: postgres
"""
import glob
import json
import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


@lru_cache(maxsize=1)
def _credential():
    return DefaultAzureCredential()


@lru_cache(maxsize=None)
def get_secret(name: str) -> str:
    client = SecretClient(vault_url=os.environ["KEY_VAULT_URL"], credential=_credential())
    return client.get_secret(name).value


def get_conn():
    return psycopg2.connect(
        host=get_secret("pg-host"),
        user=get_secret("pg-user"),
        password=get_secret("pg-password"),
        dbname=os.getenv("PG_DATABASE", "postgres"),
        sslmode="require",
        connect_timeout=10,
    )


def run_migrations():
    """Apply every migrations/*.sql file in name order (files are idempotent)."""
    conn = get_conn()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
                with open(path, "r", encoding="utf-8") as f:
                    cur.execute(f.read())
                print(f"applied migration: {os.path.basename(path)}")
    finally:
        conn.close()


def _to_jsonable(o):
    if hasattr(o, "tolist"):
        return o.tolist()
    return float(o)


def save_forecast(store_nbr, family, horizon, onpromotion, is_holiday, predictions):
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO forecast_history
                    (store_nbr, family, horizon, onpromotion, is_holiday, predictions)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    int(store_nbr),
                    family,
                    int(horizon),
                    [int(x) for x in onpromotion],
                    [int(x) for x in is_holiday],
                    Json(predictions, dumps=lambda o: json.dumps(o, default=_to_jsonable)),
                ),
            )
    finally:
        conn.close()


def load_history(limit=20):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT created_at AS timestamp, store_nbr, family, horizon,
                       onpromotion, is_holiday, predictions
                FROM forecast_history
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def count_rows(table: str) -> int:
    if table not in ("forecast_history", "uploaded_files"):
        raise ValueError("unknown table")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]
    finally:
        conn.close()


def upload_file(original_name: str, data: bytes) -> str:
    """Upload bytes to Blob Storage using managed identity and record it in Postgres."""
    account = os.environ["STORAGE_ACCOUNT"]
    container = os.getenv("BLOB_CONTAINER", "uploads")
    blob_name = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}-{original_name}"

    service = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net", credential=_credential()
    )
    service.get_blob_client(container=container, blob=blob_name).upload_blob(data)

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO uploaded_files (original_name, blob_name, container, size_bytes)
                VALUES (%s, %s, %s, %s)
                """,
                (original_name, blob_name, container, len(data)),
            )
    finally:
        conn.close()
    return blob_name