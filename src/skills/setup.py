"""
注册所有游戏开发 Skill
"""
from src.skills.registry import Tool, register_skill
from src.skills.game_tools import (
    calculate_game_balance,
    validate_code_syntax,
    enhance_art_prompt,
    generate_asset_checklist,
)
from src.services.vector_rag_service import vector_rag


def _rag_search(query: str, top_k: int = 5) -> str:
    """RAG 检索的 Tool 封装"""
    results = vector_rag.retrieve(query, top_k=top_k)
    if not results:
        return "未找到相关知识。"
    lines = []
    for r in results:
        lines.append(f"[{r.get('id', '?')}] {r['content'][:500]}")
    return "\n\n".join(lines)


def register_all_skills():
    """一次性注册所有 Skill"""

    # Skill 1: 数值设计
    register_skill(
        name="game_balance",
        description="游戏数值平衡分析与校验，包括战斗平衡、经济系统、成长曲线",
        tools=[
            Tool(
                name="calc_balance",
                description="计算战斗数值平衡：输入 base_attack/base_defense/health/level/scaling_factor/target_ttk",
                func=calculate_game_balance,
                params_schema={
                    "type": "object",
                    "properties": {
                        "base_attack": {"type": "number", "description": "基础攻击力"},
                        "base_defense": {"type": "number", "description": "基础防御力"},
                        "health": {"type": "number", "description": "生命值"},
                        "level": {"type": "integer", "description": "等级"},
                        "scaling_factor": {"type": "number", "description": "成长系数"},
                        "target_ttk": {"type": "number", "description": "目标击杀时间(秒)"},
                    },
                    "required": ["base_attack", "health"],
                },
            ),
        ],
    )

    # Skill 2: 代码工具
    register_skill(
        name="code_tools",
        description="代码生成辅助工具：语法校验、代码分析、性能检查",
        tools=[
            Tool(
                name="validate_syntax",
                description="校验代码语法并进行分析",
                func=validate_code_syntax,
                params_schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "待校验的代码"},
                        "language": {"type": "string", "description": "编程语言", "default": "python"},
                    },
                    "required": ["code"],
                },
            ),
        ],
    )

    # Skill 3: AIGC 资产
    register_skill(
        name="aigc_asset",
        description="AI 内容生成辅助：2D图像/3D模型/动画 Prompt 增强、资源清单自动生成",
        tools=[
            Tool(
                name="enhance_prompt",
                description="增强 2D/3D 资产生成 Prompt（适配 SD/MJ 等主流模型）",
                func=enhance_art_prompt,
                params_schema={
                    "type": "object",
                    "properties": {
                        "base_prompt": {"type": "string", "description": "基础提示词"},
                        "style": {
                            "type": "string",
                            "description": "风格：realistic/stylized/pixel/lowpoly",
                            "enum": ["realistic", "stylized", "pixel", "lowpoly"],
                        },
                    },
                    "required": ["base_prompt"],
                },
            ),
            Tool(
                name="gen_asset_checklist",
                description="根据游戏设计自动生成美术/音效/UI 资源清单",
                func=generate_asset_checklist,
                params_schema={
                    "type": "object",
                    "properties": {
                        "design": {
                            "type": "object",
                            "description": "游戏设计规格 {genre, key_features, art_style}",
                        },
                    },
                    "required": ["design"],
                },
            ),
        ],
    )

    # Skill 4: 知识库检索
    register_skill(
        name="game_knowledge",
        description="游戏开发知识库检索：设计模式、引擎 API、最佳实践",
        tools=[
            Tool(
                name="search_knowledge",
                description="在游戏开发知识库中语义搜索",
                func=_rag_search,
                params_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索查询"},
                        "top_k": {"type": "integer", "description": "返回条数", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
        ],
    )

    # Skill 5: 配置导出
    register_skill(
        name="config_export",
        description="游戏策划配置生成与导出（JSON/CSV/YAML）",
        tools=[
            Tool(
                name="gen_asset_checklist_2",
                description="同 aigc_asset.gen_asset_checklist - 资源清单生成",
                func=generate_asset_checklist,
                params_schema={
                    "type": "object",
                    "properties": {
                        "design": {"type": "object", "description": "游戏设计规格"},
                    },
                    "required": ["design"],
                },
            ),
        ],
    )
