import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

import discord_webhook as discord
import httpx
import humanize
import trio
import yaml
from loguru import logger

from hll_seed_vip.constants import API_KEY, API_KEY_FORMAT
from hll_seed_vip.io import get_gamestate, get_online_players, get_public_info, get_vips
from hll_seed_vip.utils import (
    calc_vip_expiration_timestamp,
    collect_steam_ids,
    filter_indefinite_vip_steam_ids,
    filter_online_players,
    get_next_player_bucket,
    is_seeded,
    load_config,
    make_seed_announcement_embed,
    message_players,
    reward_players,
)

CONFIG_FILE_NAME: Final = os.getenv("CONFIG_FILE_NAME", "config.yml")
CONFIG_DIR: Final = os.getenv("CONFIG_DIR", "./config")
LOG_FILE_NAME: Final = os.getenv("LOG_FILE_NAME", "seeding.log")
LOG_DIR: Final = os.getenv("LOG_DIR", "./logs")
TAG_VERSION: Final = os.getenv("TAG_VERSION", "<unknown>")


async def raise_on_4xx_5xx(response):
    response.raise_for_status()


async def main():
    api_key = os.getenv(API_KEY)
    headers = {"Authorization": API_KEY_FORMAT.format(api_key=api_key)}

    if api_key is None:
        raise ValueError(f"{API_KEY} must be set")

    try:
        config = load_config(Path(CONFIG_DIR).joinpath(CONFIG_FILE_NAME))
    except yaml.YAMLError as e:
        logger.error(f"Unable to parse your config file: {e}")
        sys.exit(1)
    try:
        if config.language:
            logger.info(f"Attempting to activate language={config.language}")
            humanize.activate(config.language)
    except FileNotFoundError:
        logger.error(
            f"Unable to activate language={config.language}, defaulting to English"
        )

    whs: list[discord.DiscordWebhook] = []
    if config.discord_webhooks:
        whs = [discord.DiscordWebhook(url=str(url)) for url in config.discord_webhooks]

    async with httpx.AsyncClient(
        headers=headers, event_hooks={"response": [raise_on_4xx_5xx]}
    ) as client:
        to_add_vip_steam_ids: set[str] = set()
        no_reward_steam_ids: set[str] = set()
        player_name_lookup: dict[str, str] = {}
        prev_announced_bucket: int = 0
        player_buckets = config.discord_seeding_player_buckets
        if player_buckets:
            next_player_bucket = player_buckets[0]
        else:
            next_player_bucket = None
        last_bucket_announced = False
        seeded_timestamp: datetime | None = None

        gamestate = await get_gamestate(client, config.base_url)
        is_seeding = not is_seeded(config=config, gamestate=gamestate)
        try:
            while True:
                online_players = await get_online_players(client, config.base_url)
                if online_players is None:
                    logger.debug(
                        f"Did not receive a usable result from `get_online_players`, continuing"
                    )
                    continue

                gamestate = await get_gamestate(client, config.base_url)

                if gamestate is None:
                    logger.debug(
                        f"Did not receive a usable result from `get_gamestate`, continuing"
                    )
                    continue

                total_players = (
                    gamestate.num_allied_players + gamestate.num_axis_players
                )

                player_name_lookup |= {
                    p.player_id: p.name for p in online_players.players.values()
                }

                logger.debug(
                    f"{is_seeding=} {len(online_players.players.keys())} online players (`get_players`), {gamestate.num_allied_players} allied {gamestate.num_axis_players} axis players (gamestate)",
                )
                to_add_vip_steam_ids = collect_steam_ids(
                    config=config,
                    players=online_players,
                    cum_steam_ids=to_add_vip_steam_ids,
                )

                # Server seeded
                if is_seeding and is_seeded(config=config, gamestate=gamestate):
                    seeded_timestamp = datetime.now(tz=timezone.utc)
                    logger.info(f"Server seeded at {seeded_timestamp.isoformat()}")
                    current_vips = await get_vips(client, config.base_url)

                    # only include online players in the current_vips
                    current_vips = filter_online_players(current_vips, online_players)

                    # no vip reward needed for indefinite vip holders
                    indefinite_vip_steam_ids = filter_indefinite_vip_steam_ids(
                        current_vips
                    )
                    to_add_vip_steam_ids -= indefinite_vip_steam_ids

                    # Players who were online when we seeded but didn't meet the criteria for VIP
                    no_reward_steam_ids = {
                        p.player_id for p in online_players.players.values()
                    } - to_add_vip_steam_ids

                    expiration_timestamps = defaultdict(
                        lambda: calc_vip_expiration_timestamp(
                            config=config,
                            expiration=None,
                            from_time=seeded_timestamp or datetime.now(tz=timezone.utc),
                        )
                    )
                    for player in current_vips.values():
                        expiration_timestamps[
                            player.player.player_id
                        ] = calc_vip_expiration_timestamp(
                            config=config,
                            expiration=player.expiration_date if player else None,
                            from_time=seeded_timestamp,
                        )

                    # Add or update VIP in CRCON
                    await reward_players(
                        client=client,
                        config=config,
                        to_add_vip_steam_ids=to_add_vip_steam_ids,
                        current_vips=current_vips,
                        players_lookup=player_name_lookup,
                        expiration_timestamps=expiration_timestamps,
                    )

                    # Message those who earned VIP
                    await message_players(
                        client=client,
                        config=config,
                        message=config.message_reward,
                        steam_ids=to_add_vip_steam_ids,
                        expiration_timestamps=expiration_timestamps,
                    )

                    # Message those who did not earn
                    await message_players(
                        client=client,
                        config=config,
                        message=config.message_non_vip,
                        steam_ids=no_reward_steam_ids,
                        expiration_timestamps=None,
                    )

                    # Post seeding complete Discord message
                    if whs:
                        public_info = await get_public_info(client, config.base_url)
                        logger.debug(
                            f"Making embed for `{config.discord_seeding_complete_message}`"
                        )
                        embed = make_seed_announcement_embed(
                            message=config.discord_seeding_complete_message,
                            current_map=public_info["current_map"]["map"][
                                "pretty_name"
                            ],
                            time_remaining=gamestate.raw_time_remaining,
                            player_count_message=config.discord_player_count_message,
                            num_allied_players=gamestate.num_allied_players,
                            num_axis_players=gamestate.num_axis_players,
                        )
                        if embed:
                            for wh in whs:
                                wh.add_embed(embed)
                                wh.execute(remove_embeds=True)

                    # Reset for next seed
                    last_bucket_announced = False
                    prev_announced_bucket = 0
                    to_add_vip_steam_ids.clear()
                    is_seeding = False
                elif (
                    not is_seeding
                    and not is_seeded(config=config, gamestate=gamestate)
                    and total_players > 0
                ):
                    delta: timedelta | None = None
                    if seeded_timestamp:
                        delta = datetime.now(tz=timezone.utc) - seeded_timestamp

                    if not seeded_timestamp:
                        logger.debug(
                            f"Back in seeding: seeded_timestamp={seeded_timestamp} {delta=} {config.buffer=}"
                        )
                        is_seeding = True
                    elif delta and (delta > config.buffer):
                        logger.debug(
                            f"Back in seeding: seeded_timestamp={seeded_timestamp.isoformat()} {delta=} delta > buffer {delta > config.buffer} {config.buffer=}"
                        )
                        is_seeding = True
                    else:
                        logger.info(
                            f"Delaying seeding mode due to buffer of {config.buffer} > {delta} time since seeded"
                        )

                if is_seeding:
                    sleep_time = config.poll_time_seeding

                    # When we fall back into seeding with players still on the
                    # server we want to announce the largest bucket possible or
                    # it will announce from the smallest to the largest and spam
                    # Discord with unneccessary announcements
                    next_player_bucket = get_next_player_bucket(
                        config.discord_seeding_player_buckets,
                        total_players=total_players,
                    )

                    # Announce seeding progress
                    logger.debug(
                        f"whs={[wh.url for wh in whs]} {config.discord_seeding_player_buckets=} {total_players=} {prev_announced_bucket=} {next_player_bucket=} {last_bucket_announced=}"
                    )
                    if (
                        whs
                        and next_player_bucket
                        and not last_bucket_announced
                        and prev_announced_bucket < next_player_bucket
                        and total_players >= next_player_bucket
                    ):
                        prev_announced_bucket = next_player_bucket

                        public_info = await get_public_info(client, config.base_url)
                        embed = make_seed_announcement_embed(
                            message=config.discord_seeding_in_progress_message.format(
                                player_count=total_players
                            ),
                            current_map=public_info["current_map"]["map"][
                                "pretty_name"
                            ],
                            time_remaining=gamestate.raw_time_remaining,
                            player_count_message=config.discord_player_count_message,
                            num_allied_players=gamestate.num_allied_players,
                            num_axis_players=gamestate.num_axis_players,
                        )
                        if (
                            next_player_bucket
                            == config.discord_seeding_player_buckets[-1]
                        ):
                            logger.debug(f"setting last_bucket_announced=True")
                            last_bucket_announced = True

                        if embed:
                            for wh in whs:
                                wh.add_embed(embed)
                                wh.execute(remove_embeds=True)

                else:
                    sleep_time = config.poll_time_seeded

                logger.info(f"{TAG_VERSION=} sleeping {sleep_time=}")
                await trio.sleep(sleep_time)
        except* Exception as eg:
            for e in eg.exceptions:
                logger.exception(e)
            raise


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # TODO: expose log retention/rotation as configurable options
    logger.add(
        Path(LOG_DIR).joinpath(LOG_FILE_NAME),
        level=os.getenv("LOG_LEVEL", "DEBUG"),
        rotation="10 MB",
        retention="10 days",
    )
    trio.run(main)
