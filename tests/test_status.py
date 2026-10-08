from microfleet.status import parse_all_statuses, parse_service_name, parse_status


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


def test_service_name_can_be_discovered_before_status_is_complete():
    assert parse_service_name('\x1b[32mChecking service "new-service" .....') == "new-service"
    assert parse_service_name('Checking service "all" ..... running.') is None
    assert parse_service_name('Checking service "unfinished') is None
    assert parse_service_name('Not a status line "new-service"') is None
