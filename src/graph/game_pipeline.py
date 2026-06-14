"""
LangGraph 多 Agent 流水线编排器 (6 Agents)
流程: Input → Designer → Narrative → CodeGen → Reviewer → Test → Art → END
"""
import uuid
import structlog
from typing import Literal
from langgraph.graph import StateGraph, END

from src.graph.state import GameDevState
from src.agents.game_designer import game_designer_agent
from src.agents.narrative_agent import narrative_agent
from src.agents.code_generator import code_generator_agent
from src.agents.code_reviewer import code_reviewer_agent
from src.agents.test_agent import test_agent
from src.agents.art_director import art_director_agent
from src.config.settings import settings

logger = structlog.get_logger()


async def node_input(state: GameDevState) -> dict:
    tid = state.thread_id or str(uuid.uuid4())[:8]
    logger.info("pipeline_start", thread_id=tid)
    return {"thread_id": tid}


async def node_designer(state: GameDevState) -> dict:
    return await game_designer_agent(state.model_dump())


async def node_narrative(state: GameDevState) -> dict:
    return await narrative_agent(state.model_dump())


async def node_codegen(state: GameDevState) -> dict:
    return await code_generator_agent(state.model_dump())


async def node_reviewer(state: GameDevState) -> dict:
    return await code_reviewer_agent(state.model_dump())


async def node_test(state: GameDevState) -> dict:
    return await test_agent(state.model_dump())


async def node_art_director(state: GameDevState) -> dict:
    return await art_director_agent(state.model_dump())


def should_regenerate(state: GameDevState) -> Literal["codegen", "test"]:
    needs = state.needs_regeneration
    count = state.loopback_count
    if needs and count < settings.MAX_LOOPBACKS:
        logger.info("pipeline_loopback", count=count + 1)
        return "codegen"
    return "test"


def should_run_art(state: GameDevState) -> Literal["art_director", "__end__"]:
    """美术生成前置条件：Designer/Narrative/CodeGen/Test 必须成功；Reviewer 允许循环耗尽后强制通过"""
    design = state.game_design or {}
    narrative = state.narrative or {}
    code_result = state.code_result or {}
    code_review = state.code_review or {}
    test_result = state.test_result or {}
    loopback_exhausted = state.loopback_count >= settings.MAX_LOOPBACKS

    failed = []
    if not design.get("title"):
        failed.append("策划未产出有效设计")
    if not narrative.get("characters"):
        failed.append("叙事未产出角色")
    if not code_result.get("run_passed"):
        failed.append("代码未通过运行验证")
    # Reviewer：循环耗尽时允许通过（已有警告标记），否则必须 passed
    if not loopback_exhausted and not code_review.get("passed"):
        failed.append(f"代码审查未通过(score={code_review.get('score','?')})")
    if not test_result.get("passed") and not test_result.get("skipped"):
        failed.append("自动化测试未通过")

    if failed:
        logger.info("art_prerequisite_skip", reasons=failed)
        return END
    logger.info("art_prerequisite_pass")
    return "art_director"


def build_pipeline() -> StateGraph:
    workflow = StateGraph(GameDevState)

    workflow.add_node("input", node_input)
    workflow.add_node("designer", node_designer)
    workflow.add_node("narrative", node_narrative)
    workflow.add_node("codegen", node_codegen)
    workflow.add_node("reviewer", node_reviewer)
    workflow.add_node("test", node_test)
    workflow.add_node("art_director", node_art_director)

    workflow.set_entry_point("input")
    workflow.add_edge("input", "designer")
    workflow.add_edge("designer", "narrative")
    workflow.add_edge("narrative", "codegen")
    workflow.add_edge("codegen", "reviewer")
    workflow.add_conditional_edges("reviewer", should_regenerate,
                                    {"codegen": "codegen", "test": "test"})
    # Test 之后加条件分支：全部前置通过才进 Art，否则直接结束
    workflow.add_conditional_edges("test", should_run_art, {
        "art_director": "art_director",
        END: END,
    })
    workflow.add_edge("art_director", END)

    return workflow


pipeline = build_pipeline().compile()


async def run_game_dev_pipeline(user_request: str, continue_thread: str = None) -> dict:
    # 如果是继续模式，加载之前的状态
    prev_context = None
    if continue_thread:
        from src.services.memory import get_session
        prev = get_session(continue_thread)
        if prev and prev.get("state"):
            prev_context = prev
            logger.info("pipeline_continue", thread_id=continue_thread, title=prev.get("game_title"))

    tid = continue_thread or str(uuid.uuid4())[:8]
    initial_state = GameDevState(
        raw_input=user_request, thread_id=tid,
        messages=[], errors=[], loopback_count=0,
    )

    # 如果有之前的上下文，注入到 raw_input
    if prev_context:
        prev_state = prev_context["state"]
        prev_design = prev_state.get("game_design", {})
        prev_title = prev_design.get("title", "") if isinstance(prev_design, dict) else ""
        prev_genre = prev_design.get("genre", "") if isinstance(prev_design, dict) else ""
        initial_state.raw_input = (
            f"[继续之前的游戏: 《{prev_title}》({prev_genre})]\n{user_request}"
        )

    logger.info("pipeline_run_start", thread_id=tid)
    final_state = await pipeline.ainvoke(initial_state)
    if hasattr(final_state, 'model_dump'):
        result = final_state.model_dump()
        errors = final_state.errors
    else:
        result = final_state
        errors = result.get("errors", [])

    logger.info("pipeline_run_complete", thread_id=tid, errors=len(errors))
    return result
