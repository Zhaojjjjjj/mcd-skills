#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦积分守卫 · 确定性兑换顾问 (expiry_advisor)

输入：麦当劳积分账户快照（可用积分、即将过期积分及过期时间）
      + 积分商城商品列表（含积分成本与预估价值）
输出：按"过期优先、单位积分价值最大"排序的兑换方案，
      每个方案含积分成本、价值估算与过期风险提示。

仅使用 Python 标准库。排序逻辑是确定性的——同样的输入
永远得到同样的输出，Agent 不许"心算"替代它。

用法：
    python3 expiry_advisor.py                                  # 内置演示数据
    python3 expiry_advisor.py --account account.json --products products.json
    python3 expiry_advisor.py --account account.json --products products.json --format json
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class ExpiringBucket:
    """一批即将过期的积分。"""
    points: int
    expire_date: str        # YYYY-MM-DD
    days_left: int = 0      # 相对"今天"的剩余天数（可为负 = 已过期）

    def risk(self) -> str:
        if self.days_left < 0:
            return "⚫已过期"
        if self.days_left <= 3:
            return "🔴紧急"
        if self.days_left <= 7:
            return "🟠偏高"
        if self.days_left <= 14:
            return "🟡注意"
        return "🟢健康"


@dataclass
class Product:
    """商城可兑换商品。"""
    id: str
    name: str
    points_cost: int
    value_cny: float        # 预估人民币价值（来自商品详情或官方定价）
    category: str = ""
    valid_days: int = 0

    @property
    def value_per_1k(self) -> float:
        """每千积分价值：排序的核心键。"""
        if self.points_cost <= 0:
            return 0.0
        return self.value_cny / self.points_cost * 1000


@dataclass
class PlanItem:
    product: Product
    qty: int
    expiring_used: int      # 本项消耗的"即将过期"积分
    note: str = ""

    @property
    def points_cost(self) -> int:
        return self.product.points_cost * self.qty

    @property
    def est_value(self) -> float:
        return round(self.product.value_cny * self.qty, 2)


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_json_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_account(data: dict, today: date):
    available = int(data.get("available_points", 0))
    frozen = int(data.get("frozen_points", 0))
    buckets = []
    for b in data.get("expiring") or []:
        d = parse_date(b["expire_date"])
        buckets.append(ExpiringBucket(
            points=int(b["points"]),
            expire_date=b["expire_date"],
            days_left=(d - today).days,
        ))
    buckets.sort(key=lambda x: x.days_left)
    return available, frozen, buckets


def parse_products(data: list) -> list:
    products = []
    for p in data or []:
        try:
            prod = Product(
                id=str(p.get("id", "")),
                name=str(p.get("name", "")),
                points_cost=int(p.get("points_cost", 0)),
                value_cny=float(p.get("value_cny", 0) or 0),
                category=str(p.get("category", "") or ""),
                valid_days=int(p.get("valid_days", 0) or 0),
            )
        except (TypeError, ValueError):
            continue
        if prod.points_cost > 0 and prod.value_cny > 0:
            products.append(prod)
    return products


# ---------------------------------------------------------------------------
# 核心算法：过期优先 + 单位价值最大
# ---------------------------------------------------------------------------

