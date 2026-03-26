import httpx

from .models import (
    MMRData,
    PlayerInfo,
    MatchData,
    V4MatchData
)

class HenrikClient():
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://api.henrikdev.xyz/valorant'

    def _parse_username(self, username: str):
        name, tag = username.split("#")
        return name, tag

    async def get_player_info(self, username: str):
        name, tag = self._parse_username(username)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v1/account/{name}/{tag}",
                headers={"Authorization": self.api_key}
            )
            data = response.json()["data"]
            return PlayerInfo(**data)

    async def get_match_history(self, username: str, region: str, count: int):
        name, tag = self._parse_username(username)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v3/matches/{region}/{name}/{tag}?mode=competitive&size={count}",
                headers={"Authorization": self.api_key}
            )
            matches = response.json()["data"]
            return [MatchData(**match) for match in matches]

    async def get_mmr(self, username: str, region: str):
        name, tag = self._parse_username(username)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v2/mmr/{region}/{name}/{tag}",
                headers={"Authorization": self.api_key}
            )
            mmr_results = response.json()["data"]
            return MMRData(**mmr_results)

    async def get_match(self, region: str, match_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v4/match/{region}/{match_id}",
                headers={"Authorization": self.api_key}
            )
            data = response.json()["data"]
            return V4MatchData(**data)
