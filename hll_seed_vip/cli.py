import os
from datetime import datetime, timezone
from itertools import cycle
from pathlib import Path

import discord_webhook as discord
import httpx
import trio
from loguru import logger

from hll_seed_vip.constants import API_KEY, API_KEY_FORMAT
from hll_seed_vip.io import (
    get_gamestate,
    get_online_players,
    get_public_info,
    get_vips,
    message_player,
    reward_players,
)
from hll_seed_vip.utils import (
    collect_steam_ids,
    is_seeded,
    load_config,
    make_seed_announcement_embed,
    should_announce_seeding_progress,
)

CONFIG_FILE_NAME = os.getenv("CONFIG_FILE_NAME", "config.yml")
CONFIG_DIR = os.getenv("CONFIG_DIR", "./config")
LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "seeding.log")
LOG_DIR = os.getenv("LOG_DIR", "./logs")


async def raise_on_4xx_5xx(response):
    response.raise_for_status()


async def main():
    api_key = os.getenv(API_KEY)
    headers = {"Authorization": API_KEY_FORMAT.format(api_key=api_key)}

    if api_key is None:
        raise ValueError(f"{API_KEY} must be set")

    config = load_config(Path(CONFIG_DIR).joinpath(CONFIG_FILE_NAME))

    whs: list[discord.DiscordWebhook] = []
    if config.discord_webhooks:
        whs = [discord.DiscordWebhook(url=str(url)) for url in config.discord_webhooks]

    async with httpx.AsyncClient(
        headers=headers, event_hooks={"response": [raise_on_4xx_5xx]}
    ) as client:
        to_add_vip_steam_ids: set[str] | None = set()
        player_name_lookup: dict[str, str] = {}
        prev_announced_bucket: int = 0
        player_buckets = cycle(config.discord_seeding_player_buckets)
        next_player_bucket = next(player_buckets)
        last_bucket_announced = False
        gamestate = await get_gamestate(client, config.base_url)
        is_seeding = not is_seeded(config=config, gamestate=gamestate)
        try:
            while True:
                players = await get_online_players(client, config.base_url)
                gamestate = await get_gamestate(client, config.base_url)
                total_players = (
                    gamestate.num_allied_players + gamestate.num_axis_players
                )

                player_name_lookup |= {
                    p.steam_id_64: p.name for p in players.players.values()
                }

                logger.debug(
                    f"{is_seeding=} {len(players.players.keys())} online players (`get_players`), {gamestate.num_allied_players} allied {gamestate.num_axis_players} axis players (gamestate)",
                )
                to_add_vip_steam_ids = collect_steam_ids(
                    config=config,
                    players=players,
                    cum_steam_ids=to_add_vip_steam_ids,
                )

                # Server seeded
                if is_seeding and is_seeded(config=config, gamestate=gamestate):
                    seeded_timestamp = datetime.now(tz=timezone.utc)
                    logger.info(f"Server seeded at {seeded_timestamp.isoformat()}")
                    current_vips = await get_vips(client, config.base_url)

                    await reward_players(
                        client=client,
                        config=config,
                        to_add_vip_steam_ids=to_add_vip_steam_ids,
                        current_vips=current_vips,
                        seeded_timestamp=seeded_timestamp,
                        players_lookup=player_name_lookup,
                    )

                    # Post seeding complete message
                    if whs:
                        public_info = await get_public_info(client, config.base_url)
                        logger.debug(
                            f"Making embed for `{config.discord_seeding_complete_message}`"
                        )
                        embed = make_seed_announcement_embed(
                            message=config.discord_seeding_complete_message,
                            current_map=public_info["current_map_human_name"],
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
                    logger.debug(f"not is_seeding and not is_seeded")
                    is_seeding = True

                if is_seeding:
                    sleep_time = config.poll_time_seeding

                    # Announce seeding progres
                    logger.debug(
                        f"whs={[wh.url for wh in whs]} {config.discord_seeding_player_buckets=} {total_players=} {prev_announced_bucket=} {next_player_bucket=} {last_bucket_announced=}"
                    )
                    if whs and should_announce_seeding_progress(
                        player_buckets=config.discord_seeding_player_buckets,
                        total_players=total_players,
                        prev_announced_bucket=prev_announced_bucket,
                        next_player_bucket=next_player_bucket,
                        last_bucket_announced=last_bucket_announced,
                    ):
                        logger.debug(
                            f"{next_player_bucket=} {config.discord_seeding_player_buckets[-1]=}"
                        )
                        if (
                            next_player_bucket
                            == config.discord_seeding_player_buckets[-1]
                        ):
                            logger.debug(f"setting last_bucket_announced=True")
                            last_bucket_announced = True

                        prev_announced_bucket = next_player_bucket
                        next_player_bucket = next(player_buckets)

                        logger.debug(
                            f"{prev_announced_bucket=} {next_player_bucket=} {player_buckets=}"
                        )

                        public_info = await get_public_info(client, config.base_url)
                        embed = make_seed_announcement_embed(
                            message=config.discord_seeding_in_progress_message.format(
                                player_count=total_players
                            ),
                            current_map=public_info["current_map_human_name"],
                            time_remaining=gamestate.raw_time_remaining,
                            player_count_message=config.discord_player_count_message,
                            num_allied_players=gamestate.num_allied_players,
                            num_axis_players=gamestate.num_axis_players,
                        )
                        if embed:
                            for wh in whs:
                                wh.add_embed(embed)
                                wh.execute(remove_embeds=True)

                else:
                    sleep_time = config.poll_time_seeded

                logger.info(f"sleeping {sleep_time=}")
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
