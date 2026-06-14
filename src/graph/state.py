"""
共享状态定义 - GameDevState
LangGraph StateGraph 共享状态，6 Agent 流水线
"""
from typing import Annotated, Optional
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class GameDevState(BaseModel):
    """
    游戏开发流水线共享状态
    6 个 Agent 按序读写：
    Designer → Narrative → CodeGen → Reviewer → Test → Art → END
    """
    # 用户原始输入
    raw_input: str = ""

    # Agent 1: Game Designer → 策划配置生成
    game_design: Optional[dict] = None

    # Agent 2: Narrative Agent → 程序剧本生成
    narrative: Optional[dict] = None

    # Agent 3: Code Generator → 代码生成+自动验证+自动修复
    code_result: Optional[dict] = None

    # Agent 4: Code Reviewer → 代码审查
    code_review: Optional[dict] = None
    needs_regeneration: bool = False
    review_feedback: Optional[dict] = None  # 审查反馈，供 CodeGen 定向修复用（bugs + optimizations + security）

    # Agent 5: Test Agent → 自动测试生成+执行
    test_result: Optional[dict] = None

    # Agent 6: Art Director → 美术指引 + 实际图片生成
    art_directive: Optional[dict] = None
    generated_images: list[dict] = Field(default_factory=list)

    # 元数据
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    loopback_count: int = 0
    thread_id: str = ""
    token_usage: dict = Field(default_factory=dict)
