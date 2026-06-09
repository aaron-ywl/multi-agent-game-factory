"""
Agent 2: Narrative Agent (叙事/剧本 Agent)
负责：程序剧本生成 - 世界观、剧情、角色对话
"""
import json
import structlog
from src.services.llm_client import llm_client
from src.services.vector_rag_service import vector_rag

logger = structlog.get_logger()

SYSTEM_PROMPT = """你是一个资深游戏叙事设计师，专精于世界观构建、角色设计、战斗技能设定。

输出合法 JSON：
{
  "world_setting": "世界观设定（100字）",
  "main_plot": "剧情概要（100字）",
  "characters": [
    {
      "name": "角色名",
      "role": "主角/反派",
      "personality": "性格",
      "background": "背景",
      "skills": [
        {"name": "技能名", "damage": 数值(10-50), "cooldown": 冷却回合(0-3), "animation": "ASCII动画效果(如 ▄▄⚡▄▄)"}
      ]
    }
  ],
  "quest_design": [
    {"name": "任务名", "type": "主线/支线", "objective": "目标"}
  ]
}"""


async def narrative_agent(state: dict) -> dict:
    """
    Agent 2: 叙事设计
    输入: game_design + raw_input
    输出: narrative (NarrativeSpec)
    """
    design = state.get("game_design", {})
    if not design:
        return {"errors": ["缺少 game_design"]}

    genre = design.get("genre", "RPG")
    title = design.get("title", "")
    features = design.get("key_features", [])
    core = design.get("core_mechanic", "")

    # RAG 检索叙事参考
    rag_query = f"{genre} 游戏世界观 {title} {' '.join(features[:2])}"
    rag_hits = await vector_rag.retrieve(rag_query, top_k=3)
    rag_context = ""
    if rag_hits:
        rag_context = "\n".join([h["content"][:300] for h in rag_hits])

    logger.info("agent_narrative_start", genre=genre, title=title)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""为以下游戏设计世界观和角色：

游戏类型: {genre}
游戏标题: {title}
核心玩法: {core}
关键特性: {', '.join(features)}
{('参考：' + rag_context) if rag_context else ''}

重要: 每个角色必须包含 3 个技能，每个技能有 name、damage(10-50)、cooldown(0-3)、animation(ASCII字符串)。
输出 JSON。"""},
    ]

    try:
        result = await llm_client.achat_json(messages, temperature=0.9)
        logger.info("agent_narrative_done", chars=len(result.get("characters", [])))
    except Exception as e:
        logger.error("agent_narrative_failed", error=str(e))
        return {"errors": [f"Narrative Agent 失败: {str(e)}"]}

    return {
        "narrative": {
            "world_setting": result.get("world_setting", ""),
            "main_plot": result.get("main_plot", ""),
            "characters": result.get("characters", []),
            "dialogue_samples": result.get("dialogue_samples", []),
            "quest_design": result.get("quest_design", []),
        },
        "messages": [{
            "role": "ai", "name": "narrative",
            "content": f"叙事设计完成: {len(result.get('characters', []))} 个角色, "
                       f"{len(result.get('quest_design', []))} 个任务"
        }],
    }
