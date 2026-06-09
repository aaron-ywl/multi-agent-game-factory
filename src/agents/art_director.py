"""
Agent 5: Art Director Agent (美术总监 Agent)
负责：真正调用 Qwen-Image-2.0 生成 2D 角色/场景图片
"""
import json
import structlog
from src.services.llm_client import llm_client
from src.services.image_gen import image_gen
from src.skills.game_tools import enhance_art_prompt, generate_asset_checklist
from src.services.vector_rag_service import vector_rag

logger = structlog.get_logger()

SYSTEM_PROMPT = """你是一个游戏美术总监。为游戏角色和场景生成简短精炼的 AIGC prompt。

要求：
1. 每个 prompt 控制在 200 字符以内
2. 必须包含：主体描述 + 风格 + 质量词
3. 角色 prompt 格式："anime [职业/种族], [外观特征], [服饰], game character, cel-shading, vibrant colors"
4. 场景 prompt 格式："[场景类型], [氛围], [关键元素], anime background, wide shot"

输出合法 JSON：
{
  "concept_desc": "整体美术概念（50字）",
  "character_prompts": [
    {"name": "角色名", "prompt": "生成prompt"}
  ],
  "environment_prompts": [
    {"name": "场景名", "prompt": "生成prompt"}
  ],
  "color_palette": ["#色1", "#色2", "#色3", "#色4", "#色5"]
}
"""


async def art_director_agent(state: dict) -> dict:
    """Agent 5: 美术总监 — 生成 Prompt 并真实出图"""
    design = state.get("game_design", {})
    narrative = state.get("narrative", {})

    if not design:
        return {"errors": ["缺少 game_design"]}

    genre = design.get("genre", "二次元卡牌")
    title = design.get("title", "")
    art_style = design.get("art_style", "日式二次元赛璐璐风格")
    chars = narrative.get("characters", []) if narrative else []
    world_setting = narrative.get("world_setting", "") if narrative else ""

    # RAG 检索美术参考
    rag_query = f"{genre} {art_style} 游戏美术 概念设计"
    rag_hits = await vector_rag.retrieve(rag_query, top_k=2)
    rag_context = ""
    if rag_hits:
        rag_context = "\n".join([h["content"][:200] for h in rag_hits])

    logger.info("agent_art_director_start", genre=genre, art_style=art_style)

    # Step 1: LLM 生成 Prompt 列表
    char_names = [c.get("name", "?") for c in chars[:3]] if chars else ["主角", "伙伴", "对手"]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""游戏: 《{title}》 ({genre})
美术风格: {art_style}
世界观: {world_setting[:200]}
角色: {', '.join(char_names)}
{('参考: ' + rag_context) if rag_context else ''}

请生成角色和场景的 AIGC prompt（每个 200 字以内）。输出 JSON。"""},
    ]

    try:
        result = await llm_client.achat_json(messages, temperature=0.7)
        logger.info("agent_art_director_prompts_ready")
    except Exception as e:
        logger.error("agent_art_director_failed", error=str(e)[:80])
        return {"errors": [f"美术总监失败: {str(e)[:100]}"]}

    # Step 2: 增强 Prompt 并调用 Qwen-Image-2.0 生成图片
    enhanced_2d = ""
    generated_images = []

    # 生成角色图（选前2个角色）
    char_prompts = result.get("character_prompts", [])
    for cp in char_prompts[:2]:
        base_prompt = cp.get("prompt", "")
        if base_prompt:
            enhanced = enhance_art_prompt(base_prompt, "stylized")[:800]
            img_result = image_gen.generate_character(
                name=cp.get("name", "角色"),
                desc=enhanced,
            )
            if img_result:
                img_result["name"] = cp.get("name", "角色")
                img_result["type"] = "character"
                generated_images.append(img_result)
            logger.info("char_image_gen", name=cp.get("name"), ok=img_result is not None)

    # 生成场景图（选1个）
    env_prompts = result.get("environment_prompts", [])
    if env_prompts:
        ep = env_prompts[0]
        env_prompt = ep.get("prompt", "")
        if env_prompt:
            enhanced_env = enhance_art_prompt(env_prompt, "stylized")[:800]
            img_result = image_gen.generate_environment(scene_desc=enhanced_env)
            if img_result:
                img_result["name"] = ep.get("name", "主场景")
                img_result["type"] = "environment"
                generated_images.append(img_result)

    # Step 3: 构建 2D Prompt 展示
    try:
        enhanced_2d = json.dumps(
            {cp["name"]: enhance_art_prompt(cp["prompt"], "stylized")[:400]
             for cp in char_prompts[:2] if cp.get("prompt")},
            ensure_ascii=False, indent=2)
    except Exception:
        enhanced_2d = str(char_prompts[:2])

    # 生成资源清单
    asset_checklist = generate_asset_checklist({
        "genre": genre,
        "key_features": design.get("key_features", []),
        "art_style": art_style,
    })

    return {
        "art_directive": {
            "concept_desc": result.get("concept_desc", ""),
            "prompt_2d": enhanced_2d,
            "prompt_3d": json.dumps(result.get("environment_prompts", []), ensure_ascii=False),
            "prompt_animation": json.dumps(result.get("character_prompts", [])[:2], ensure_ascii=False),
            "color_palette": result.get("color_palette", []),
            "references": ["Qwen-Image-2.0 实时生成"],
        },
        "generated_images": generated_images,
        "messages": [{
            "role": "ai", "name": "art_director",
            "content": f"美术指引完成 + 真正生成 {len(generated_images)} 张图片: "
                       f"{', '.join(i['name'] for i in generated_images)}"
        }],
    }
