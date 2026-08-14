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
    discord_trades_min_amd_ifvg_conf: float = 75.0

    # Demo executor — set true only when intentionally enabling live account fills
    execution_allow_live: bool = False

    # Alert category toggles (Telegram + Discord when each is enabled)
    telegram_alert_risk: bool = True
    telegram_alert_float_target: bool = True
    telegram_alert_entry: bool = True
    telegram_alert_signals: bool = True
    telegram_alert_swing: bool = True
    telegram_alert_liquidity_grab: bool = True
    telegram_alert_gold_smc: bool = True
    telegram_alert_amd_ifvg: bool = True
    telegram_alert_box_theory: bool = True
    telegram_alert_execution: bool = True
    telegram_gold_smc_min_score: float = 75.0

    # Box Theory — dedicated Discord webhook (analysis only)
    discord_box_webhook_url: str | None = None
    discord_box_alerts_enabled: bool = False
    # Comma-separated BoxEvent names; empty = BUY_CONFIRMED,SELL_CONFIRMED,BULL_TRAP,BEAR_TRAP
    discord_box_alert_events: str = ""

    # ICT Strategy — dedicated Discord webhook (state-change alerts only)
    discord_ict_webhook_url: str | None = None
    discord_ict_alerts_enabled: bool = False
    discord_ict_min_confidence: float = 75.0
    discord_ict_cooldown_sec: int = 300
    # Comma-separated setup states; empty = LIQUIDITY_SWEPT,MSS_CONFIRMED,ENTRY_ZONE_ACTIVE,TRIGGERED,INVALIDATED,TARGET_REACHED
    discord_ict_alert_events: str = ""

    # H4→M15 FVG — dedicated Discord webhook (ENTRY_READY advisory)
    discord_h4_m15_fvg_webhook_url: str | None = None
    discord_h4_m15_fvg_alerts_enabled: bool = False
    discord_h4_m15_fvg_min_score: float = 50.0
    discord_h4_m15_fvg_cooldown_sec: int = 300
    discord_h4_m15_fvg_alert_events: str = ""

    # Multi-strategy confluence engine (master verdict enhancement)
    confluence_enabled: bool = False
    confluence_freshness_threshold_sec: float = 900.0
    confluence_stale_weight_factor: float = 0.5
    confluence_min_agreeing_strong: int = 2
    confluence_min_confidence_strong: float = 78.0
    confluence_min_confidence_setup: float = 62.0
    confluence_conflict_penalty: float = 18.0
    confluence_macro_weight: float = 0.35

    # Market news / macro intelligence (Step 3+)
    market_news_enabled: bool = True
    market_news_ai_enabled: bool = False
    news_risk_high_before: int = 30
    news_risk_high_after: int = 15
    central_bank_seed_path: str = ""

    # Discord macro / news alerts (Step 12)
    discord_macro_alerts_enabled: bool = False
    discord_macro_webhook_url: str | None = None
    discord_macro_cooldown_sec: int = 300
    discord_macro_approach_minutes: str = "15,30"
    discord_macro_alignment_min_confidence: float = 65.0

    # External news providers (Step 13)
    market_news_rss_enabled: bool = False
    market_news_rss_feeds: str = ""
    market_news_api_enabled: bool = False
    newsapi_key: str | None = None
    newsapi_query: str = "forex OR gold OR federal reserve OR CPI OR FOMC"
    market_news_external_fetch_timeout_sec: float = 15.0
    # Comma-separated macro desk watchlist (default: gold + major FX)
    market_news_major_pairs: str = "XAUUSD,EURUSD,USDJPY"
    # FXSTREET_API_KEY=  # reserved for future licensed adapter


@lru_cache
def get_settings() -> Settings:
    return Settings()