def build_plan(available: int, buckets: list, products: list,
               max_per_product: int = 3) -> dict:
    live = [b for b in buckets if b.days_left >= 0]
    expired = [b for b in buckets if b.days_left < 0]
    expiring_total = sum(b.points for b in live)
    expired_lost = sum(b.points for b in expired)
    ranked = sorted(products, key=lambda p: p.value_per_1k, reverse=True)

    plan: list = []
    remaining_total = available
    remaining_expiring = expiring_total

    if expiring_total == 0:
        # 无过期压力：给 2 个"可选兑换"（纯按单位价值排序）
        for prod in ranked[:2]:
            if remaining_total >= prod.points_cost:
                plan.append(PlanItem(prod, 1, 0, "无过期压力，可选兑换"))
                remaining_total -= prod.points_cost
    else:
        for prod in ranked:
            if remaining_expiring <= 0:
                break
            if remaining_total < prod.points_cost:
                continue
            affordable = remaining_total // prod.points_cost
            # 需要多少件才能把剩余"即将过期"积分花光（向上取整）
            need = (remaining_expiring + prod.points_cost - 1) // prod.points_cost
            qty = max(1, min(affordable, need, max_per_product))
            cost = qty * prod.points_cost
            used = min(cost, remaining_expiring)
            note = ("一次性覆盖全部即将过期积分"
                    if used >= remaining_expiring
                    else f"覆盖 {used} 即将过期积分")
            plan.append(PlanItem(prod, qty, used, note))
            remaining_total -= cost
            remaining_expiring -= used

    return {
        "available": available,
        "expiring_total": expiring_total,
        "expired_lost": expired_lost,
        "buckets": buckets,
        "plan": plan,
        "total_cost": sum(i.points_cost for i in plan),
        "total_value": round(sum(i.est_value for i in plan), 2),
        "rescued": expiring_total - remaining_expiring,
        "leftover": remaining_expiring,
    }


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def report_text(res: dict, today: date) -> str:
    L = []
    L.append(f"🍔 麦麦积分守卫 · 兑换方案报告（基准日期 {today}）")
    L.append("━" * 34)
    L.append("【账户快照】")
    L.append(f"  可用积分：{res['available']}")
    live = [b for b in res["buckets"] if b.days_left >= 0]
    if live:
        L.append(f"  即将过期：{res['expiring_total']}（{len(live)} 批）")
        for b in live:
            when = "今天" if b.days_left == 0 else f"{b.days_left} 天后"
            L.append(f"    {b.risk()} {b.points} 积分，{when}过期（{b.expire_date}）")
    else:
        L.append("  即将过期：无 🎉")
    if res["expired_lost"]:
        L.append(f"  ⚫ 已过期损失：{res['expired_lost']} 积分（已无法挽回）")
    L.append("")
    L.append("【推荐兑换方案】（过期优先 · 单位价值最大）")
    if not res["plan"]:
        L.append("  暂无可推荐方案：积分不足以兑换任何商品，或商城暂无可兑商品。")
    for i, it in enumerate(res["plan"], 1):
        p = it.product
        L.append(f"  方案 {i}：{p.name} ×{it.qty}")
        L.append(f"    积分成本：{it.points_cost} ｜ 预估价值：¥{it.est_value} ｜ "
                 f"每千积分价值：¥{p.value_per_1k:.1f}")
        L.append(f"    消耗过期积分：{it.expiring_used} ｜ {it.note}")
    L.append("")
    L.append("【风险提示】")
    if res["leftover"] > 0:
        L.append(f"  ⚠️ 仍有 {res['leftover']} 积分即将过期未被方案覆盖，"
                 "建议追加兑换或到店消费。")
    elif res["expiring_total"] > 0:
        L.append(f"  ✅ 全部 {res['rescued']} 即将过期积分均已覆盖。")
    else:
        L.append("  ✅ 暂无过期风险。")
    if res["total_cost"] >= 5000:
        L.append("  🔔 本次方案积分成本 ≥5000，执行前请二次确认。")
    L.append("")
    L.append("注：价值为预估（按商城/官方定价折算），兑换前请以 mall-product-detail 返回为准；")
    L.append("    任何兑换都必须经用户确认后执行。")
    return "\n".join(L)


