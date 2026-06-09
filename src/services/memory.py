"""
三层 Memory 系统 — SQLite 持久化 + 自动摘要 + 产物反哺
==================================================
Layer 1: 对话记忆 — SQLite sessions 表存储每次流水线产物
Layer 2: 工作记忆 — State 序列化/反序列化（跨请求恢复）
Layer 3: 长期记忆 — 通过的代码自动入库 Milvus
"""
import json
import sqlite3
import time
import hashlib
import structlog
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.services.llm_client import llm_client

logger = structlog.get_logger()

DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "sessions.db")

# ============================================
# 数据库初始化
# ============================================

def _get_conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            thread_id    TEXT PRIMARY KEY,
            summary      TEXT DEFAULT '',
            raw_input    TEXT DEFAULT '',
            game_title   TEXT DEFAULT '',
            game_genre   TEXT DEFAULT '',
            game_type    TEXT DEFAULT '',
            code_passed  INTEGER DEFAULT 0,
            test_passed  INTEGER DEFAULT 0,
            test_count   TEXT DEFAULT '0/0',
            image_count  INTEGER DEFAULT 0,
            error_count  INTEGER DEFAULT 0,
            token_usage  INTEGER DEFAULT 0,
            state_json   TEXT DEFAULT '{}',
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_feedback (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id    TEXT,
            content      TEXT,
            content_hash TEXT UNIQUE,
            source       TEXT,
            quality      REAL DEFAULT 0.5,
            created_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    logger.info("memory_db_ready", path=DB_PATH)


# ============================================
# 会话 CRUD
# ============================================

def save_session(state: dict):
    """保存/更新一个会话（只存有实质产出的）"""
    design = state.get("game_design", {}) or {}
    code_result = state.get("code_result", {}) or {}

    # 质量门槛：没有设计产出就不存
    if not design or not design.get("title"):
        logger.info("session_skipped", reason="无有效设计产出")
        return

    conn = _get_conn()
    test_result = state.get("test_result", {}) or {}

    thread_id = state.get("thread_id", "unknown")
    game_title = design.get("title", "")
    game_genre = design.get("genre", "")
    game_type = code_result.get("game_type", "")
    code_passed = 1 if code_result.get("run_passed") else 0
    test_passed = 1 if test_result.get("passed") else 0
    test_count = f"{test_result.get('passed_count',0)}/{test_result.get('failed_count',0)}"
    image_count = len(state.get("generated_images", []))
    error_count = len(state.get("errors", []))
    raw_input = state.get("raw_input", "")

    # 序列化 State（跳过不可序列化的字段）
    state_copy = {}
    for k, v in state.items():
        if k == "messages":
            continue  # LangGraph messages 有特殊结构，跳过
        try:
            json.dumps(v, ensure_ascii=False, default=str)
            state_copy[k] = v
        except (TypeError, ValueError):
            state_copy[k] = str(v)[:500]
    state_json = json.dumps(state_copy, ensure_ascii=False, default=str)

    conn.execute("""
        INSERT INTO sessions (thread_id, summary, raw_input, game_title, game_genre,
              game_type, code_passed, test_passed, test_count, image_count,
              error_count, state_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(thread_id) DO UPDATE SET
            summary=excluded.summary, game_title=excluded.game_title,
            game_genre=excluded.game_genre, game_type=excluded.game_type,
            code_passed=excluded.code_passed, test_passed=excluded.test_passed,
            test_count=excluded.test_count, image_count=excluded.image_count,
            error_count=excluded.error_count, state_json=excluded.state_json,
            updated_at=datetime('now')
    """, (thread_id, "", raw_input, game_title, game_genre, game_type,
          code_passed, test_passed, test_count, image_count, error_count, state_json))
    conn.commit()
    conn.close()
    logger.info("session_saved", thread_id=thread_id, title=game_title)


async def generate_summary(thread_id: str):
    """异步生成会话摘要（在流水线完成后调用）"""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE thread_id=?", (thread_id,)).fetchone()
    if not row:
        conn.close()
        return

    game_title = row["game_title"] or "未命名"
    game_genre = row["game_genre"] or "未知类型"
    code_ok = "✅" if row["code_passed"] else "⚠️"
    test_info = row["test_count"]
    img_count = row["image_count"]
    err_count = row["error_count"]

    # LLM 生成一句话摘要
    try:
        resp = await llm_client.achat([{
            "role": "user",
            "content": f"用一句话（不超过30字）总结这个游戏开发会话：\n"
                       f"游戏: 《{game_title}》({game_genre})\n代码:{code_ok} 测试:{test_info} 图片:{img_count}张 错误:{err_count}个"
        }], temperature=0.3, max_tokens=80)
        summary = resp.strip()
    except Exception:
        summary = f"《{game_title}》{game_genre} {code_ok}{test_info}"

    conn.execute("UPDATE sessions SET summary=? WHERE thread_id=?", (summary[:200], thread_id))
    conn.commit()
    conn.close()
    logger.info("summary_generated", thread_id=thread_id, summary=summary[:80])


def list_sessions(limit: int = 15) -> list[dict]:
    """列出最近会话"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT thread_id, summary, game_title, game_genre, game_type,"
        " code_passed, test_passed, test_count, image_count, error_count,"
        " created_at, updated_at FROM sessions "
        "ORDER BY updated_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session(thread_id: str) -> Optional[dict]:
    """加载一个会话的完整状态"""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE thread_id=?", (thread_id,)).fetchone()
    conn.close()
    if not row:
        return None

    result = dict(row)
    try:
        result["state"] = json.loads(result.get("state_json", "{}"))
    except json.JSONDecodeError:
        result["state"] = {}
    return result


def load_previous_state(hint: str = "") -> Optional[dict]:
    """
    自动判断用户是否想继续之前的会话
    返回上一个会话的 state，或 None
    """
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None

    # 检查是否是"继续"语义
    continue_keywords = ["继续", "刚才", "上次", "上一个", "之前", "改", "修改", "换个",
                         "在这个基础上", "基于", "刚刚的", "接着", "前一", "这个游戏"]
    if any(kw in hint for kw in continue_keywords):
        try:
            state = json.loads(row["state_json"] or "{}")
            logger.info("session_loaded", thread_id=row["thread_id"],
                        title=row["game_title"])
            return {
                "state": state,
                "thread_id": row["thread_id"],
                "summary": row["summary"],
                "game_title": row["game_title"],
            }
        except json.JSONDecodeError:
            return None
    return None


# ============================================
# 第三层: 产物反哺知识库
# ============================================

def get_pending_feedback() -> list[dict]:
    """获取待入库的高质量产物（代码通过 + 测试通过）"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT s.thread_id, s.game_title, s.game_genre, s.game_type, s.state_json "
        "FROM sessions s "
        "WHERE s.code_passed=1 AND s.test_passed=1 "
        "AND s.thread_id NOT IN (SELECT thread_id FROM knowledge_feedback) "
        "ORDER BY s.updated_at DESC LIMIT 10"
    ).fetchall()
    conn.close()

    feedbacks = []
    for row in rows:
        try:
            state = json.loads(row["state_json"] or "{}")
            code_result = state.get("code_result", {})
            files = code_result.get("files", [])
            if files and files[0].get("content"):
                code = files[0].get("content", "")
                content_hash = hashlib.md5(code.encode()).hexdigest()
                feedbacks.append({
                    "thread_id": row["thread_id"],
                    "content": code[:3000],
                    "content_hash": content_hash,
                    "source": f"session_{row['thread_id']}",
                    "game_title": row["game_title"],
                    "game_type": row["game_type"],
                })
        except (json.JSONDecodeError, KeyError):
            pass
    return feedbacks


