#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcd-lottery-ev · 麦麦抽奖精算 EV 计算器

确定性脚本,仅依赖 Python 标准库。
用于计算麦当劳积分抽奖的单抽期望值(EV)与历史回本率,输出"抽 / 不抽 / 抽几次"建议。

价值估算口径(透明、可复现):
  - 餐品 / 实物奖品:按麦当劳官方售价估算(元)
  - 优惠券:按"券面额 x 核销率"估算,核销率默认 0.5;也可直接在 value 中填入最终估算值
  - 积分奖品:按积分单价折算(默认 100 积分 = 1 元)
  - "谢谢参与"类:价值为 0

用法示例:
  python3 ev.py --prizes prizes.json --cost 100
  python3 ev.py --prizes prizes.json --cost 100 --point-value 0.008 --free-draws 2
  python3 ev.py --history history.json --total-cost 2000
  python3 ev.py --demo            # 内置演示数据(含 README 中的 EV=0.78 示例)
  python3 ev.py --prizes prizes.json --cost 100 --json

prizes.json 格式:
  [
    {"name": "巨无霸兑换券", "probability": 0.01, "value": 25.0},
    {"name": "谢谢参与",     "probability": 0.85, "value": 0.0}
  ]
  probability 为小数(0~1);若总和不为 1,脚本会自动归一化并提示。

history.json 格式:
  [
    {"name": "中薯兑换券", "value": 12.0, "won_at": "2026-09-12"},
    {"name": "50 积分",    "value": 0.5,  "won_at": "2026-09-15"}
  ]
