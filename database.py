
"""Database connection helper for the MediCare Hospital Management System.

Keep credentials in a local .env file (never commit that file to Git).
This loader intentionally uses only Python's standard library.
"""

from pathlib import Path
import os

import mysql.connector
from mysql.connector import Error


def _load_local_env():
    env_path = Path(__file__).resolve().parent / ".env"

    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


_load_local_env()


def get_connection():
    """Return a MySQL connection, or None after logging a safe error."""

    password = os.environ.get("DB_PASSWORD", "")

    if not password:
        print(
            "Database connection error: DB_PASSWORD is missing. "
            "Create .env from .env.example."
        )
        return None

    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=password,
            database=os.environ.get(
                "DB_NAME", "hospital_management"
            ),
            connection_timeout=8,
            autocommit=False,
        )

    except (Error, ValueError) as exc:
        print("Database connection error:", exc)
        return None