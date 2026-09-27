import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core import http
from app.geo import ais
from app.geo.router import router as geo_router
from app.metadata.router import router as metadata_router
from app.recon.router import router as recon_router
from app.settings_router import router as settings_router
from app.tools.router import router as tools_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await ais.stop()
    await http.close()


def create_app() -> FastAPI:
    app = FastAPI(title="OSINT Dashboard", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Map layers (cables alone is several MB) and the tool catalog compress ~5-10x. SSE is excluded.
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    for r in (recon_router, geo_router, metadata_router, tools_router, settings_router):
        app.include_router(r)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    # Serve the production build of the frontend if a complete one exists (npm run build).
    # A half-written dist (interrupted build) must not stop the API from starting.
    if (FRONTEND_DIST / "index.html").is_file() and (FRONTEND_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
