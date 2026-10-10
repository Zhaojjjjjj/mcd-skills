#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
party_checklist.py — 麦麦派对通 · 派对筹备 checklist 生成器

根据派对信息（类型 / 人数 / 日期 / 城市），输出一份可执行的筹备清单：
  - 预约提前量提醒（距离今天还有多少天，是否来得及）
  - 餐品数量估算（主餐 / 饮品 / 儿童餐）
  - 派对当天待办事项

仅使用 Python 标准库，无第三方依赖。

示例：
    python party_checklist.py --type birthday --guests 10 --kids 8 \\
        --date 2026-10-17 --city 上海 --store "麦当劳南京东路餐厅"

    python party_checklist.py --type team --guests 20 \\
        --date 2026-10-23 --city 上海 --budget-per-person 50
"""

import argparse
import datetime
import sys

# 提前量建议（天）
LEAD_DAYS = {
    "birthday": 7,   # 主题派对建议至少提前 7 天
    "team": 3,       # 企业团餐建议至少提前 3 天
}

TYPE_NAMES = {
    "birthday": "儿童生日派对",
    "team": "企业团建聚餐",
}


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="麦麦派对通 · 派对筹备 checklist 生成器",
        epilog="示例: python party_checklist.py --type birthday --guests 10 "
               "--kids 8 --date 2026-10-17 --city 上海",
    )
    p.add_argument("--type", dest="party_type", required=True,
                   choices=["birthday", "team"],
                   help="派对类型：birthday=儿童生日派对，team=企业团建聚餐")
    p.add_argument("--guests", type=int, required=True,
                   help="总人数（含小朋友）")
    p.add_argument("--kids", type=int, default=0,
                   help="其中小朋友人数（仅 birthday 类型，默认 0）")
    p.add_argument("--date", required=True,
                   help="派对日期，格式 YYYY-MM-DD")
    p.add_argument("--city", required=True, help="举办城市")
    p.add_argument("--store", default="", help="目标门店（可选）")
    p.add_argument("--budget-per-person", type=float, default=0,
                   help="人均预算（元，可选，用于 team 类型估算）")
    return p.parse_args(argv)


def days_until(date_str, today):
    target = datetime.date.fromisoformat(date_str)
    return (target - today).days


def lead_time_section(party_type, delta_days):
    """预约提前量提醒"""
    lines = ["## ⏰ 预约提前量提醒", ""]
    need = LEAD_DAYS[party_type]
    if delta_days < 0:
        lines.append(f"- ⚠️ 日期已过去（{delta_days} 天），请重新选择日期。")
    elif delta_days == 0:
        lines.append("- ⚠️ 就是今天！热门场次大概率已约满，建议立刻查场次，"
                     "同时准备 Plan B（换门店 / 改期）。")
    elif delta_days < need:
        lines.append(f"- ⚠️ 距离派对只有 **{delta_days} 天**，少于建议提前量 "
                     f"**{need} 天**。")
        lines.append("- 👉 行动：今天就用 mcd-party-buddy 查场次并锁单，"
                     "不要再拖。")
    else:
        lines.append(f"- ✅ 距离派对还有 **{delta_days} 天**，"
                     f"满足建议提前量（{need} 天），时间充裕。")
        lines.append("- 👉 行动：本周内完成「城市→门店→日期→场次」四级确认并下单。")
    lines.append("")
    return lines


def food_estimate_section(args):
    """餐品数量估算"""
    lines = ["## 🍔 餐品数量估算", ""]
    lines.append("> 以下为经验估算，最终以麦当劳 MCP `query-meals` 返回的"
                "实时菜单和 `calculate-price` 算价为准。")
    lines.append("")
    if args.party_type == "birthday":
        kids = min(args.kids, args.guests)
        adults = args.guests - kids
        lines.append(f"- 小朋友 {kids} 位 → 开心乐园餐 × {kids} 份")
        if adults:
            # 成人按 1 份主餐 + 饮品，备 10% 余量
            main = adults + (1 if adults % 10 else 0)
            lines.append(f"- 大人 {adults} 位 → 主餐 × {main} 份（含 10% 余量）"
                         f"＋ 饮品 × {adults} 杯")
        lines.append("- 生日蛋糕：如需自带，提前与门店确认是否允许带入")
        lines.append("- 备选：多备 2 份儿童餐，应对临时加人的小朋友")
    else:
        guests = args.guests
        # 团餐按人均 1 份主餐 + 1 杯饮品，主餐备 110%
        main = int(guests * 1.1) + (1 if guests * 1.1 % 1 else 0)
        lines.append(f"- {guests} 人 → 主餐 × {main} 份（110% 备量）"
                     f"＋ 饮品 × {guests} 杯")
        if args.budget_per_person:
            total = guests * args.budget_per_person
            lines.append(f"- 人均预算 {args.budget_per_person:.0f} 元 → "
                         f"总预算约 {total:.0f} 元（报销记得开发票）")
        lines.append("- 忌口统计：提前在群里接龙（过敏 / 清真 / 素食），"
                     "下单前逐一核对")
    lines.append("")
    return lines


def todo_section(args):
    """派对当天待办"""
    lines = ["## ✅ 派对当天待办", ""]
    todos = [
        "提前 30 分钟到店，和店员确认派对区布置",
        "清点人数，实际到场人数与下单份数核对",
        "拍照留念（全家福 / 合影别忘了拍）",
    ]
    if args.party_type == "birthday":
        todos += [
            "准备生日帽 / 小礼物（如有），提前分装好",
            "切蛋糕环节预留 15 分钟，注意小朋友安全",
        ]
    else:
        todos += [
            "保留支付凭证 / 发票，团建报销用",
            "结束后在群里发合影，@ 负责订餐的同学致谢",
        ]
    for i, t in enumerate(todos, 1):
        lines.append(f"- [ ] {i}. {t}")
    lines.append("")
    return lines


def build_checklist(args, today):
    delta = days_until(args.date, today)
    weekday = datetime.date.fromisoformat(args.date).strftime("%A")
    weekday_cn = {"Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
                  "Thursday": "周四", "Friday": "周五",
                  "Saturday": "周六", "Sunday": "周日"}[weekday]

    lines = [f"# 🎉 {TYPE_NAMES[args.party_type]}筹备清单", ""]
    lines.append(f"- 城市：{args.city}")
    if args.store:
        lines.append(f"- 门店：{args.store}")
    lines.append(f"- 日期：{args.date}（{weekday_cn}）")
    lines.append(f"- 人数：{args.guests} 人"
                 + (f"（小朋友 {args.kids} 位）"
                    if args.party_type == "birthday" else ""))
    lines.append("")
    lines += lead_time_section(args.party_type, delta)
    lines += food_estimate_section(args)
    lines += todo_section(args)
    lines.append("---")
    lines.append("由 mcd-party-buddy（麦麦派对通）生成 · "
                 "M-CODE 麦当劳程序员创意开发大赛参赛作品")
    return "\n".join(lines)


def main(argv=None):
    args = parse_args(argv)
    if args.guests <= 0:
        print("错误：--guests 必须大于 0", file=sys.stderr)
        return 2
    try:
        datetime.date.fromisoformat(args.date)
    except ValueError:
        print("错误：--date 格式应为 YYYY-MM-DD", file=sys.stderr)
        return 2
    print(build_checklist(args, datetime.date.today()))
    return 0


if __name__ == "__main__":
    # 无参数运行时跑一段演示，方便快速预览输出效果
    if len(sys.argv) == 1:
        demo_today = datetime.date(2026, 10, 10)
        demo_args = parse_args([
            "--type", "birthday",
            "--guests", "10",
            "--kids", "8",
            "--date", "2026-10-17",
            "--city", "上海",
            "--store", "麦当劳南京东路餐厅",
        ])
        print(build_checklist(demo_args, demo_today))
    else:
        sys.exit(main())
