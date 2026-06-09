"""FastAPI 应用入口"""
import structlog
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.api.routes import router
from src.skills.setup import register_all_skills

logger = structlog.get_logger()
STATIC_DIR = Path(__file__).parent.parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Game AI Agent",
        description="多 Agent 协作游戏开发 AI 工具链",
        version="2.0.0",
        docs_url=None, redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(router)

    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.on_event("startup")
    async def startup():
        register_all_skills()
        logger.info("game_ai_agent_started")

    return app


app = create_app()
