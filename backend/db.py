"""Connection helper for the AML/KYC Postgres database (pgvector-enabled).

Reads connection details from environment variables, with sensible local
defaults for development against a locally running Postgres instance.
"""

import os

import asyncpg

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "aml_kyc_copilot")
DB_USER = os.environ.get("DB_USER", os.environ.get("USER", "postgres"))
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")


async def get_connection() -> asyncpg.Connection:
    """Opens a new asyncpg connection using the env-configured settings above."""
    return await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD or None,
    )
