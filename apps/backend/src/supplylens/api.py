from fastapi import FastAPI

app = FastAPI(title="SupplyLens")

@app.get("/health")
def health() -> dict[str,str]:
    return {"status": "ok"}