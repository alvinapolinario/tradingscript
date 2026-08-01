"""Application configuration — local secrets only, no broker hard-coding."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Vantage MT5 AI Decision Assistant Backend"
    host: str = "127.0.0.1"
    port: int = 8000
    # Public URL used in health/heartbeat links + CORS (no trailing slash)
    public_base_url: str = "http://187.77.142.118:8000"
    local_api_token: str = "local-dev-token-change-me"
    max_response_age_seconds: int = 120
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-sol"
    use_llm: bool = False

    # Position equity-risk severity bands (% of equity at SL)
    risk_low_max_pct: float = 1.0          # < 1% = LOW
    risk_moderate_max_pct: float = 2.0     # < 2% = MODERATE
    risk_high_max_pct: float = 5.0         # < 5% = HIGH
    risk_very_high_max_pct: float = 10.0   # < 10% = VERY_HIGH; else CRITICAL
    # Max allowed open-position equity risk before CRITICAL warning
    max_position_risk_pct: float = 2.0
    # Warn when floating profit reaches this % of equity (take-profit discipline)
    float_profit_target_pct: float = 10.0
    rsi_exhaust: float = 32.0

    # Telegram Bot alerts (backend only — never in EA)
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_cooldown_sec: int = 300

    # Discord webhook alerts (backend only)
    discord_enabled: bool = False
    discord_webhook_url: str | None = None
    discord_cooldown_sec: int = 300
    # When true: Discord only gets actionable trade setups (no WATCH / entry / module noise)
    discord_trades_only: bool = False
    discord_trades_min_swing_conf: float = 72.0

    # Alert category toggles (Telegram + Discord when each is enabled)
    telegram_alert_risk: bool = True
    telegram_alert_float_target: bool = True
    telegram_alert_entry: bool = True
    telegram_alert_signals: bool = True
    telegram_alert_swing: bool = True
    telegram_alert_liquidity_grab: bool = True
    telegram_alert_gold_smc: bool = True
    telegram_alert_execution: bool = True
    telegram_gold_smc_min_score: float = 75.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
