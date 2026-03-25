from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SLG AI Game API"
    debug: bool = False

    database_url: str = "postgresql+psycopg://slg:slg@db:5432/slgdb"

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    turn_token_budget: int = 20000
    turn_output_max_tokens: int = 2500

    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
