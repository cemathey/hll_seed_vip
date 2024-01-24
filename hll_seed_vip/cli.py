import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import trio
from loguru import logger

from hll_seed_vip.constants import API_KEY, API_KEY_FORMAT
from hll_seed_vip.io import get_gamestate, get_online_players, get_vips, reward_players
from hll_seed_vip.utils import collect_steam_ids, is_seeded, load_config


async def main():
    api_key = os.getenv(API_KEY)
    headers = {"Authorization": API_KEY_FORMAT.format(api_key=api_key)}

    if api_key is None:
        raise ValueError(f"{API_KEY} must be set")

    config = load_config(Path("config/config.yml"))

    async with httpx.AsyncClient(headers=headers) as client:
        to_add_vip_steam_ids: set[str] | None = set()
        gamestate = await get_gamestate(client, config.base_url)
        is_seeding = not is_seeded(config=config, gamestate=gamestate)
        while True:
            players = await get_online_players(client, config.base_url)
            gamestate = await get_gamestate(client, config.base_url)

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
                )

                to_add_vip_steam_ids.clear()
                is_seeding = False
            elif not is_seeding and not is_seeded(config=config, gamestate=gamestate):
                logger.debug(f"not is_seeding and not is_seeded")
                is_seeding = True

            if is_seeding:
                sleep_time = config.poll_time_seeding
            else:
                sleep_time = config.poll_time_seeded

            logger.debug(f"sleeping {sleep_time=}")
            await trio.sleep(sleep_time)


if __name__ == "__main__":
    logger.add("./logs/seeding.log", level=os.getenv("LOGURU_LEVEL", "DEBUG"))
    trio.run(main)
