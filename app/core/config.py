from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NIRA"
    env: str = "development"

    gemini_api_key: str = ""
    google_application_credentials: str = ""

    database_url: str = "sqlite:///./nira.db"

    n8n_webhook_url: str = ""

    # LLM settings
    llm_enabled: bool = True
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash-lite"
    llm_timeout_seconds: float = 6.0

    # Gemini / Vertex settings
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"

    # Groq settings
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()