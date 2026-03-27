from pydantic_settings import BaseSettings, SettingsConfigDict

class My_Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    henrik_api_key: str