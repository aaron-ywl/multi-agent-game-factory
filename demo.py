#!/usr/bin/env python3
"""
Game AI Agent 交互式 Demo
支持两种模式:
  1. 完整流水线模式: python demo.py run "开发一个仙侠RPG..."
  2. 单工具模式: python demo.py tool balance --attack 50 --health 500
"""
import asyncio
import json
import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.game_pipeline import run_game_dev_pipeline
from src.skills.setup import register_all_skills
from src.skills.game_tools import (
    calculate_game_balance,
    validate_code_syntax,
    enhance_art_prompt,
    generate_asset_checklist,
)
from src.services.vector_rag_service import vector_rag

# 初始化
register_all_skills()


def print_header(title: str, char: str = "="):
    print(f"\n{char * 60}")
    print(f"  {title}")
    print(f"{char * 60}")


def print_section(title: str):
    print(f"\n{'─' * 50}")
    print(f"  📌 {title}")
    print(f"{'─' * 50}")


def print_json(obj, indent=2):
    """安全打印 JSON"""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except (json.JSONDecodeError, TypeError):
            print(obj)
            return
    print(json.dumps(obj, ensure_ascii=False, indent=indent))


async def run_pipeline_demo(requirement: str):
    """运行完整 5-Agent 流水线"""
    print_header("🎮 游戏 AI Agent - 完整流水线 Demo")

    print(f"\n📝 输入需求: {requirement}\n")

    start = time.time()

    # Phase 1: 初始化知识库
    print("🔧 初始化知识库...")
    _index_knowledge_base()
    print(f"   知识库文档数: {vector_rag.document_count}")

    # Phase 2: 运行流水线
    print("\n🚀 启动 5-Agent 流水线...")
    state = await run_game_dev_pipeline(requirement)

    elapsed = time.time() - start

    # Phase 3: 输出结果
    print_header("📊 流水线执行结果", "=")

    # Agent 1: Game Designer
    design = state.get("game_design", {})
    if design:
        print_section("Agent 1: 游戏策划 (Game Designer)")
        print(f"   游戏标题: {design.get('title', 'N/A')}")
        print(f"   游戏类型: {design.get('genre', 'N/A')}")
        print(f"   核心玩法: {design.get('core_mechanic', 'N/A')}")
        print(f"   目标平台: {design.get('target_platform', 'N/A')}")
        print(f"   美术风格: {design.get('art_style', 'N/A')}")
        print(f"   关键特性: {', '.join(design.get('key_features', []))}")
        print(f"   难度曲线: {design.get('difficulty_curve', 'N/A')[:100]}")
        print(f"   商业化:   {design.get('monetization', 'N/A')}")

    # Agent 2: Narrative
    narrative = state.get("narrative", {})
    if narrative:
        print_section("Agent 2: 叙事设计 (Narrative)")
        print(f"   世界观: {narrative.get('world_setting', 'N/A')[:200]}")
        print(f"   主线概要: {narrative.get('main_plot', 'N/A')[:200]}")
        chars = narrative.get("characters", [])
        print(f"   角色数: {len(chars)}")
        for c in chars[:3]:
            print(f"     - {c.get('name', '?')} ({c.get('role', '?')}): {c.get('personality', '?')[:60]}")
        quests = narrative.get("quest_design", [])
        print(f"   任务数: {len(quests)}")
        for q in quests[:3]:
            print(f"     - {q.get('name', '?')} [{q.get('type', '?')}]: {q.get('objective', '?')[:60]}")

    # Agent 3: Code Generator
    code_result = state.get("code_result", {})
    if code_result:
        print_section("Agent 3: 代码生成 (Code Generator)")
        print(f"   语言: {code_result.get('language', 'N/A')}")
        print(f"   入口: {code_result.get('entry_point', 'N/A')}")
        print(f"   架构: {code_result.get('architecture_notes', 'N/A')[:200]}")
        files = code_result.get("files", [])
        print(f"   文件数: {len(files)}")
        for f in files:
            v = f.get("validation", {})
            valid_str = "✅" if v.get("valid") else "⚠️"
            print(f"     {valid_str} {f.get('path', '?')} ({len(f.get('content', ''))} 字符)"
                  f" - {f.get('description', '')[:50]}")
        # 输出第一个文件的代码
        if files:
            print(f"\n   ── 代码预览 ({files[0].get('path', 'file')}) ──")
            content = files[0].get("content", "")
            for i, line in enumerate(content.split("\n")[:30]):
                print(f"   {i+1:3d}| {line}")

    # Agent 4: Code Reviewer
    review = state.get("code_review", {})
    if review:
        print_section("Agent 4: 代码审查 (Code Reviewer)")
        score = review.get("score", 0)
        status_icon = "✅ 通过" if review.get("passed") else "⚠️ 需改进"
        print(f"   综合评分: {score}/100 {status_icon}")
        bugs = review.get("bugs", [])
        if bugs:
            print(f"   🐛 发现 {len(bugs)} 个问题:")
            for b in bugs[:5]:
                print(f"     [{b.get('severity', '?')}] {b.get('file', '?')}:"
                      f"{b.get('line', '?')} - {b.get('description', '?')[:80]}")
        optimizations = review.get("optimizations", [])
        if optimizations:
            print(f"   ⚡ 优化建议 {len(optimizations)} 条:")
            for o in optimizations[:3]:
                print(f"     [{o.get('category', '?')}] {o.get('description', '?')[:80]}")
        security = review.get("security_issues", [])
        if security:
            print(f"   🔒 安全问题 {len(security)} 项:")
            for s in security[:3]:
                print(f"     [{s.get('severity', '?')}] {s.get('description', '?')[:80]}")

    # Agent 5: Test Agent
    test_result = state.get("test_result", {})
    if test_result and not test_result.get("skipped"):
        print_section("Agent 5: 自动测试 (Test Agent)")
        ok = test_result.get("passed", False)
        print(f"   状态: {'✅ 全部通过' if ok else '⚠️ 存在失败'} | {test_result.get('summary', '')}")
        print(f"   通过: {test_result.get('passed_count', 0)} | 失败: {test_result.get('failed_count', 0)}")
        if test_result.get("auto_fixed"):
            print(f"   自动修复: ✅")
        output = test_result.get("output", "")
        if output:
            print(f"   输出预览:\n{output[:500]}")

    # Agent 6: Art Director
    art = state.get("art_directive", {})
    images = state.get("generated_images", [])
    if art:
        print_section("Agent 6: 美术总监+出图 (Art Director)")
        print(f"   概念: {art.get('concept_desc', 'N/A')[:200]}")
        palette = art.get("color_palette", [])
        if palette:
            print(f"   色板: {' '.join(palette[:6])}")
        if images:
            print(f"\n   🖼️ Qwen-Image-2.0 实际生成 ({len(images)} 张):")
            for img in images:
                print(f"     [{img.get('type','?')}] {img.get('name','?')}: {img.get('url','?')[:80]}...")

    # Errors
    errors = state.get("errors", [])
    if errors:
        print_section("⚠️ 错误信息")
        for e in errors:
            print(f"   - {e}")

    print_header(f"✅ 流水线执行完成 | 耗时 {elapsed:.1f}s "
                 f"| Thread: {state.get('thread_id', 'N/A')}")


