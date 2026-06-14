"""
Agent 3: Code Generator — 生成可运行代码 + 自动验证 + 自动修复
自动检测游戏类型（格斗/塔防），用 <CODE> 标签提取避免 JSON 解析失败
"""
import subprocess
import os
import re
import json
import structlog
from pathlib import Path

from src.services.llm_client import llm_client
from src.skills.game_tools import validate_code_syntax
from src.services.vector_rag_service import vector_rag

logger = structlog.get_logger()
OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"

# ===== 两类游戏代码模板 =====

FIGHTER_PROMPT = """你是游戏程序员，生成 1v1 回合制对战 Demo。

约束: 禁止 time/os/sleep/input/while True, for循环限次, 只 import random
结构: Fighter类(name/hp/skills/use_skill/hp_bar), 技能含damage+cooldown+ASCII动画, main()自动8回合输出胜负

用 <CODE> 和 </CODE> 包裹完整代码。"""

TD_PROMPT = """你是塔防游戏程序员，生成植物大战僵尸风网格塔防 Demo。

约束: 禁止 time/os/sleep/input/while True, 波次用 for wave in range, 只 import random
必须: 二维数组grid[row][col]战场, Plant类(攻击)+Zombie类(移动啃咬), 阳光系统(+25/回合),
      5种植物🌻🌱🥜❄️💣, 3种僵尸🧟🛡️👹, main()预设防线+3波自动运行+打印ASCII战场

用 <CODE> 和 </CODE> 包裹完整代码。"""

FIX_PROMPT = """修复以下游戏代码。禁止 time/os/sleep/input/while True，必须自动运行。

错误: {error}

当前代码:
```python
{code}
```

用 <CODE> 和 </CODE> 包裹修复后完整代码。"""

FIX_FROM_REVIEW_PROMPT = """根据代码审查反馈，定向修复以下具体问题。只修改有问题的部分，保持其他代码结构和逻辑不变。

【必须修复的 Bug】
{bugs}

【性能/结构优化建议】
{optimizations}

【安全风险】
{security_issues}

【审查总结】
{summary}

当前代码:
```python
{code}
```

规则:
1. 逐一修复上面的每个 bug，不要引入新问题
2. 优化建议酌情采纳，安全风险必须消除
3. 禁止 time/os/sleep/input/while True
4. 保持代码可自动运行（main() 函数入口）
5. 用 <CODE> 和 </CODE> 包裹修复后完整代码。"""


