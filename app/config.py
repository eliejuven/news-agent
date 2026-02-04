from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database (SQLite MVP)
    DATABASE_URL: str = "sqlite:///news_agent.db"

    # Placeholder for later (email)
    EMAIL_TO: str = ""
    EMAIL_FROM: str = ""

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""


settings = Settings()