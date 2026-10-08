from PySide6.QtWidgets import QApplication

from microfleet.database import Database
from microfleet.main_window import MainWindow
from microfleet.models import Microservice, Server


def test_service_buttons_send_common_script_command(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    database_path = tmp_path / "ui.db"
    monkeypatch.setenv("MICROFLEET_DB_PATH", str(database_path))
    db = Database(database_path)
    server = db.save_server(
        Server(
            name="production", host="example.invalid", ssh_user="deploy",
            auth_type="password", management_script_path="/opt/my scripts/manage.sh",
        )
    )
    db.save_service(Microservice(server_id=server.id, name="billing api"))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    class FakeSession:
        commands: list[str] = []

        def send_command(self, command):
            self.commands.append(command)
            return True

    fake_session = FakeSession()
    monkeypatch.setattr(window, "_session_for_command", lambda _server: fake_session)
    monkeypatch.setattr(window.credential_store, "get_dek", lambda: None)
    try:
        window._run_service_action(window.services[0], "restart", 0)
        window._run_all_action("status")
        assert fake_session.commands == [
            "stty -echo; '/opt/my scripts/manage.sh' restart 'billing api'; "
            "stty echo; '/opt/my scripts/manage.sh' status 'billing api'",
            "'/opt/my scripts/manage.sh' status all",
        ]
        assert all("printf" not in command for command in fake_session.commands)
    finally:
        window.close()


def test_status_output_updates_service_row(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    database_path = tmp_path / "status-ui.db"
    monkeypatch.setenv("MICROFLEET_DB_PATH", str(database_path))
    db = Database(database_path)
    server = db.save_server(
        Server(
            name="production", host="example.invalid", ssh_user="deploy",
            auth_type="password", management_script_path="/opt/manage.sh",
        )
    )
    db.save_service(Microservice(server_id=server.id, name="orders"))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    class FakeSession:
        def __init__(self):
            self.commands = []

        def send_command(self, command):
            self.commands.append(command)
            return True

        def isRunning(self):
            return True

    session = FakeSession()
    monkeypatch.setattr(window, "_session_for_command", lambda _server: session)
    monkeypatch.setattr(window.credential_store, "get_dek", lambda: None)
    window.sessions[server.id] = session
    try:
        window._run_service_action(window.services[0], "start", 0)
        window._on_ssh_output(server.id, "$ /opt/manage.sh start orders\r\n")
        window._on_ssh_output(server.id, "Started orders\n")
        assert len(session.commands) == 1
        assert "/opt/manage.sh status orders" in session.commands[0]
        window._on_ssh_output(server.id, "$ /opt/manage.sh status orders\r\n")
        window._on_ssh_output(server.id, '\x1b[32mChecking service "ord')
        window._on_ssh_output(server.id, 'ers" ..... running.\x1b[0m\n')
        assert window.service_table.item(0, 2).text() == "Работает"
        assert "\x1b[32m" not in window.terminal.toPlainText()
        assert "printf" not in window.terminal.toPlainText()
        assert "/opt/manage.sh status orders" in window.terminal.toPlainText()
        assert 'Checking service "orders" ..... running.' in window.terminal.toPlainText()
    finally:
        window.sessions.pop(server.id)
        window.close()


def test_dek_prompts_are_answered_without_exposing_password(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    database_path = tmp_path / "dek-ui.db"
    monkeypatch.setenv("MICROFLEET_DB_PATH", str(database_path))
    db = Database(database_path)
    server = db.save_server(Server(
        name="production", host="example.invalid", ssh_user="deploy",
        auth_type="password", management_script_path="/opt/manage.sh",
    ))
    db.save_service(Microservice(server_id=server.id, name="orders"))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.dek_password = "abcdefgh"

    class FakeSession:
        def __init__(self):
            self.commands = []

        def send_command(self, command):
            self.commands.append(command)
            return True

    session = FakeSession()
    monkeypatch.setattr(window, "_session_for_command", lambda _server: session)
    window.sessions[server.id] = session
    try:
        window._run_service_action(window.services[0], "start", 0)
        assert len(session.commands) == 1
        assert session.commands[0] == (
            "stty -echo; /opt/manage.sh start orders; "
            "stty echo; /opt/manage.sh status orders"
        )
        window._on_ssh_output(server.id, "Enter first password comp")
        assert len(session.commands) == 1
        window._on_ssh_output(server.id, "onent:")
        assert session.commands[1] == "abcd"
        window._on_ssh_output(server.id, "abcd\r\nEnter second password component:")
        assert session.commands[2] == "efgh"
        window._on_ssh_output(server.id, "efgh\r\n")
        window._on_ssh_output(server.id, 'Checking service "orders" ..... running.\n')
        assert window.service_table.item(0, 2).text() == "Работает"
        assert server.id not in window.dek_automations
        assert "abcd" not in window.terminal.toPlainText()
        assert "efgh" not in window.terminal.toPlainText()
    finally:
        window.sessions.pop(server.id)
        window.close()


def test_saved_password_is_loaded_on_next_launch(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    database_path = tmp_path / "saved-password-ui.db"
    monkeypatch.setenv("MICROFLEET_DB_PATH", str(database_path))
    db = Database(database_path)
    server = db.save_server(Server(
        name="production", host="example.invalid", ssh_user="deploy", auth_type="password",
    ))

    class FakeCredentialStore:
        available = True

        def __init__(self, _path):
            pass

        def get(self, current):
            return "saved-secret" if current.id == server.id else None

    connections = []
    monkeypatch.setattr("microfleet.main_window.CredentialStore", FakeCredentialStore)
    monkeypatch.setattr(
        MainWindow, "_connect_server",
        lambda _self, current, quiet=False: connections.append((current.id, quiet)),
    )
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.passwords[server.id] == "saved-secret"
        assert connections == [(server.id, True)]
    finally:
        window.close()
