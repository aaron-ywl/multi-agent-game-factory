"""
游戏开发专用工具集
- 数值平衡计算、代码验证、Prompt 增强、资源清单生成
"""
import json
import re
import math
import structlog

logger = structlog.get_logger()


# ============ 数值平衡计算器 ============

def calculate_game_balance(params: dict) -> dict:
    """
    游戏数值平衡校验
    输入: {base_attack, base_defense, health, level, scaling_factor, ...}
    输出: {balance_score, time_to_kill, dps_ratio, is_balanced, warnings, suggestions}
    """
    try:
        base_atk = float(params.get("base_attack", 10))
        base_def = float(params.get("base_defense", 5))
        health = float(params.get("health", 100))
        level = int(params.get("level", 1))
        scaling = float(params.get("scaling_factor", 0.1))
        target_ttk = float(params.get("target_ttk", 10.0))

        atk_scaled = base_atk * (1 + scaling * (level - 1))
        effective_dmg = max(1, atk_scaled - base_def * 0.5)
        ttk = health / effective_dmg if effective_dmg > 0 else 999
        dps_ratio = effective_dmg / health

        warnings = []
        suggestions = []

        if ttk < target_ttk * 0.5:
            warnings.append(f"TTK 过短 ({ttk:.1f}s)，战斗节奏偏快")
            suggestions.append(f"增加 HP 至 {int(health * target_ttk / ttk)} 或降低攻击力")
        elif ttk > target_ttk * 2.0:
            warnings.append(f"TTK 过长 ({ttk:.1f}s)，战斗节奏偏慢")
            suggestions.append(f"降低 HP 或提升攻击力")

        if dps_ratio > 0.3 and level <= 1:
            warnings.append("Lv1 伤害占比过高，存在秒杀风险")
            suggestions.append("降低基础攻击力或引入伤害上限机制")

        balance_score = 100 - len(warnings) * 20 - abs(ttk - target_ttk) / target_ttk * 20
        balance_score = max(0, min(100, round(balance_score, 1)))

        return {
            "balance_score": balance_score,
            "time_to_kill": round(ttk, 2),
            "dps_ratio": round(dps_ratio, 3),
            "effective_damage": round(effective_dmg, 2),
            "is_balanced": balance_score >= 70,
            "warnings": warnings,
            "suggestions": suggestions,
        }
    except Exception as e:
        logger.error("balance_calc_failed", error=str(e))
        return {"error": str(e), "is_balanced": False}


# ============ 代码语法校验 ============

def validate_code_syntax(code: str, language: str = "python") -> dict:
    """
    基础语法校验
    返回: {valid, errors, line_count, function_count, class_count}
    """
    try:
        lines = code.strip().split("\n")
        line_count = len(lines)

        # 统计函数/类
        func_count = len(re.findall(r"\bdef\s+(\w+)", code)) if language == "python" else 0
        class_count = len(re.findall(r"\bclass\s+(\w+)", code)) if language == "python" else 0

        errors = []
        if language == "python":
            try:
                compile(code, "<validate>", "exec")
            except SyntaxError as e:
                errors.append({"line": e.lineno, "msg": e.msg, "text": e.text})

        # 常见问题检测
        if "import *" in code:
            errors.append({"line": 0, "msg": "避免使用 wildcard import (import *)", "text": ""})
        if "eval(" in code or "exec(" in code:
            errors.append({"line": 0, "msg": "存在 eval/exec 安全风险", "text": ""})
        if "TODO" in code or "FIXME" in code:
            errors.append({"line": 0, "msg": "存在未完成的 TODO/FIXME", "text": ""})

        return {
            "valid": len([e for e in errors if e.get("text")]) == 0,
            "errors": errors,
            "line_count": line_count,
            "function_count": func_count,
            "class_count": class_count,
        }
    except Exception as e:
        return {"valid": False, "errors": [{"line": 0, "msg": str(e), "text": ""}]}


