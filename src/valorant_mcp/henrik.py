import asyncio
import time

import httpx

from .cache import MatchCache
from .models import MMR, Account, Match, MMRHistoryEntry

PAGE_SIZE = 10  # v4/matches caps size at 10; deeper history uses `start`
MAX_RETRY_WAIT_S = 20
LIST_TTL_S = 300


class HenrikAPIError(Exception):
    pass


def parse_username(username: str) -> tuple[str, str]:
    name, sep, tag = username.strip().rpartition("#")
    if not sep or not name or not tag:
        raise ValueError(f"Expected a Riot ID like 'name#TAG', got {username!r}")
    return name, tag


class HenrikClient:
    def __init__(self, api_key: str, base_url: str = "https://api.henrikdev.xyz/valorant",
                 region: str = "na", platform: str = "pc", cache: MatchCache | None = None):
        self.base_url = base_url.rstrip("/")
        self.region = region
        self.platform = platform
        self.cache = cache
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": api_key},
            timeout=30.0,
        )
        # (name, tag, region, mode, map) -> (fetched_at, matches newest first)
        self._lists: dict[tuple, tuple[float, list[Match]]] = {}

    async def aclose(self):
        await self._http.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        attempt = 0
        while True:
            response = await self._http.get(path, params=params)
            if response.status_code != 429:
                return _check_response(response)
            wait = _retry_after(response)
            attempt += 1
            if attempt >= 3 or wait > MAX_RETRY_WAIT_S:
                raise HenrikAPIError(
                    f"Rate limited by Henrik API. Try again in ~{wait:.0f}s "
                    "(or use a smaller match count)."
                )
            await asyncio.sleep(wait)

    async def get_account(self, username: str) -> Account:
        name, tag = parse_username(username)
        body = await self._get(f"/v2/account/{name}/{tag}")
        return Account(**body["data"])

    async def get_mmr(self, username: str, region: str | None = None) -> MMR:
        name, tag = parse_username(username)
        body = await self._get(f"/v3/mmr/{region or self.region}/{self.platform}/{name}/{tag}")
        return MMR(**body["data"])

    async def get_mmr_history(self, username: str, count: int,
                              region: str | None = None) -> list[MMRHistoryEntry]:
        # The stored endpoint reaches further back than the live one.
        name, tag = parse_username(username)
        body = await self._get(
            f"/v2/stored-mmr-history/{region or self.region}/{self.platform}/{name}/{tag}",
            {"size": count, "page": 1},
        )
        return [MMRHistoryEntry(**e) for e in body["data"]]

    async def get_matches(self, username: str, count: int, mode: str | None = "competitive",
                          map_name: str | None = None, region: str | None = None) -> list[Match]:
        """Recent full v4 matches, newest first. Pages through v4/matches 10 at a time."""
        name, tag = parse_username(username)
        region = region or self.region
        key = (name.lower(), tag.lower(), region, mode, (map_name or "").lower())

        cached = self._lists.get(key)
        if cached and time.monotonic() - cached[0] < LIST_TTL_S and len(cached[1]) >= count:
            return cached[1][:count]

        matches: list[Match] = []
        seen: set[str] = set()
        start = 0
        while len(matches) < count:
            body = await self._get(
                f"/v4/matches/{region}/{self.platform}/{name}/{tag}",
                {"mode": mode, "map": map_name, "size": PAGE_SIZE, "start": start},
            )
            page = body["data"]
            for raw in page:
                if self.cache:
                    self.cache.put(raw)
                match = Match(**raw)
                if match.metadata.match_id not in seen:
                    seen.add(match.metadata.match_id)
                    matches.append(match)
            if len(page) < PAGE_SIZE:
                break
            start += PAGE_SIZE

        self._lists[key] = (time.monotonic(), matches)
        return matches[:count]

    async def get_match(self, match_id: str, region: str | None = None) -> Match:
        if self.cache and (raw := self.cache.get(match_id)):
            return Match(**raw)
        body = await self._get(f"/v4/match/{region or self.region}/{match_id}")
        if self.cache:
            self.cache.put(body["data"])
        return Match(**body["data"])


def _retry_after(response: httpx.Response) -> float:
    for header in ("Retry-After", "X-RateLimit-Reset"):
        value = response.headers.get(header)
        if value:
            try:
                return max(1.0, float(value))
            except ValueError:
                pass
    return 5.0


def _check_response(response: httpx.Response) -> dict:
    if response.status_code == 200:
        body = response.json()
        if "data" not in body:
            raise HenrikAPIError(f"Unexpected API response: {str(body)[:200]}")
        return body
    try:
        errors = response.json().get("errors") or []
        message = "; ".join(e.get("message", "") for e in errors) or response.text[:200]
    except ValueError:
        message = response.text[:200]
    if response.status_code == 404:
        raise HenrikAPIError(f"Not found: {message}. Check the Riot ID, region and platform.")
    raise HenrikAPIError(f"Henrik API error (status {response.status_code}): {message}")
