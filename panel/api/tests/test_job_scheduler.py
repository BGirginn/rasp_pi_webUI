import os
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("TELEMETRY_DB_PATH", ":memory:")

import pytest

from services.job_scheduler import next_cron_run, parse_cron


def test_cron_parser_supports_ranges_lists_and_steps():
    minutes, hours, days, months, weekdays = parse_cron("*/15 1-3 1,15 * 1-5")
    assert minutes == {0, 15, 30, 45}
    assert hours == {1, 2, 3}
    assert days == {1, 15}
    assert 12 in months
    assert weekdays == {1, 2, 3, 4, 5}


def test_next_cron_run_uses_requested_timezone():
    after = datetime(2026, 7, 13, 20, 59, tzinfo=timezone.utc)
    result = next_cron_run("0 0 * * *", "Europe/Istanbul", after)
    assert result == datetime(2026, 7, 13, 21, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("expression", ["* * *", "61 * * * *", "*/0 * * * *", "* * 0 * *"])
def test_invalid_cron_is_rejected(expression):
    with pytest.raises(ValueError):
        parse_cron(expression)
