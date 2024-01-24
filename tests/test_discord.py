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
        num_allied_players=num_allied,
        num_axis_players=num_axis,
    )

    print(e)

    assert False
