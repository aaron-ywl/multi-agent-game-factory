"""
Agent 4: Code Reviewer Agent (自动代码审查 Agent)
负责：代码安全性扫描、性能分析、最佳实践检查
"""
import json
import structlog
from src.services.llm_client import llm_client

logger = structlog.get_logger()

SYSTEM_PROMPT = """你是一个资深游戏技术主管/代码审查专家。你的任务是审查游戏代码并给出改进建议。

审查维度：
1. 正确性 - 逻辑是否有 Bug、边界条件处理
2. 性能 - 是否有性能瓶颈、可以优化
3. 安全 - 是否有安全问题（注入、不安全调用等）
4. 可维护性 - 代码结构是否清晰、是否易于扩展
5. 游戏特有 - 帧率稳定性、对象池使用、资源管理

你必须输出合法 JSON：
{
  "score": 85,
  "passed": true/false,
  "bugs": [
    {"severity": "critical/major/minor", "file": "文件名", "line": 行号, "description": "问题描述", "fix": "修复建议"}
  ],
  "optimizations": [
    {"category": "性能/内存/可读性", "description": "优化建议", "code_before": "原代码", "code_after": "建议修改"}
  ],
  "security_issues": [
    {"severity": "high/medium/low", "description": "安全描述", "fix": "修复方案"}
  ],
  "summary": "总体评价（50字以内）"
}
"""


async def code_reviewer_agent(state: dict) -> dict:
    """
    Agent 4: 代码审查 + 自动优化
    输入: code_result
    输出: code_review (CodeReviewResult), needs_regeneration
    """
    code_result = state.get("code_result", {})
    if not code_result or not code_result.get("files"):
        return {"errors": ["缺少 code_result"]}

    files = code_result.get("files", [])
    language = code_result.get("language", "python")

    # 构建审查内容（限制长度避免 token 溢出）
    code_snippets = []
    total_chars = 0
    for f in files:
        content = f.get("content", "")
        snippet = content[:2000]  # 每个文件最多2000字符
        code_snippets.append(f"### {f.get('path', 'unknown')}\n```{language}\n{snippet}\n```")
        total_chars += len(snippet)
        if total_chars > 8000:
            break

    code_text = "\n\n".join(code_snippets)
    validation_issues = []
    for f in files:
        v = f.get("validation", {})
        if v and v.get("errors"):
            validation_issues.extend(v["errors"])

    logger.info("agent_reviewer_start", files=len(files), code_chars=total_chars)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请审查以下游戏代码：

{code_text}

{'语法校验发现的问题：' + json.dumps(validation_issues, ensure_ascii=False) if validation_issues else ''}

请从正确性、性能、安全性、可维护性、游戏特性五个维度进行全面审查。输出 JSON。"""},
    ]

    try:
        result = await llm_client.achat_json(messages, temperature=0.2)
        logger.info("agent_reviewer_done", score=result.get("score", 0))
    except Exception as e:
        logger.error("agent_reviewer_failed", error=str(e))
        return {"errors": [f"Code Reviewer 失败: {str(e)}"]}

    score = result.get("score", 60)
    bugs = result.get("bugs", [])
    optimizations = result.get("optimizations", [])
    security_issues = result.get("security_issues", [])

    # 双重门禁：分数 ≥ 70 且 无 critical/major bug 才算通过
    has_blocking_bugs = any(
        b.get("severity", "") in ("critical", "major") for b in bugs
    )
    needs_regeneration = score < 70 or has_blocking_bugs

    return {
        "code_review": {
            "score": score,
            "passed": not needs_regeneration,
            "bugs": bugs,
            "optimizations": optimizations,
            "security_issues": security_issues,
        },
        "needs_regeneration": needs_regeneration,
        # 定向修复上下文：CodeGen 拿到后只修具体 bug，不全量重写
        "review_feedback": {
            "bugs": bugs,
            "optimizations": optimizations,
            "security_issues": security_issues,
            "summary": result.get("summary", ""),
        } if needs_regeneration else None,
        "messages": [{
            "role": "ai", "name": "code_reviewer",
            "content": f"代码审查完成: 评分 {score}/100, {'✅ 通过' if not needs_regeneration else '⚠️ 需改进'}" +
                       (f" → 定向修复 {len(bugs)} 个问题" if needs_regeneration else "")
        }],
    }
