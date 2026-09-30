from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AlphaNumeric B2B Platform"
    environment: str = "development"
    database_url: str = "sqlite:///./alphanumeric.db"
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    allowed_origins: str = "http://localhost:5173"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_name: str = "System Administrator"
    company_name: str = "AlphaNumeric"
    company_gstin: str = ""
    company_pan: str = ""
    company_address: str = ""
    company_phone: str = ""
    company_email: str = ""
    company_logo_path: str | None = None
    brand_primary: str = "#0B2E59"
    brand_accent: str = "#1268DC"
    bank_name: str = ""
    bank_account_name: str = ""
    bank_account_number: str = ""
    bank_ifsc: str = ""
    media_root: str = "./media"
    media_max_bytes: int = 8 * 1024 * 1024
    media_max_files_per_product: int = 12
    media_storage_provider: str = "local"
    google_drive_client_id: str | None = None
    google_drive_client_secret: str | None = None
    google_drive_refresh_token: str | None = None
    google_drive_root_folder_id: str | None = None
    google_drive_root_folder_name: str = "AlphaNumeric Quotation"
    google_drive_quota_warning_percent: int = 90
    external_import_allowed_domains: str = "arcotindia.com,www.arcotindia.com"
    public_app_url: str = "http://localhost:5173"
    invitation_expiry_hours: int = 24
    email_backend: str = "console"
    email_file_dir: str = "./media/email"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from: str = "noreply@alphanumeric.local"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]


@lru_cache

def get_settings() -> Settings:
    return Settings()


settings = get_settings()
