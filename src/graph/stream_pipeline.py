"""
SSE 流式流水线 — 6 Agent 实时事件推送
"""
import json
import uuid
import structlog
from typing import AsyncGenerator

from src.agents.game_designer import game_designer_agent
from src.agents.narrative_agent import narrative_agent
from src.agents.code_generator import code_generator_agent
from src.agents.code_reviewer import code_reviewer_agent
from src.agents.test_agent import test_agent
from src.agents.art_director import art_director_agent

logger = structlog.get_logger()


def _event(event_type: str, agent: str, data: dict = None) -> str:
    return json.dumps({"type": event_type, "agent": agent, "data": data or {}}, ensure_ascii=False)


async def run_streaming_pipeline(user_request: str, continue_thread: str = None) -> AsyncGenerator[str, None]:
    # 继续模式：加载之前的状态
    prev_context = None
    if continue_thread:
        from src.services.memory import get_session
        prev = get_session(continue_thread)
        if prev:
            prev_context = prev
            prev_design = (prev.get("state") or {}).get("game_design", {})
            prev_title = prev_design.get("title", "") if isinstance(prev_design, dict) else ""
            prev_genre = prev_design.get("genre", "") if isinstance(prev_design, dict) else ""
            user_request = f"[继续: 《{prev_title}》({prev_genre})]\n{user_request}"

    thread_id = continue_thread or str(uuid.uuid4())[:8]
    state: dict = {"raw_input": user_request, "thread_id": thread_id,
                    "messages": [], "errors": [], "loopback_count": 0}

    # ===== Agent 1: Designer =====
    yield _event("agent_start", "designer", {"name": "游戏策划", "desc": "分析需求，生成游戏设计文档..."})
    try:
        r = await game_designer_agent(state); state.update(r)
        d = state.get("game_design", {})
        yield _event("agent_done", "designer", {
            "summary": f"《{d.get('title','?')}》- {d.get('genre','?')} | {d.get('core_mechanic','?')[:60]}",
            "output": d,
        })
    except Exception as e:
        state.setdefault("errors", []).append(f"策划失败: {e}")
        yield _event("agent_error", "designer", {"error": str(e)[:200]})

    # ===== Agent 2: Narrative =====
    yield _event("agent_start", "narrative", {"name": "叙事设计", "desc": "构建世界观与剧情..."})
    try:
        r = await narrative_agent(state); state.update(r)
        n = state.get("narrative", {})
        yield _event("agent_done", "narrative", {
            "summary": f"角色{len(n.get('characters',[]))}个 任务{len(n.get('quest_design',[]))}个",
            "output": n,
        })
    except Exception as e:
        state.setdefault("errors", []).append(f"叙事失败: {e}")
        yield _event("agent_error", "narrative", {"error": str(e)[:200]})

    # ===== Agent 3: CodeGen (生成+验证+修复) =====
    yield _event("agent_start", "codegen", {"name": "代码生成+验证", "desc": "生成代码→编译运行→自动修复..."})
    try:
        r = await code_generator_agent(state); state.update(r)
        c = state.get("code_result", {})
        run_ok = c.get("run_passed", False)
        fixed = c.get("auto_fixed", False)
        yield _event("agent_done", "codegen", {
            "summary": f"代码{'✅ 运行通过' if run_ok else '⚠️ 运行失败'}{' (自动修复' + str(c.get('fix_attempts',0)) + '次)' if fixed else ''}",
            "output": c,
        })
    except Exception as e:
        state.setdefault("errors", []).append(f"代码生成失败: {e}")
        yield _event("agent_error", "codegen", {"error": str(e)[:200]})

    # ===== Agent 4: Reviewer =====
    if state.get("code_result", {}).get("files"):
        yield _event("agent_start", "reviewer", {"name": "代码审查", "desc": "审查代码质量..."})
        try:
            r = await code_reviewer_agent(state); state.update(r)
            rev = state.get("code_review", {})
            yield _event("agent_done", "reviewer", {
                "summary": f"评分{rev.get('score',0)}/100 {'✅' if rev.get('passed') else '⚠️'} {len(rev.get('bugs',[]))}个问题",
                "output": rev,
            })
        except Exception as e:
            state.setdefault("errors", []).append(f"审查失败: {e}")
            yield _event("agent_error", "reviewer", {"error": str(e)[:200]})
    else:
        yield _event("agent_skip", "reviewer", {"reason": "无代码"})

    # ===== Agent 5: Test (pytest生成+执行) =====
    if state.get("code_result", {}).get("files"):
        yield _event("agent_start", "test", {"name": "自动化测试", "desc": "生成pytest→执行→修复..."})
        try:
            r = await test_agent(state); state.update(r)
            t = state.get("test_result", {})
            if t.get("skipped"):
                yield _event("agent_done", "test", {"summary": f"跳过: {t.get('reason','')}", "output": t})
            else:
                yield _event("agent_done", "test", {
                    "summary": f"测试{'✅' if t.get('passed') else '⚠️'} {t.get('summary','')}",
                    "output": t,
                })
        except Exception as e:
            state.setdefault("errors", []).append(f"测试失败: {e}")
            yield _event("agent_error", "test", {"error": str(e)[:200]})
    else:
        yield _event("agent_skip", "test", {"reason": "无代码"})

    # ===== Agent 6: Art (Prompt + 真正出图) =====
    yield _event("agent_start", "art", {"name": "美术总监+出图", "desc": "Prompt生成→Qwen-Image-2.0实际出图..."})
    try:
        r = await art_director_agent(state); state.update(r)
        art = state.get("art_directive", {})
        images = state.get("generated_images", [])
        yield _event("agent_done", "art", {
            "summary": f"色板{len(art.get('color_palette',[]))}色 🖼️实际生成{len(images)}张图",
            "output": art,
            "generated_images": images,
        })
    except Exception as e:
        state.setdefault("errors", []).append(f"美术失败: {e}")
        yield _event("agent_error", "art", {"error": str(e)[:200]})

    # 完成
    yield _event("pipeline_done", "system", {
        "summary": f"6 Agent流水线完成 · {len(state.get('errors',[]))}错误 · 产物: outputs/",
        "full_state": {
            "game_design": state.get("game_design"),
            "narrative": state.get("narrative"),
            "code_result": state.get("code_result"),
            "code_review": state.get("code_review"),
            "test_result": state.get("test_result"),
            "art_directive": state.get("art_directive"),
            "generated_images": state.get("generated_images", []),
            "errors": state.get("errors", []),
            "thread_id": state.get("thread_id"),
        },
    })
