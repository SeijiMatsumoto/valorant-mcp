from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    henrik_api_key: str
    # Set to https://beta.api.henrikdev.xyz/valorant to get the 4.10 beta fields
    # (performance ratings, MVPs, first blood). Analysis works without them.
    henrik_base_url: str = "https://api.henrikdev.xyz/valorant"
    valorant_region: str = "na"
    valorant_platform: str = "pc"
    cache_dir: Path = Path.home() / ".cache" / "valorant-mcp"
