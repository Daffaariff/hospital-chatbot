"""FastAPI app."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.adapters.factory import get_llm
from app.api.v1.router import api_router
from app.core.config import ROOT, settings
from app.core.logging import get_logger, setup_logging
from app.ingest.__main__ import run_ingest
from app.services.chat_service import ChatService
from app.services.index import KnowledgeIndex
from app.services.store import Store

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    index = KnowledgeIndex()
    # NOTE: sync with the committed snapshot on every start; re-embeds only if parsed content changed.
    # Live crawling is an explicit refresh (Cloudflare blocks datacenter IPs).
    run_ingest(index=index, offline=True)
    store = Store()
    app.state.index, app.state.store = index, store
    app.state.chat = ChatService(get_llm(), index, store)
    log.info(f"ready: {len(index.chunks)} chunks, llm={settings.LLM_PROVIDER}")
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