def mark_feedback_indexed(thread_id: str, content_hash: str):
    """标记产物已入库"""
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO knowledge_feedback (thread_id, content_hash) VALUES (?, ?)",
        (thread_id, content_hash)
    )
    conn.commit()
    conn.close()
    logger.info("feedback_marked", thread_id=thread_id)


async def auto_feedback_to_knowledge():
    """自动将高质量产物反哺到 Milvus 知识库"""
    try:
        from src.services.vector_rag_service import vector_rag
        items = get_pending_feedback()
        if not items:
            return 0

        indexed = 0
        for item in items:
            try:
                doc_hash = item["content_hash"]
                # 检查去重
                conn = _get_conn()
                exists = conn.execute(
                    "SELECT 1 FROM knowledge_feedback WHERE content_hash=?",
                    (doc_hash,)
                ).fetchone()
                conn.close()
                if exists:
                    continue

                # 入库 Milvus
                vector_rag.index_documents([{
                    "content": f"游戏: {item['game_title']} ({item['game_type']})\n"
                              f"已通过运行验证的代码:\n{item['content'][:1500]}",
                    "metadata": {
                        "source": item["source"],
                        "section": item.get("game_title", ""),
                        "type": "generated_code",
                    }
                }])
                mark_feedback_indexed(item["thread_id"], doc_hash)
                indexed += 1
            except Exception as e:
                logger.warning("feedback_item_failed", error=str(e)[:80])

        if indexed > 0:
            logger.info("auto_feedback_done", count=indexed)
        return indexed
    except Exception as e:
        logger.warning("auto_feedback_error", error=str(e)[:80])
    return 0


# Startup
init_db()
