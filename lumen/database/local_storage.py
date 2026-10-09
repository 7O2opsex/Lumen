"""SQLite-backed storage for local analysis history."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lumen.config import DB_PATH


class LocalStorage:
    """Persist analysis history on the local machine."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        title TEXT NOT NULL,
                        data_json TEXT NOT NULL
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def add_history(self, kind: str, title: str, data: Any) -> int:
        """Store one result and return its history identifier."""
        created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO history (created_at, kind, title, data_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (created_at, kind, title, json.dumps(data, ensure_ascii=False, default=str)),
                )
                return int(cursor.lastrowid)

    def get_history(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        """Return the newest history records, with decoded result data."""
        query = """
            SELECT id, created_at, kind, title, data_json
            FROM history
            ORDER BY id DESC
        """
        parameters: tuple[int, ...] = ()
        if limit is not None:
            if limit < 0:
                raise ValueError("History limit cannot be negative")
            query += " LIMIT ?"
            parameters = (limit,)

        with closing(self._connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [
            {
                "id": row[0],
                "created_at": row[1],
                "kind": row[2],
                "title": row[3],
                "data": json.loads(row[4]),
            }
            for row in rows
        ]
