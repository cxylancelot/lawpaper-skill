#!/usr/bin/env python3
"""
关卡检查脚本 (check_stage.py)

读取 references/stage-checklists.md 中的检查清单，
对用户提交的文本进行当前阶段的关卡验证。

用法:
    python check_stage.py <stage_number>                        # 交互式
    python check_stage.py <stage_number> --file paper.md        # 检查文件
    python check_stage.py <stage_number> --file paper.md --json # JSON 输出
    python check_stage.py list                                  # 列出所有阶段

stage_number: 0-7（对应 Step 0 到 Step 7）
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional

# 技能目录
SKILL_DIR = Path(os.environ.get("HERMES_SKILL_DIR", Path(__file__).resolve().parent.parent))

# ============================================================
# 关卡定义（与 stage-checklists.md 保持同步）
# ============================================================

# 每阶段的检查项：(编号, 检查项描述, 处方引用, 自动检查函数名)
# 自动检查函数返回 (通过: bool, 备注: str)

STAGES = {
    0: {
        "name": "Step 0: 论文类型与方向",
        "checks": [
            ("0.1", "已确定论文类型", "SKILL.md Step 0 或 references/decision-tree.md"),
            ("0.2", "核心问题可以用一句话说清", "回到'你现在最困惑的一件事是什么？'"),
            ("0.3", "研究起点明确", "references/decision-tree.md"),
            ("0.4", "已确认目标篇幅", "不同篇幅选择不同深度的选题"),
        ]
    },
    1: {
        "name": "Step 1: 选题篇",
        "checks": [
            ("1.1", "核心问题是可争辩的", "references/topic-selection.md 第一章"),
            ("1.2", "选题通过三维创新判断", "references/topic-selection.md 第二章"),
            ("1.3", "选题通过可行性评估", "references/topic-selection.md 第三章"),
            ("1.4", "核心概念有操作性定义", "references/topic-selection.md 第五章"),
            ("1.5", "选题与目标期刊方向一致", "references/topic-selection.md 第四章"),
            ("1.6", "理论框架已知适用场景和边界", "references/theory-frameworks.md"),
        ]
    },
    2: {
        "name": "Step 2: 文献篇",
        "checks": [
            ("2.1", "已检索法学核心数据库", "references/literature-search.md 第一章"),
            ("2.2", "已检索立法材料或外文数据库", "references/literature-search.md 各数据库部分"),
            ("2.3", "所有文献通过Tier 1存在性验证", "references/literature-search.md 第二章"),
            ("2.4", "核心论据文献通过Tier 2验证", "references/literature-search.md 第二章"),
            ("2.5", "未读原文者未描述其论证过程", "SKILL.md R3"),
            ("2.6", "文献综述有评述而非只罗列", "references/legal-writing.md 第三章"),
            ("2.7", "论文在已有研究中的位置清晰", "references/legal-writing.md 第三章"),
        ]
    },
    3: {
        "name": "Step 3: 调查篇",
        "checks": [
            ("3.1", "研究方法与问题性质匹配", "references/investigation-methods.md"),
            ("3.2", "经验方法已说明数据来源和筛选", "references/investigation-methods.md"),
            ("3.3", "通过四层一致性检查", "references/investigation-methods.md 第二章"),
            ("3.4", "清楚方法的边界和局限", "references/investigation-methods.md 第二章"),
        ]
    },
    4: {
        "name": "Step 4: 论证篇",
        "checks": [
            ("4.1", "核心论点一句话可说明且可争辩", "references/legal-argumentation.md"),
            ("4.2", "论证方法选择恰当", "references/legal-argumentation.md 第一章"),
            ("4.3", "Toulmin六元素齐全", "references/legal-argumentation.md 第二章"),
            ("4.4", "无7类逻辑问题", "references/legal-argumentation.md 第二章"),
            ("4.5", "已完成反例压力测试", "references/legal-argumentation.md 第三章"),
            ("4.6", "已检查法条但书条款", "references/legal-argumentation.md + common-mistakes.md"),
        ]
    },
    5: {
        "name": "Step 5: 行文篇",
        "checks": [
            ("5.1", "结构遵循标准模式且章节递进", "references/legal-writing.md 第一章"),
            ("5.2", "引言第一段具体", "references/legal-writing.md 第二章"),
            ("5.3", "引言含核心问题+论点方向+结构", "references/legal-writing.md 第二章"),
            ("5.4", "摘要包含问题/方法/发现/意义", "references/legal-writing.md 第四章"),
            ("5.5", "标题用'对象：论证方向'格式", "references/legal-writing.md 第五章"),
            ("5.6", "无口语化表达，自称统一", "references/academic-expressions.md"),
            ("5.7", "结论不重复前言", "references/legal-writing.md 第四章"),
        ]
    },
    6: {
        "name": "Step 6: 格式篇",
        "checks": [
            ("6.1", "法条引注含版本/时效", "references/legal-citation.md + R5"),
            ("6.2", "判例引注含案号+法院+日期", "references/legal-citation.md + R6"),
            ("6.3", "各类法律文件引注格式正确", "references/legal-citation.md 第二章"),
            ("6.4", "各类文献引注格式正确", "references/legal-citation.md 第四章"),
            ("6.5", "全篇引注风格一致", "references/legal-citation.md 第五、七章"),
            ("6.6", "脚注编号连续", "references/legal-citation.md 第六章"),
        ]
    },
    7: {
        "name": "Step 7: 伦理篇",
        "checks": [
            ("7.1", "经验性主张有类案检索支撑", "references/legal-ethics.md 第一章"),
            ("7.2", "法条均核实为有效版本", "references/legal-ethics.md 第二章"),
            ("7.3", "裁判文书引用已脱敏", "references/legal-ethics.md 第三章"),
            ("7.4", "利益冲突已声明", "references/legal-ethics.md 第四章"),
            ("7.5", "AI辅助已适当披露", "references/legal-ethics.md 第五章"),
            ("7.6", "一稿多投等伦理问题已检查", "references/legal-ethics.md 第六章"),
        ]
    },
}


# ============================================================
# 自动检查函数
# ============================================================

def auto_check_0_2(text: str) -> (bool, str):
    """检查是否有清晰的问题句（Step 0.2）"""
    # 查找常见的问题表述模式
    patterns = [
        r'本文[试尝][图试][论证回答探讨](?:的是)?[，：:\s]*(.{10,100})',
        r'核心问题[是在于][：:\s]*(.{10,100})',
        r'本文[的]?[主要核心]?问题[是在于][：:\s]*(.{10,100})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:3000])
        if match:
            question = match.group(1) if match.lastindex else match.group(0)
            if len(question) >= 10:
                return True, f"检测到问题句: {question[:80]}..."
    return False, "未在引言部分检测到明确的问题句"

def auto_check_1_4(text: str) -> (bool, str):
    """检查是否有概念的操作性定义（Step 1.4）"""
    patterns = [
        r'本文所称[的]?[「「""]?([^」」""]{2,20})[」」""]?[，,]*(?:是指|指的是|界定为|定义为)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:5000])
        if match:
            return True, f"检测到概念定义: {match.group(0)[:60]}..."
    return False, "未检测到核心概念的操作性定义"

def auto_check_5_1(text: str) -> (bool, str):
    """检查引言第一段是否具体（Step 5.2）"""
    intro_start = text[:500]
    banned_openings = [
        r'随着.{0,30}(?:社会|经济|科技|互联网|大数据|人工智能)',
        r'在.{0,20}(?:背景|形势|语境|时代)下',
    ]
    for pattern in banned_openings:
        if re.search(pattern, intro_start):
            return False, f"引言开头过于泛化（匹配模式: {pattern}）"
    return True, "引言开头未使用常见泛化模式"

def auto_check_5_6(text: str) -> (bool, str):
    """检查口语化和自称统一（Step 5.6）"""
    colloquial = re.findall(r'说白了|大家[都就]知道|笔者觉得|这就意味着我们要|有意思的是', text[:5000])
    if colloquial:
        return False, f"检测到口语化表达: {', '.join(colloquial[:3])}"
    # 检查自称统一
    benwen = len(re.findall(r'本文', text[:5000]))
    bizhe = len(re.findall(r'笔者', text[:5000]))
    women = len(re.findall(r'(?<![本笔])我们', text[:5000]))
    styles = []
    if benwen > 0: styles.append('本文')
    if bizhe > 0: styles.append('笔者')
    if women > 2: styles.append('我们')
    if len(styles) > 1:
        return False, f"自称方式不统一（检测到: {', '.join(styles)}），建议统一使用'本文'"
    return True, f"自称统一使用: {styles[0] if styles else '未检测到自称'}"


# 自动检查函数映射
AUTO_CHECKS = {
    "0.2": auto_check_0_2,
    "1.4": auto_check_1_4,
    "5.2": auto_check_5_1,
    "5.6": auto_check_5_6,
}


# ============================================================
# 交互模式
# ============================================================

def run_interactive(stage_num: int) -> dict:
    """交互式关卡检查"""
    stage = STAGES[stage_num]
    print(f"\n{'='*50}")
    print(f"  {stage['name']} - 关卡检查")
    print(f"{'='*50}\n")
    print("请逐项回答（y=通过 / n=未通过 / s=跳过）\n")

    results = []
    for check_id, check_desc, prescription in stage["checks"]:
        answer = input(f"[{check_id}] {check_desc}  [y/n/s]: ").strip().lower()
        status = "通过" if answer == "y" else ("未通过" if answer == "n" else "跳过")
        results.append({
            "id": check_id,
            "description": check_desc,
            "status": status,
            "prescription": prescription if answer == "n" else "",
        })

    passed = sum(1 for r in results if r["status"] == "通过")
    failed = sum(1 for r in results if r["status"] == "未通过")
    total = len(results)

    print(f"\n{'='*50}")
    print(f"  结果: {passed}/{total} 通过")
    if failed > 0:
        print(f"\n  ⚠️  以下项目未通过，建议修复后再进入下一阶段：")
        for r in results:
            if r["status"] == "未通过":
                print(f"  [{r['id']}] {r['description']}")
                print(f"      → {r['prescription']}")
        print(f"\n  🚫 建议暂停，修复未通过项后重新检查。")
    else:
        print(f"\n  ✅ 所有检查通过（含跳过项），可以进入下一阶段。")
    print(f"{'='*50}\n")

    return {
        "stage": stage_num,
        "stage_name": stage["name"],
        "passed": passed,
        "failed": failed,
        "skipped": total - passed - failed,
        "total": total,
        "results": results,
        "can_proceed": failed == 0,
    }


def run_auto(text: str, stage_num: int) -> dict:
    """自动检查（能自动化的项目）"""
    stage = STAGES[stage_num]
    results = []

    for check_id, check_desc, prescription in stage["checks"]:
        if check_id in AUTO_CHECKS:
            passed, note = AUTO_CHECKS[check_id](text)
            results.append({
                "id": check_id,
                "description": check_desc,
                "status": "通过" if passed else "未通过",
                "auto": True,
                "note": note,
                "prescription": prescription if not passed else "",
            })
        else:
            results.append({
                "id": check_id,
                "description": check_desc,
                "status": "需人工判断",
                "auto": False,
                "note": "此项需要人工判断",
                "prescription": prescription,
            })

    auto_passed = sum(1 for r in results if r["status"] == "通过")
    auto_failed = sum(1 for r in results if r["status"] == "未通过")
    manual = sum(1 for r in results if r["status"] == "需人工判断")

    return {
        "stage": stage_num,
        "stage_name": stage["name"],
        "auto_passed": auto_passed,
        "auto_failed": auto_failed,
        "manual": manual,
        "results": results,
    }


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="关卡检查 (check_stage.py)")
    parser.add_argument("stage", help="阶段编号 (0-7) 或 'list' 列出所有阶段")
    parser.add_argument("--file", "-f", help="待检查的论文文件（可选，用于自动检查）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.stage == "list":
        for num, stage in STAGES.items():
            print(f"Step {num}: {stage['name']} ({len(stage['checks'])} 项检查)")
        return

    try:
        stage_num = int(args.stage)
        if stage_num not in STAGES:
            print(f"错误: 阶段编号必须在 0-7 之间，收到: {stage_num}", file=sys.stderr)
            sys.exit(1)
    except ValueError:
        print(f"错误: 无效的阶段编号: {args.stage}", file=sys.stderr)
        sys.exit(1)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"错误: 文件不存在 - {args.file}", file=sys.stderr)
            sys.exit(1)

        result = run_auto(text, stage_num)
    else:
        result = run_interactive(stage_num)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
