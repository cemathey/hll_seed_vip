from datetime import datetime, timedelta
from enum import Enum
from typing import TypedDict

import pydantic
import typing_extensions


class ConfigTimeDeltaType(TypedDict):
    seconds: int
    minutes: int
    hours: int


class ConfigRequirementsType(TypedDict):
    buffer: ConfigTimeDeltaType
    min_allies: int
    max_allies: int
    min_axis: int
    max_axis: int
    online_when_seeded: bool
    minimum_play_time: ConfigTimeDeltaType


class ConfigVipRewardType(TypedDict):
    forward: bool
    player_name_not_current_vip: str
    cumulative: bool
    timeframe: ConfigTimeDeltaType
    nice_time_delta: bool
    nice_expiration_date: bool


class ConfigDiscordType(TypedDict):
    webhooks: list[pydantic.HttpUrl]
    seeding_complete_message: str
    seeding_in_progress_message: str
    player_count_message: str
    seeding_player_buckets: list[int]


class ConfigPlayerMessageType(TypedDict):
    reward: str
    non_vip: str


class ConfigType(TypedDict):
    language: str | None
    base_url: str
    discord: ConfigDiscordType
    player_messages: ConfigPlayerMessageType
    dry_run: bool
    poll_time_seeding: int
    poll_time_seeded: int
    requirements: ConfigRequirementsType
    vip_reward: ConfigVipRewardType


class ServerConfig(pydantic.BaseModel):
    language: str | None
    base_url: str
    discord_webhooks: list[pydantic.HttpUrl] = pydantic.Field(default_factory=list)
    discord_seeding_complete_message: str
    discord_player_count_message: str
    discord_seeding_in_progress_message: str
    discord_seeding_player_buckets: list[int]
    dry_run: bool

    buffer: timedelta
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

    # player messages
    message_reward: str
    message_non_vip: str

    # rewards
    forward: bool
    player_name_not_current_vip: str
    cumulative_vip: bool
    vip_reward: timedelta
    nice_time_delta: bool
    nice_expiration_date: bool

    @pydantic.field_validator("base_url")
    @classmethod
    def only_valid_urls(cls, v):
        return str(pydantic.HttpUrl(v))


class Player(pydantic.BaseModel):
    name: str
    player_id: str
    current_playtime_seconds: int


class VipPlayer(pydantic.BaseModel):
    player: Player
    expiration_date: datetime | None


class ServerPopulation(pydantic.BaseModel):
    players: dict[str, Player]


class GameState(pydantic.BaseModel):
    num_allied_players: int
    num_axis_players: int
    allied_score: int
    axis_score: int
    raw_time_remaining: str
    time_remaining: float
    current_map: "LayerType"
    next_map: "LayerType"


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

    current_time_secs: int = pydantic.Field(ge=0)

    def is_met(self):
        return self.current_time_secs >= self.min_time_secs


class Team(str, Enum):
    ALLIES = "allies"
    AXIS = "axis"


class _Faction(pydantic.BaseModel):
    name: str
    team: Team


class Faction(Enum):
    CW = _Faction(name="gb", team=Team.ALLIES)
    GB = _Faction(name="gb", team=Team.ALLIES)
    GER = _Faction(name="ger", team=Team.AXIS)
    RUS = _Faction(name="rus", team=Team.ALLIES)
    US = _Faction(name="us", team=Team.ALLIES)


class MapType(typing_extensions.TypedDict):
    id: str
    name: str
    tag: str
    pretty_name: str
    shortname: str
    allies: Faction
    axis: Faction


class LayerType(typing_extensions.TypedDict):
    id: str
    map: MapType
    game_mode: str
    attackers: str | None
    environment: str
    pretty_name: str
    image_name: str
    image_url: str | None


class PublicInfoMapType(TypedDict):
    map: LayerType
    start: float | None


class PublicInfoPlayerType(TypedDict):
    allied: int
    axis: int


class PublicInfoScoreType(TypedDict):
    allied: int
    axis: int


class VoteMapResultType(TypedDict):
    total_votes: int
    winning_maps: list[tuple[LayerType, int]]


class PublicInfoNameType(TypedDict):
    name: str
    short_name: str
    public_stats_port: int | None
    public_stats_port_https: int | None


class PublicInfoType(TypedDict):
    """TypedDict for rcon.views.get_public_info"""

    current_map: PublicInfoMapType
    next_map: PublicInfoMapType
    player_count: int
    max_player_count: int
    player_count_by_team: PublicInfoPlayerType
    score: PublicInfoScoreType
    time_remaining: float
    vote_status: VoteMapResultType | None
    name: PublicInfoNameType