def report_json(res: dict, today: date) -> str:
    return json.dumps({
        "as_of": str(today),
        "available_points": res["available"],
        "expiring_total": res["expiring_total"],
        "expired_lost": res["expired_lost"],
        "buckets": [
            {"points": b.points, "expire_date": b.expire_date,
             "days_left": b.days_left, "risk": b.risk()}
            for b in res["buckets"]
        ],
        "plan": [
            {"rank": i + 1,
             "product_id": it.product.id,
             "product": it.product.name,
             "qty": it.qty,
             "points_cost": it.points_cost,
             "est_value_cny": it.est_value,
             "value_per_1k_cny": round(it.product.value_per_1k, 2),
             "expiring_points_used": it.expiring_used,
             "note": it.note}
            for i, it in enumerate(res["plan"])
        ],
        "total_cost": res["total_cost"],
        "total_value_cny": res["total_value"],
        "rescued_expiring": res["rescued"],
        "leftover_expiring": res["leftover"],
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 演示数据
# ---------------------------------------------------------------------------

def demo_data(today: date):
    d = lambda n: str(today + timedelta(days=n))
    account = {
        "available_points": 8000,
        "frozen_points": 0,
        "expiring": [
            {"points": 3000, "expire_date": d(7)},
            {"points": 1500, "expire_date": d(30)},
        ],
    }
    products = [
        {"id": "p001", "name": "麦辣鸡腿堡单人餐券", "points_cost": 2500,
         "value_cny": 25.0, "category": "餐券", "valid_days": 30},
        {"id": "p002", "name": "巨无霸单人餐券", "points_cost": 2800,
         "value_cny": 27.0, "category": "餐券", "valid_days": 30},
        {"id": "p003", "name": "10 块麦乐鸡券", "points_cost": 1800,
         "value_cny": 16.0, "category": "小食券", "valid_days": 30},
        {"id": "p004", "name": "中薯免费券", "points_cost": 1200,
         "value_cny": 9.0, "category": "小食券", "valid_days": 30},
        {"id": "p005", "name": "圆筒冰淇淋券", "points_cost": 800,
         "value_cny": 5.0, "category": "甜品券", "valid_days": 30},
        {"id": "p006", "name": "麦麦帆布包", "points_cost": 5000,
         "value_cny": 35.0, "category": "周边", "valid_days": 90},
    ]
    return account, products


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="麦麦积分守卫 · 确定性兑换顾问："
                    "按“过期优先、单位积分价值最大”输出兑换方案。",
        epilog="示例：python3 expiry_advisor.py "
               "--account account.json --products products.json")
    ap.add_argument("--account",
                    help="积分账户 JSON 文件（含 available_points / expiring[]；"
                         "不传则使用内置演示数据）")
    ap.add_argument("--products",
                    help="商城商品 JSON 文件（数组，每项含 id/name/points_cost/value_cny；"
                         "不传则使用内置演示数据）")
    ap.add_argument("--format", choices=["text", "json"], default="text",
                    help="输出格式（默认 text）")
    ap.add_argument("--today",
                    help="基准日期 YYYY-MM-DD（默认今天；用于复现/测试）")
    ap.add_argument("--max-per-product", type=int, default=3,
                    help="单个商品单次推荐上限（默认 3）")
    args = ap.parse_args(argv)

    today = parse_date(args.today) if args.today else date.today()

    if args.account or args.products:
        if not (args.account and args.products):
            ap.error("--account 与 --products 需同时提供（或都不提供以使用演示数据）。")
        account_data = load_json_file(args.account)
        products_data = load_json_file(args.products)
        demo = False
    else:
        account_data, products_data = demo_data(today)
        demo = True

    available, _frozen, buckets = parse_account(account_data, today)
    products = parse_products(products_data)
    if not products:
        print("商城商品列表为空或无有效数据，无法计算方案。", file=sys.stderr)
        return 2
    res = build_plan(available, buckets, products, args.max_per_product)

    if demo and args.format == "text":
        print(">>> 使用内置演示数据（上班族：8000 积分，其中 3000 在 7 天后过期）\n")
    print(report_json(res, today) if args.format == "json"
          else report_text(res, today))
    return 0


if __name__ == "__main__":
    sys.exit(main())
