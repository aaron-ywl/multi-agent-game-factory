import random
from typing import List, Dict, Optional

# -------------------- 数据定义 --------------------
class Element:
    FIRE = "火"
    WATER = "水"
    WIND = "风"
    EARTH = "土"
    LIGHT = "光"
    DARK = "暗"

ELEMENT_WEAKNESS = {
    Element.FIRE: Element.WATER,
    Element.WATER: Element.WIND,
    Element.WIND: Element.EARTH,
    Element.EARTH: Element.FIRE,
    Element.LIGHT: Element.DARK,
    Element.DARK: Element.LIGHT,
}

class Fighter:
    def __init__(self, name: str, element: str, hp: int, atk: int, skill_name: str, skill_desc: str):
        self.name = name
        self.element = element
        self.max_hp = hp
        self.hp = hp
        self.atk = atk
        self.skill_name = skill_name
        self.skill_desc = skill_desc
        self.is_alive = True
        self.buffs: Dict[str, int] = {}

    def take_damage(self, damage: int) -> None:
        self.hp -= damage
        if self.hp <= 0:
            self.hp = 0
            self.is_alive = False

    def use_skill(self, target: 'Fighter') -> int:
        """返回造成的伤害值"""
        base_damage = self.atk
        # 元素克制
        if ELEMENT_WEAKNESS.get(self.element) == target.element:
            base_damage = int(base_damage * 1.5)
            print(f"  [克制] {self.name} 对 {target.name} 造成额外伤害!")
        elif ELEMENT_WEAKNESS.get(target.element) == self.element:
            base_damage = int(base_damage * 0.7)
            print(f"  [被抵抗] {self.name} 对 {target.name} 伤害降低。")
        # 随机浮动
        damage = int(base_damage * random.uniform(0.9, 1.1))
        target.take_damage(damage)
        return damage

    def __str__(self) -> str:
        return f"{self.name}({self.element}) HP:{self.hp}/{self.max_hp}"

class Player:
    def __init__(self, name: str):
        self.name = name
        self.team: List[Fighter] = []
        self.gold = 100  # 抽卡货币

    def draw_card(self, card_pool: List[Fighter]) -> Optional[Fighter]:
        if self.gold < 20:
            print(f"{self.name} 金币不足，无法抽卡!")
            return None
        self.gold -= 20
        card = random.choice(card_pool)
        print(f"{self.name} 消耗20金币，抽到了: {card.name}")
        return card

    def add_to_team(self, fighter: Fighter) -> bool:
        if len(self.team) >= 5:
            print("队伍已满，无法添加!")
            return False
        self.team.append(fighter)
        print(f"{fighter.name} 加入了 {self.name} 的队伍!")
        return True

    def get_alive_fighters(self) -> List[Fighter]:
        return [f for f in self.team if f.is_alive]

# -------------------- 战场 --------------------
class HexGrid:
    def __init__(self, radius: int = 2):
        """简单六边形网格，半径2表示中心+2圈"""
        self.radius = radius
        self.grid: Dict[str, Optional[Fighter]] = {}
        # 生成坐标 (q,r,s) 满足 q+r+s=0
        for q in range(-radius, radius+1):
            for r in range(-radius, radius+1):
                s = -q - r
                if abs(s) <= radius:
                    self.grid[f"{q},{r},{s}"] = None

    def place_fighter(self, fighter: Fighter, coord: str) -> bool:
        if coord in self.grid and self.grid[coord] is None:
            self.grid[coord] = fighter
            return True
        return False

    def print_grid(self, player_a: Player, player_b: Player) -> None:
        """简单ASCII打印"""
        print("\n战场俯瞰 (A方在上，B方在下):")
        for r in range(-self.radius, self.radius+1):
            row_str = "  " * abs(r)
            for q in range(-self.radius, self.radius+1):
                s = -q - r
                if abs(s) <= self.radius:
                    coord = f"{q},{r},{s}"
                    f = self.grid[coord]
                    if f:
                        # 判断属于哪一方
                        if f in player_a.team:
                            row_str += "A "
                        else:
                            row_str += "B "
                    else:
                        row_str += ". "
            print(row_str)
        print("图例: A-玩家队伍, B-敌人队伍, .-空位")