def _extract_code(text: str) -> str:
    """从 <CODE> 标签提取代码，兜底直接返回原文"""
    m = re.search(r'<CODE>\s*\n?(.*?)\n?\s*</CODE>', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # 兜底: 尝试从 ```python 提取
    m = re.search(r'```python\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _detect_game_type(state: dict) -> str:
    raw = state.get("raw_input", "")
    design = state.get("game_design", {})
    genre = design.get("genre", "")
    core = design.get("core_mechanic", "")
    combined = f"{raw} {genre} {design.get('title','')} {core}"

    # 卡牌/RPG 特征：优先匹配，避免被"网格"等通用词误判为塔防
    card_keywords = ["卡牌", "抽卡", "羁绊", "卡牌RPG", "gacha", "card game",
                     "回合制", "PVP", "PVE", "对战"]
    is_card_game = any(kw.lower() in combined.lower() for kw in card_keywords)

    # 塔防强特征：只有这些词出现才算塔防（去掉了"网格/grid/布阵/防线"等通用词）
    td_strong = ["塔防", "tower defense", "植物大战僵尸", "pvz",
                 "僵尸", "阳光", "sun", "波次", "wave",
                 "豌豆", "坚果", "樱桃", "向日葵", "寒冰", "5x9", "5×9"]

    is_td = any(kw.lower() in combined.lower() for kw in td_strong)

    # 卡牌游戏优先生成对战模板，即使策划文档里提到了"网格"
    if is_card_game and not is_td:
        logger.info("codegen_type", type="fighter", reason="card_rpg_detected")
        return "fighter"

    if is_td:
        logger.info("codegen_type", type="tower_defense", reason="td_keywords")
        return "tower_defense"

    return "fighter"


def _save_code(path: Path, code: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    return path


def _run_code(filepath: Path) -> tuple[bool, str]:
    try:
        r = subprocess.run(["python3", str(filepath)], capture_output=True, text=True, timeout=15, cwd=str(OUTPUT_DIR))
        out = r.stdout[:2500] + ("...(截断)" if len(r.stdout) > 2500 else "")
        if r.returncode != 0:
            out += f"\nSTDERR:\n{r.stderr[:1500]}"
            return False, out
        return True, out
    except subprocess.TimeoutExpired:
        return False, "执行超时(>15s)"
    except Exception as e:
        return False, f"执行异常: {e}"


async def _fix_code(code: str, error: str, design: str) -> str:
    try:
        resp = await llm_client.achat(
            [{"role":"system","content":"你是游戏调试专家。修复代码，用<CODE></CODE>包裹。"},
             {"role":"user","content": FIX_PROMPT.format(error=error[:1000], code=code[:4000])}],
            temperature=0.1, max_tokens=4096)
        return _extract_code(resp)
    except Exception as e:
        logger.error("fix_failed", error=str(e)[:80])
    return ""


async def _fix_from_review(code: str, feedback: dict) -> str:
    """根据 Reviewer 反馈定向修复代码中的具体问题"""
    bugs = json.dumps(feedback.get("bugs", []), ensure_ascii=False, indent=2)[:2000]
    optimizations = json.dumps(feedback.get("optimizations", []), ensure_ascii=False, indent=2)[:1500]
    security = json.dumps(feedback.get("security_issues", []), ensure_ascii=False, indent=2)[:1000]
    summary = feedback.get("summary", "")[:300]

    prompt = FIX_FROM_REVIEW_PROMPT.format(
        bugs=bugs, optimizations=optimizations, security_issues=security,
        summary=summary, code=code[:4000]
    )
    try:
        resp = await llm_client.achat(
            [{"role":"system","content":"你是游戏调试专家，根据审查反馈逐一修复代码问题。用<CODE></CODE>包裹。"},
             {"role":"user","content": prompt}],
            temperature=0.1, max_tokens=4096)
        fixed = _extract_code(resp)
        if fixed and len(fixed) > 200:
            return fixed
    except Exception as e:
        logger.error("review_fix_failed", error=str(e)[:80])
    return ""


async def code_generator_agent(state: dict) -> dict:
    design = state.get("game_design", {})
    narrative = state.get("narrative", {})
    if not design:
        return {"errors": ["缺少 game_design"]}

    # ===== 定向修复路径：Reviewer 发现 bug，回传具体问题让 LLM 修 =====
    review_feedback = state.get("review_feedback")
    if review_feedback:
        logger.info("agent_codegen_fix_mode", bugs=len(review_feedback.get("bugs",[])))
        current_code = ""
        prev_code_result = state.get("code_result", {})
        for f in prev_code_result.get("files", []):
            if f.get("path", "").endswith(".py"):
                current_code = f.get("content", "")
                break

        if not current_code:
            return {"errors": ["定向修复失败: 缺少当前代码"]}

        # LLM 根据具体 bug 做定向修复
        fixed_code = await _fix_from_review(current_code, review_feedback)
        if not fixed_code:
            return {"errors": ["定向修复失败: LLM 未返回有效代码"],
                    "review_feedback": None}

        code = fixed_code
        filepath = _save_code(OUTPUT_DIR / "main.py", code)

        # 修复后重新验证
        validation = validate_code_syntax(code, "python")
        run_passed, run_output = False, ""
        ok, out = _run_code(filepath)
        if ok:
            run_passed, run_output = True, out
            logger.info("review_fix_run_pass")
        else:
            # 审查修复后运行失败 → 用错误日志再修一次（兜底）
            logger.warning("review_fix_run_fail", error=out[:120])
            fallback = await _fix_code(code, out, "定向修复后验证失败")
            if fallback and len(fallback) > 200:
                code = fallback
                _save_code(filepath, code)
                ok2, out2 = _run_code(filepath)
                if ok2:
                    run_passed, run_output = True, out2
                    logger.info("review_fix_fallback_pass")
                else:
                    run_output = out2
            else:
                run_output = out

        loopback_count = state.get("loopback_count", 0) + 1
        return {
            "code_result": {
                "language": "python", "entry_point": "main.py",
                "files": [{"path":"main.py","description":"审查后定向修复","content":code,"validation":validation}],
                "run_passed": run_passed, "run_output": run_output[:2000],
                "auto_fixed": True, "fix_attempts": 1,
                "game_type": _detect_game_type(state),
            },
            "review_feedback": None,  # 清除反馈，避免重复修复
            "loopback_count": loopback_count,
            "messages": [{"role":"ai","name":"code_generator",
                "content": f"定向修复完成: {'✅ 通过' if run_passed else '⚠️ 运行失败'} [审查反馈修复]"}]}

    # ===== 正常生成路径 =====
    game_type = _detect_game_type(state)
    system_prompt = TD_PROMPT if game_type == "tower_defense" else FIGHTER_PROMPT

    genre = design.get("genre", "RPG")
    core = design.get("core_mechanic", "")
    features = design.get("key_features", [])
    characters = narrative.get("characters", []) if narrative else []
    design_summary = f"{genre} - {core}"
    char_desc = f"角色: {[c['name'] for c in characters[:3]]}" if characters else ""

    rag_hits = await vector_rag.retrieve(f"{game_type} 代码架构", top_k=2)
    rag_context = "\n".join([h["content"][:300] for h in rag_hits]) if rag_hits else ""

    user_msg = f"""{design_summary} | {char_desc}
{('参考: ' + rag_context) if rag_context else ''}
写一个可运行的 main.py。用 <CODE></CODE> 包裹代码。"""

    logger.info("agent_codegen_start", game_type=game_type, genre=genre)

    # Step 1: 生成代码
    code = ""
    for attempt in range(2):
        try:
            resp = await llm_client.achat(
                [{"role":"system","content":system_prompt},{"role":"user","content":user_msg}],
                temperature=0.3, max_tokens=4096)
            code = _extract_code(resp)
            if code and len(code) > 200:
                break
            logger.warning("code_extract_empty", attempt=attempt)
        except Exception as e:
            logger.error("codegen_llm_failed", attempt=attempt, error=str(e)[:80])

    if not code or len(code) < 200:
        return {"errors": ["代码生成失败或太短"], "code_result": {"language":"python","files":[],"entry_point":"main.py"}}

    filepath = _save_code(OUTPUT_DIR / "main.py", code)

    # Step 2: 语法校验
    validation = validate_code_syntax(code, "python")

    # Step 3: 运行验证 + 自动修复 (最多2次)
    run_passed, run_output, fix_attempts = False, "", 0
    for attempt in range(3):
        ok, out = _run_code(filepath)
        if ok:
            run_passed, run_output = True, out
            logger.info("code_run_pass", attempt=attempt)
            break
        else:
            logger.warning("code_run_fail", attempt=attempt, error=out[:200])
            fix_attempts += 1
            run_output = out
            if attempt < 2:
                fixed = await _fix_code(code, out, design_summary)
                if fixed and len(fixed) > 200:
                    code = fixed
                    _save_code(filepath, code)
                    logger.info("code_fix_applied", attempt=attempt+1)

    return {
        "code_result": {
            "language": "python", "entry_point": "main.py",
            "files": [{"path":"main.py","description":"","content":code,"validation":validation}],
            "run_passed": run_passed, "run_output": run_output[:2000],
            "auto_fixed": fix_attempts > 0, "fix_attempts": fix_attempts,
            "game_type": game_type,
        },
        "messages": [{"role":"ai","name":"code_generator",
            "content": f"代码{'✅通过' if run_passed else '⚠️失败'}{' (修复'+str(fix_attempts)+'次)' if fix_attempts else ''}[{game_type}]"}],
    }
