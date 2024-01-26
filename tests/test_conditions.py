from datetime import datetime, timedelta

import pytest
from pydantic import HttpUrl

from hll_seed_vip.models import (
    GameState,
    Player,
    PlayerCountCondition,
    ServerConfig,
    ServerPopulation,
)
from hll_seed_vip.utils import all_met, calc_vip_expiration_timestamp, collect_steam_ids


def make_mock_gamestate(
    time_remaining: str = "1:00:00",
    current_map: str = "SomeMap",
    allied: int = 0,
    axis: int = 0,
) -> GameState:
    return GameState(
        raw_time_remaining=time_remaining,
        current_map=current_map,
        num_allied_players=allied,
        num_axis_players=axis,
    )


def make_mock_player(
    steam_id_64: str, name: str = "No Name", current_playertime_seconds: int = 1
):
    return Player(
        name=name,
        steam_id_64=steam_id_64,
        current_playtime_seconds=current_playertime_seconds,
    )


def make_mock_server_pop(players: dict[str, Player] | None = None):
    if players is None:
        players = {}

    return ServerPopulation(players=players)


def make_mock_config(
    name="No server name",
    url="http://example.com",
    dry_run=True,
    poll_time_seeded=60,
    poll_time_seeding=300,
    min_allies=1,
    min_axis=1,
    max_allies=20,
    max_axis=20,
    minimum_time=timedelta(minutes=5),
    online_when_seeded=False,
    cumulative_vip=False,
    vip_reward=timedelta(hours=24),
    message_reward="seed reward message",
    message_on_connect="on connect message",
    nice_delta=True,
    nice_date=True,
) -> ServerConfig:
    return ServerConfig(
        base_url=str(HttpUrl(url=url)),  # type: ignore
        discord_webhook=None,
        discord_seeding_complete_message="Server is live",
        discord_seeding_in_progress_message="Server has reached {player_count} players",
        discord_player_count_message="{num_allied_players} - {num_axis_players}",
        discord_seeding_player_buckets=[10, 20, 30],
        dry_run=dry_run,
        poll_time_seeded=poll_time_seeded,
        poll_time_seeding=poll_time_seeding,
        min_allies=min_allies,
        min_axis=min_axis,
        max_allies=max_allies,
        max_axis=max_axis,
        minimum_play_time=minimum_time,
        online_when_seeded=online_when_seeded,
        cumulative_vip=cumulative_vip,
        vip_reward=vip_reward,
        message_reward=message_reward,
        message_on_connect=message_on_connect,
        nice_delta=nice_delta,
        nice_date=nice_date,
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
            datetime.fromisoformat("2023-12-20T22:38:13.780570"),
            datetime.fromisoformat("2023-12-20T22:38:13.780570") + timedelta(hours=24),
        ),
        (
            make_mock_config(cumulative_vip=True, vip_reward=timedelta(hours=24)),
            datetime.fromisoformat("2023-12-21T22:38:13.780570"),
            datetime.fromisoformat("2023-12-20T22:38:13.780570"),
            datetime.fromisoformat("2023-12-21T22:38:13.780570") + timedelta(hours=24),
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
        players={s: make_mock_player(steam_id_64=s) for s in steam_ids}
    )
    gamestate = make_mock_gamestate(allied=20, axis=20)
    cum_steam_ids = set()

    cum_steam_ids = collect_steam_ids(
        config=config, players=players, cum_steam_ids=cum_steam_ids
    )

    players = make_mock_server_pop(
        players={s: make_mock_player(steam_id_64=s) for s in steam_ids[:-1]}
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
        players={s: make_mock_player(steam_id_64=s) for s in steam_ids}
    )
    gamestate = make_mock_gamestate(allied=20, axis=20)
    cum_steam_ids = set()

    cum_steam_ids = collect_steam_ids(
        config=config, players=players, cum_steam_ids=cum_steam_ids
    )

    players = make_mock_server_pop(
        players={s: make_mock_player(steam_id_64=s) for s in steam_ids[:-1]}
    )
    cum_steam_ids = collect_steam_ids(
        config=config, players=players, cum_steam_ids=cum_steam_ids
    )

    assert cum_steam_ids == set(steam_ids[:-1])
