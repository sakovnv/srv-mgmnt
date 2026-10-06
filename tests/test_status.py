from microfleet.status import CommandStream, parse_all_statuses, parse_status, tracked_service_command


TOKEN = "0123456789abcdef0123456789abcdef"


def test_command_stream_handles_split_markers_and_keeps_visible_output():
    command = tracked_service_command("/opt/manage.sh", "status", "orders", TOKEN)
    assert "/opt/manage.sh status orders" in command
    assert "\\036MF:BEGIN:" in command
    stream = CommandStream()
    stream.expect_echo(TOKEN, command, "/opt/manage.sh status orders")
    echoed = "prompt$ " + command + "\r\n"
    visible, results = stream.feed(echoed[:55])
    assert visible == "prompt$ "
    assert results == []
    visible, results = stream.feed(echoed[55:])
    assert visible == "/opt/manage.sh status orders\r\n"
    assert results == []
    first, results = stream.feed("prompt$ \x1eMF:BEGIN:012345")
    assert first == "prompt$ "
    assert results == []
    second, results = stream.feed(
        "6789abcdef0123456789abcdef\x1e\x1b[32morders: running\x1b[0m\r\n"
        "\x1eMF:END:0123456789abcdef0123456789abcdef:0\x1e"
    )
    assert second == "\x1b[32morders: running\x1b[0m\r\n"
    assert len(results) == 1
    assert results[0].token == TOKEN
    assert results[0].exit_code == 0
    assert parse_status(results[0].output) == "running"


def test_echoed_command_wrapped_by_pty_is_hidden():
    command = tracked_service_command("/opt/manage.sh", "status", "orders", TOKEN)
    stream = CommandStream()
    stream.expect_echo(TOKEN, command, "/opt/manage.sh status orders")
    wrapped = command[:90] + "\r\n" + command[90:]
    visible, _ = stream.feed("$ " + wrapped + "\r\n")
    assert visible == "$ /opt/manage.sh status orders\r\n"


def test_no_echo_host_does_not_hide_later_output():
    command = tracked_service_command("/opt/manage.sh", "status", "orders", TOKEN)
    stream = CommandStream()
    stream.expect_echo(TOKEN, command, "/opt/manage.sh status orders")
    visible, results = stream.feed(
        f"\x1eMF:BEGIN:{TOKEN}\x1eorders: running\n"
        f"\x1eMF:END:{TOKEN}:0\x1e"
    )
    assert visible == "orders: running\n"
    assert len(results) == 1
    assert stream.feed("printf is plain output now")[0] == "printf is plain output now"


def test_status_parser_handles_negative_and_colored_output():
    assert parse_status("\x1b[31morders is not running\x1b[0m") == "stopped"
    assert parse_status("orders: inactive (dead)") == "stopped"
    assert parse_status("billing: запущен") == "running"
    assert parse_status("billing: failed") == "failed"


def test_all_statuses_match_specific_service_names():
    output = "billing-api: running\napi: stopped\nunknown: active\n"
    assert parse_all_statuses(output, ["api", "billing-api"]) == {
        "api": "stopped", "billing-api": "running"
    }


def test_actual_checking_service_output_for_one_and_all():
    running = 'Checking service "issuing-service" .....                      running.'
    stopped = 'Checking service "billing-api" .....    stopped.'
    assert parse_status(running) == "running"
    assert parse_status(stopped) == "stopped"
    assert parse_all_statuses(
        f"\x1b[32m{running}\x1b[0m\n\x1b[31m{stopped}\x1b[0m\n",
        ["issuing-service", "billing-api"],
    ) == {"issuing-service": "running", "billing-api": "stopped"}


def test_unknown_service_does_not_set_all_statuses():
    assert parse_all_statuses(
        'Checking service "other-service" ..... running.',
        ["issuing-service", "billing-api"],
    ) == {}
