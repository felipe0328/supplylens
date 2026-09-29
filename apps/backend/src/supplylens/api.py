from fastapi import FastAPI
from supplylens.routes.v1.routes import router as v1_router

app = FastAPI(title="SupplyLens")

app.include_router(v1_router, prefix="/v1", tags=["v1"])

@app.get("/health")
def health() -> dict[str,str]:
    return {"status": "ok"}