from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Server:
    id: int | None = None
    name: str = ""
    host: str = ""
    port: int = 22
    ssh_user: str = ""
    run_as_user: str = ""
    auth_type: str = "key"
    key_path: str = ""
    group_name: str = ""
    notes: str = ""
    management_script_path: str = ""


@dataclass(slots=True)
class Microservice:
    id: int | None = None
    server_id: int = 0
    name: str = ""
    description: str = ""
    sort_order: int = 0
