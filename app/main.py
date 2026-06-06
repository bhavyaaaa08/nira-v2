from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.call_routes import router as call_router
from app.api.voice_ws_routes import router as voice_ws_router
from app.db.database import init_db

from app.services.operations_store import operations_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    operations_store.init_db()
    yield


app = FastAPI(
    title="NIRA v2 API",
    description="Multi-agent real-time voice intelligence platform for banking customer operations.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root() -> dict:
    return {
        "app": "NIRA v2",
        "status": "running",
        "description": "Neural Intelligence for Risk & Assistance",
    }


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "healthy",
    }


app.include_router(call_router)
app.include_router(voice_ws_router)