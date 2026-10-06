from microfleet.models import Server
from microfleet.ssh import (
    clean_terminal_output,
    command_for,
    service_command,
    service_shell_command,
    switch_user_command,
)


def test_command_uses_target_login_user():
    server = Server(run_as_user="service-user")
    result = command_for(server, "echo hello")
    assert result == "sudo su - service-user -c 'bash -lc '\"'\"'echo hello'\"'\"''"


def test_interactive_shell_switches_with_sudo_su():
    assert switch_user_command(" service-user ") == "sudo su - service-user"


def test_service_command_quotes_path():
    server = Server(run_as_user="apps")
    result = service_command(server, "/opt/my service/control.sh", "restart", "billing api")
    assert "restart" in result
    assert "my service" in result
    assert "billing api" in result


def test_rejects_unknown_action():
    server = Server()
    try:
        service_command(server, "/tmp/x", "remove", "orders")
    except ValueError:
        pass
    else:
        raise AssertionError("ValueError expected")


def test_interactive_service_command_does_not_spawn_another_login_shell():
    result = service_shell_command("/opt/my service/control.sh", "status", "orders api")
    assert result == "'/opt/my service/control.sh' status 'orders api'"
    assert "sudo" not in result


def test_all_target_uses_common_script():
    assert service_shell_command("/opt/manage.sh", "restart", "all") == "/opt/manage.sh restart all"


def test_terminal_control_sequences_are_removed():
    assert clean_terminal_output("\x1b[32mready\x1b[0m\r\n") == "ready\n"
