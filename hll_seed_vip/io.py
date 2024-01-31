import urllib.parse
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from hll_seed_vip.models import (
    GameState,
    Player,
    ServerConfig,
    ServerPopulation,
    VipPlayer,
)
from hll_seed_vip.utils import (
    calc_vip_expiration_timestamp,
    format_player_message,
    format_vip_reward_name,
    with_backoff_retry,
)


@with_backoff_retry()
async def get_public_info(
    client: httpx.AsyncClient, server_url: str, endpoint="api/public_info"
) -> dict[str, Any]:
    url = urllib.parse.urljoin(server_url, endpoint)
    response = await client.get(url=url)
    raw_response = response.json()["result"]

    return {"current_map_human_name": raw_response["current_map"]["human_name"]}


@with_backoff_retry()
async def get_vips(
    client: httpx.AsyncClient,
    server_url: str,
    endpoint="api/get_vip_ids",
) -> dict[str, VipPlayer]:
    url = urllib.parse.urljoin(server_url, endpoint)
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


@with_backoff_retry()
async def get_gamestate(
    client: httpx.AsyncClient,
    server_url: str,
    endpoint="api/get_gamestate",
) -> GameState:
    url = urllib.parse.urljoin(server_url, endpoint)
    response = await client.get(url=url)
    result = response.json()["result"]

    return GameState(
        raw_time_remaining=result["raw_time_remaining"],
        current_map=result["current_map"],
        num_allied_players=result["num_allied_players"],
        num_axis_players=result["num_axis_players"],
    )


@with_backoff_retry()
async def get_online_players(
    client: httpx.AsyncClient,
    server_url: str,
    endpoint="api/get_players",
) -> ServerPopulation:
    url = urllib.parse.urljoin(server_url, endpoint)
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


@with_backoff_retry()
async def add_vip(
    client: httpx.AsyncClient,
    server_url: str,
    steam_id_64: str,
    player_name: str,
    expiration_timestamp: datetime | None,
    endpoint="api/do_add_vip",
):
    url = urllib.parse.urljoin(server_url, endpoint)

    body = {
        "steam_id_64": steam_id_64,
        "name": player_name,
        "expiration": expiration_timestamp.isoformat()
        if expiration_timestamp
        else None,
    }
    logger.debug(f"add_vip {url=} {body=}")
    response = await client.post(url=url, json=body)
    result = response.json()["result"]
    logger.info(
        f"added VIP for {steam_id_64=} {expiration_timestamp=} {player_name=} {result=}",
    )


@with_backoff_retry()
async def message_player(
    client: httpx.AsyncClient,
    server_url: str,
    steam_id_64: str,
    message: str,
    endpoint="api/do_message_player",
):
    url = urllib.parse.urljoin(server_url, endpoint)
    body = {"steam_id_64": steam_id_64, "message": message}
    response = await client.post(url=url, json=body)
    logger.info(f"messaged player {steam_id_64}: {message}")


async def reward_players(
    client: httpx.AsyncClient,
    config: ServerConfig,
    to_add_vip_steam_ids: set[str],
    current_vips: dict[str, VipPlayer],
    seeded_timestamp: datetime,
    players_lookup: dict[str, str],
):
    # TODO: make concurrent
    logger.info(f"Rewarding players with VIP {config.dry_run=}")
    logger.info(f"Total={len(to_add_vip_steam_ids)} {to_add_vip_steam_ids=}")
    logger.debug(f"Total={len(current_vips)=} {current_vips=}")
    for steam_id_64 in to_add_vip_steam_ids:
        player = current_vips.get(steam_id_64)
        expiration_date = calc_vip_expiration_timestamp(
            config=config,
            expiration=player.expiration_date if player else None,
            from_time=seeded_timestamp,
        )
        msg = format_player_message(
            config.message_reward,
            vip_reward=config.vip_reward,
            vip_expiration=expiration_date,
            nice_delta=config.nice_delta,
            nice_date=config.nice_date,
        )
        vip_name = (
            player.player.name
            if player
            else format_vip_reward_name(
                players_lookup.get(steam_id_64, "No player name found")
            )
        )
        if not config.dry_run:
            logger.info(
                f"{config.dry_run=} adding VIP to {steam_id_64=} {player=} {vip_name=} {expiration_date=}",
            )
            await add_vip(
                client=client,
                server_url=config.base_url,
                steam_id_64=steam_id_64,
                player_name=vip_name,
                expiration_timestamp=expiration_date,
            )

            if config.message_reward:
                logger.info(f"{config.dry_run=} messaging {steam_id_64}: {msg}")
                await message_player(
                    client,
                    server_url=config.base_url,
                    steam_id_64=steam_id_64,
                    message=msg,
                )

        else:
            logger.info(
                f"{config.dry_run=} adding VIP to {steam_id_64=} {player=} {vip_name=} {expiration_date=}",
            )
            logger.info(f"{config.dry_run=} messaging {steam_id_64}: {msg}")
