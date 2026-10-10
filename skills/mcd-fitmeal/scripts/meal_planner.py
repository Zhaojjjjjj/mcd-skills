#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcd-fitmeal · 确定性配餐脚本

根据麦当劳官方 MCP 营养数据（list-nutrition-foods 返回的餐品营养成分），
按用户的热量 / 蛋白质 / 碳水 / 钠 / 预算目标，计算出达标的 Top-N 套餐组合。

设计原则：组合优化用确定性算法完成，不依赖 LLM 心算，保证结果可复现、
可解释。实际使用时，--data 传入从 MCP 拉取的真实营养 JSON。

营养 JSON 格式（list）：
[
  {"code": "S001", "name": "麦香鸡（去酱版）", "category": "主食",
   "kcal": 375, "protein_g": 29, "fat_g": 13, "carbs_g": 38,
   "sodium_mg": 620, "price_cny": 15.0},
  ...
]
category 取值：主食 / 小食 / 饮料

示例：
    python3 meal_planner.py --demo
    python3 meal_planner.py --data nutrition.json --mode 减脂 --top 5
    python3 meal_planner.py --data nutrition.json --mode 增肌 --cal-min 700 --cal-max 1000 --protein-min 45 --budget-max 40 --json
"""

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# 三种模式的默认目标（用户给出的具体数字永远优先于默认值）
# ---------------------------------------------------------------------------
MODE_PRESETS = {
    "cut": {
        "label": "减脂",
        "cal_min": 400, "cal_max": 600,
        "protein_min": 30, "carbs_max": None, "sodium_max": 1200,
    },
    "bulk": {
        "label": "增肌",
        "cal_min": 700, "cal_max": 1000,
        "protein_min": 45, "carbs_max": None, "sodium_max": None,
    },
    "sugar": {
        "label": "控糖",
        "cal_min": 400, "cal_max": 700,
        "protein_min": 25, "carbs_max": 45, "sodium_max": 1200,
    },
}

MODE_ALIASES = {
    "cut": "cut", "cutting": "cut", "减脂": "cut",
    "bulk": "bulk", "bulking": "bulk", "增肌": "bulk",
    "sugar": "sugar", "控糖": "sugar",
}

# ---------------------------------------------------------------------------
# 内置示例菜单（仅用于 --demo 演示；实际使用请传入 MCP 真实数据）
# 数值为示例，请以麦当劳官方 MCP / 门店公示为准
# ---------------------------------------------------------------------------
SAMPLE_MENU = [
    {"code": "S001", "name": "麦香鸡（去酱版）", "category": "主食",
     "kcal": 375, "protein_g": 29, "fat_g": 13, "carbs_g": 38,
     "sodium_mg": 620, "price_cny": 15.0},
    {"code": "S002", "name": "麦香鸡", "category": "主食",
     "kcal": 425, "protein_g": 28, "fat_g": 18, "carbs_g": 40,
     "sodium_mg": 780, "price_cny": 15.0},
    {"code": "S003", "name": "板烧鸡腿堡", "category": "主食",
     "kcal": 400, "protein_g": 23, "fat_g": 14, "carbs_g": 42,
     "sodium_mg": 800, "price_cny": 21.0},
    {"code": "S004", "name": "双层深海鳕鱼堡", "category": "主食",
     "kcal": 450, "protein_g": 22, "fat_g": 18, "carbs_g": 46,
     "sodium_mg": 820, "price_cny": 24.0},
    {"code": "S005", "name": "巨无霸", "category": "主食",
     "kcal": 540, "protein_g": 25, "fat_g": 28, "carbs_g": 42,
     "sodium_mg": 940, "price_cny": 27.5},
    {"code": "S006", "name": "麦乐鸡（5块）", "category": "小食",
     "kcal": 230, "protein_g": 12, "fat_g": 14, "carbs_g": 12,
     "sodium_mg": 480, "price_cny": 12.5},
    {"code": "S007", "name": "玉米杯", "category": "小食",
     "kcal": 110, "protein_g": 3, "fat_g": 1, "carbs_g": 24,
     "sodium_mg": 10, "price_cny": 9.0},
    {"code": "S008", "name": "脆薯条（小）", "category": "小食",
     "kcal": 220, "protein_g": 3, "fat_g": 11, "carbs_g": 28,
     "sodium_mg": 150, "price_cny": 9.0},
    {"code": "S009", "name": "纯牛奶", "category": "饮料",
     "kcal": 150, "protein_g": 8, "fat_g": 8, "carbs_g": 11,
     "sodium_mg": 120, "price_cny": 9.0},
    {"code": "S010", "name": "鲜煮咖啡（小）", "category": "饮料",
     "kcal": 5, "protein_g": 0, "fat_g": 0, "carbs_g": 1,
     "sodium_mg": 5, "price_cny": 10.0},
    {"code": "S011", "name": "无糖可乐（小）", "category": "饮料",
     "kcal": 0, "protein_g": 0, "fat_g": 0, "carbs_g": 0,
     "sodium_mg": 20, "price_cny": 8.0},
]


def load_items(path):
    """从 JSON 文件加载餐品营养数据。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("items", data.get("foods", []))
    return data


