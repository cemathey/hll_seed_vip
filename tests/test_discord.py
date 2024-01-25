from pprint import pprint

from hll_seed_vip.utils import make_seed_announcement_embed


def test_make_seed_announcement_embed():
    msg = "BEER is live!"
    current_map = "kharkov"
    time_remaining = "1:25:34"
    num_axis = 5
    num_allied = 8
    e = make_seed_announcement_embed(
        message=msg,
        current_map=current_map,
        time_remaining=time_remaining,
        player_count_message="{num_allied_players} - {num_axis_players}",
        num_allied_players=num_allied,
        num_axis_players=num_axis,
    )

    assert e
    assert e.title == msg
    assert e.footer

    for field, expected in zip(
        e.fields,
        [
            {"inline": True, "name": "Current Map", "value": "kharkov"},
            {"inline": True, "name": "Time Remaining", "value": "1:25:34"},
            {"inline": True, "name": "Players Per Team", "value": "8 - 5"},
        ],
    ):
        assert field == expected

    # assert False
