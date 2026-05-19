from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NIRA"
    env: str = "development"

    gemini_api_key: str = ""
    google_application_credentials: str = ""

    database_url: str = "sqlite:///./nira.db"

    n8n_webhook_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()