def run_tool_demo(tool_name: str, **kwargs):
    """运行单工具 Demo"""
    print_header(f"🔧 工具 Demo: {tool_name}")

    if tool_name == "balance":
        result = calculate_game_balance(kwargs)
        print_json(result)

    elif tool_name == "validate":
        code = kwargs.get("code", "def hello():\n    print('hello')")
        result = validate_code_syntax(code)
        print_json(result)

    elif tool_name == "enhance":
        prompt = kwargs.get("prompt", "a warrior character")
        style = kwargs.get("style", "stylized")
        result = enhance_art_prompt(prompt, style)
        print(f"\n原 Prompt: {prompt}")
        print(f"\n增强后 Prompt:\n{result}")

    elif tool_name == "checklist":
        result = generate_asset_checklist({
            "genre": kwargs.get("genre", "RPG"),
            "key_features": kwargs.get("features", []),
            "art_style": kwargs.get("style", ""),
        })
        print_json(result)

    elif tool_name == "skills":
        from src.skills.registry import list_skills
        print(f"已注册 Skill: {list_skills()}")

    else:
        print(f"未知工具: {tool_name}")
        print("可用工具: balance, validate, enhance, checklist, skills")


def _index_knowledge_base():
    """播种游戏开发知识到向量库"""
    knowledge_docs = [
        # 游戏设计范式
        "游戏设计：RPG的核心循环是 探索→战斗→获取→成长→探索 的正反馈循环。"
        "每次循环应提供新的挑战和更丰富的奖励。",
        "游戏设计：MOBA游戏的5v5对战模式中，地图设计应包含三条主要路线和野区，"
        "每条路线有不同的资源分布和战略意义。",
        "游戏设计：卡牌游戏的数值设计遵循费用曲线原则，高费用卡牌应提供更高的价值，"
        "但也需要低费用卡牌维持节奏。",
        "游戏设计：战斗系统设计中，TTK(Time To Kill)是核心指标。PvE通常控制在10-30秒，"
        "PvP则控制在3-8秒以保证紧张感。",
        "游戏设计：Roguelike游戏的核心是程序化生成与永久死亡机制，"
        "每次游戏体验不同但保持一致性。",

        # 编程模式
        "游戏编程：推荐使用ECS(Entity Component System)架构来处理大量游戏实体，"
        "核心是数据与逻辑分离，适合需要高性能的场景。",
        "游戏编程：游戏主循环通常采用固定时间步长(Fixed Timestep)模式："
        "while running: process_input(); update(dt); render()。物理更新应在固定时间步长中进行。",
        "游戏编程：对象池(Object Pool)模式是游戏开发的常用优化手段，预创建对象并复用，"
        "避免频繁的GC导致的帧率波动。",
        "游戏编程：状态机(State Machine)用于管理角色状态（待机/移动/攻击/死亡），"
        "每个状态有 OnEnter/OnUpdate/OnExit 三个生命周期。",
        "游戏编程：事件系统(Event Bus)用于解耦模块间通信，"
        "使用发布-订阅模式实现伤害事件、UI更新等。",

        # AIGC 美术
        "AIGC美术：使用Stable Diffusion生成游戏概念图时，Prompt应包含：主体描述+风格词+质量词+光照+构图。"
        "例如 'a warrior in plate armor, fantasy art style, trending on ArtStation, "
        "cinematic lighting, 8K, highly detailed'。",
        "AIGC美术：3D资产生成流程：概念图(2D) → 图像转3D(Mesh生成) → 拓扑优化 → UV展开 → "
        "纹理生成 → 骨骼绑定 → 动画制作。可用工具：Meshy/CSM/Stable Projectorz。",
        "AIGC美术：游戏UI设计遵循 60-30-10 色彩法则：60%主色(背景)、30%辅色(面板)、10%强调色(按钮)。"
        "确保色彩一致性和品牌识别度。",
    ]

    # 只在知识库为空时播种
    if vector_rag.document_count == 0:
        count = vector_rag.index_knowledge(knowledge_docs)
        print(f"   ✅ 知识库初始化完成: {count} 条文档")
    else:
        print(f"   📚 知识库已有 {vector_rag.document_count} 条文档，跳过初始化")