"""

import argparse
import json
import sys

DEFAULT_POINT_VALUE = 0.01  # 1 积分 = 0.01 元(100 积分 = 1 元)

# 建议分级阈值(与 SKILL.md 保持一致)
TIER_STRONG = 1.0  # EV >= 1.0 : 强烈推荐
TIER_OK = 0.7      # 0.7 <= EV < 1.0 : 可抽


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit(f"错误:找不到文件 {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"错误:JSON 解析失败 {path}: {e}")


def normalize(prizes):
    """概率归一化:总和不为 1 时自动归一化并提示。"""
    total = sum(p["probability"] for p in prizes)
    if total <= 0:
        sys.exit("错误:概率总和必须大于 0")
    if abs(total - 1.0) > 1e-9:
        print(f"[提示] 概率总和为 {total:.4f},已自动归一化为 1。", file=sys.stderr)
        for p in prizes:
            p["probability"] = p["probability"] / total
    return prizes


def calc_ev(prizes, cost_points, point_value=DEFAULT_POINT_VALUE):
    prizes = normalize([dict(p) for p in prizes])
    rows = []
    for p in prizes:
        contrib = p["probability"] * p["value"]
        rows.append({
            "name": p["name"],
            "probability": p["probability"],
            "value": p["value"],
            "contribution": contrib,
        })
    expected = sum(r["contribution"] for r in rows)
    cost_rmb = cost_points * point_value
    ev_ratio = (expected / cost_rmb) if cost_rmb > 0 else float("inf")
    return {
        "rows": rows,
        "expected_value": expected,
        "cost_points": cost_points,
        "cost_rmb": cost_rmb,
        "point_value": point_value,
        "ev_ratio": ev_ratio,
    }


def recommend(ev_ratio, free_draws=0):
    if free_draws > 0:
        free_note = f"你还有 {free_draws} 次免费抽奖,免费的 EV 永远 >= 0,先把免费次数抽完。"
    else:
        free_note = "没有免费次数,全部消耗均为积分。"
    if ev_ratio >= TIER_STRONG:
        tier, advice = "🟢 强烈推荐", "数学期望为正,长期抽稳赚不赔(方差自负)。"
    elif ev_ratio >= TIER_OK:
        tier, advice = "🟡 可抽", "小额娱乐消费,期望小亏,就当买个开心。"
    else:
        tier, advice = "🔴 不建议", f"单抽期望亏损 {(1 - ev_ratio) * 100:.0f}%,积分留着换吃的更香。"
    return tier, advice, free_note


def calc_history(records, total_cost_points, point_value=DEFAULT_POINT_VALUE):
    total_value = sum(r["value"] for r in records)
    cost_rmb = total_cost_points * point_value
    payback = (total_value / cost_rmb) if cost_rmb > 0 else 0.0
    return {
        "records": records,
        "total_value": total_value,
        "total_cost_points": total_cost_points,
        "cost_rmb": cost_rmb,
        "point_value": point_value,
        "payback_rate": payback,
    }


def print_ev_report(res, free_draws=0, as_json=False):
    if as_json:
        tier, advice, free_note = recommend(res["ev_ratio"], free_draws)
        print(json.dumps({
            "expected_value_rmb": round(res["expected_value"], 4),
            "cost_points": res["cost_points"],
            "cost_rmb": round(res["cost_rmb"], 4),
            "ev_ratio": round(res["ev_ratio"], 4),
            "tier": tier, "advice": advice, "free_draws_note": free_note,
        }, ensure_ascii=False, indent=2))
        return
    print("=" * 54)
    print("  🎰 麦麦抽奖精算 · EV 报告")
    print("=" * 54)
    print(f"  {'奖品':<12}{'概率':>8}{'估算价值(元)':>14}{'期望贡献':>12}")
    print("  " + "-" * 50)
    for r in res["rows"]:
        print(f"  {r['name']:<12}{r['probability']:>7.1%}{r['value']:>14.2f}{r['contribution']:>12.4f}")
    print("  " + "-" * 50)
    print(f"  单抽期望回报: {res['expected_value']:.4f} 元")
    print(f"  单抽成本:     {res['cost_points']} 积分 ≈ {res['cost_rmb']:.2f} 元"
          f"(积分单价 {res['point_value']} 元/分)")
    print(f"  EV 比率:      {res['ev_ratio']:.3f}")
    print()
    tier, advice, free_note = recommend(res["ev_ratio"], free_draws)
    print(f"  [{tier}] {advice}")
    print(f"  {free_note}")
    print("=" * 54)


def print_history_report(res, as_json=False):
    if as_json:
        print(json.dumps({
            "draws": len(res["records"]),
            "total_value_rmb": round(res["total_value"], 2),
            "total_cost_points": res["total_cost_points"],
            "cost_rmb": round(res["cost_rmb"], 2),
            "payback_rate": round(res["payback_rate"], 4),
        }, ensure_ascii=False, indent=2))
        return
    print("=" * 54)
    print("  📉 麦麦抽奖精算 · 战绩复盘")
    print("=" * 54)
    print(f"  中奖记录: {len(res['records'])} 条")
    for r in res["records"]:
        won_at = r.get("won_at", "-")
        print(f"    - {r['name']:<12} 估算价值 {r['value']:.2f} 元  ({won_at})")
    print("  " + "-" * 50)
    print(f"  累计获得价值: {res['total_value']:.2f} 元")
    print(f"  累计消耗:     {res['total_cost_points']} 积分 ≈ {res['cost_rmb']:.2f} 元")
    print(f"  真实回本率:   {res['payback_rate']:.1%}", end="")
    if res["payback_rate"] >= 1.0:
        print("  —— 欧皇,失敬失敬 🙇")
    elif res["payback_rate"] >= 0.7:
        print("  —— 小亏,就当娱乐消费了 🙂")
    else:
        print("  —— 血亏,下次先问精算师再抽 🩸")
    print("=" * 54)


DEMO_PRIZES = [
    {"name": "巨无霸兑换券", "probability": 0.01, "value": 25.0},
    {"name": "中薯兑换券",   "probability": 0.04, "value": 12.0},
    {"name": "50 积分",      "probability": 0.10, "value": 0.50},
    {"name": "谢谢参与",     "probability": 0.85, "value": 0.0},
]

DEMO_HISTORY = [
    {"name": "中薯兑换券", "value": 12.0, "won_at": "2026-09-12"},
    {"name": "50 积分",    "value": 0.5,  "won_at": "2026-09-15"},
    {"name": "50 积分",    "value": 0.5,  "won_at": "2026-09-21"},
    {"name": "50 积分",    "value": 0.5,  "won_at": "2026-09-28"},
]


def run_demo(as_json=False):
    print(">>> 演示:本期「金秋抽奖」EV 计算(单抽 100 积分,剩余免费次数 2)\n")
    res = calc_ev(DEMO_PRIZES, cost_points=100)
    print_ev_report(res, free_draws=2, as_json=as_json)
    print("\n>>> 演示:历史战绩复盘(20 次抽奖,累计消耗 2000 积分)\n")
    hist = calc_history(DEMO_HISTORY, total_cost_points=2000)
    print_history_report(hist, as_json=as_json)


def build_parser():
    ap = argparse.ArgumentParser(
        description="麦麦抽奖精算:麦当劳积分抽奖 EV 计算器(仅 Python 标准库)。")
    ap.add_argument("--prizes", help="奖品列表 JSON 文件路径")
    ap.add_argument("--cost", type=int, default=0, help="单抽消耗积分")
    ap.add_argument("--point-value", type=float, default=DEFAULT_POINT_VALUE,
                    help=f"积分单价(元/分),默认 {DEFAULT_POINT_VALUE}")
    ap.add_argument("--free-draws", type=int, default=0, help="剩余免费抽奖次数")
    ap.add_argument("--history", help="历史中奖记录 JSON 文件路径")
    ap.add_argument("--total-cost", type=int, default=0, help="历史累计消耗积分")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果(便于 Agent 解析)")
    ap.add_argument("--demo", action="store_true", help="运行内置演示数据")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.demo:
        run_demo(as_json=args.json)
    elif args.history:
        records = load_json(args.history)
        res = calc_history(records, args.total_cost, args.point_value)
        print_history_report(res, as_json=args.json)
    elif args.prizes:
        prizes = load_json(args.prizes)
        res = calc_ev(prizes, args.cost, args.point_value)
        print_ev_report(res, free_draws=args.free_draws, as_json=args.json)
    else:
        build_parser().print_help()
        print("\n示例: python3 ev.py --demo")


if __name__ == "__main__":
    main()
