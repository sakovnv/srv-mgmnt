"""Per-user configuration paths and one-time migration from AppData."""

from __future__ import annotations

import getpass
import hashlib
import os
import re
import sqlite3
import sys
import ctypes
from ctypes import wintypes
from contextlib import closing
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from .credentials import CredentialStore
from .database import Database


def application_directory() -> Path:
    """Use the .exe directory, or the project root while running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def current_user_identity() -> str:
    """Read the authenticated Windows identity, not editable environment variables."""
    if os.name != "nt":
        return getpass.getuser()
    api = ctypes.WinDLL("Secur32.dll", use_last_error=True)
    function = api.GetUserNameExW
    function.argtypes = [wintypes.ULONG, wintypes.LPWSTR, ctypes.POINTER(wintypes.ULONG)]
    function.restype = wintypes.BOOLEAN
    size = wintypes.ULONG(512)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not function(2, buffer, ctypes.byref(size)):  # NameSamCompatible = 2
        raise ctypes.WinError(ctypes.get_last_error())
    return buffer.value


def user_directory_name() -> str:
    """Keep Windows domain users with the same short name in separate folders."""
    identity = current_user_identity()
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", identity).strip(" ._")[:60]
    digest = hashlib.sha256(identity.casefold().encode("utf-8")).hexdigest()[:10]
    return f"{label or 'user'}-{digest}"


def default_database_path() -> Path:
    return application_directory() / "config" / "users" / user_directory_name() / "microfleet.db"


def prepare_database_path(legacy_path: Path) -> tuple[Path, list[str]]:
    """Copy existing user data once; never remove the old database or credentials."""
    override = os.environ.get("MICROFLEET_DB_PATH")
    if override:
        return Path(override), []

    target = default_database_path()
    if target.exists() or not legacy_path.is_file():
        return target, []

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        legacy_uri = f"file:{quote(legacy_path.resolve().as_posix(), safe='/:')}?mode=ro"
        with closing(sqlite3.connect(legacy_uri, uri=True)) as source:
            with closing(sqlite3.connect(temporary)) as destination:
                source.backup(destination)
        if not target.exists():
            try:
                temporary.rename(target)
            except FileExistsError:
                pass  # Another instance completed the migration first.
    finally:
        temporary.unlink(missing_ok=True)

    warnings: list[str] = []
    if target.exists():
        previous = CredentialStore(legacy_path)
        current = CredentialStore(target)
        if previous.available and current.available:
            for server in Database(target).list_servers():
                if server.auth_type != "password":
                    continue
                try:
                    password = previous.get(server)
                    if password and not current.get(server):
                        current.set(server, password)
                except Exception as exc:
                    warnings.append(f"{server.name}: {exc}")
    return target, warnings