async def main():
    if len(sys.argv) < 2:
        print("Game AI Agent - 多 Agent 游戏开发工具链 Demo")
        print()
        print("用法:")
        print("  # 完整流水线")
        print('  python demo.py run "开发一个二次元卡牌RPG游戏，核心玩法是抽卡+回合制战斗"')
        print()
        print("  # 单工具")
        print("  python demo.py tool balance --attack 50 --health 500")
        print("  python demo.py tool validate --code 'def test(): pass'")
        print("  python demo.py tool enhance --prompt 'a dragon' --style stylized")
        print("  python demo.py tool checklist --genre RPG")
        print("  python demo.py tool skills")
        return

    command = sys.argv[1]

    if command == "run":
        requirement = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if not requirement:
            print("❌ 请提供游戏开发需求描述")
            return
        await run_pipeline_demo(requirement)

    elif command == "tool":
        if len(sys.argv) < 3:
            print("❌ 请指定工具名称: balance, validate, enhance, checklist, skills")
            return

        tool_name = sys.argv[2]
        kwargs = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i].startswith("--"):
                key = sys.argv[i][2:]
                val = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
                # 尝试解析为数值
                try:
                    val = float(val) if "." in val else int(val)
                except ValueError:
                    pass
                kwargs[key] = val
                i += 2
            else:
                i += 1

        if tool_name == "balance":
            run_tool_demo("balance",
                          base_attack=kwargs.get("attack", 10),
                          base_defense=kwargs.get("defense", 5),
                          health=kwargs.get("health", 100))
        elif tool_name == "validate":
            run_tool_demo("validate", code=kwargs.get("code", "def test(): pass"))
        elif tool_name == "enhance":
            run_tool_demo("enhance", prompt=kwargs.get("prompt", "a warrior"),
                          style=kwargs.get("style", "stylized"))
        elif tool_name == "checklist":
            run_tool_demo("checklist", genre=kwargs.get("genre", "RPG"))
        elif tool_name == "skills":
            run_tool_demo("skills")
        else:
            print(f"❌ 未知工具: {tool_name}")

    else:
        print(f"❌ 未知命令: {command}")
        print("可用命令: run, tool")


if __name__ == "__main__":
    asyncio.run(main())
