from datetime import datetime, timedelta

import pytest
from pydantic import HttpUrl

from hll_seed_vip.models import (
    Faction,
    GameState,
    LayerType,
    MapType,
    Player,
    PlayerCountCondition,
    ServerConfig,
    ServerPopulation,
    VipPlayer,
)
from hll_seed_vip.utils import (
    all_met,
    calc_vip_expiration_timestamp,
    collect_steam_ids,
    filter_indefinite_vip_steam_ids,
    filter_online_players,
    has_indefinite_vip,
)


def make_mock_map(
    id: str = "mortain",
    name: str = "MORTAIN",
    tag: str = "MOR",
    pretty_name: str = "Mortain",
    shortname: str = "MOR",
    allies=Faction.US,
    axis=Faction.GER,
) -> MapType:
    return {
        "id": id,
        "name": name,
        "tag": tag,
        "pretty_name": pretty_name,
        "shortname": shortname,
        "allies": allies,
        "axis": axis,
    }


def make_mock_layer(
    id: str = "mortain_offensiveger_overcast",
    map: MapType = make_mock_map(),
    game_mode="warfare",
    attackers="axis",
    environment="overcast",
    pretty_name="Mortain Off. GER (Overcast)",
    image_name="mortain-overcast.webp",
    image_url: str | None = None,
) -> LayerType:
    return {
        "id": id,
        "map": map,
        "game_mode": game_mode,
        "attackers": attackers,
        "environment": environment,
        "pretty_name": pretty_name,
        "image_name": image_name,
        "image_url": image_url,
    }


def make_mock_gamestate(
    current_map: LayerType = make_mock_layer(),
    allied: int = 0,
    axis: int = 0,
    allied_score: int = 2,
    axis_score: int = 3,
    raw_time_remaining: str = "",
    time_remaining: float = 360,
    next_map: LayerType = make_mock_layer(),
) -> GameState:
    return GameState(
        raw_time_remaining=raw_time_remaining,
        current_map=current_map,
        num_allied_players=allied,
        num_axis_players=axis,
        allied_score=allied_score,
        axis_score=axis_score,
        time_remaining=time_remaining,
        next_map=next_map,
    )


def make_mock_player(
    player_id: str, name: str = "No Name", current_playertime_seconds: int = 1
) -> Player:
    return Player(
        name=name,
        player_id=player_id,
        current_playtime_seconds=current_playertime_seconds,
    )


def make_mock_vip_player(
    player_id: str, expiration_date: datetime | None = None
) -> VipPlayer:
    return VipPlayer(
        player=make_mock_player(player_id=player_id),
        expiration_date=expiration_date,
    )


def make_mock_get_vips_dict(
    data: dict[str, datetime] | None = None
) -> dict[str, VipPlayer]:
    return {
        player_id: make_mock_vip_player(
            player_id=player_id, expiration_date=expiration_date
        )
        for player_id, expiration_date in (data or {}).items()
    }


def make_mock_server_pop(players: dict[str, Player] | None = None) -> ServerPopulation:
    if players is None:
        players = {}

    return ServerPopulation(players=players)


def make_mock_config(
    lanugage=None,
    url="http://example.com",
    dry_run=True,
    buffer=timedelta(minutes=5),
    poll_time_seeded=60,
    poll_time_seeding=300,
    min_allies=1,
    min_axis=1,
    max_allies=20,
    max_axis=20,
    minimum_time=timedelta(minutes=5),
    player_name_not_current_vip="{player_name} - HLL Seed VIP",
    online_when_seeded=False,
    cumulative_vip=False,
    forward=True,
    vip_reward=timedelta(hours=24),
    message_reward="seed reward message",
    message_non_vip="non vip message",
    nice_time_delta=True,
    nice_expiration_date=True,
) -> ServerConfig:
    return ServerConfig(
        language=lanugage,
        base_url=str(HttpUrl(url=url)),  # type: ignore
        discord_webhooks=[],
        discord_seeding_complete_message="Server is live",
        discord_seeding_in_progress_message="Server has reached {player_count} players",
        discord_player_count_message="{num_allied_players} - {num_axis_players}",
        discord_seeding_player_buckets=[10, 20, 30],
        dry_run=dry_run,
        buffer=buffer,
        poll_time_seeded=poll_time_seeded,
        poll_time_seeding=poll_time_seeding,
        min_allies=min_allies,
        min_axis=min_axis,
        max_allies=max_allies,
        max_axis=max_axis,
        minimum_play_time=minimum_time,
        player_name_not_current_vip=player_name_not_current_vip,
        online_when_seeded=online_when_seeded,
        cumulative_vip=cumulative_vip,
        forward=forward,
        vip_reward=vip_reward,
        message_reward=message_reward,
        message_non_vip=message_non_vip,
        nice_time_delta=nice_time_delta,
        nice_expiration_date=nice_expiration_date,
    )


@pytest.mark.parametrize(
    "conditions, expected",
    [
        (
            [
                PlayerCountCondition(
                    faction="axis", min_players=3, max_players=10, current_players=5
                ),
                PlayerCountCondition(
                    faction="allies", min_players=3, max_players=10, current_players=5
                ),
            ],
            True,
        ),
        (
            [
                PlayerCountCondition(
                    faction="axis", min_players=3, max_players=10, current_players=5
                ),
                PlayerCountCondition(
                    faction="allies", min_players=3, max_players=10, current_players=11
                ),
            ],
            False,
        ),
    ],
)
def test_player_count_conditions(conditions, expected):
    assert all_met(conditions) == expected


