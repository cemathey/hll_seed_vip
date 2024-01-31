from datetime import date, datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from hll_seed_vip.utils import format_player_message, format_vip_reward_name

with freeze_time("2024-01-31"):
    NOW = datetime.now()
    NOW_UTC = datetime.now(tz=timezone.utc)
    NOW_UTC_PLUS_01_00 = datetime.now(tz=timezone(offset=timedelta(hours=1)))
    TODAY = date.today()
    TOMORROW = TODAY + timedelta(days=1)
    YESTERDAY = TODAY - timedelta(days=1)


@pytest.mark.parametrize(
    "msg, vip_reward, vip_expiration, nice_time_delta, nice_expiration_date, expected",
    [
        ("seed", timedelta(hours=12), datetime.utcnow(), False, False, "seed"),
        (
            "Thank you for helping us seed, you've been granted {vip_reward} of VIP",
            timedelta(hours=12),
            datetime.utcnow(),
            True,
            True,
            "Thank you for helping us seed, you've been granted 12 hours of VIP",
        ),
        (
            "Thank you for helping us seed, your VIP expires {vip_expiration}",
            timedelta(hours=12),
            datetime(year=2024, month=12, day=1, hour=13, tzinfo=timezone.utc),
            True,
            True,
            "Thank you for helping us seed, your VIP expires 9 months from now",
        ),
        (
            "Thank you for helping us seed, you earned {vip_reward} of VIP and your VIP expires {vip_expiration}",
            timedelta(hours=12),
            datetime(year=2024, month=12, day=1, hour=13, tzinfo=timezone.utc),
            True,
            True,
            "Thank you for helping us seed, you earned 12 hours of VIP and your VIP expires 9 months from now",
        ),
        (
            "Thank you for helping us seed!",
            timedelta(hours=12),
            datetime(year=2024, month=12, day=1, hour=13, tzinfo=timezone.utc),
            True,
            True,
            "Thank you for helping us seed!",
        ),
    ],
)
def test_format_player_message(
    msg: str,
    vip_reward: timedelta,
    vip_expiration: datetime,
    nice_time_delta: bool,
    nice_expiration_date: bool,
    expected: str,
):
    assert (
        format_player_message(
            message=msg,
            vip_reward=vip_reward,
            vip_expiration=vip_expiration,
            nice_time_delta=nice_time_delta,
            nice_expiration_date=nice_expiration_date,
        )
        == expected
    )


@pytest.mark.parametrize(
    "name, format_str, expected",
    [("some_dude", "{player_name} - HLL Seed VIP", "some_dude - HLL Seed VIP")],
)
def test_format_vip_reward_name(name, format_str, expected):
    assert format_vip_reward_name(player_name=name, format_str=format_str) == expected
