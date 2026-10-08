import os

import pytest

from microfleet.credentials import CredentialStore
from microfleet.models import Server


@pytest.mark.skipif(os.name != "nt", reason="Windows Credential Manager only")
def test_windows_credential_round_trip(tmp_path):
    store = CredentialStore(tmp_path / "isolated-test.db")
    server = Server(id=1, host="example.invalid", port=22, ssh_user="test-user")
    try:
        assert store.get(server) is None
        store.set(server, "Тестовый-секрет-123")
        assert store.get(server) == "Тестовый-секрет-123"
        assert store.get(Server(id=1, host="other.invalid", ssh_user="test-user")) is None
    finally:
        store.delete(server)
    assert store.get(server) is None


@pytest.mark.skipif(os.name != "nt", reason="Windows Credential Manager only")
def test_windows_dek_credential_round_trip(tmp_path):
    store = CredentialStore(tmp_path / "isolated-dek-test.db")
    store._dek_target = f"MicroFleet:test:dek:{tmp_path.name}"
    try:
        assert store.get_dek() is None
        store.set_dek("long-test-dek-password")
        assert store.get_dek() == "long-test-dek-password"
    finally:
        store.delete_dek()
    assert store.get_dek() is None