# ============ AIGC Prompt 增强器 ============

def enhance_art_prompt(base_prompt: str, style: str = "realistic") -> str:
    """
    为 2D/3D 资产生成增强 Prompt（符合 Stable Diffusion / Midjourney 最佳实践）
    输入: 基础描述
    输出: 增强后的专业 prompt
    """
    style_modifiers = {
        "realistic": "photorealistic, 8K resolution, ray tracing, physically-based rendering, "
                      "unreal engine 5, hyperdetailed, subsurface scattering",
        "stylized": "stylized art, cel-shading, vibrant colors, clean lines, "
                      "concept art style, Studio Ghibli inspired, hand-painted textures",
        "pixel": "pixel art, 32-bit, retro game style, crisp edges, limited color palette, "
                  "SNES style, sprite work",
        "lowpoly": "low poly, flat shading, minimalist geometry, vibrant ambient occlusion, "
                    "stylized 3D, game-ready asset",
    }
    negative = ("low quality, blurry, distorted, deformed, ugly, watermark, text, "
                "bad anatomy, extra limbs, missing fingers")
    style_str = style_modifiers.get(style, style_modifiers["realistic"])
    return f"{base_prompt}, {style_str} --negative {negative}"


# ============ 资源清单生成器 ============

def generate_asset_checklist(design: dict) -> dict:
    """
    根据游戏设计规格自动生成美术资源清单
    返回: {characters, environments, ui_elements, animations, vfx, props}
    """
    genre = design.get("genre", "").lower()
    features = design.get("key_features", [])
    art_style = design.get("art_style", "")

    checklist = {
        "characters": [],
        "environments": [],
        "ui_elements": ["主菜单", "HUD", "背包界面", "设置面板", "加载画面"],
        "animations": [],
        "vfx": [],
        "props": [],
    }

    if "rpg" in genre:
        checklist["characters"].extend(["主角（4方向行走+战斗）", "NPC×10+", "怪物×8+"])
        checklist["environments"].extend(["城镇", "野外", "地下城", "村庄"])
        checklist["animations"].extend(["待机", "行走", "攻击", "技能释放", "受伤", "死亡"])
        checklist["vfx"].extend(["技能特效", "升级光效", "传送特效", "伤害数字"])
        checklist["props"].extend(["宝箱", "药水", "装备图标", "传送门"])

    elif "fps" in genre or "shooter" in genre:
        checklist["characters"].extend(["玩家角色（第一人称武器）", "敌人×5+", "队友角色"])
        checklist["environments"].extend(["战场", "建筑内部", "城市街道"])
        checklist["animations"].extend(["换弹", "瞄准", "射击", "奔跑", "蹲伏"])
        checklist["vfx"].extend(["枪口火焰", "弹道轨迹", "爆炸", "烟雾", "血液"])
        checklist["props"].extend(["武器模型", "弹药箱", "掩体", "载具"])

    elif "moba" in genre:
        checklist["characters"].extend(["英雄角色×10+", "小兵", "野怪", "防御塔"])
        checklist["environments"].extend(["三路地图", "河道", "野区", "基地"])
        checklist["animations"].extend(["技能连招", "回城", "传送", "击杀特效"])
        checklist["vfx"].extend(["范围技能", "控制效果", "Buff/Debuff标识"])
        checklist["ui_elements"].extend(["小地图", "技能栏", "装备商店", "计分板"])

    elif "card" in genre or "卡牌" in genre:
        checklist["ui_elements"].extend(["卡牌面板", "抽牌动画", "回合指示器", "能量槽"])
        checklist["characters"].extend(["卡牌插画×30+", "英雄立绘"])
        checklist["vfx"].extend(["抽卡特效", "战斗特效", "进化特效"])

    # 通用项
    checklist["ui_elements"].append("音效管理界面")
    checklist["vfx"].append("UI 过渡动画")

    return checklist
