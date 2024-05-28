from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

import discord_webhook as discord
import httpx
import yaml
from humanize import naturaldelta, naturaltime
from loguru import logger

from hll_seed_vip.constants import INDEFINITE_VIP_DATE
from hll_seed_vip.io import add_vip, message_player
from hll_seed_vip.models import (
    BaseCondition,
    ConfigDiscordType,
    ConfigPlayerMessageType,
    ConfigRequirementsType,
    ConfigType,
    ConfigVipRewardType,
    GameState,
    PlayerCountCondition,
    PlayTimeCondition,
    ServerConfig,
    ServerPopulation,
    VipPlayer,
)


def has_indefinite_vip(player: VipPlayer | None) -> bool:
    """Return true if the player has an indefinite VIP status"""
    if player is None or player.expiration_date is None:
        return False
    expiration = player.expiration_date
    return expiration >= INDEFINITE_VIP_DATE


def filter_indefinite_vip_steam_ids(current_vips: dict[str, VipPlayer]) -> set[str]:
    """Return a set of steam IDs that have indefinite VIP status"""
    return {
        player_id
        for player_id, vip_player in current_vips.items()
        if has_indefinite_vip(vip_player)
    }


def filter_online_players(
    vips: dict[str, VipPlayer], players: ServerPopulation
) -> dict[str, VipPlayer]:
    """Return a dictionary of players that are online"""
    return {
        player_id: vip_player
        for player_id, vip_player in vips.items()
        if player_id in players.players
    }


