#!/usr/bin/env python3
"""
游戏开发知识库 PDF 生成器
生成 5 份专业中文游戏开发知识文档，覆盖 JD 所需全部领域
"""
import os
from pathlib import Path
from fpdf import FPDF

OUTPUT_DIR = Path(__file__).parent / "data" / "knowledge_pdfs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 使用支持中文的字体（系统自带）
# macOS 系统自带 PingFang
FONT_PATH = "/System/Library/Fonts/PingFang.ttc"
FALLBACK_FONT = "/System/Library/Fonts/STHeiti Light.ttc"

if not os.path.exists(FONT_PATH):
    FONT_PATH = FALLBACK_FONT


class ChinesePDF(FPDF):
    def __init__(self, title):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.add_font("CN", "", FONT_PATH, uni=True)
        self.add_font("CN", "B", FONT_PATH, uni=True)
        self.title_text = title

    def header(self):
        if self.page_no() == 1:
            self.set_font("CN", "B", 18)
            self.cell(0, 14, self.title_text, new_x="LMARGIN", new_y="NEXT", align="C")
            self.set_draw_color(92, 110, 245)
            self.set_line_width(0.6)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)

    def section(self, title):
        self.set_font("CN", "B", 14)
        self.set_text_color(20, 20, 50)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 180, 200)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def body(self, text):
        self.set_font("CN", "", 10.5)
        self.set_text_color(50, 50, 70)
        self.multi_cell(0, 6.5, text)
        self.ln(2)

    def sub_section(self, title):
        self.set_font("CN", "B", 11.5)
        self.set_text_color(60, 60, 100)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def bullet(self, text):
        self.set_font("CN", "", 10)
        self.set_text_color(60, 60, 80)
        self.cell(5, 6, "•")
        x = self.get_x()
        self.multi_cell(0, 6, text)


