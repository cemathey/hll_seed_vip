import inspect
import urllib.parse
from datetime import datetime
from functools import wraps
from itertools import cycle
from typing import Any

import httpx
import trio
from loguru import logger

from hll_seed_vip.models import (
    GameState,
    Player,
    PublicInfoType,
    ServerPopulation,
    VipPlayer,
)


def with_backoff_retry():
    backoffs = (0, 1, 1.5, 2, 4, 8, 16)

    def decorator(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            # Helpfully sourced (with updates) from
            # https://stackoverflow.com/questions/218616/how-to-get-method-parameter-names
            args_name = inspect.getfullargspec(func)[0]
            args_dict = dict(zip(args_name, args))
            server_url: str = args_dict.get("server_url", None)
            for idx, backoff in enumerate(cycle(backoffs)):
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPError as e:
                    logger.error(e)
                    logger.warning(
                        f"Retrying attempt {idx+1}, sleeping for {backoff} seconds for {server_url} function={func.__name__}"
                    )
                    await trio.sleep(backoff)
                    continue

        return wrapped

    return decorator


@with_backoff_retry()
async def get_public_info(
    client: httpx.AsyncClient, server_url: str, endpoint="api/get_public_info"
) -> PublicInfoType:
    url = urllib.parse.urljoin(server_url, endpoint)
    response = await client.get(url=url)
    raw_response = response.json()["result"]

    return raw_response


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
        if raw_player["profile"] is None:
            # Apparently CRCON will occasionally not return a player profile
            logger.debug(f"No CRCON profile, skipping {raw_player}")
            continue
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
    forward: bool,
    endpoint="api/do_add_vip",
):
    url = urllib.parse.urljoin(server_url, endpoint)

    body = {
        "forward": forward,
        "steam_id_64": steam_id_64,
        "name": player_name,
        "expiration": (
            expiration_timestamp.isoformat() if expiration_timestamp else None
        ),
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
    logger.info(f"Messaging player {steam_id_64}: {message}")
    response = await client.post(url=url, json=body)
