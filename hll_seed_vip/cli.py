import os
from datetime import datetime, timezone
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

    wh: discord.DiscordWebhook | None = None
    if config.discord_webhook:
        wh = discord.DiscordWebhook(url=str(config.discord_webhook))

    async with httpx.AsyncClient(
        headers=headers, event_hooks={"response": [raise_on_4xx_5xx]}
    ) as client:
        to_add_vip_steam_ids: set[str] | None = set()
        player_name_lookup: dict[str, str] = {}
        prev_announced_player_count: int = 0
        player_buckets = iter(config.discord_seeding_player_buckets)
        next_player_bucket = next(player_buckets)
        last_bucket_announced = False
        gamestate = await get_gamestate(client, config.base_url)
        is_seeding = not is_seeded(config=config, gamestate=gamestate)
        # if wh:
        #     embed = make_seed_announcement_embed(
        #         message=config.discord_seeding_complete_message,
        #         current_map=gamestate.current_map,
        #         time_remaining=gamestate.raw_time_remaining,
        #         player_count_message=config.discord_player_count_message,
        #         num_allied_players=gamestate.num_allied_players,
        #         num_axis_players=gamestate.num_axis_players,
        #     )
        #     if embed:
        #         wh.add_embed(embed)
        #         wh.execute(remove_embeds=True)
        while True:
            players = await get_online_players(client, config.base_url)
            gamestate = await get_gamestate(client, config.base_url)
            total_players = gamestate.num_allied_players + gamestate.num_axis_players

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

            if is_seeding and is_seeded(config=config, gamestate=gamestate):
                seeded_timestamp = datetime.now(tz=timezone.utc)
                logger.info(f"server seeded at {seeded_timestamp.isoformat()}")
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
                if wh:
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
                        wh.add_embed(embed)
                        wh.execute(remove_embeds=True)

                # Reset for next seed
                player_buckets = iter(config.discord_seeding_player_buckets)
                last_bucket_announced = False
                prev_announced_player_count: int = 0
                to_add_vip_steam_ids.clear()
                is_seeding = False
            elif not is_seeding and not is_seeded(config=config, gamestate=gamestate):
                logger.debug(f"not is_seeding and not is_seeded")
                is_seeding = True

            if is_seeding:
                sleep_time = config.poll_time_seeding

                # Announce seeding progres
                logger.debug(
                    f"{wh=} {config.discord_seeding_player_buckets=} {total_players=} {prev_announced_player_count=} {next_player_bucket=} {last_bucket_announced=}"
                )
                if (
                    wh
                    and config.discord_seeding_player_buckets
                    and total_players > prev_announced_player_count
                    and total_players >= next_player_bucket
                    and not last_bucket_announced
                ):
                    if next_player_bucket == config.discord_seeding_player_buckets[-1]:
                        last_bucket_announced = True

                    prev_announced_player_count = next_player_bucket
                    next_player_bucket = next(player_buckets)

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
                        wh.add_embed(embed)
                        wh.execute(remove_embeds=True)

            else:
                sleep_time = config.poll_time_seeded

            logger.info(f"sleeping {sleep_time=}")
            await trio.sleep(sleep_time)


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    logger.add(
        Path(LOG_DIR).joinpath(LOG_FILE_NAME), level=os.getenv("LOGURU_LEVEL", "DEBUG")
    )
    trio.run(main)
