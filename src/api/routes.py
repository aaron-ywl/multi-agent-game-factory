"""
FastAPI 路由 — Game AI Agent
SSE 流式 + REST + Milvus RAG + Memory
"""
import json
import structlog
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.graph.game_pipeline import run_game_dev_pipeline
from src.graph.stream_pipeline import run_streaming_pipeline
from src.services.vector_rag_service import vector_rag
from src.services.memory import (
    list_sessions, get_session,
    save_session, generate_summary, auto_feedback_to_knowledge,
)
from src.config.settings import settings
from src.skills.game_tools import (
    calculate_game_balance, validate_code_syntax,
    enhance_art_prompt, generate_asset_checklist,
)
from src.skills.setup import register_all_skills
from src.skills.registry import list_skills

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1", tags=["game-ai"])

# 临时缓存：流水线完成后暂存 state，等用户手动保存
_pending: dict[str, dict] = {}


def _cache(state: dict):
    tid = state.get("thread_id", "")
    if tid:
        _pending[tid] = state
        if len(_pending) > 10:
            _pending.pop(next(iter(_pending)))


# ============ 模型 ============
class GameDevRequest(BaseModel):
    requirement: str = Field(..., min_length=3)
    genre_hint: Optional[str] = None
    continue_thread: Optional[str] = None

class BalanceRequest(BaseModel):
    base_attack: float = 10.0; base_defense: float = 5.0
    health: float = 100.0; level: int = 1
    scaling_factor: float = 0.1; target_ttk: float = 10.0

class CodeValidateRequest(BaseModel):
    code: str = Field(..., min_length=1); language: str = "python"

class ArtPromptRequest(BaseModel):
    base_prompt: str = Field(..., min_length=1); style: str = "realistic"

class AssetChecklistRequest(BaseModel):
    genre: str = "RPG"; key_features: list[str] = []; art_style: str = ""


# ============ 核心流水线 ============
@router.post("/generate")
async def generate_game(req: GameDevRequest):
    register_all_skills()
    try:
        state = await run_game_dev_pipeline(req.requirement, req.continue_thread)
        _cache(state)
        design = state.get("game_design", {})
        review = state.get("code_review", {})
        parts = []
        if design: parts.append(f"《{design.get('title','')}》({design.get('genre','')})")
        if review: parts.append(f"评分:{review.get('score',0)}/100")
        return {
            "thread_id": state.get("thread_id", ""),
            "game_design": design or None, "narrative": state.get("narrative"),
            "code_result": state.get("code_result"), "code_review": review or None,
            "test_result": state.get("test_result"), "art_directive": state.get("art_directive"),
            "generated_images": state.get("generated_images", []),
            "errors": state.get("errors", []),
            "saved": False,
            "summary": " | ".join(parts) if parts else "完成",
        }
    except Exception as e:
        logger.error("pipeline_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-stream")
async def generate_game_stream(req: GameDevRequest):
    register_all_skills()
    async def gen():
        try:
            async for evt in run_streaming_pipeline(req.requirement, req.continue_thread):
                if '"type": "pipeline_done"' in evt:
                    try:
                        d = json.loads(evt)
                        fs = d.get("data", {}).get("full_state", {})
                        if fs:
                            _cache(fs)
                    except json.JSONDecodeError:
                        pass
                yield f"data: {evt}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','data':{'error':str(e)[:200]}},ensure_ascii=False)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})


# ============ 工具 ============
@router.post("/tools/balance")
async def tool_balance(req: BalanceRequest):
    return calculate_game_balance(req.model_dump())

@router.post("/tools/validate-code")
async def tool_validate_code(req: CodeValidateRequest):
    return validate_code_syntax(req.code, req.language)

@router.post("/tools/enhance-prompt")
async def tool_enhance_prompt(req: ArtPromptRequest):
    return {"enhanced_prompt": enhance_art_prompt(req.base_prompt, req.style)}

@router.post("/tools/asset-checklist")
async def tool_asset_checklist(req: AssetChecklistRequest):
    return generate_asset_checklist({"genre":req.genre,"key_features":req.key_features,"art_style":req.art_style})

@router.get("/tools/skills")
async def get_skills():
    register_all_skills()
    return {"skills": list_skills()}


# ============ 知识库 ============
@router.get("/vector/stats")
async def vector_stats():
    return {"document_count": vector_rag.document_count, "backend": "Milvus Lite",
            "collection": "game_dev_knowledge",
            "dim": settings.EMBEDDING_DIM, "embedding_model": settings.EMBEDDING_MODEL}

@router.post("/vector/reindex")
async def reindex_knowledge():
    vector_rag.reindex()
    count = vector_rag.index_pdf_directory(settings.KNOWLEDGE_PDF_DIR)
    return {"status": "ok", "reindexed": True, "pdf_chunks": count}

@router.post("/vector/index-pdfs")
async def index_all_pdfs():
    count = vector_rag.index_pdf_directory(settings.KNOWLEDGE_PDF_DIR)
    return {"status": "ok", "indexed_chunks": count}


# ============ 会话 ============
@router.get("/sessions")
async def api_list_sessions(limit: int = 15):
    return {"sessions": list_sessions(limit)}

@router.get("/sessions/{thread_id}")
async def api_get_session(thread_id: str):
    s = get_session(thread_id)
    if not s: raise HTTPException(status_code=404, detail="会话不存在")
    return s

@router.post("/sessions/{thread_id}/save")
async def api_save_session(thread_id: str):
    """用户手动保存"""
    state = _pending.pop(thread_id, None)
    if not state:
        raise HTTPException(status_code=404, detail="未找到待保存的会话")
    try:
        save_session(state)
        import asyncio
        asyncio.create_task(generate_summary(thread_id))
        asyncio.create_task(auto_feedback_to_knowledge())
        return {"status": "ok", "saved": True, "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)[:100]}")

@router.post("/sessions/{thread_id}/discard")
async def api_discard_session(thread_id: str):
    """用户丢弃"""
    _pending.pop(thread_id, None)
    return {"status": "ok", "discarded": True}


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "game-ai-agent"}
