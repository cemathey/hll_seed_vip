import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import yaml
from loguru import logger

from hll_seed_vip.models import (
    BaseCondition,
    ConfigRequirementsType,
    ConfigType,
    ConfigVipRewardType,
    GameState,
    PlayerCountCondition,
    PlayTimeCondition,
    ServerConfig,
    ServerPopulation,
)


def load_config(path: Path) -> ServerConfig:
    with open(path) as fp:
        raw_config: ConfigType = yaml.safe_load(fp)
    logger.debug(f"{raw_config=}")

    requirements = ConfigRequirementsType(**raw_config["requirements"])
    vip_reward = ConfigVipRewardType(**raw_config["vip_reward"])

    return ServerConfig(
        base_url=raw_config["base_url"],
        dry_run=raw_config["dry_run"],
        poll_time_seeding=raw_config["poll_time_seeding"],
        poll_time_seeded=raw_config["poll_time_seeded"],
        min_allies=requirements["min_allies"],
        max_allies=requirements["max_allies"],
        min_axis=requirements["min_axis"],
        max_axis=requirements["max_axis"],
        minimum_play_time=timedelta(**requirements["minimum_play_time"]),
        online_when_seeded=requirements["online_when_seeded"],
        cumulative_vip=vip_reward["cumulative"],
        vip_reward=timedelta(**vip_reward["timeframe"]),
    )


def all_met(conditions: Iterable[BaseCondition]):
    return all(c.is_met() for c in conditions)


def check_population_conditions(config: ServerConfig, gamestate: GameState):
    """Return if the current player count is within min/max players for seeding"""
    player_count_conditions = [
        PlayerCountCondition(
            faction="allies",
            min_players=config.min_allies,
            max_players=config.max_allies,
            current_players=gamestate.num_allied_players,
        ),
        PlayerCountCondition(
            faction="axis",
            min_players=config.min_axis,
            max_players=config.max_axis,
            current_players=gamestate.num_axis_players,
        ),
    ]

    logger.debug(f"{gamestate=}")
    logger.debug(f"{player_count_conditions=}")

    if not all_met(player_count_conditions):
        logger.debug(
            f"{player_count_conditions[0].is_met()=} {player_count_conditions[1].is_met()=} breaking"
        )
        return False

    return True


def check_player_conditions(
    config: ServerConfig, server_pop: ServerPopulation
) -> set[str]:
    """Return a set of steam IDs that meet seeding criteria"""
    return set(
        player.steam_id_64
        for player in server_pop.players.values()
        if PlayTimeCondition(
            min_time_secs=int(config.minimum_play_time.total_seconds()),
            current_time_secs=player.current_playtime_seconds,
        ).is_met()
    )


def is_seeded(config: ServerConfig, gamestate: GameState) -> bool:
    """Return if the server has enough players to be out of seeding"""
    return (
        gamestate.num_allied_players >= config.max_allies
        and gamestate.num_axis_players >= config.max_axis
    )


def calc_vip_expiration_timestamp(
    config: ServerConfig, expiration: datetime | None, from_time: datetime
) -> datetime:
    """Return the players new expiration date accounting for reward/existing timestamps"""
    if expiration is None:
        timestamp = from_time + config.vip_reward
        return timestamp

    if config.cumulative_vip:
        return expiration + config.vip_reward
    else:
        # Don't step on the old expiration if it's longer than the new one
        timestamp = from_time + config.vip_reward
        if timestamp < expiration:
            return expiration
        else:
            return timestamp


def collect_steam_ids(
    config: ServerConfig,
    players: ServerPopulation,
    gamestate: GameState,
    cum_steam_ids: set[str] | None = None,
) -> tuple[set[str], int]:
    logger.debug(
        f"collect_steam_ids {config=} {players=} {gamestate=} {cum_steam_ids=}"
    )

    if cum_steam_ids is None:
        cum_steam_ids = set()

    if not check_population_conditions(
        config=config,
        gamestate=gamestate,
    ):
        logger.debug(f"population conditions not met")
        raise ValueError()
    else:
        player_conditions_steam_ids = check_player_conditions(
            config=config, server_pop=players
        )

        if config.online_when_seeded:
            cum_steam_ids = set(player_conditions_steam_ids)
        else:
            cum_steam_ids |= player_conditions_steam_ids

    return cum_steam_ids, config.poll_time_seeding
