from __future__ import annotations

import re

from .ssh import clean_terminal_output


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
_SERVICE_NAME = re.compile(
    r"(?i)^\s*Checking\s+service\s+[\"'](?P<name>[^\"'\r\n]+)[\"']"
)


def parse_service_name(text: str) -> str | None:
    """Read a service name even while its status line is still being printed."""
    match = _SERVICE_NAME.match(clean_terminal_output(text))
    if match is None:
        return None
    name = match.group("name").strip()
    return name if name and len(name) <= 255 and name.isprintable() and name.casefold() != "all" else None


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
