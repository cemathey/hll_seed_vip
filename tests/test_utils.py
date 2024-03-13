import pytest

from hll_seed_vip.utils import get_next_player_bucket


@pytest.mark.parametrize(
    "buckets, total_players, expected",
    [
        ([10, 20, 30, 40], 37, 30),
        ([10, 20, 30, 40], 3, None),
        ([10, 20, 30, 40], 11, 10),
        ([10, 20, 30, 40], 20, 20),
        ([10, 20, 30, 40], 21, 20),
        ([10, 20, 30, 40], 30, 30),
        ([10, 20, 30], 34, 30),
        ([], 37, None),
    ],
)
def test_get_next_player_bucket(buckets, total_players, expected):
    assert (
        get_next_player_bucket(
            player_buckets=buckets,
            total_players=total_players,
        )
        == expected
    )
