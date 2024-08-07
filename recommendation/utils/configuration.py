from pydantic import AnyUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuration settings for the Recommendation service.
    Refer https://docs.pydantic.dev/latest/concepts/pydantic_settings/ for more details.
    """

    LOG_LEVEL: str = "DEBUG"
    PROJECT_NAME: str = "Recommendation service"
    PROJECT_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    API_VERSION: str = "v1"
    LANGUAGE_PAIRS_API: AnyUrl = "https://cxserver.wikimedia.org/v1/languagepairs"
    CXSERVER_URL: AnyUrl = "https://cxserver.wikimedia.org"
    CXSERVER_HEADER: str | None = None
    LANGUAGE_PAIRS_API_HEADER: str | None = None
    WIKIPEDIA_API: AnyUrl = "https://{source}.wikipedia.org/w/api.php"
    WIKIPEDIA_API_HEADER: str | None = None
    EVENT_LOGGER_API: AnyUrl = "https://intake-analytics.wikimedia.org/v1/events?hasty=true"
    EVENT_LOGGER_API_HEADER: str | None = None
    USER_AGENT_HEADER: str = "WMF Recommendation API (https://recommend.wmflabs.org/; leila@wikimedia.org)"


configuration = Settings()
