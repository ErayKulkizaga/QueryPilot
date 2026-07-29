from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.analyses import router as analyses_router
from app.api.baselines import router as baselines_router
from app.api.workload import router as workload_router
from app.reporting import shutdown_reporting_service
from app.schemas import HealthResponse


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    shutdown_reporting_service()


def create_app() -> FastAPI:
    app = FastAPI(
        title="QueryPilot Local",
        version=__version__,
        description="Safety-first PostgreSQL execution-plan analysis API.",
        lifespan=lifespan,
    )
    app.include_router(analyses_router)
    app.include_router(baselines_router)
    app.include_router(workload_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="querypilot-local",
            version=__version__,
        )

    return app


app = create_app()
