from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flyttsignal.api.router import router


def create_app() -> FastAPI:
    app = FastAPI(title="FlyttSignal API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "PUT"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()
