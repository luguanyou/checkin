from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "mysql+pymysql://attendance:attendance@127.0.0.1:3306/attendance"
    jwt_secret: SecretStr = SecretStr("development-secret-change-before-deploy")
    jwt_algorithm: str = "HS256"
    frontend_origin: str = "https://localhost"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 604800
    refresh_cookie_secure: bool = True
    admin_username: str = "admin"
    admin_display_name: str = "超级管理员"
    admin_password: SecretStr | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