def totals_of(items):
    """汇总一组餐品的营养与价格。"""
    t = {"kcal": 0, "protein_g": 0, "fat_g": 0, "carbs_g": 0,
         "sodium_mg": 0, "price_cny": 0.0}
    for it in items:
        t["kcal"] += it.get("kcal", 0)
        t["protein_g"] += it.get("protein_g", 0)
        t["fat_g"] += it.get("fat_g", 0)
        t["carbs_g"] += it.get("carbs_g", 0)
        t["sodium_mg"] += it.get("sodium_mg", 0)
        t["price_cny"] += it.get("price_cny", 0) or 0
    t["price_cny"] = round(t["price_cny"], 2)
    return t


def meets(totals, targets):
    """检查组合是否满足全部目标。"""
    if not (targets["cal_min"] <= totals["kcal"] <= targets["cal_max"]):
        return False
    if totals["protein_g"] < targets["protein_min"]:
        return False
    if targets.get("carbs_max") is not None and totals["carbs_g"] > targets["carbs_max"]:
        return False
    if targets.get("sodium_max") is not None and totals["sodium_mg"] > targets["sodium_max"]:
        return False
    if targets.get("budget_max") is not None and totals["price_cny"] > targets["budget_max"]:
        return False
    return True


def score(totals):
    """排序分数：蛋白质密度优先，其次钠越低越好，再次价格越低越好。"""
    density = totals["protein_g"] / max(totals["kcal"], 1) * 100
    return (round(density, 3), -totals["sodium_mg"], -totals["price_cny"])


def plan(items, targets, top_n=5):
    """生成达标组合：1 份主食 + 可选 1 份小食 + 可选 1 份饮料。"""
    mains = [i for i in items if i.get("category") == "主食"]
    sides = [i for i in items if i.get("category") == "小食"]
    drinks = [i for i in items if i.get("category") == "饮料"]

    results = []
    for main in mains:
        for side in [None] + sides:
            for drink in [None] + drinks:
                combo = [x for x in (main, side, drink) if x]
                t = totals_of(combo)
                if meets(t, targets):
                    results.append({
                        "items": [{"code": x.get("code"), "name": x["name"]} for x in combo],
                        "totals": t,
                        "protein_density": round(t["protein_g"] / max(t["kcal"], 1) * 100, 2),
                    })
    results.sort(key=lambda r: score(r["totals"]), reverse=True)
    return results[:top_n]


def print_table(results, label):
    """人类可读的表格输出。"""
    print("【%s】达标组合 Top-%d" % (label, len(results)))
    print("-" * 78)
    for idx, r in enumerate(results, 1):
        names = " + ".join(x["name"] for x in r["items"])
        t = r["totals"]
        print("%d. %s" % (idx, names))
        print("   热量 %d kcal｜蛋白质 %dg｜脂肪 %dg｜碳水 %dg｜钠 %dmg"
              % (t["kcal"], t["protein_g"], t["fat_g"], t["carbs_g"], t["sodium_mg"]))
        print("   参考价 ¥%s｜蛋白密度 %sg/100kcal" % (t["price_cny"], r["protein_density"]))
    print("-" * 78)
    print("注：营养数据仅供参考，实际以门店公示为准；价格为示例，实际以算价工具为准。")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="mcd-fitmeal 确定性配餐脚本：按营养目标计算达标的麦当劳套餐组合。",
        epilog="示例: python3 meal_planner.py --demo",
    )
    p.add_argument("--data", help="餐品营养 JSON 文件路径（不传则用内置示例菜单）")
    p.add_argument("--mode", default="cut",
                   help="模式：cut/减脂、bulk/增肌、sugar/控糖（默认 cut）")
    p.add_argument("--cal-min", type=int, help="热量下限 kcal（覆盖模式默认）")
    p.add_argument("--cal-max", type=int, help="热量上限 kcal（覆盖模式默认）")
    p.add_argument("--protein-min", type=float, help="蛋白质下限 g（覆盖模式默认）")
    p.add_argument("--carbs-max", type=float, help="碳水上限 g（覆盖模式默认）")
    p.add_argument("--sodium-max", type=float, help="钠上限 mg（覆盖模式默认）")
    p.add_argument("--budget-max", type=float, help="预算上限 元（可选）")
    p.add_argument("--top", type=int, default=5, help="返回 Top-N 组合（默认 5）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    p.add_argument("--demo", action="store_true", help="用内置示例菜单跑减脂演示")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.demo:
        results = plan(SAMPLE_MENU, dict(MODE_PRESETS["cut"]), top_n=5)
        print(">> 演示：减脂模式（400–600 kcal，蛋白质 ≥30g），内置示例菜单")
        print_table(results, "减脂")
        return 0

    mode_key = MODE_ALIASES.get(str(args.mode).strip().lower(), "cut")
    targets = dict(MODE_PRESETS[mode_key])
    for key in ("cal_min", "cal_max", "protein_min", "carbs_max", "sodium_max", "budget_max"):
        val = getattr(args, key)
        if val is not None:
            targets[key] = val
    label = MODE_PRESETS[mode_key]["label"]

    if args.data:
        items = load_items(args.data)
    else:
        print("提示：未指定 --data，使用内置示例菜单；实际使用请传入 MCP 真实数据。",
              file=sys.stderr)
        items = SAMPLE_MENU

    results = plan(items, targets, top_n=args.top)
    if not results:
        print("未找到达标组合，请放宽目标后重试。", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"mode": label, "targets": targets, "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print_table(results, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
