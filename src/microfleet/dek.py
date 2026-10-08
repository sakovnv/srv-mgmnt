"""Prompt detection and output redaction for interactive DEK entry."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ssh import clean_terminal_output


FIRST_PROMPT = "Enter first password component:"
SECOND_PROMPT = "Enter second password component:"


def split_dek_password(password: str) -> tuple[str, str]:
    """Put the extra character, if any, in the first component."""
    if len(password) < 2 or any(char in password for char in "\r\n\x00"):
        raise ValueError("DEK-пароль должен содержать минимум два символа без перевода строки")
    middle = (len(password) + 1) // 2
    return password[:middle], password[middle:]


class DekPromptResponder:
    def __init__(self, password: str) -> None:
        self.components = split_dek_password(password)
        self._expected = 0
        self._buffer = ""
        self.pairs_completed = 0

    def feed(self, text: str) -> list[str]:
        """Return only components whose complete prompts arrived, even across packets."""
        self._buffer = clean_terminal_output(self._buffer + text)
        answers: list[str] = []
        prompts = (FIRST_PROMPT, SECOND_PROMPT)
        while True:
            prompt = prompts[self._expected]
            position = self._buffer.find(prompt)
            if position < 0:
                self._buffer = self._buffer[-(max(map(len, prompts)) - 1):]
                return answers
            self._buffer = self._buffer[position + len(prompt):]
            answers.append(self.components[self._expected])
            self._expected = 1 - self._expected
            if self._expected == 0:
                self.pairs_completed += 1


class SecretRedactor:
    """Hide either DEK component even when terminal packets split its echo."""

    def __init__(self, password: str) -> None:
        self._patterns = sorted(set(split_dek_password(password)), key=len, reverse=True)
        self._tail = ""
        self._longest = max(map(len, self._patterns))

    def feed(self, text: str) -> str:
        combined = self._tail + text
        end = max(0, len(combined) - self._longest + 1)
        for pattern in self._patterns:
            position = combined.find(pattern)
            while position >= 0:
                if position < end < position + len(pattern):
                    end = position
                position = combined.find(pattern, position + 1)
        visible, self._tail = combined[:end], combined[end:]
        return self._replace(visible)

    def finish(self) -> str:
        visible, self._tail = self._tail, ""
        visible = self._replace(visible)
        for pattern in self._patterns:
            for length in range(len(pattern) - 1, 0, -1):
                if visible.endswith(pattern[:length]):
                    return visible[:-length] + "[DEK скрыт]"
        return visible

    def _replace(self, text: str) -> str:
        for pattern in self._patterns:
            text = text.replace(pattern, "[DEK скрыт]")
        return text


@dataclass
class DekAutomation:
    password: str
    expected_names: set[str]
    complete_on_any_status: bool = field(init=False)
    saw_status_line: bool = False
    responder: DekPromptResponder = field(init=False)
    redactor: SecretRedactor = field(init=False)

    def __post_init__(self) -> None:
        self.complete_on_any_status = not self.expected_names
        self.responder = DekPromptResponder(self.password)
        self.redactor = SecretRedactor(self.password)
