from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Microservice, Server


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL DEFAULT 22,
                    ssh_user TEXT NOT NULL,
                    run_as_user TEXT NOT NULL DEFAULT '',
                    auth_type TEXT NOT NULL DEFAULT 'key',
                    key_path TEXT NOT NULL DEFAULT '',
                    group_name TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    management_script_path TEXT NOT NULL DEFAULT '',
                    UNIQUE(host, port, ssh_user)
                );

                CREATE TABLE IF NOT EXISTS microservices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    script_path TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(server_id, name)
                );
                """
            )
            # Existing installations used a script path on each service. Keep that
            # legacy column intact; the common path now belongs to the server.
            columns = {row["name"] for row in db.execute("PRAGMA table_info(servers)")}
            if "management_script_path" not in columns:
                db.execute(
                    "ALTER TABLE servers ADD COLUMN management_script_path TEXT NOT NULL DEFAULT ''"
                )

    def list_servers(self) -> list[Server]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM servers ORDER BY group_name, name COLLATE NOCASE"
            ).fetchall()
        return [Server(**dict(row)) for row in rows]

    def save_server(self, server: Server) -> Server:
        values = (
            server.name.strip(), server.host.strip(), server.port,
            server.ssh_user.strip(), server.run_as_user.strip(), server.auth_type,
            server.key_path.strip(), server.group_name.strip(), server.notes.strip(),
            server.management_script_path.strip(),
        )
        with self._connect() as db:
            if server.id is None:
                cursor = db.execute(
                    """INSERT INTO servers
                    (name, host, port, ssh_user, run_as_user, auth_type, key_path, group_name, notes, management_script_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    values,
                )
                server.id = int(cursor.lastrowid)
            else:
                db.execute(
                    """UPDATE servers SET name=?, host=?, port=?, ssh_user=?,
                    run_as_user=?, auth_type=?, key_path=?, group_name=?, notes=?,
                    management_script_path=? WHERE id=?""",
                    (*values, server.id),
                )
        return server

    def delete_server(self, server_id: int) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM servers WHERE id = ?", (server_id,))

    def list_services(self, server_id: int) -> list[Microservice]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT id, server_id, name, description, sort_order
                FROM microservices WHERE server_id = ?
                ORDER BY sort_order, name COLLATE NOCASE""",
                (server_id,),
            ).fetchall()
        return [Microservice(**dict(row)) for row in rows]

    def save_service(self, service: Microservice) -> Microservice:
        values = (
            service.server_id, service.name.strip(), service.description.strip(),
            service.sort_order,
        )
        with self._connect() as db:
            if service.id is None:
                cursor = db.execute(
                    """INSERT INTO microservices
                    (server_id, name, script_path, description, sort_order)
                    VALUES (?, ?, '', ?, ?)""",
                    values,
                )
                service.id = int(cursor.lastrowid)
            else:
                db.execute(
                    """UPDATE microservices SET server_id=?, name=?,
                    description=?, sort_order=? WHERE id=?""",
                    (*values, service.id),
                )
        return service

    def delete_service(self, service_id: int) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM microservices WHERE id = ?", (service_id,))
