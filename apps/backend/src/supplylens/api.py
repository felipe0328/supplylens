from fastapi import FastAPI

from supplylens.config import AppEnvironment, get_app_environment
from supplylens.routes.v1.routes import router as v1_router


def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app(environment: AppEnvironment | None = None) -> FastAPI:
    app_environment = get_app_environment() if environment is None else environment
    app = FastAPI(
        title="SupplyLens",
        debug=app_environment is AppEnvironment.DEVELOPMENT,
    )
    app.include_router(v1_router, prefix="/api/v1", tags=["v1"])
    app.add_api_route("/health", health, methods=["GET"])

    return app


app = create_app()
