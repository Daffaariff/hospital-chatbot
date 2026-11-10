"""App settings loaded from env / .env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

BASE = "https://www.placidway.com"
SOURCE_PAGES = [
    ("clinic_profile", f"{BASE}/profile/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center"),
    ("package", f"{BASE}/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC"),
    ("package", f"{BASE}/package/7902/Alternative-Adrenal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC"),
    ("package", f"{BASE}/package/7901/Alternative-Anal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC"),
    ("videos", f"{BASE}/profile-videos/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center"),
    ("price_list", f"{BASE}/price-list/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center"),
    ("price_comparison", f"{BASE}/search-medical-pricings/Alternative-Medicine/All/1"),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    APP_NAME: str = "PlacidWay Knowledge Bot"
    API_V1_PREFIX: str = "/api/v1"
    API_KEYS: str = ""
    LOG_LEVEL: str = "INFO"

    LLM_PROVIDER: str = "anthropic"  # anthropic | openai
    ANSWER_MODEL: str = "claude-opus-5-5"
    ROUTER_MODEL: str = "claude-haiku-5-5"
    CLAIM_CHECK: bool = True
    CHECK_MODEL: str = "claude-haiku-5-5"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_JSON_MODE: str = "schema"  # schema | object (for models without JSON-schema support)
    LLM_TIMEOUT: float = 60.0
    LLM_MAX_RETRIES: int = 2
    LLM_MAX_CONCURRENCY: int = 8

    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    SPARSE_MODEL: str = "Qdrant/bm25"
    TOP_K: int = 6
    QDRANT_URL: str = ""  # empty = embedded local mode under DATA_DIR/qdrant
    METADATA_FILTERS: bool = True
    RERANK_MODEL: str = "jinaai/jina-reranker-v1-turbo-en"  # empty disables reranking
    RERANK_CANDIDATES: int = 20
    HISTORY_TURNS: int = 6

    USER_AGENT: str = "PlacidWayKnowledgeBot/0.1 (+https://github.com/Daffaariff/hospital-chatbot)"
    CRAWL_DELAY: float = 3.0
    QUOTE_URL: str = "https://www.placidway.com/contact-us"

    DATA_DIR: Path = ROOT / "data"
    SNAPSHOT_DIR: Path = ROOT / "snapshot"

    STT_PROVIDER: str = "deepgram"
    TTS_PROVIDER: str = "cartesia"
    DEEPGRAM_API_KEY: str = ""
    CARTESIA_API_KEY: str = ""
    CARTESIA_VOICE_ID: str = ""

    @property
    def api_keys(self) -> set[str]:
        return {k.strip() for k in self.API_KEYS.split(",") if k.strip()}


settings = Settings()
