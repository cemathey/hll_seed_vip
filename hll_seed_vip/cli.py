import os
from datetime import datetime, timezone
from pathlib import Path

import discord_webhook as discord
import httpx
import trio
from loguru import logger

from hll_seed_vip.constants import API_KEY, API_KEY_FORMAT
from hll_seed_vip.io import get_gamestate, get_online_players, get_vips, reward_players
from hll_seed_vip.utils import (
    collect_steam_ids,
    is_seeded,
    load_config,
    make_seed_announcement_embed,
)

CONFIG_FILE_NAME = os.getenv("CONFIG_FILE_NAME", "config.yml")
LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "seeding.log")
LOG_DIR = os.getenv("LOG_DIR", "./logs")


async def raise_on_4xx_5xx(response):
    response.raise_for_status()


async def main():
    api_key = os.getenv(API_KEY)
    headers = {"Authorization": API_KEY_FORMAT.format(api_key=api_key)}

    if api_key is None:
        raise ValueError(f"{API_KEY} must be set")

    config = load_config(Path(CONFIG_FILE_NAME))

    wh: discord.DiscordWebhook | None = None
    if config.discord_webhook:
        wh = discord.DiscordWebhook(url=str(config.discord_webhook))

    async with httpx.AsyncClient(
        headers=headers, event_hooks={"response": [raise_on_4xx_5xx]}
    ) as client:
        to_add_vip_steam_ids: set[str] | None = set()
        player_name_lookup: dict[str, str] = {}
        gamestate = await get_gamestate(client, config.base_url)
        is_seeding = not is_seeded(config=config, gamestate=gamestate)
        # if wh:
        #     embed = make_seed_announcement_embed(
        #         message=config.discord_seeding_complete_message,
        #         current_map=gamestate.current_map,
        #         time_remaining=gamestate.raw_time_remaining,
        #         num_allied_players=gamestate.num_allied_players,
        #         num_axis_players=gamestate.num_axis_players,
        #     )
        #     if embed:
        #         wh.add_embed(embed)
        #         wh.execute(remove_embeds=True)
        while True:
            players = await get_online_players(client, config.base_url)
            gamestate = await get_gamestate(client, config.base_url)

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

                if wh:
                    embed = make_seed_announcement_embed(
                        message=config.discord_seeding_complete_message,
                        current_map=gamestate.current_map,
                        time_remaining=gamestate.raw_time_remaining,
                        num_allied_players=gamestate.num_allied_players,
                        num_axis_players=gamestate.num_axis_players,
                    )
                    if embed:
                        wh.add_embed(embed)
                        wh.execute(remove_embeds=True)

                to_add_vip_steam_ids.clear()
                is_seeding = False
            elif not is_seeding and not is_seeded(config=config, gamestate=gamestate):
                logger.debug(f"not is_seeding and not is_seeded")
                is_seeding = True

            if is_seeding:
                sleep_time = config.poll_time_seeding
            else:
                sleep_time = config.poll_time_seeded

            logger.info(f"sleeping {sleep_time=}")
            await trio.sleep(sleep_time)


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    logger.add(
        Path(LOG_DIR).joinpath(LOG_FILE_NAME), level=os.getenv("LOGURU_LEVEL", "DEBUG")
    )
    trio.run(main)
