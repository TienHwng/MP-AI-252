"""Web search integrations for HERA."""

from web_search.duckduckgo_client import DuckDuckGoSearchService
from web_search.intent_classifier import SearchIntent, SearchIntentClassifier
from web_search.news_client import NewsAPIService
from web_search.weather_client import OpenWeatherMapService

__all__ = [
	"DuckDuckGoSearchService",
	"NewsAPIService",
	"OpenWeatherMapService",
	"SearchIntent",
	"SearchIntentClassifier",
]
