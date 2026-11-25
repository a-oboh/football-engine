"""Pydantic v2 models for API-Football v3 (api-football.com) JSON responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiFootballVenue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str | None = None
    city: str | None = None


class ApiFootballStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    long: str | None = None
    short: str = "NS"
    elapsed: int | None = None


class ApiFootballFixtureMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    referee: str | None = None
    timezone: str = "UTC"
    date: datetime
    timestamp: int | None = None
    venue: ApiFootballVenue | None = None
    status: ApiFootballStatus


class ApiFootballLeagueMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    country: str | None = None
    logo: str | None = None
    season: int
    round: str | None = None


class ApiFootballTeamSide(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    logo: str | None = None
    winner: bool | None = None


class ApiFootballTeamsPair(BaseModel):
    model_config = ConfigDict(extra="ignore")

    home: ApiFootballTeamSide
    away: ApiFootballTeamSide


class ApiFootballGoalsPair(BaseModel):
    model_config = ConfigDict(extra="ignore")

    home: int | None = None
    away: int | None = None


class ApiFootballScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore")

    halftime: ApiFootballGoalsPair = Field(default_factory=ApiFootballGoalsPair)
    fulltime: ApiFootballGoalsPair = Field(default_factory=ApiFootballGoalsPair)


class ApiFootballFixtureItem(BaseModel):
    """Single item in the `response` array of `GET /fixtures`."""

    model_config = ConfigDict(extra="ignore")

    fixture: ApiFootballFixtureMeta
    league: ApiFootballLeagueMeta
    teams: ApiFootballTeamsPair
    goals: ApiFootballGoalsPair
    score: ApiFootballScoreBreakdown = Field(default_factory=ApiFootballScoreBreakdown)


class ApiFootballStatPair(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    value: int | float | str | None = None


class ApiFootballTeamStatisticsItem(BaseModel):
    """Single team entry in `GET /fixtures/statistics?fixture={id}`."""

    model_config = ConfigDict(extra="ignore")

    team: ApiFootballTeamSide
    statistics: list[ApiFootballStatPair] = Field(default_factory=list)


class ApiFootballOddValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str
    odd: str


class ApiFootballBetMarket(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    values: list[ApiFootballOddValue] = Field(default_factory=list)


class ApiFootballBookmakerItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    bets: list[ApiFootballBetMarket] = Field(default_factory=list)


class ApiFootballOddsFixtureRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int


class ApiFootballOddsItem(BaseModel):
    """Single item in `GET /odds`."""

    model_config = ConfigDict(extra="ignore")

    fixture: ApiFootballOddsFixtureRef
    bookmakers: list[ApiFootballBookmakerItem] = Field(default_factory=list)


class ApiFootballEnvelope(BaseModel):
    """Top-level response envelope returned by v3.football.api-sports.io."""

    model_config = ConfigDict(extra="ignore")

    get: str | None = None
    parameters: dict[str, Any] | list[Any] = Field(default_factory=dict)
    errors: dict[str, Any] | list[Any] = Field(default_factory=dict)
    results: int = 0
    response: list[dict[str, Any]] = Field(default_factory=list)
