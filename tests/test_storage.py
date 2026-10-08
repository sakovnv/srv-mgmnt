from pathlib import Path

from microfleet.database import Database
from microfleet.models import Microservice, Server
from microfleet import storage


def test_legacy_database_and_passwords_migrate_once(tmp_path, monkeypatch):
    monkeypatch.delenv("MICROFLEET_DB_PATH", raising=False)
    target = tmp_path / "portable" / "config" / "users" / "domain_user" / "microfleet.db"
    old_path = tmp_path / "old-appdata" / "microfleet.db"
    monkeypatch.setattr(storage, "default_database_path", lambda: target)
    old_db = Database(old_path)
    server = old_db.save_server(Server(
        name="Production", host="example.invalid", ssh_user="deploy", auth_type="password",
    ))
    old_db.save_service(Microservice(server_id=server.id, name="orders"))

    secrets = {(old_path, server.id): "test-password"}

    class FakeCredentialStore:
        available = True

        def __init__(self, path):
            self.path = Path(path)

        def get(self, current):
            return secrets.get((self.path, current.id))

        def set(self, current, password):
            secrets[(self.path, current.id)] = password

    monkeypatch.setattr(storage, "CredentialStore", FakeCredentialStore)
    actual, warnings = storage.prepare_database_path(old_path)
    assert actual == target
    assert warnings == []
    assert target.is_file() and old_path.is_file()
    assert [item.name for item in Database(target).list_services(server.id)] == ["orders"]
    assert secrets[(target, server.id)] == "test-password"

    # A later launch must not overwrite edits made in the new location.
    Database(target).save_server(Server(
        id=server.id, name="Renamed", host="example.invalid", ssh_user="deploy",
        auth_type="password",
    ))
    storage.prepare_database_path(old_path)
    assert Database(target).list_servers()[0].name == "Renamed"


def test_explicit_database_path_bypasses_portable_layout(tmp_path, monkeypatch):
    selected = tmp_path / "custom.db"
    monkeypatch.setenv("MICROFLEET_DB_PATH", str(selected))
    assert storage.prepare_database_path(tmp_path / "old.db") == (selected, [])


def test_user_folder_is_distinct_for_windows_domains(monkeypatch):
    monkeypatch.setattr(storage, "current_user_identity", lambda: "DOMAIN_A\\operator")
    first = storage.user_directory_name()
    monkeypatch.setattr(storage, "current_user_identity", lambda: "DOMAIN_B\\operator")
    second = storage.user_directory_name()
    assert first != second
    assert "/" not in first and "\\" not in first


def test_frozen_application_stores_config_beside_exe(tmp_path, monkeypatch):
    executable = tmp_path / "MicroFleet.exe"
    monkeypatch.setattr(storage.sys, "frozen", True, raising=False)
    monkeypatch.setattr(storage.sys, "executable", str(executable))
    monkeypatch.setattr(storage, "user_directory_name", lambda: "DOMAIN_operator-123")
    assert storage.default_database_path() == (
        tmp_path / "config" / "users" / "DOMAIN_operator-123" / "microfleet.db"
    )
