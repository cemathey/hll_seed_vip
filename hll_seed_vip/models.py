from datetime import datetime, timedelta
from typing import TypedDict

import pydantic


class ConfigTimeDeltaType(TypedDict):
    seconds: int
    minutes: int
    hours: int


class ConfigRequirementsType(TypedDict):
    min_allies: int
    max_allies: int
    min_axis: int
    max_axis: int
    online_when_seeded: bool
    minimum_play_time: ConfigTimeDeltaType


class ConfigVipRewardType(TypedDict):
    cumulative: bool
    timeframe: ConfigTimeDeltaType
    player_message: str
    nice_delta: bool
    nice_date: bool


class ConfigType(TypedDict):
    base_url: str
    dry_run: bool
    poll_time_seeding: int
    poll_time_seeded: int
    requirements: ConfigRequirementsType
    vip_reward: ConfigVipRewardType


class ServerConfig(pydantic.BaseModel):
    base_url: str
    dry_run: bool

    poll_time_seeding: int
    poll_time_seeded: int

    # player count conditions
    min_allies: int
    min_axis: int
    max_allies: int
    max_axis: int

    # player conditions
    minimum_play_time: timedelta
    online_when_seeded: bool

    # rewards
    cumulative_vip: bool
    vip_reward: timedelta
    player_message: str
    nice_delta: bool
    nice_date: bool

    @pydantic.field_validator("base_url")
    @classmethod
    def only_valid_urls(cls, v):
        return str(pydantic.HttpUrl(v))


class Player(pydantic.BaseModel):
    name: str
    steam_id_64: str
    current_playtime_seconds: int


class VipPlayer(pydantic.BaseModel):
    player: Player
    expiration_date: datetime | None


class ServerPopulation(pydantic.BaseModel):
    players: dict[str, Player]


class GameState(pydantic.BaseModel):
    num_allied_players: int
    num_axis_players: int


class BaseCondition(pydantic.BaseModel):
    def is_met(self):
        raise NotImplementedError


class PlayerCountCondition(BaseCondition):
    faction: str
    min_players: int = pydantic.Field(ge=0, le=50)
    max_players: int = pydantic.Field(ge=0, le=50)

    current_players: int = pydantic.Field(ge=0, le=50)

    def is_met(self):
        return self.min_players <= self.current_players <= self.max_players


class PlayTimeCondition(BaseCondition):
    min_time_secs: int = pydantic.Field(ge=1)

    current_time_secs: int = pydantic.Field(ge=1)

    def is_met(self):
        return self.current_time_secs >= self.min_time_secs