# -------------------- 游戏逻辑 --------------------
def create_card_pool() -> List[Fighter]:
    return [
        Fighter("焰心·艾莉娅", Element.FIRE, hp=300, atk=45, skill_name="烈焰斩", skill_desc="对目标造成火焰伤害"),
        Fighter("暗蚀·维吉尔", Element.DARK, hp=280, atk=50, skill_name="暗影突袭", skill_desc="对目标造成暗影伤害"),
        Fighter("清流·米拉", Element.WATER, hp=320, atk=40, skill_name="水之冲击", skill_desc="对目标造成水流伤害"),
        Fighter("磐石·格伦", Element.EARTH, hp=400, atk=35, skill_name="岩崩", skill_desc="对目标造成土石伤害"),
        Fighter("疾风·西尔维娅", Element.WIND, hp=270, atk=48, skill_name="风刃", skill_desc="对目标造成风刃伤害"),
        Fighter("圣光·奥罗拉", Element.LIGHT, hp=290, atk=42, skill_name="光明之锤", skill_desc="对目标造成光耀伤害"),
    ]

def battle_round(player: Player, enemy: Player, round_num: int) -> None:
    print(f"\n=== 第 {round_num} 回合开始 ===")
    # 玩家队伍行动
    for fighter in player.get_alive_fighters():
        if not enemy.get_alive_fighters():
            break
        target = random.choice(enemy.get_alive_fighters())
        dmg = fighter.use_skill(target)
        print(f"  {fighter.name} 使用 [{fighter.skill_name}] 对 {target.name} 造成 {dmg} 伤害!")
        if not target.is_alive:
            print(f"  {target.name} 被击败!")
    # 敌人队伍行动
    for fighter in enemy.get_alive_fighters():
        if not player.get_alive_fighters():
            break
        target = random.choice(player.get_alive_fighters())
        dmg = fighter.use_skill(target)
        print(f"  {fighter.name} 使用 [{fighter.skill_name}] 对 {target.name} 造成 {dmg} 伤害!")
        if not target.is_alive:
            print(f"  {target.name} 被击败!")

def main():
    print("===== 二次元卡牌RPG Demo =====")
    # 初始化
    player = Player("冒险者")
    enemy = Player("暗影军团")
    card_pool = create_card_pool()
    grid = HexGrid(radius=2)

    # 抽卡阶段
    print("\n--- 抽卡阶段 ---")
    for _ in range(3):
        card = player.draw_card(card_pool)
        if card:
            player.add_to_team(card)
    # 敌人预设队伍
    enemy_fighters = [card_pool[1], card_pool[3], card_pool[5]]  # 维吉尔, 格伦, 奥罗拉
    for f in enemy_fighters:
        enemy.add_to_team(f)

    # 布置队伍到六边形网格 (简单固定位置)
    print("\n--- 布置队伍 ---")
    player_coords = ["0,2,-2", "-1,1,0", "1,1,-2"]
    enemy_coords = ["0,-2,2", "-1,-1,2", "1,-1,0"]
    for i, fighter in enumerate(player.team):
        if i < len(player_coords):
            grid.place_fighter(fighter, player_coords[i])
    for i, fighter in enumerate(enemy.team):
        if i < len(enemy_coords):
            grid.place_fighter(fighter, enemy_coords[i])
    grid.print_grid(player, enemy)

    # 战斗阶段
    max_rounds = 10
    for round_num in range(1, max_rounds + 1):
        battle_round(player, enemy, round_num)
        # 检查胜负
        if not player.get_alive_fighters():
            print(f"\n{player.name} 的队伍全灭! 战斗结束。")
            break
        if not enemy.get_alive_fighters():
            print(f"\n{enemy.name} 的队伍全灭! 胜利!")
            break
        # 显示状态
        print(f"\n回合结束状态:")
        print(f"{player.name} 队伍: {[str(f) for f in player.team if f.is_alive]}")
        print(f"{enemy.name} 队伍: {[str(f) for f in enemy.team if f.is_alive]}")
    else:
        print(f"\n达到最大回合数 {max_rounds}，战斗平局!")

    print("\n===== 游戏结束 =====")

if __name__ == "__main__":
    main()