from datetime import datetime

import httpx
from loguru import logger

from hll_seed_vip.models import (
    GameState,
    Player,
    ServerConfig,
    ServerPopulation,
    VipPlayer,
)
from hll_seed_vip.utils import calc_vip_expiration_timestamp


async def get_vips(
    client: httpx.AsyncClient,
    server_url: str,
    endpoint="get_vip_ids",
) -> dict[str, VipPlayer]:
    url = f"{server_url}api/{endpoint}"
    response = await client.get(url=url)

    raw_vips = response.json()["result"]
    return {
        vip["steam_id_64"]: VipPlayer(
            player=Player(
                steam_id_64=vip["steam_id_64"],
                name=vip["name"],
                current_playtime_seconds=0,
            ),
            expiration_date=vip["vip_expiration"],
        )
        for vip in raw_vips
    }


async def get_gamestate(
    client: httpx.AsyncClient,
    server_url: str,
    endpoint="get_gamestate",
) -> GameState:
    url = f"{server_url}api/{endpoint}"
    response = await client.get(url=url)
    result = response.json()["result"]

    return GameState(
        num_allied_players=result["num_allied_players"],
        num_axis_players=result["num_axis_players"],
    )


async def get_online_players(
    client: httpx.AsyncClient,
    server_url: str,
    endpoint="get_players",
) -> ServerPopulation:
    url = f"{server_url}api/{endpoint}"
    response = await client.get(url=url)
    result = response.json()["result"]
    players = {}
    for raw_player in result:
        name = raw_player["name"]
        steam_id_64 = steam_id_64 = raw_player["steam_id_64"]
        current_playtime_seconds = raw_player["profile"]["current_playtime_seconds"]
        p = Player(
            name=name,
            steam_id_64=steam_id_64,
            current_playtime_seconds=current_playtime_seconds,
        )
        players[p.steam_id_64] = p

    return ServerPopulation(players=players)


async def add_vip(
    client: httpx.AsyncClient,
    server_url: str,
    steam_id_64: str,
    player_name: str,
    expiration_timestamp: datetime | None,
    endpoint="do_add_vip",
):
    url = f"{server_url}api/{endpoint}"
    body = {
        "steam_id_64": steam_id_64,
        "name": player_name,
        "expiration": expiration_timestamp,
    }
    response = await client.post(url=url, data=body)
    result = response.json()["result"]
    logger.info(
        f"added VIP for {steam_id_64=} {expiration_timestamp=} {player_name=} {result=}",
    )


async def reward_players(
    client: httpx.AsyncClient,
    config: ServerConfig,
    to_add_vip_steam_ids: set[str],
    current_vips: dict[str, VipPlayer],
    seeded_timestamp: datetime,
):
    # TODO: make concurrent
    logger.debug(f"Rewarding players with VIP {config.dry_run=}")
    logger.debug(f"{to_add_vip_steam_ids=}")
    logger.debug(f"{current_vips=}")
    for steam_id_64 in to_add_vip_steam_ids:
        player = current_vips[steam_id_64]
        expiration_date = calc_vip_expiration_timestamp(
            config=config,
            expiration=player.expiration_date,
            from_time=seeded_timestamp,
        )
        if not config.dry_run:
            await add_vip(
                client=client,
                server_url=config.base_url,
                steam_id_64=steam_id_64,
                player_name=player.player.name,
                expiration_timestamp=expiration_date,
            )
        else:
            logger.debug(
                f"{config.dry_run=} adding VIP to {steam_id_64=} {player=} {expiration_date=}",
            )
