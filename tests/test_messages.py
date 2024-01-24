from datetime import datetime, timedelta, timezone

import pytest

from hll_seed_vip.utils import format_player_message


@pytest.mark.parametrize(
    "msg, vip_reward, vip_expiration, nice_delta, nice_date, expected",
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
            "Thank you for helping us seed, your VIP expires 10 months from now",
        ),
    ],
)
def test_format_player_message(
    msg, vip_reward, vip_expiration, nice_delta, nice_date, expected
):
    assert (
        format_player_message(
            message=msg,
            vip_reward=vip_reward,
            vip_expiration=vip_expiration,
            nice_delta=nice_delta,
            nice_date=nice_date,
        )
        == expected
    )
