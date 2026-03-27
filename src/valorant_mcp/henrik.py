import httpx

from .models import (
    MMRData,
    PlayerInfo,
    MatchData,
    V4MatchData
)


class HenrikAPIError(Exception):
    pass


class HenrikClient():
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://api.henrikdev.xyz/valorant'

    def _parse_username(self, username: str):
        name, tag = username.split("#")
        return name, tag

    def _check_response(self, response: httpx.Response):
        if response.status_code == 429:
            raise HenrikAPIError("Rate limited by Henrik API. Please wait a moment and try again.")
        if response.status_code == 404:
            raise HenrikAPIError("Player not found. Check the username and tag.")
        if response.status_code != 200:
            raise HenrikAPIError(f"Henrik API error (status {response.status_code}): {response.text[:200]}")
        body = response.json()
        if "data" not in body:
            raise HenrikAPIError(f"Unexpected API response: {str(body)[:200]}")
        return body["data"]

    async def get_player_info(self, username: str):
        name, tag = self._parse_username(username)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/account/{name}/{tag}",
                headers={"Authorization": self.api_key}
            )
            data = self._check_response(response)
            return PlayerInfo(**data)

    async def get_match_history(self, username: str, region: str, count: int, mode: str = "competitive"):
        name, tag = self._parse_username(username)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v3/matches/{region}/{name}/{tag}?mode={mode}&size={count}",
                headers={"Authorization": self.api_key}
            )
            data = self._check_response(response)
            return [MatchData(**match) for match in data]

    async def get_mmr(self, username: str, region: str):
        name, tag = self._parse_username(username)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v2/mmr/{region}/{name}/{tag}",
                headers={"Authorization": self.api_key}
            )
            data = self._check_response(response)
            return MMRData(**data)

    async def get_match(self, region: str, match_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v4/match/{region}/{match_id}",
                headers={"Authorization": self.api_key}
            )
            data = self._check_response(response)
            return V4MatchData(**data)
