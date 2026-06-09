"""
Agent 1: Game Designer Agent (游戏策划 Agent)
负责：策划配置生成 - 从用户需求分析→输出正式游戏设计规格
"""
import json
import structlog
from src.services.llm_client import llm_client
from src.skills.game_tools import calculate_game_balance, generate_asset_checklist
from src.services.vector_rag_service import vector_rag

logger = structlog.get_logger()

SYSTEM_PROMPT = """你是一个资深游戏策划，专精于将模糊的创意需求转化为严谨的游戏设计文档(GDD)。

你的能力：
1. 分析用户需求，提炼核心玩法
2. 结合市场趋势和玩家心理设计游戏系统
3. 输出结构化的游戏设计规格

你必须输出合法 JSON，格式如下：
{
  "genre": "游戏类型",
  "title": "游戏标题",
  "core_mechanic": "核心玩法一句话描述",
  "target_platform": "目标平台",
  "art_style": "美术风格建议",
  "key_features": ["特性1", "特性2", "特性3"],
  "difficulty_curve": "难度曲线设计思路",
  "monetization": "商业化模式建议",
  "design_rationale": "设计理由（简要）"
}
"""


async def game_designer_agent(state: dict) -> dict:
    """
    Agent 1: 游戏策划
    输入: raw_input
    输出: game_design (GameDesignSpec)
    """
    raw_input = state.get("raw_input", "")
    if not raw_input:
        return {"errors": ["缺少 raw_input"]}

    # Step 1: RAG 检索类似设计参考
    rag_hits = await vector_rag.retrieve(f"游戏设计 {raw_input}", top_k=3)
    rag_context = ""
    if rag_hits:
        rag_context = "\n".join([h["content"][:300] for h in rag_hits])

    logger.info("agent_designer_start", input_len=len(raw_input), rag_hits=len(rag_hits))

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请根据以下需求，完成游戏设计规格：

需求描述: {raw_input}

{('参考知识：' + rag_context) if rag_context else ''}

请用 JSON 输出完整设计规格。"""},
    ]

    try:
        result = await llm_client.achat_json(messages, temperature=0.8)
        logger.info("agent_designer_done", genre=result.get("genre", "unknown"))
    except Exception as e:
        logger.error("agent_designer_failed", error=str(e))
        return {"errors": [f"Designer Agent 失败: {str(e)}"]}

    # Step 2: 用内置工具做数值平衡预检
    balance_check = None
    try:
        # 如果设计中有数值参数，进行平衡校验
        if any(kw in raw_input.lower() for kw in ["攻击", "伤害", "血量", "hp", "damage", "attack"]):
            balance_check = calculate_game_balance({
                "base_attack": result.get("damage_base", 50),
                "base_defense": result.get("defense_base", 20),
                "health": result.get("health_base", 500),
            })
            logger.info("agent_designer_balance_check", result=balance_check)
    except Exception:
        pass

    # Step 3: 生成资源清单
    asset_checklist = None
    try:
        asset_checklist = generate_asset_checklist({
            "genre": result.get("genre", ""),
            "key_features": result.get("key_features", []),
            "art_style": result.get("art_style", ""),
        })
    except Exception:
        pass

    return {
        "game_design": {
            "genre": result.get("genre", ""),
            "title": result.get("title", ""),
            "core_mechanic": result.get("core_mechanic", ""),
            "target_platform": result.get("target_platform", "PC"),
            "art_style": result.get("art_style", ""),
            "key_features": result.get("key_features", []),
            "difficulty_curve": result.get("difficulty_curve", ""),
            "monetization": result.get("monetization", ""),
        },
        "messages": [{
            "role": "ai", "name": "game_designer",
            "content": f"设计完成: {result.get('title', '')} ({result.get('genre', '')}) - "
                       f"核心玩法: {result.get('core_mechanic', '')}"
        }],
    }