@pytest.mark.parametrize(
    "config, expiration, from_time, expected",
    [
        (
            make_mock_config(cumulative_vip=False, vip_reward=timedelta(hours=24)),
            None,
            datetime.fromisoformat("2023-12-20T22:38:13.780570:00Z"),
            datetime.fromisoformat("2023-12-20T22:38:13.780570:00Z")
            + timedelta(hours=24),
        ),
        (
            make_mock_config(cumulative_vip=True, vip_reward=timedelta(hours=24)),
            datetime.fromisoformat("2023-12-21T22:38:13.780570:00Z"),
            datetime.fromisoformat("2023-12-20T22:38:13.780570:00Z"),
            datetime.fromisoformat("2023-12-21T22:38:13.780570:00Z")
            + timedelta(hours=24),
        ),
    ],
)
def test_cumulative_expirations(
    config: ServerConfig,
    expiration: datetime | None,
    from_time: datetime,
    expected: datetime,
):
    assert (
        calc_vip_expiration_timestamp(
            config=config, expiration=expiration, from_time=from_time
        )
        == expected
    )


def test_has_indefinite_vip():
    vip_player = make_mock_vip_player(player_id="1")
    assert not has_indefinite_vip(vip_player)

    vip_player = make_mock_vip_player(
        # this expiration date is in the past
        player_id="1",
        expiration_date=datetime.fromisoformat("2024-01-01T00:00:00Z"),
    )
    assert not has_indefinite_vip(vip_player)

    vip_player = make_mock_vip_player(
        player_id="1", expiration_date=datetime.fromisoformat("3000-01-01T00:00:00Z")
    )
    assert has_indefinite_vip(vip_player)

    vip_player = make_mock_vip_player(
        player_id="1", expiration_date=datetime.fromisoformat("3333-01-01T00:00:00Z")
    )
    assert has_indefinite_vip(vip_player)


def test_filter_indefinite_vip_steam_ids():
    vips = make_mock_get_vips_dict(
        data={
            # this expiration date is in the past
            "1": datetime.fromisoformat("2024-01-01T00:00:00Z"),
            "2": datetime.fromisoformat("3000-01-01T00:00:00Z"),
            "3": datetime.fromisoformat("3333-01-01T00:00:00Z"),
        }
    )

    assert set(filter_indefinite_vip_steam_ids(vips)) == {"2", "3"}

    vips = {}
    assert set(filter_indefinite_vip_steam_ids(vips)) == set()


def test_filter_online_players():
    vips = make_mock_get_vips_dict(
        data={
            "1": datetime.fromisoformat("2024-01-01T00:00:00Z"),
            "2": datetime.fromisoformat("3000-01-01T00:00:00Z"),
            "3": datetime.fromisoformat("3333-01-01T00:00:00Z"),
        }
    )

    players = make_mock_server_pop(
        players={s: make_mock_player(player_id=s) for s in ["0", "1", "2", "3", "4"]}
    )
    assert set(filter_online_players(vips, players)) == {"1", "2", "3"}

    players = make_mock_server_pop(
        players={s: make_mock_player(player_id=s) for s in ["1", "3"]}
    )
    assert set(filter_online_players(vips, players)) == {"1", "3"}

    players = make_mock_server_pop(
        players={s: make_mock_player(player_id=s) for s in ["1", "4"]}
    )
    assert set(filter_online_players(vips, players)) == {"1"}

    players = make_mock_server_pop(players={})
    assert set(filter_online_players(vips, players)) == set()


def test_collect_steam_ids():
    config = make_mock_config(
        min_allies=5,
        max_allies=25,
        min_axis=5,
        max_axis=25,
        minimum_time=timedelta(seconds=1),
        online_when_seeded=False,
    )

    steam_ids = ["1", "2", "3"]

    players = make_mock_server_pop(
        players={s: make_mock_player(player_id=s) for s in steam_ids}
    )
    gamestate = make_mock_gamestate(allied=20, axis=20)
    cum_steam_ids = set()

    cum_steam_ids = collect_steam_ids(
        config=config, players=players, cum_steam_ids=cum_steam_ids
    )

    players = make_mock_server_pop(
        players={s: make_mock_player(player_id=s) for s in steam_ids[:-1]}
    )
    cum_steam_ids = collect_steam_ids(
        config=config, players=players, cum_steam_ids=cum_steam_ids
    )

    assert cum_steam_ids == set(steam_ids)


def test_collect_steam_ids_online_only():
    config = make_mock_config(
        min_allies=5,
        max_allies=25,
        min_axis=5,
        max_axis=25,
        minimum_time=timedelta(seconds=1),
        online_when_seeded=True,
    )

    steam_ids = ["1", "2", "3"]

    players = make_mock_server_pop(
        players={s: make_mock_player(player_id=s) for s in steam_ids}
    )
    gamestate = make_mock_gamestate(allied=20, axis=20)
    cum_steam_ids = set()

    cum_steam_ids = collect_steam_ids(
        config=config, players=players, cum_steam_ids=cum_steam_ids
    )

    players = make_mock_server_pop(
        players={s: make_mock_player(player_id=s) for s in steam_ids[:-1]}
    )
    cum_steam_ids = collect_steam_ids(
        config=config, players=players, cum_steam_ids=cum_steam_ids
    )

    assert cum_steam_ids == set(steam_ids[:-1])
