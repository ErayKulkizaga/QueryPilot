from fastapi import FastAPI

from app import __version__
from app.api.analyses import router as analyses_router
from app.schemas import HealthResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title="QueryPilot Local",
        version=__version__,
        description="Safety-first PostgreSQL execution-plan analysis API.",
    )
    app.include_router(analyses_router)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="querypilot-local",
            version=__version__,
        )

    return app


app = create_app()