def load_config(path: Path) -> ServerConfig:
    with open(path) as fp:
        raw_config: ConfigType = yaml.safe_load(fp)
    logger.debug(f"{raw_config=}")

    requirements = ConfigRequirementsType(**raw_config["requirements"])
    vip_reward = ConfigVipRewardType(**raw_config["vip_reward"])
    discord = ConfigDiscordType(**raw_config["discord"])
    player_messages = ConfigPlayerMessageType(**raw_config["player_messages"])

    return ServerConfig(
        language=raw_config.get("language"),
        base_url=raw_config["base_url"],
        discord_webhooks=discord["webhooks"],
        discord_seeding_complete_message=discord["seeding_complete_message"],
        discord_seeding_in_progress_message=discord["seeding_in_progress_message"],
        discord_player_count_message=discord["player_count_message"],
        discord_seeding_player_buckets=discord["seeding_player_buckets"],
        dry_run=raw_config["dry_run"],
        buffer=timedelta(**requirements["buffer"]),
        poll_time_seeding=raw_config["poll_time_seeding"],
        poll_time_seeded=raw_config["poll_time_seeded"],
        min_allies=requirements["min_allies"],
        max_allies=requirements["max_allies"],
        min_axis=requirements["min_axis"],
        max_axis=requirements["max_axis"],
        minimum_play_time=timedelta(**requirements["minimum_play_time"]),
        online_when_seeded=requirements["online_when_seeded"],
        forward=vip_reward["forward"],
        player_name_not_current_vip=vip_reward["player_name_not_current_vip"],
        cumulative_vip=vip_reward["cumulative"],
        vip_reward=timedelta(**vip_reward["timeframe"]),
        message_reward=player_messages["reward"],
        message_non_vip=player_messages["non_vip"],
        nice_time_delta=vip_reward["nice_time_delta"],
        nice_expiration_date=vip_reward["nice_expiration_date"],
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

    logger.debug(
        f"{player_count_conditions[0]}={player_count_conditions[0].is_met()} {player_count_conditions[1]}={player_count_conditions[1].is_met()} breaking",
    )
    if not all_met(player_count_conditions):
        return False

    return True


def check_player_conditions(
    config: ServerConfig, server_pop: ServerPopulation
) -> set[str]:
    """Return a set of steam IDs that meet seeding criteria"""
    return set(
        player.player_id
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
    cum_steam_ids: set[str],
) -> set[str]:
    player_conditions_steam_ids = check_player_conditions(
        config=config, server_pop=players
    )

    if config.online_when_seeded:
        cum_steam_ids = set(player_conditions_steam_ids)
    else:
        cum_steam_ids |= player_conditions_steam_ids

    return cum_steam_ids


def format_player_message(
    message: str,
    vip_reward: timedelta,
    vip_expiration: datetime,
    nice_time_delta: bool = True,
    nice_expiration_date: bool = True,
) -> str:
    if nice_time_delta:
        delta = naturaldelta(vip_reward)
    else:
        delta = vip_reward

    if nice_expiration_date:
        date = naturaltime(vip_expiration)
    else:
        date = vip_expiration.isoformat()

    return message.format(vip_reward=delta, vip_expiration=date)


def make_seed_announcement_embed(
    message: str | None,
    current_map: str,
    time_remaining: str,
    player_count_message: str,
    num_axis_players: int,
    num_allied_players: int,
) -> discord.DiscordEmbed | None:
    if not message:
        return

    logger.debug(f"{num_allied_players=} {num_axis_players=}")

    embed = discord.DiscordEmbed(title=message)
    embed.set_timestamp(datetime.now(tz=timezone.utc))
    embed.add_embed_field(name="Current Map", value=current_map)
    embed.add_embed_field(name="Time Remaining", value=time_remaining)
    embed.add_embed_field(
        name="Players Per Team",
        value=player_count_message.format(
            num_allied_players=num_allied_players, num_axis_players=num_axis_players
        ),
    )

    return embed


def format_vip_reward_name(player_name: str, format_str):
    return format_str.format(player_name=player_name)


def should_announce_seeding_progress(
    player_buckets: list[int],
    total_players: int,
    prev_announced_bucket: int,
    next_player_bucket: int,
    last_bucket_announced: bool,
) -> bool:
    return (
        len(player_buckets) > 0
        and total_players > prev_announced_bucket
        and total_players >= next_player_bucket
        and not last_bucket_announced
    )


async def message_players(
    client: httpx.AsyncClient,
    config: ServerConfig,
    message: str,
    steam_ids: Iterable[str],
    expiration_timestamps: defaultdict[str, datetime] | None,
):
    for steam_id in steam_ids:
        if expiration_timestamps:
            formatted_message = format_player_message(
                message=message,
                vip_reward=config.vip_reward,
                vip_expiration=expiration_timestamps[steam_id],
                nice_time_delta=config.nice_time_delta,
                nice_expiration_date=config.nice_expiration_date,
            )
        else:
            formatted_message = message

        if config.dry_run:
            logger.info(f"{config.dry_run=} messaging {steam_id}: {formatted_message}")
        else:
            await message_player(
                client=client,
                server_url=config.base_url,
                player_id=steam_id,
                message=formatted_message,
            )


async def reward_players(
    client: httpx.AsyncClient,
    config: ServerConfig,
    to_add_vip_steam_ids: set[str],
    current_vips: dict[str, VipPlayer],
    players_lookup: dict[str, str],
    expiration_timestamps: defaultdict[str, datetime],
):
    # TODO: make concurrent
    logger.info(f"Rewarding players with VIP {config.dry_run=}")
    logger.info(f"Total={len(to_add_vip_steam_ids)} {to_add_vip_steam_ids=}")
    logger.debug(f"Total={len(current_vips)=} {current_vips=}")
    for player_id in to_add_vip_steam_ids:
        player = current_vips.get(player_id)
        expiration_date = expiration_timestamps[player_id]

        if has_indefinite_vip(player):
            logger.info(
                f"{config.dry_run=} Skipping! pre-existing indefinite VIP for {player_id=} {player=} {vip_name=} {expiration_date=}"
            )
            continue

        vip_name = (
            player.player.name
            if player
            else format_vip_reward_name(
                players_lookup.get(player_id, "No player name found"),
                format_str=config.player_name_not_current_vip,
            )
        )

        if not config.dry_run:
            logger.info(
                f"{config.dry_run=} adding VIP to {player_id=} {player=} {vip_name=} {expiration_date=}",
            )
            await add_vip(
                client=client,
                server_url=config.base_url,
                player_id=player_id,
                player_name=vip_name,
                expiration_timestamp=expiration_date,
                forward=config.forward,
            )

        else:
            logger.info(
                f"{config.dry_run=} adding VIP to {player_id=} {player=} {vip_name=} {expiration_date=}",
            )


def get_next_player_bucket(
    player_buckets: Sequence[int],
    total_players: int,
) -> int | None:
    idx = None
    for idx, ele in enumerate(player_buckets):
        if ele > total_players:
            break

    try:
        if total_players > player_buckets[-1]:
            return player_buckets[-1]
        elif idx:
            return player_buckets[idx - 1]
    except IndexError:
        return None
