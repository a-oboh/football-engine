"""HTTP client for API-Football v3 (https://v3.football.api-sports.io)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .schemas import (
    ApiFootballEnvelope,
    ApiFootballFixtureItem,
    ApiFootballOddsItem,
    ApiFootballTeamStatisticsItem,
)

DEFAULT_API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"


class ApiFootballError(RuntimeError):
    """Raised when api-football.com returns an HTTP or envelope error."""


@dataclass(frozen=True)
class ApiFootballResponse:
    """Parsed envelope along with rate-limit quota headers."""

    envelope: ApiFootballEnvelope
    requests_remaining: int | None
    requests_limit: int | None


TransportCallable = Callable[
    [str, Mapping[str, str]],
    tuple[int, Mapping[str, str], bytes],
]


def _default_urllib_transport(
    url: str,
    headers: Mapping[str, str],
) -> tuple[int, Mapping[str, str], bytes]:
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            status_code = int(response.status)
            resp_headers = {k.lower(): v for k, v in response.headers.items()}
            body = response.read()
            return status_code, resp_headers, body
    except HTTPError as error:
        body = error.read() if error.fp is not None else b""
        raise ApiFootballError(
            f"API-Football HTTP {error.code}: {body.decode('utf-8', errors='replace')}"
        ) from error
    except URLError as error:
        raise ApiFootballError(f"API-Football network error: {error.reason}") from error


class ApiFootballClient:
    """Typed client for v3.football.api-sports.io."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: TransportCallable | None = None,
    ) -> None:
        resolved_key = (
            api_key
            if api_key is not None
            else os.getenv("API_FOOTBALL_KEY", "").strip()
        )
        if not resolved_key:
            raise ApiFootballError(
                "API_FOOTBALL_KEY is not configured. Set API_FOOTBALL_KEY in .env "
                "with your api-football.com key."
            )
        self.api_key = resolved_key
        self.base_url = (
            base_url
            or os.getenv("API_FOOTBALL_BASE_URL", DEFAULT_API_FOOTBALL_BASE_URL)
        ).rstrip("/")
        self._transport = transport or _default_urllib_transport
        self.last_requests_remaining: int | None = None
        self.last_requests_limit: int | None = None

    def get_envelope(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> ApiFootballResponse:
        clean_path = "/" + path.lstrip("/")
        query = (
            "?" + urlencode({k: v for k, v in params.items() if v is not None})
            if params
            else ""
        )
        url = f"{self.base_url}{clean_path}{query}"
        headers = {
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        }
        status_code, resp_headers, raw_body = self._transport(url, headers)
        if status_code >= 400:
            raise ApiFootballError(
                f"API-Football returned HTTP {status_code} for {clean_path}"
            )

        lower_headers = {k.lower(): v for k, v in resp_headers.items()}
        remaining = _parse_optional_int(
            lower_headers.get("x-ratelimit-requests-remaining")
        )
        limit = _parse_optional_int(lower_headers.get("x-ratelimit-requests-limit"))
        self.last_requests_remaining = remaining
        self.last_requests_limit = limit

        payload = json.loads(raw_body.decode("utf-8"))
        envelope = ApiFootballEnvelope.model_validate(payload)
        if envelope.errors:
            if isinstance(envelope.errors, dict) and envelope.errors:
                raise ApiFootballError(
                    f"API-Football error response: {envelope.errors}"
                )
            if isinstance(envelope.errors, list) and len(envelope.errors) > 0:
                raise ApiFootballError(
                    f"API-Football error response: {envelope.errors}"
                )

        return ApiFootballResponse(
            envelope=envelope,
            requests_remaining=remaining,
            requests_limit=limit,
        )

    def fetch_fixtures(
        self,
        *,
        league_id: int,
        season_year: int,
    ) -> tuple[list[ApiFootballFixtureItem], int | None]:
        resp = self.get_envelope(
            "/fixtures",
            {"league": league_id, "season": season_year},
        )
        items = [
            ApiFootballFixtureItem.model_validate(row) for row in resp.envelope.response
        ]
        return items, resp.requests_remaining

    def fetch_fixture_statistics(
        self,
        *,
        fixture_id: int,
    ) -> tuple[list[ApiFootballTeamStatisticsItem], int | None]:
        resp = self.get_envelope(
            "/fixtures/statistics",
            {"fixture": fixture_id},
        )
        items = [
            ApiFootballTeamStatisticsItem.model_validate(row)
            for row in resp.envelope.response
        ]
        return items, resp.requests_remaining

    def fetch_odds(
        self,
        *,
        league_id: int | None = None,
        season_year: int | None = None,
        fixture_id: int | None = None,
    ) -> tuple[list[ApiFootballOddsItem], int | None]:
        resp = self.get_envelope(
            "/odds",
            {
                "league": league_id,
                "season": season_year,
                "fixture": fixture_id,
            },
        )
        items = [
            ApiFootballOddsItem.model_validate(row) for row in resp.envelope.response
        ]
        return items, resp.requests_remaining


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
