from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings for the Recommendation service.
    Refer https://docs.pydantic.dev/latest/concepts/pydantic_settings/ for more details.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    LOG_LEVEL: str = "DEBUG"
    PROJECT_NAME: str = "Recommendation service"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    API_VERSION: str = "v1"
    COLLECTIONS_NAMESPACE: int = 0
    COLLECTIONS_CATEGORY: str = "Pages including a page collection"
    LANGUAGE_PAIRS_API: AnyUrl = "https://cxserver.wikimedia.org/v2/list/languagepairs"
    CXSERVER_URL: AnyUrl = "https://cxserver.wikimedia.org"
    CXSERVER_HEADER: str | None = "cxserver.wikimedia.org"
    API_CONCURRENCY_LIMIT: int = 10
    LANGUAGE_PAIRS_API_HEADER: str | None = None
    WIKIPEDIA_API: AnyUrl = "https://{source}.wikipedia.org/w/api.php"
    WIKIPEDIA_API_HEADER: str | None = "{source}.wikipedia.org"
    WIKIDATA_API: AnyUrl = "https://www.wikidata.org/w/api.php"
    WIKIDATA_API_HEADER: str | None = "www.wikidata.org"
    WIKIMEDIA_API: AnyUrl = "https://meta.wikimedia.org/w/api.php"
    WIKIMEDIA_API_HEADER: str | None = "meta.wikimedia.org"
    EVENT_LOGGER_API: AnyUrl = "https://intake-analytics.wikimedia.org/v1/events?hasty=true"
    EVENT_LOGGER_API_HEADER: str | None = None
    USER_AGENT_HEADER: str = "WMF Recommendation API (https://recommend.wmcloud.org/; leila@wikimedia.org)"
    CACHE_DIRECTORY: str = ".cache"
    DEBUG: bool = False

    # Article difficulty thresholds (in bytes)
    ARTICLE_EASY_THRESHOLD: int = 5000  # 5 KB - below this is stub, above is easy
    ARTICLE_MEDIUM_THRESHOLD: int = 25000  # 25 KB - above this is medium difficulty
    ARTICLE_HARD_THRESHOLD: int = 75000  # 75 KB - above this is hard difficulty

    # Section difficulty thresholds (in bytes)
    SECTION_EASY_THRESHOLD: int = 1000  # 1 KB - below this is stub, above is easy
    SECTION_MEDIUM_THRESHOLD: int = 3000  # 3 KB - above this is medium difficulty
    SECTION_HARD_THRESHOLD: int = 10000  # 10 KB - above this is hard difficulty


configuration = Settings()
