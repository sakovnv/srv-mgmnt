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
        commands: list[tuple[str, str]] = []

        def send_managed_command(self, command, token):
            self.commands.append((command, token))
            return True

    fake_session = FakeSession()
    monkeypatch.setattr(window, "_session_for_command", lambda _server: fake_session)
    try:
        window._run_service_action(window.services[0], "restart", 0)
        window._run_all_action("status")
        assert len(fake_session.commands) == 2
        assert "/opt/my scripts/manage.sh" in fake_session.commands[0][0]
        assert "restart" in fake_session.commands[0][0]
        assert "billing api" in fake_session.commands[0][0]
        assert "/opt/my scripts/manage.sh" in fake_session.commands[1][0]
        assert "status all" in fake_session.commands[1][0]
        assert all("printf" not in command for command, _ in fake_session.commands)
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

        def send_managed_command(self, command, token):
            self.commands.append((command, token))
            return True

        def isRunning(self):
            return True

    session = FakeSession()
    monkeypatch.setattr(window, "_session_for_command", lambda _server: session)
    window.sessions[server.id] = session
    try:
        window._run_service_action(window.services[0], "start", 0)
        action_token = session.commands[0][1]
        window._on_managed_output(server.id, action_token, "Started orders\n")
        window._on_managed_finished(server.id, action_token, 0)
        assert len(session.commands) == 2
        assert "/opt/manage.sh status orders" in session.commands[1][0]
        status_token = session.commands[1][1]
        window._on_managed_output(
            server.id, status_token,
            '\x1b[32mChecking service "orders" ..... running.\x1b[0m\n',
        )
        window._on_managed_finished(server.id, status_token, 0)
        assert window.service_table.item(0, 2).text() == "Работает"
        assert "\x1b[32m" not in window.terminal.toPlainText()
        assert "printf" not in window.terminal.toPlainText()
        assert "/opt/manage.sh status orders" in window.terminal.toPlainText()
        assert 'Checking service "orders" ..... running.' in window.terminal.toPlainText()
    finally:
        window.sessions.pop(server.id)
        window.close()
