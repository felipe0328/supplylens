from importlib.metadata import version

from fastapi import FastAPI

from supplylens.config import AppEnvironment, get_app_environment
from supplylens.routes.v1.routes import router as v1_router
from supplylens.schemas.common import HealthResponse


def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app(environment: AppEnvironment | None = None) -> FastAPI:
    app_environment = get_app_environment() if environment is None else environment
    app = FastAPI(
        title="SupplyLens API",
        summary="Traceable supplier document ingestion for small retailers.",
        description=(
            "The SupplyLens API manages supplier PDF uploads and document records. "
            "Create an upload intent, upload the PDF to the returned storage URL, "
            "then report completion before requesting a download URL. The health "
            "routes expose process liveness and database readiness."
        ),
        version=version("supplylens"),
        openapi_tags=[
            {
                "name": "Documents",
                "description": (
                    "Create, upload, inspect, download, and delete supplier documents."
                ),
            },
            {
                "name": "Health",
                "description": "Process liveness and database readiness checks.",
            },
        ],
        debug=app_environment is AppEnvironment.DEVELOPMENT,
    )
    app.include_router(v1_router, prefix="/api/v1")
    app.add_api_route(
        "/health",
        health,
        methods=["GET"],
        response_model=HealthResponse,
        summary="Check process liveness",
        description=(
            "Returns a successful response while the API process is running. "
            "This check does not require the database."
        ),
        tags=["Health"],
    )

    return app


app = create_app()
