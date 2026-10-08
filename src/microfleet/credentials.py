"""SSH passwords in the current Windows user's Credential Manager."""

from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes
from pathlib import Path

from .models import Server


CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class CredentialStore:
    """Store secrets outside SQLite; Windows protects them for the signed-in user."""

    def __init__(self, database_path: Path) -> None:
        self.available = os.name == "nt"
        database_key = hashlib.sha256(str(database_path.resolve()).casefold().encode()).hexdigest()[:20]
        self._prefix = f"MicroFleet:ssh:{database_key}"
        self._dek_target = "MicroFleet:dek:v1"
        if not self.available:
            return
        self._api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self._api.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
        self._api.CredWriteW.restype = wintypes.BOOL
        self._api.CredReadW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_Credential)),
        ]
        self._api.CredReadW.restype = wintypes.BOOL
        self._api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._api.CredDeleteW.restype = wintypes.BOOL
        self._api.CredFree.argtypes = [ctypes.c_void_p]
        self._api.CredFree.restype = None

    def _target(self, server: Server) -> str:
        if server.id is None:
            raise ValueError("Server must be saved before storing a password")
        endpoint = f"{server.host.casefold()}:{server.port}:{server.ssh_user.casefold()}"
        endpoint_key = hashlib.sha256(endpoint.encode()).hexdigest()[:20]
        return f"{self._prefix}:{server.id}:{endpoint_key}"

    def get(self, server: Server) -> str | None:
        return self._read(self._target(server))

    def get_dek(self) -> str | None:
        return self._read(self._dek_target)

    def _read(self, target: str) -> str | None:
        if not self.available:
            return None
        result = ctypes.POINTER(_Credential)()
        if not self._api.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(result)):
            error = ctypes.get_last_error()
            if error == ERROR_NOT_FOUND:
                return None
            raise ctypes.WinError(error)
        try:
            entry = result.contents
            blob = ctypes.string_at(entry.CredentialBlob, entry.CredentialBlobSize)
            return blob.decode("utf-8")
        finally:
            self._api.CredFree(result)

    def set(self, server: Server, password: str) -> None:
        self._write(self._target(server), password, server.ssh_user)

    def set_dek(self, password: str) -> None:
        self._write(self._dek_target, password, "MicroFleet DEK")

    def _write(self, target: str, password: str, username: str) -> None:
        if not self.available:
            raise RuntimeError("Secure password storage is available only on Windows")
        data = password.encode("utf-8")
        if not data or len(data) > 2560:
            raise ValueError("SSH password must be between 1 and 2560 UTF-8 bytes")
        blob = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        entry = _Credential()
        entry.Type = CRED_TYPE_GENERIC
        entry.TargetName = target
        entry.CredentialBlobSize = len(data)
        entry.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        entry.Persist = CRED_PERSIST_LOCAL_MACHINE
        entry.UserName = username
        if not self._api.CredWriteW(ctypes.byref(entry), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def delete(self, server: Server) -> None:
        self._delete(self._target(server))

    def delete_dek(self) -> None:
        self._delete(self._dek_target)

    def _delete(self, target: str) -> None:
        if not self.available:
            return
        if not self._api.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
            error = ctypes.get_last_error()
            if error != ERROR_NOT_FOUND:
                raise ctypes.WinError(error)
