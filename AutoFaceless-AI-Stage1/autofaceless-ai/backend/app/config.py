from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "AutoFaceless AI"
    database_url: str = "sqlite:///./autofaceless.db"
    jwt_secret: str = "CHANGE-ME-before-deploy-use-a-long-random-secret"
    access_token_minutes: int = 60 * 24
    default_daily_quota: int = 2
    allowed_origins: str = "http://localhost:3000"
    max_upload_mb: int = 100

settings = Settings()
