from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    public_base_url: str = ""

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_agent_name: str = "mandi-gemini-agent"
    livekit_explicit_dispatch: bool = True
    livekit_room_prefix: str = "mandi-call"

    google_api_key: str = ""
    gemini_live_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    gemini_live_voice: str = "Puck"

    exotel_account_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_subdomain: str = "api.in.exotel.com"
    exotel_caller_id: str = ""
    exotel_ai_caller_id: str = ""
    exotel_agentstream_app_id: str = ""
    exotel_agentstream_flow_url: str = ""
    exotel_status_callback_url: str | None = None

    inbound_sample_rate: int = Field(default=8000, ge=8000)
    livekit_sample_rate: int = Field(default=48000, ge=8000)
    channels: int = 1

    @field_validator("public_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def exotel_calls_url(self) -> str:
        return f"https://{self.exotel_subdomain}/v1/Accounts/{self.exotel_account_sid}/Calls/connect"

    @property
    def agentstream_ws_url(self) -> str:
        if not self.public_base_url:
            return ""
        base = self.public_base_url.replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/ws/exotel/agentstream"

    @property
    def agentstream_dynamic_url(self) -> str:
        if not self.public_base_url:
            return ""
        return f"{self.public_base_url}/exotel/agentstream-url"

    @property
    def agentstream_flow_url(self) -> str:
        if self.exotel_agentstream_flow_url:
            return self.exotel_agentstream_flow_url
        if not self.exotel_agentstream_app_id or self.exotel_agentstream_app_id == "replace-me":
            return ""
        return (
            f"http://my.exotel.com/{self.exotel_account_sid}/exoml/start_voice/"
            f"{self.exotel_agentstream_app_id}"
        )

    @property
    def outbound_ai_caller_id(self) -> str:
        return self.exotel_ai_caller_id or self.exotel_caller_id


@lru_cache
def get_settings() -> Settings:
    return Settings()
