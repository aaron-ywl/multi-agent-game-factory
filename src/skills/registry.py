"""
Skill / Tool 抽象层
将 Agent 能力解耦为可组合的 Skill 和 Tool，方便复用和扩展
参考 medical 项目的 skill 注册模式
"""
from dataclasses import dataclass, field
from typing import Callable, Any, Optional

# 全局注册表
_skill_registry: dict[str, "Skill"] = {}


@dataclass
class Tool:
    """单个工具：名称 + 描述 + 可调用"""
    name: str
    description: str
    func: Callable
    params_schema: dict = field(default_factory=dict)


@dataclass
class Skill:
    """技能组：一组相关工具的命名集合"""
    name: str
    description: str
    tools: list[Tool] = field(default_factory=list)


# ==================== Skill 注册 ====================

def register_skill(name: str, description: str, tools: list[Tool]) -> Skill:
    """注册一个 Skill 到全局注册表"""
    skill = Skill(name=name, description=description, tools=tools)
    _skill_registry[name] = skill
    return skill


def get_skill(name: str) -> Optional[Skill]:
    """按名称获取 Skill"""
    return _skill_registry.get(name)


def list_skills() -> list[str]:
    """列出所有已注册的 Skill 名称"""
    return list(_skill_registry.keys())


def get_all_tools() -> list[dict]:
    """获取所有 Skill 的 Tool 列表（用于 LLM function calling）"""
    tools = []
    for skill in _skill_registry.values():
        for tool in skill.tools:
            tools.append({
                "type": "function",
                "function": {
                    "name": f"{skill.name}__{tool.name}",
                    "description": tool.description,
                    "parameters": tool.params_schema,
                }
            })
    return tools
