import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

DB_PATH = Path("data/app.db")


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                patient_code TEXT PRIMARY KEY,
                patient_name TEXT NOT NULL,
                pin_salt TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                consent TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT NOT NULL,
                record_type TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                payload_encrypted TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner, record_type, recorded_at)
            )
            """
        )

        columns = [row["name"] for row in conn.execute("PRAGMA table_info(records)").fetchall()]
        if "owner" not in columns:
            conn.execute(
                """
                CREATE TABLE records_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_encrypted TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(owner, record_type, recorded_at)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO records_new(id, owner, record_type, recorded_at, payload_encrypted, created_at, updated_at)
                SELECT id, 'legacy', record_type, recorded_at, payload_encrypted, created_at, updated_at
                FROM records
                """
            )
            conn.execute("DROP TABLE records")
            conn.execute("ALTER TABLE records_new RENAME TO records")


def _scoped_key(key: str, owner: str | None) -> str:
    if owner:
        return f"user:{owner}:{key}"
    return key


def get_setting(key: str, default: str | None = None, owner: str | None = None) -> str | None:
    scoped = _scoped_key(key, owner)
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (scoped,)).fetchone()
    if row is None:
        return default
    return row["value"]


def set_setting(key: str, value: str, owner: str | None = None) -> None:
    scoped = _scoped_key(key, owner)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (scoped, value),
        )


def get_user(patient_code: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT patient_code, patient_name, pin_salt, pin_hash, consent, created_at
            FROM users WHERE patient_code = ?
            """,
            (patient_code,),
        ).fetchone()
    return dict(row) if row else None


def create_user(
    patient_code: str,
    patient_name: str,
    pin_salt: str,
    pin_hash: str,
    consent: str = "true",
) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users(patient_code, patient_name, pin_salt, pin_hash, consent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (patient_code, patient_name, pin_salt, pin_hash, consent, now),
        )


def has_duplicate(owner: str, record_type: str, recorded_at: str, exclude_id: int | None = None) -> bool:
    query = "SELECT id FROM records WHERE owner = ? AND record_type = ? AND recorded_at = ?"
    params: list[Any] = [owner, record_type, recorded_at]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)

    with get_connection() as conn:
        row = conn.execute(query, tuple(params)).fetchone()
    return row is not None


def save_record(
    owner: str,
    record_type: str,
    recorded_at: str,
    payload: dict,
    fernet: Fernet,
    record_id: int | None = None,
) -> int:
    now = datetime.utcnow().isoformat()
    encrypted = fernet.encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("utf-8")

    with get_connection() as conn:
        if record_id is None:
            cursor = conn.execute(
                """
                INSERT INTO records(owner, record_type, recorded_at, payload_encrypted, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (owner, record_type, recorded_at, encrypted, now, now),
            )
            return int(cursor.lastrowid)

        conn.execute(
            """
            UPDATE records
            SET owner = ?, record_type = ?, recorded_at = ?, payload_encrypted = ?, updated_at = ?
            WHERE id = ?
            """,
            (owner, record_type, recorded_at, encrypted, now, record_id),
        )
        return record_id


def delete_record(record_id: int, owner: str | None = None) -> None:
    query = "DELETE FROM records WHERE id = ?"
    params: list[Any] = [record_id]
    if owner:
        query += " AND owner = ?"
        params.append(owner)

    with get_connection() as conn:
        conn.execute(query, tuple(params))


def load_records(owner: str, fernet: Fernet, record_type: str | None = None) -> list[dict]:
    query = "SELECT id, owner, record_type, recorded_at, payload_encrypted FROM records WHERE owner = ?"
    params: tuple[Any, ...] = (owner,)
    if record_type:
        query += " AND record_type = ?"
        params = (owner, record_type)
    query += " ORDER BY recorded_at DESC"

    rows: list[dict] = []
    with get_connection() as conn:
        for row in conn.execute(query, params).fetchall():
            decrypted = fernet.decrypt(row["payload_encrypted"].encode("utf-8"))
            payload = json.loads(decrypted.decode("utf-8"))
            rows.append(
                {
                    "id": row["id"],
                    "owner": row["owner"],
                    "record_type": row["record_type"],
                    "recorded_at": row["recorded_at"],
                    **payload,
                }
            )
    return rows


def reset_local_data() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM records")
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM users")
