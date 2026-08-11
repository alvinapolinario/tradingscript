"""News source adapters."""
from app.market_news.providers.base import BaseNewsProvider, NewsProvider, ProviderFetchResult
from app.market_news.providers.manual import ManualNewsProvider
from app.market_news.providers.mt5_calendar import Mt5CalendarProvider
from app.market_news.providers.registry import ProviderRegistry, get_registry

__all__ = [
    "BaseNewsProvider",
    "ManualNewsProvider",
    "Mt5CalendarProvider",
    "NewsProvider",
    "ProviderFetchResult",
    "ProviderRegistry",
    "get_registry",
]
