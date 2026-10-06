from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass

from .ssh import clean_terminal_output, service_shell_command


MARKER = re.compile(r"\x1eMF:(BEGIN|END):([0-9a-f]{32})(?::(-?\d+))?\x1e")


@dataclass(frozen=True, slots=True)
class CommandResult:
    token: str
    output: str
    exit_code: int


@dataclass(frozen=True, slots=True)
class EchoExpectation:
    token: str
    command: str
    display: str


class CommandStream:
    """Remove command delimiters while collecting the corresponding PTY output."""

    def __init__(self) -> None:
        self._pending = ""
        self._active_token: str | None = None
        self._captured: list[str] = []
        self._expected_echoes: deque[EchoExpectation] = deque()
        self._echo_candidate = ""
        self._echo_position = 0

    def expect_echo(self, token: str, command: str, display: str) -> None:
        self._expected_echoes.append(EchoExpectation(token, command, display))

    def feed(self, chunk: str) -> tuple[str, list[CommandResult]]:
        self._pending += self._hide_command_echo(chunk)
        visible: list[str] = []
        results: list[CommandResult] = []
        while True:
            marker = MARKER.search(self._pending)
            if marker:
                content = self._pending[:marker.start()]
                self._emit(content, visible)
                self._pending = self._pending[marker.end():]
                kind, token, code = marker.groups()
                if kind == "BEGIN":
                    # Some hosts disable TTY echo. Retire that expectation when
                    # the command actually starts so it cannot hide later text.
                    if self._expected_echoes and self._expected_echoes[0].token == token:
                        self._expected_echoes.popleft()
                        self._echo_candidate = ""
                        self._echo_position = 0
                    self._active_token = token
                    self._captured = []
                elif self._active_token == token:
                    results.append(CommandResult(token, "".join(self._captured), int(code or 0)))
                    self._active_token = None
                    self._captured = []
                continue
            # A delimiter may be split across SSH packets. Keep only its prefix.
            last_separator = self._pending.rfind("\x1e")
            if last_separator < 0:
                self._emit(self._pending, visible)
                self._pending = ""
            elif len(self._pending) - last_separator > 64:
                self._emit(self._pending[:last_separator + 1], visible)
                self._pending = self._pending[last_separator + 1:]
            else:
                self._emit(self._pending[:last_separator], visible)
                self._pending = self._pending[last_separator:]
            return "".join(visible), results

    def _hide_command_echo(self, chunk: str) -> str:
        visible: list[str] = []
        for char in chunk:
            while True:
                if not self._expected_echoes:
                    visible.append(char)
                    break
                expected = self._expected_echoes[0]
                if char == expected.command[self._echo_position]:
                    self._echo_candidate += char
                    self._echo_position += 1
                    if self._echo_position == len(expected.command):
                        visible.append(expected.display)
                        self._expected_echoes.popleft()
                        self._echo_candidate = ""
                        self._echo_position = 0
                    break
                # PTYs may wrap a long echoed input line at the terminal width.
                if self._echo_position and char in "\r\n":
                    self._echo_candidate += char
                    break
                if self._echo_candidate:
                    visible.append(self._echo_candidate)
                    self._echo_candidate = ""
                    self._echo_position = 0
                    continue
                visible.append(char)
                break
        return "".join(visible)

    def _emit(self, content: str, visible: list[str]) -> None:
        if content:
            visible.append(content)
            if self._active_token is not None:
                self._captured.append(content)


def tracked_service_command(script_path: str, action: str, service_name: str, token: str) -> str:
    """Wrap a service action with non-echoed record-separator markers."""
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("Invalid command token")
    command = service_shell_command(script_path, action, service_name)
    return (
        f"printf '\\036MF:BEGIN:{token}\\036'; "
        f"{command}; __microfleet_rc=$?; "
        f"printf '\\036MF:END:{token}:%s\\036' \"$__microfleet_rc\""
    )


_FAILED = re.compile(r"(?i)(?<!\w)(?:failed|failure|error|crashed|ошибка|ошибкой|сбой|упал)(?!\w)")
_STOPPED = re.compile(
    r"(?i)(?<!\w)(?:not\s+running|not\s+active|inactive|stopped|stop|dead|"
    r"не\s+запущен(?:а|о)?|не\s+работает|остановлен(?:а|о)?|выключен(?:а|о)?)(?!\w)"
)
_RUNNING = re.compile(
    r"(?i)(?<!\w)(?:running|active|started|online|запущен(?:а|о)?|работает|активен(?:а|о)?)(?!\w)"
)
_CHECKING_SERVICE = re.compile(
    r"(?i)^\s*Checking\s+service\s+[\"'](?P<name>[^\"']+)[\"']"
    r"\s*\.{2,}\s*(?P<state>not\s+running|running|stopped|failed)\.?\s*$"
)


def parse_status(text: str) -> str | None:
    """Return the last recognized status in a status command's output."""
    clean = clean_terminal_output(text)
    result = None
    for line in clean.splitlines():
        structured = _CHECKING_SERVICE.match(line)
        if structured:
            state = structured.group("state").lower()
            result = "stopped" if state == "not running" else state
        elif _FAILED.search(line):
            result = "failed"
        elif _STOPPED.search(line):
            result = "stopped"
        elif _RUNNING.search(line):
            result = "running"
    return result


def parse_all_statuses(text: str, service_names: list[str]) -> dict[str, str]:
    """Match one service name and state on each line of a `status all` response."""
    clean = clean_terminal_output(text)
    found: dict[str, str] = {}
    names = sorted(service_names, key=len, reverse=True)
    by_name = {name.casefold(): name for name in service_names}
    for line in clean.splitlines():
        structured = _CHECKING_SERVICE.match(line)
        if structured:
            name = by_name.get(structured.group("name").casefold())
            if name is not None:
                state = structured.group("state").lower()
                found[name] = "stopped" if state == "not running" else state
            continue
        state = parse_status(line)
        if state is None:
            continue
        for name in names:
            if re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w.-])", line, re.I):
                found[name] = state
                break
    return found
