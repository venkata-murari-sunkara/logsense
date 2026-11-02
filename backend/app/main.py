import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

logger = logging.getLogger("logsense.main")


class NoCacheStaticFiles(StaticFiles):
    """This app's frontend changes on every backend deploy during active
    development; a browser silently serving a stale cached JS/CSS file (no
    error, no visible sign anything's wrong) is a confusing, hard-to-diagnose
    failure mode we've already hit once. Force revalidation on every request
    instead of trusting far-future/default caching heuristics.
    """

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

from app.config import REPO_ROOT
from app.routers import analyses, blocks, chat, evaluations, reports, simulation, stats
from app.services import simulation as simulation_service
from app.services.detector import get_model
from app.services.embeddings import get_embedding_model
from app.services.evaluation import mark_orphaned_runs_failed
from app.services.explanation import get_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load these once, up front, instead of lazily on first use — the
    # evaluation service runs several blocks concurrently, and letting
    # multiple threads race to construct these on first use crashed the
    # process (sentence-transformers/torch isn't safe to initialize from
    # concurrent threads).
    get_model()
    get_embedding_model()
    get_client()
    # This app runs as a single process (see mark_orphaned_runs_failed's
    # docstring) — a "running" row at this exact moment is always a leftover
    # from a previous process, never a real in-progress run of this one.
    orphaned = mark_orphaned_runs_failed()
    if orphaned:
        logger.warning("Marked %d orphaned evaluation run(s) as failed on startup", orphaned)
    yield
    simulation_service.stop()


app = FastAPI(title="LogSense API", lifespan=lifespan)


@app.middleware("http")
async def no_store_api_responses(request, call_next):
    """Static assets already force revalidation (NoCacheStaticFiles above);
    the /api/* JSON responses had no cache directive at all, which some
    browsers can heuristically cache for GETs with no explicit signal.
    Every stat/list endpoint here reflects live, frequently-changing state
    (reviewed_at, analysis counts, simulation status), so never cache them.
    """
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(blocks.router)
app.include_router(analyses.router)
app.include_router(chat.router)
app.include_router(evaluations.router)
app.include_router(reports.router)
app.include_router(simulation.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


frontend_dir = REPO_ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/", NoCacheStaticFiles(directory=frontend_dir, html=True), name="frontend")
