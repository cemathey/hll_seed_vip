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
        to_add_vip_steam_ids: set[str] | None = None
        while True:
            players = await get_online_players(client, config.base_url)
            gamestate = await get_gamestate(client, config.base_url)

            logger.debug(
                "%s online players (`get_players`), %s allied %s axis players (gamestate)",
                len(players.players.keys()),
                gamestate.num_allied_players,
                gamestate.num_axis_players,
            )
            try:
                to_add_vip_steam_ids, sleep_time = collect_steam_ids(
                    config=config,
                    players=players,
                    gamestate=gamestate,
                    cum_steam_ids=to_add_vip_steam_ids,
                )
            except ValueError as e:
                logger.error(f"sleeping {config.poll_time_seeding=} due to %s", e)
                await trio.sleep(config.poll_time_seeding)
                continue

            if is_seeded(config=config, gamestate=gamestate):
                seeded_timestamp = datetime.now(tz=timezone.utc)
                logger.info(f"server seeded at {seeded_timestamp.isoformat()}")
                current_vips = await get_vips(client, config.base_url)
                # add VIPs

                await reward_players(
                    client=client,
                    config=config,
                    to_add_vip_steam_ids=to_add_vip_steam_ids,
                    current_vips=current_vips,
                    seeded_timestamp=seeded_timestamp,
                )

                to_add_vip_steam_ids.clear()
                sleep_time = config.poll_time_seeded
            else:
                # not seeded
                sleep_time = config.poll_time_seeding

            logger.debug(f"sleeping {sleep_time=}")
            await trio.sleep(sleep_time)


if __name__ == "__main__":
    logger.add(f"./logs/seeding.log", level=os.getenv("LOGURU_LEVEL", "DEBUG"))
    trio.run(main)
