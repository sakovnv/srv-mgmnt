from __future__ import annotations

import queue
import re
import shlex
import socket
import threading
import time
import codecs
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from .models import Server


ANSI_ESCAPE = re.compile(
    r"(?:\x1B\][^\x07]*(?:\x07|\x1B\\))|"
    r"(?:\x1B[@-_][0-?]*[ -/]*[@-~])"
)


def clean_terminal_output(text: str) -> str:
    """Convert common terminal control sequences to readable plain text."""
    text = ANSI_ESCAPE.sub("", text)
    return text.replace("\r\n", "\n").replace("\r", "")


def switch_user_command(user: str) -> str:
    """Enter the configured user's login shell through sudo and su."""
    return f"sudo su - {shlex.quote(user.strip())}"


def command_for(server: Server, command: str) -> str:
    """Build a one-shot command for non-interactive SSH usage."""
    login_command = f"bash -lc {shlex.quote(command)}"
    if not server.run_as_user.strip():
        return login_command
    return f"{switch_user_command(server.run_as_user)} -c {shlex.quote(login_command)}"


def service_shell_command(script_path: str, action: str, service_name: str) -> str:
    """Build a common-script command for an interactive login shell."""
    if action not in {"start", "stop", "restart", "status"}:
        raise ValueError(f"Unsupported service action: {action}")
    if not script_path.strip() or not service_name.strip():
        raise ValueError("Script path and service name are required")
    return f"{shlex.quote(script_path.strip())} {action} {shlex.quote(service_name.strip())}"


def service_command(server: Server, script_path: str, action: str, service_name: str) -> str:
    """Build a complete one-shot service command (kept for CLI integrations)."""
    return command_for(server, service_shell_command(script_path, action, service_name))


@dataclass(slots=True)
class ConnectionSecret:
    password: str = ""


class SSHSession(QThread):
    """Persistent interactive SSH terminal for one server."""

    output = Signal(int, str)
    state = Signal(int, str)
    session_finished = Signal(int, str)

    def __init__(
        self,
        server: Server,
        secret: ConnectionSecret | None = None,
        timeout: int = 8,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.server = server
        self.secret = secret or ConnectionSecret()
        self.timeout = timeout
        self._outgoing: queue.Queue[tuple[str, object]] = queue.Queue()
        self._stop_event = threading.Event()
        self._client = None
        self._channel = None

    def send_command(self, command: str) -> bool:
        if self._stop_event.is_set():
            return False
        self._outgoing.put(("command", command.rstrip("\r\n") + "\n"))
        return True

    def send_interrupt(self) -> bool:
        if self._stop_event.is_set():
            return False
        self._outgoing.put(("raw", b"\x03"))
        return True

    def resize_terminal(self, width: int, height: int) -> None:
        if self.isRunning():
            self._outgoing.put(("resize", (max(40, width), max(10, height))))

    def stop(self) -> None:
        self._stop_event.set()
        self._outgoing.put(("stop", None))
        if self._channel is not None:
            self._channel.close()
        if self._client is not None:
            self._client.close()

    def run(self) -> None:
        server_id = int(self.server.id or 0)
        client = None
        channel = None
        reason = "SSH-сессия закрыта"
        try:
            import paramiko

            self.state.emit(server_id, "connecting")
            client = paramiko.SSHClient()
            self._client = client
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            connect_args: dict[str, object] = {
                "hostname": self.server.host,
                "port": self.server.port,
                "username": self.server.ssh_user,
                "timeout": self.timeout,
                "banner_timeout": self.timeout,
                "auth_timeout": self.timeout,
            }
            if self.server.auth_type == "password":
                connect_args.update(
                    password=self.secret.password,
                    look_for_keys=False,
                    allow_agent=False,
                )
            elif self.server.key_path:
                connect_args["key_filename"] = self.server.key_path
            client.connect(**connect_args)
            channel = client.invoke_shell(term="xterm-256color", width=180, height=40)
            self._channel = channel
            channel.settimeout(0.0)
            self.state.emit(server_id, "online")

            if self.server.run_as_user.strip():
                channel.sendall(
                    f"{switch_user_command(self.server.run_as_user)}\n".encode("utf-8")
                )

            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            while not self._stop_event.is_set() and not channel.closed:
                self._flush_outgoing(channel)
                received = False
                while channel.recv_ready():
                    data = channel.recv(65535)
                    if not data:
                        reason = "Удалённая сторона закрыла SSH-сессию"
                        self._stop_event.set()
                        break
                    text = decoder.decode(data)
                    if text:
                        self.output.emit(server_id, text)
                    received = True
                if not received:
                    time.sleep(0.035)
            remainder = decoder.decode(b"", final=True)
            if remainder:
                self.output.emit(server_id, remainder)
        except (socket.timeout, TimeoutError):
            reason = "Истекло время ожидания SSH"
        except Exception as exc:
            reason = str(exc)
        finally:
            self.state.emit(server_id, "offline")
            if channel is not None:
                channel.close()
            if client is not None:
                client.close()
            self._channel = None
            self._client = None
            self.session_finished.emit(server_id, reason)

    def _flush_outgoing(self, channel: object) -> None:
        while True:
            try:
                kind, payload = self._outgoing.get_nowait()
            except queue.Empty:
                return
            if kind == "stop":
                return
            if kind == "resize":
                width, height = payload
                channel.resize_pty(width=width, height=height)
            elif kind == "command":
                channel.sendall(str(payload).encode("utf-8"))
            elif kind == "raw":
                channel.sendall(payload)
