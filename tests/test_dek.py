import pytest

from microfleet.dek import DekPromptResponder, SecretRedactor, split_dek_password


def test_dek_is_split_with_extra_character_in_first_half():
    assert split_dek_password("1234567") == ("1234", "567")
    with pytest.raises(ValueError):
        split_dek_password("x")
    with pytest.raises(ValueError):
        split_dek_password("ab\ncd")


def test_prompts_can_be_split_across_ssh_packets_and_repeat():
    responder = DekPromptResponder("abcdefgh")
    assert responder.feed("Enter first password comp") == []
    assert responder.feed("onent:") == ["abcd"]
    assert responder.feed("\x1b[33mEnter second password component:\x1b[0m") == ["efgh"]
    assert responder.pairs_completed == 1
    assert responder.feed("Enter first password component:") == ["abcd"]


def test_dek_echo_is_redacted_across_packets():
    redactor = SecretRedactor("abcdefgh")
    visible = redactor.feed("Enter first password component:ab")
    visible += redactor.feed("cd\r\nEnter second password component:ef")
    visible += redactor.feed("gh\r\nChecking service \"orders\" ..... running.\n")
    visible += redactor.finish()
    assert "abcd" not in visible
    assert "efgh" not in visible
    assert "[DEK скрыт]" in visible
    assert "Checking service" in visible