def generate_all_pdfs():
    # ============================================================
    # PDF 1: 游戏设计核心模式与循环
    # ============================================================
    pdf = ChinesePDF("游戏设计核心模式与循环机制")
    pdf.add_page()

    pdf.section("一、核心游戏循环 (Core Game Loop)")
    pdf.body("游戏的核心循环是所有系统的骨架。不同类型的游戏有不同的循环模式，但都遵循「行动→反馈→成长→新挑战」的基本节奏。理解核心循环是游戏策划的基本功。")
    pdf.sub_section("1.1 RPG 核心循环")
    pdf.body("RPG 的标准循环为：探索(Explore) → 战斗(Combat) → 获取(Loot) → 成长(Growth) → 探索更高难度区域。每次循环应提供递增的挑战和对应的奖励。卡牌RPG在此基础上增加了抽卡(Gacha)作为额外的获取渠道，形成双重循环。")
    pdf.sub_section("1.2 塔防核心循环")
    pdf.body("塔防(Tower Defense)的核心循环：波次准备(Prepare) → 放置塔防(Place) → 战斗阶段(Fight) → 资源结算(Settle) → 升级解锁(Upgrade)。PvZ类网格塔防中，阳光系统是循环的核心驱动力：阳光产出(向日葵/自然掉落) → 购买植物 → 植物攻击 → 击杀僵尸获取更多阳光。")
    pdf.sub_section("1.3 MOBA 核心循环")
    pdf.body("MOBA 的对局内循环：对线(Farming) → 击杀/助攻(Gank) → 获取金币经验 → 购买装备 → 推塔 → 团战 → 胜利。技能CD、资源控制、视野争夺构成策略层。")

    pdf.section("二、游戏类型设计范式")
    pdf.sub_section("2.1 卡牌RPG")
    pdf.body("卡牌RPG融合了收集(Card Collection)与角色扮演两大系统。核心设计要点：1)属性克制（水火风土/元素相生相克）2)费用曲线（Cost Curve，确保高费卡牌提供更高价值）3)稀有度分层（N/R/SR/SSR，每层强度提升约15-25%）4)阵容深度（角色之间的组合技/羁绊系统）。")
    pdf.sub_section("2.2 塔防策略")
    pdf.body("塔防游戏的核心设计要素：1)塔的定位分类（生产型/输出型/控制型/AOE型/肉盾型）2)敌人波次设计（数量递增、兵种混合、Boss波）3)地形与摆放策略（不同地形对塔的加成/限制）4)资源经济（初始资源+战斗中持续获取）。")
    pdf.sub_section("2.3 Roguelike/Roguelite")
    pdf.body("Roguelike 核心：程序化随机生成 + 永久死亡。Roguelite 变体加入了跨局成长(meta-progression)。关键设计：房间/地图生成算法（BSP/细胞自动机/预制模板拼接）、道具协同(Build Synergy)、风险回报决策。")
    pdf.sub_section("2.4 横版动作")
    pdf.body("横版动作游戏设计要素：1)连招系统（轻击/重击/特殊技的组合链，通常3-8段）2)受击反馈（屏幕震动/顿帧/击退距离）3)关卡节奏（战斗段→平台段→Boss战→奖励段）4)角色成长（技能树解锁 vs 数值成长）。")

    pdf.section("三、策略深度与玩家心流")
    pdf.body("心流(Flow State)由Mihaly Csikszentmihalyi提出，是游戏体验的黄金标准。核心公式：挑战难度 ≈ 玩家技能。太简单→无聊，太难→焦虑。")
    pdf.sub_section("3.1 难度曲线设计")
    pdf.body("标准难度曲线为三段式：1)新手期（1-30%进度）：线性教学+负反馈保护（如隐藏的伤害减免）2)成长期（30-70%）：解锁核心机制，难度梯度增大 3)终局（70-100%）：高难内容，考验最优解(Build)能力。")
    pdf.sub_section("3.2 心流控制节奏")
    pdf.body("关卡内节奏：平缓段（资源积累，2-3波）→ 紧凑段（敌人密集，1-2波）→ 高潮(Final Wave，Boss或大量敌人）→ 结算奖励。这个节奏循环被称为「心流波浪(Flow Wave)」。")

    pdf.output(str(OUTPUT_DIR / "01_游戏设计核心模式与循环.pdf"))
    print("PDF 1/5 完成: 游戏设计核心模式")

    # ============================================================
    # PDF 2: 战斗系统与数值平衡设计
    # ============================================================
    pdf = ChinesePDF("战斗系统与数值平衡公式")
    pdf.add_page()

    pdf.section("一、回合制战斗系统设计")
    pdf.body("回合制战斗是卡牌RPG最常见的基础系统。核心要素：行动顺序（速度/ATB）、技能冷却（Cooldown）、资源管理（MP/能量/行动点）。")
    pdf.sub_section("1.1 行动条系统 (ATB)")
    pdf.body("Action Time Battle 系统：每个角色有速度属性(speed)，每帧/每tick行动条累计 speed 值，满100可行动。行动后回退0并重新累计。公式：action_bar += speed * dt / 1000。当 action_bar >= 100: 可行动。")
    pdf.sub_section("1.2 技能冷却机制")
    pdf.body("冷却(Cooldown)控制技能使用频率。设计规则：1)普通攻击：cd=0，伤害基数 1.0x 2)小技能：cd=1-2，伤害 1.2-1.5x 3)大招：cd=3-5，伤害 2.0-3.0x 4)终极技：cd=6-8，伤害 4.0-6.0x 或附带强控效果。")
    pdf.sub_section("1.3 元素克制系统")
    pdf.body("属性克制增加策略深度。常用克制体系：1)三元素循环（火>草>水>火，克制方+50%伤害）2)五元素扩展（金木水火土相生相克）3)光暗双属性（互克，或克制所有四元素）。克制伤害公式：final_damage = base_damage * (1 + element_bonus)，element_bonus 通常为 0.3~1.0。")

    pdf.section("二、实时战斗与格斗数值")
    pdf.sub_section("2.1 伤害计算公式")
    pdf.body("通用 RPG/动作游戏伤害公式：damage = (attack_power * skill_multiplier - defense * defense_penetration) * (1 + crit_bonus + element_bonus)。简化版本（暗黑破坏神风格）：damage = base_atk * (1 + atk_bonus%) * skill_multiplier * (1 - defense/(defense + 1000)) * random(0.9, 1.1)。")
    pdf.sub_section("2.2 TTK (Time To Kill) 设计标准")
    pdf.body("TTK 是战斗节奏的核心指标。标准参考值：1)PvE 普通敌人：10-25秒 2)PvE Boss：60-180秒 3)PvP 对决：3-8秒（强调策略和爆发）4)MOBA团战：5-15秒(单个英雄击杀)。TTK 公式：TTK = target_hp / (attacker_dps * hit_rate)。")
    pdf.sub_section("2.3 平衡评分系统")
    pdf.body("平衡评分(Balance Score)用于评估角色/装备的强度。公式：score = (offensive_value + defensive_value + utility_value) / cost。其中 offensive_value = atk * (1+crit_rate*crit_dmg) * speed_factor，defensive_value = hp * (1+defense/1000) * (1+evasion_rate)。")

    pdf.section("三、塔防数值设计")
    pdf.sub_section("3.1 植物数值框架")
    pdf.body("PvZ 风格塔防的植物数值设计原则：1)向日葵：cost=50, production=25/回合, hp=80 2)豌豆射手：cost=100, dps=20, hp=80 3)坚果墙：cost=50, hp=400, 无攻击 4)寒冰射手：cost=175, dps=15, 附带3回合减速 5)樱桃炸弹：cost=150, 一次性AOE伤害=180。")
    pdf.sub_section("3.2 僵尸难度曲线")
    pdf.body("僵尸HP和速度随波次递增：1)普通僵尸：HP=100, speed=1格/回合 2)路障僵尸：HP=200, speed=1 3)铁桶僵尸：HP=350, speed=0.8 4)巨人僵尸：HP=800, speed=0.5, 攻击力=植物一击必杀。波次公式：WAVE_i 僵尸数 = 3 + 2*i，高级僵尸概率 = min(0.05*i, 0.4)。")

    pdf.section("四、攻击/技能实现参考")
    pdf.body("MOBA 类游戏技能设计模式：1)指向性技能（Targeted）：选择目标→播放前摇动画→结算伤害→播放后摇 2)非指向性技能（Skillshot）：创建弹道对象→每帧移动→碰撞检测→命中结算 3)范围技能（AoE）：创建圆形/扇形判定区域→范围内的所有敌人受伤。")
    pdf.body("特效管理参考：1)对象池模式：预创建技能特效实例，避免频繁GC 2)帧动画：每个技能对应一组ASCII帧（3-5帧），逐帧播放 3)冷却显示：cd_remaining / cd_max 映射到 UI 冷却图标。")

    pdf.output(str(OUTPUT_DIR / "02_战斗系统与数值平衡.pdf"))
    print("PDF 2/5 完成: 战斗系统与数值平衡")

    # ============================================================
    # PDF 3: 游戏代码架构与设计模式
    # ============================================================
    pdf = ChinesePDF("游戏代码架构与设计模式")
    pdf.add_page()

    pdf.section("一、游戏架构模式总览")
    pdf.body("游戏开发中常用的架构模式决定了代码的可维护性和性能。核心模式包括：ECS(Entity Component System)、组件式(Component-Based)、状态机(State Machine)、对象池(Object Pool)、事件总线(Event Bus)、命令模式(Command Pattern)。")

    pdf.section("二、ECS vs 组件式架构")
    pdf.sub_section("2.1 ECS (Entity Component System)")
    pdf.body("ECS 将 数据(Component) 与 逻辑(System) 完全分离。Entity 只是一个 ID，Component 存储纯数据，System 对所有包含特定组件的 Entity 执行逻辑。优势：高并发（System 可并行执行）、高灵活性（动态添加/移除组件）、缓存友好。适合：实体数量巨大的游戏（如 Vampire Survivors 类）。")
    pdf.sub_section("2.2 组件式 (Component-Based)")
    pdf.body("传统的 GameObject + Component 模式。GameObject 持有多个 Component，每个 Component 有自身的 Update() 方法。优势：直观易理解、Unity/Unreal 原生支持。适合：实体数量适中的游戏（RPG、动作游戏）。")
    pdf.body("小型Demo推荐使用组件式或更简单的面向对象模式：Hero 类直接包含 name/hp/skills/cooldowns 属性，BattleSystem 类协调战斗流程，避免过度设计。")

    pdf.section("三、状态机模式 (State Machine)")
    pdf.body("状态机是管理角色/UI/游戏流程状态的标准方案。每个状态有3个生命周期：OnEnter() - 状态进入时执行一次，OnUpdate() - 每帧/每回合执行，OnExit() - 状态退出时清理。")
    pdf.body("战斗角色状态机示例：Idle(待机) → Attack(攻击, 播放动画→造成伤害→回Idle) → Hit(受击, 播放僵直→回Idle) → Dead(死亡, 播放死亡动画→移除)。")
    pdf.body("注意：简单的回合制 Demo 不需要完整状态机。直接在 Fighter.use_skill() 中同步完成「播放动画→计算伤害→扣HP」即可，避免异步状态切换导致的伤害延迟。")

    pdf.section("四、对象池模式 (Object Pool)")
    pdf.body("对象池是游戏性能优化的核心模式。频繁创建和销毁对象（子弹、特效、敌人）会导致 GC 压力，造成帧率波动。对象池预创建一批实例，使用时从池中获取(get)，用完后归还(release)。")
    pdf.body("实现参考：class ObjectPool: 维护一个 _available: list 和一个 _in_use: set。acquire() 从 _available pop，没有可用时创建新实例。release(obj) 重置 obj 状态并放回 _available。")

    pdf.section("五、事件总线 (Event Bus)")
    pdf.body("事件总线解耦模块间通信。模块不直接调用对方，而是发布(Publish)事件和订阅(Subscribe)事件。常见事件类型：ENTITY_DIED(entity_id)、DAMAGE_DEALT(source, target, amount)、LEVEL_COMPLETE、WAVE_START。")
    pdf.body("实现：EventBus 维护 handlers: dict[str, list[callable]]。emit(event_name, **data) 调用所有已注册的 handler。小型 Demo 不需要事件总线，直接用 BattleSystem 协调即可。")

    pdf.section("六、游戏主循环")
    pdf.body("标准游戏主循环(Game Loop)：while running: dt = clock.tick(FPS); process_input(dt); update(dt); render()。固定时间步长变体：accumulator += dt; while accumulator >= FIXED_DT: update(FIXED_DT); accumulator -= FIXED_DT。")
    pdf.body("Demo 代码中，回合制游戏不需要 while True。用 for round_num in range(1, max_rounds+1) 即可，每回合调用 fighter.use_skill() + print状态。塔防用 for wave in range(1, max_waves+1)，每波内部用 for turn in range(wave_duration)。")

    pdf.section("七、Python 游戏代码最佳实践")
    pdf.body("1) 类型注解：def use_skill(self, target: Fighter) -> int 2) 数据类：用 dict 或 dataclass 存储技能配置 3) 单一职责：Plant 只管攻击判定，BattleSystem 管流程协调 4) 数值外置：SKILL_DATA、ZOMBIE_TYPES 等配置用字典常量，不在类内部硬编码 5) 测试友好：核心逻辑函数纯函数化，方便 pytest 测试。")

    pdf.output(str(OUTPUT_DIR / "03_游戏代码架构与设计模式.pdf"))
    print("PDF 3/5 完成: 代码架构与设计模式")

    # ============================================================
    # PDF 4: AIGC 美术资产生成
    # ============================================================
    pdf = ChinesePDF("AIGC美术资产生成指南")
    pdf.add_page()

    pdf.section("一、2D 角色/场景生成")
    pdf.sub_section("1.1 Stable Diffusion Prompt 工程")
    pdf.body("高质量 Prompt 结构：主体描述(Subject) + 风格词(Style) + 质量词(Quality) + 光照(Lighting) + 构图(Composition)。示例：'anime warrior with silver armor, cel-shading, vibrant colors, intricate details, trending on ArtStation, cinematic lighting, full body shot, 8K, highly detailed, sharp focus'。")
    pdf.sub_section("1.2 常用风格词汇表")
    pdf.body("写实风格：photorealistic, 8K resolution, ray tracing, physically-based rendering, Unreal Engine 5, hyperdetailed。二次元风格：anime style, cel-shading, vibrant colors, clean linework, Studio Ghibli inspired, hand-painted textures。像素风格：pixel art, 32-bit, retro game style, crisp edges, limited color palette。低多边形：low poly, flat shading, minimalist geometry, stylized 3D, game-ready asset。")
    pdf.sub_section("1.3 Negative Prompt 标配")
    pdf.body("通用 Negative Prompt：low quality, blurry, distorted, deformed, ugly, watermark, text, bad anatomy, extra limbs, missing fingers, disfigured face, cloned face, gross proportions。二次元专项：realistic photo, 3D render, western art style, thick lines。")

    pdf.section("二、3D 资产与动画生成")
    pdf.body("3D 资产生成主流流程：1)概念图生成(2D) → 2)图像转3D Mesh(Meshy/CSM/Stable Projectorz) → 3)拓扑优化与UV展开 → 4)纹理生成(PBR材质) → 5)骨骼绑定与蒙皮 → 6)动画生成(Mixamo/Cascadeur/AI动画)。")
    pdf.sub_section("2.1 3D 模型生成指引关键词")
    pdf.body("角色模型：'game character 3D model, low poly, toon shader, hand-painted texture, rigged, game-ready, FBX format, 10K triangles, mobile optimized'。场景模型：'fantasy environment 3D model, modular kit, PBR textures, UE5 compatible, stylized art, low poly, game-ready asset'。")
    pdf.sub_section("2.2 游戏动画类型")
    pdf.body("基本动作集：Idle(待机呼吸)、Walk(行走循环)、Run(奔跑)、Attack(攻击×N种)、Skill(技能释放)、Hit(受击反馈)、Death(死亡)。MOBA额外：Recall(回城)、Teleport(传送)、Taunt(嘲讽)。动作标准：每个动画循环 1-2 秒，关键帧 8-15 帧(30fps)。")

    pdf.section("三、Qwen-Image-2.0 使用指南")
    pdf.body("Qwen-Image-2.0 是阿里云百炼平台的文生图模型，支持中文 Prompt。调用方式：OpenAI 兼容接口，model='Qwen-Image-2.0'，通过 images/generations 端点。参数：prompt(最多800字符)、size(1024x1024)、n(1-4)。返回图片 URL，有效期约1周。")
    pdf.body("Qwen-Image 优化技巧：1)中文 Prompt 比英文更精准 2)Prompt 控制在200字符内效果最好 3)指定画风关键词：二次元/赛博朋克/水墨/油画/低多边形 4)Negative Prompt 同样重要：'低质量, 模糊, 扭曲, 水印, 文字'。")

    pdf.section("四、UI/UX 设计中的色彩法则")
    pdf.body("60-30-10 色彩法则：60% 主色（背景/大面积区域），30% 辅色（面板/卡片），10% 强调色（按钮/CTA/关键信息）。游戏 UI 示例：深色主题(60%深蓝黑#0a0e14) + 紫蓝面板(30%#1a2332) + 亮金按钮(10%#FFD700)。另一方案：自然主题(60%草地绿) + 木色面板(30%#8B6914) + 阳光强调(10%#FFD700)。")

    pdf.output(str(OUTPUT_DIR / "04_AIGC美术资产生成指南.pdf"))
    print("PDF 4/5 完成: AIGC美术资产生成")

    # ============================================================
    # PDF 5: 商业化设计与关卡节奏
    # ============================================================
    pdf = ChinesePDF("游戏商业化设计与关卡节奏")
    pdf.add_page()

    pdf.section("一、免费游戏(F2P)商业化模式")
    pdf.sub_section("1.1 主要变现方式")
    pdf.body("1)抽卡(Gacha)：核心收入来源。保底机制(Pity System)是合规关键——通常 90 抽硬保底、50 抽软保底(概率递增)。2)月卡/战令(Battle Pass)：稳定小额收入，通常月卡¥30、战令¥68/赛季。3)外观付费：角色皮肤、武器皮肤、头像框、主页装饰。价格区间 ¥6-168。4)便利性道具：背包扩容、扫荡券、自动战斗。5)限时礼包/首充双倍。")
    pdf.sub_section("1.2 数值不卖(Pay-to-Win 规避)")
    pdf.body("核心原则：1)竞技公平性—PVP中不售卖直接数值优势 2)时间 vs 金钱—付费加速成长但不独占 3)外观与能力分离—皮肤只改变外观不影响属性。反例：直接售卖+100攻击力的装备。正例：售卖30天经验加成buff（非付费玩家花费更多时间也能达到）。")

    pdf.section("二、关卡(Level)设计方法论")
    pdf.sub_section("2.1 关卡节奏公式")
    pdf.body("理想关卡节奏遵循「三幕结构」：第一幕(25%进度)：建立情境+教学元素。第二幕(50%进度)：复杂度爬升+核心循环加速。第三幕(25%进度)：高潮+释放。塔防关卡示例：波次1-3（普通僵尸，建立防线）→ 波次4-6（路障+铁桶混编，防线压力）→ 波次7-8（巨人Boss+大量杂兵，Final Wave）→ 胜利/失败结算。")
    pdf.sub_section("2.2 难度梯度设计")
    pdf.body("基础公式：difficulty_score = base_difficulty * (1 + level_coefficient * (level - 1))。其中 base_difficulty 是第一关的难度基准，level_coefficient 是难度增长系数（通常 0.05-0.15）。塔防波次公式：zombies_in_wave(w) = base_count + wave_num * growth_rate。高级僵尸概率 = min(0.05 * wave_num, 0.40)。")
    pdf.sub_section("2.3 竞技场(Elo/MMR)匹配")
    pdf.body("PVP 匹配算法：Elo Rating 系统。预期胜率 = 1 / (1 + 10^((opponent_elo - player_elo) / 400))。K 因子调节积分变化速率，新手用 K=32（快速收敛），老手用 K=16。匹配池：±200 Elo 范围内寻找对手，等待超过 30s 扩大范围到 ±400。")

    pdf.section("三、玩家心理学与留存设计")
    pdf.sub_section("3.1 每日任务与活跃度")
    pdf.body("每日任务体系保持玩家日活(DAU)：1)签到系统—连续7天递增奖励 2)每日任务—3-5个简单任务（战斗×3、抽卡×1、升级×1） 3)限时活动—每周/双周更新内容。奖励设计原则：任务完成时间控制在15-30分钟，奖励价值约等于¥3-5的等值资源。")
    pdf.sub_section("3.2 社交与竞技驱动")
    pdf.body("社交系统提升留存：1)公会/联盟—每日捐献+公会Boss+公会战 2)好友系统—互赠体力+好友对战 3)排行榜—多维排名(战力/爬塔/PVP段位)。异步PVP(Arena模式)：玩家设置防守阵容，其他玩家挑战 AI 控制的该阵容。降低匹配等待，增加游戏全天活跃度。")

    pdf.section("四、数值策划速查表")
    pdf.body("【伤害公式基础】final_dmg = (base_atk * skill_mult - target_def * 0.5) * (1 + crit_dmg * crit_rate) * element_multiplier * random(0.9, 1.1)")
    pdf.body("【升级曲线】EXP_to_level(n) = base_exp * (1 + growth_rate)^(n-1)。RPG 常用 base_exp=100, growth_rate=0.15。前10级快速成长，之后放缓。")
    pdf.body("【掉落概率】稀有度分布：N 60%, R 25%, SR 10%, SSR 3%, UR 2%。十连保底至少1个SR。50抽软保底(SSR概率从0.6%递增至100%)。90抽硬保底。")
    pdf.body("【经济平衡】每日免费资源产出应占总产出50-60%，剩余由付费补充。单日游戏时间控制在60-90分钟(含所有活动)。付费用户时间效率约为免费用户的1.5-2倍。")

    pdf.output(str(OUTPUT_DIR / "05_商业化与关卡节奏设计.pdf"))
    print("PDF 5/5 完成: 商业化设计与关卡节奏")


if __name__ == "__main__":
    generate_all_pdfs()
    print(f"\n✅ 全部 5 份 PDF 已生成到: {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.glob("*.pdf")):
        size_kb = f.stat().st_size / 1024
        print(f"  📄 {f.name} ({size_kb:.1f} KB)")
