#!/usr/bin/env python3
"""
法学论文质量检查脚本 (review_legal.py)

继承 humanities-thesis review.py 的规则引擎架构（regex + 术语表 + 格式模板，
不依赖 LLM 自评）并增加法学特有检查维度。

用法:
    python review_legal.py paper.md                    # 默认输出
    python review_legal.py paper.md --format json      # JSON 输出
    python review_legal.py paper.md --severity error   # 只输出 Error 级别
    python review_legal.py paper.md --output report.md # 输出到文件

程序化使用:
    from review_legal import review
    issues = review(text)
"""

import re
import sys
import json
import argparse
import os
from pathlib import Path
from collections import Counter
from typing import List, Dict, Optional, Tuple

# ============================================================
# 配置
# ============================================================

# 技能目录（可被 HERMES_SKILL_DIR 覆盖）
SKILL_DIR = Path(os.environ.get("HERMES_SKILL_DIR", Path(__file__).resolve().parent.parent))

# 严重级别
class Severity:
    ERROR = "error"       # 必须修复
    WARNING = "warning"   # 强烈建议修复
    INFO = "info"         # 参考信息

# ============================================================
# 规则引擎
# ============================================================

class Rule:
    """单条检查规则"""
    def __init__(self, rule_id: str, dimension: str, severity: str,
                 description: str, check_fn, suggestion: str = ""):
        self.id = rule_id
        self.dimension = dimension
        self.severity = severity
        self.description = description
        self.check_fn = check_fn  # (text: str) -> List[Issue]
        self.suggestion = suggestion

class Issue:
    """检查发现的问题"""
    def __init__(self, rule_id: str, severity: str, dimension: str,
                 description: str, location: str = "", context: str = "",
                 suggestion: str = ""):
        self.rule_id = rule_id
        self.severity = severity
        self.dimension = dimension
        self.description = description
        self.location = location
        self.context = context
        self.suggestion = suggestion

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "dimension": self.dimension,
            "description": self.description,
            "location": self.location,
            "context": self.context[:200],
            "suggestion": self.suggestion,
        }


# ============================================================
# 维度 1: 可信度 (Credibility)
# ============================================================

# R1-01: 模糊引用检测
VAGUE_CITATION_PATTERNS = [
    (r'有学者[认为指出]{1,2}', 'error', '模糊引用：请给出具体学者姓名'),
    (r'有研究[表明显示]{1,2}', 'error', '模糊引用：请给出具体研究文献'),
    (r'有些[学者学人]{1,2}[认为指出]{1,2}', 'error', '模糊引用：请给出具体学者姓名'),
    (r'学界[普遍一般]{1,2}[认为]{0,1}', 'warning', '模糊引用：如确为学界共识请引用代表性文献'),
    (r'司法实践[普遍通常一般]{1,2}[认为采取采用认定]{1,2}', 'error',
     '经验性主张缺乏类案检索支撑：请注明检索条件或标注"据笔者观察"'),
    (r'通说[认为]{0,1}', 'warning', '声称"通说"请引用支持该通说的代表性文献'),
]

# R1-02: 占位符检测
PLACEHOLDER_PATTERNS = [
    (r'\[待补充[^\]]*\]', 'warning', '检测到占位符：请在定稿前补充'),
    (r'\[待查[^\]]*\]', 'warning', '检测到待查标记'),
    (r'\[未[核实获取][^\]]*\]', 'warning', '检测到未核实标记'),
]

# R1-03: 过度断言检测
OVER_ASSERTION_PATTERNS = [
    (r'毫无疑问[,，]{0,1}', 'warning', '过度断言：法学论文中应谨慎使用"毫无疑问"'),
    (r'众所周知[,，]{0,1}', 'warning', '过度断言：如果"众所周知"则不需要论证；如果需要论证则不是"众所周知"'),
    (r'必然[地]{0,1}[导致造成引发]{1}', 'warning', '过度断言：因果关系断言应提供论据支持'),
    (r'显然[,，]{0,1}', 'warning', '过度断言：如果"显然"则不需要写；如果需要写则不是"显然"'),
]

# R1-04: 未来年份检测
def check_future_year(text: str) -> List[Issue]:
    """检测引用年份是否在未来"""
    import datetime
    current_year = datetime.datetime.now().year
    # 查找文献的出版年份（如 "(2028)" "[2028]" "，2028年"）
    year_pattern = re.findall(r'[\(\[（]?((?:19|20)\d{2})[\)\]）]?(?:年|年版|年第|年施行)', text)
    issues = []
    for y_str in year_pattern:
        year = int(y_str)
        if year > current_year + 1:  # 允许+1年（预出版）
            issues.append(Issue(
                rule_id="R1-04",
                severity="error",
                dimension="可信度",
                description=f"引用年份({year})超过当前年份({current_year})，可能为编造文献",
                location=f"年份: {year}",
                suggestion="核实该文献的真实出版年份"
            ))
    return issues


# ============================================================
# 维度 2: 术语一致性 (Terminology)
# ============================================================

# 法学常见术语混用检查（中文同义词在不同上下文中的混用）
LAW_TERM_SYNONYMS = [
    (r'(举证责任|证明责任)', '术语不一致：全文应统一使用"举证责任"或"证明责任"'),
    (r'(诚实信用|诚信)', '术语不一致：建议统一使用"诚实信用"（法条正式用语）'),
    (r'(构成要件|成立要件)', '术语不一致：刑法用"构成要件"，民法多用"成立要件"'),
    (r'(注意义务|谨慎义务)', '术语不一致：侵权法建议统一使用"注意义务"（duty of care标准译法）'),
    (r'(法律行为|法律交易)', '术语不一致：中国大陆法学统一使用"法律行为"（Rechtsgeschäft）'),
    (r'(不当得利|不当获利)', '术语不一致：中国大陆法学统一使用"不当得利"'),
]

def check_terminology_consistency(text: str) -> List[Issue]:
    """检查术语一致性"""
    issues = []
    paragraphs = text.split('\n\n')
    for syn_pair in LAW_TERM_SYNONYMS:
        pattern, msg = syn_pair[0], syn_pair[1]
        terms_found = re.findall(pattern, text)
        unique_terms = set(terms_found)
        if len(unique_terms) > 1:
            # 找到两个术语都在用的段落
            for i, para in enumerate(paragraphs):
                matches_in_para = re.findall(pattern, para)
                if len(set(matches_in_para)) > 1:
                    issues.append(Issue(
                        rule_id="T-01",
                        severity="warning",
                        dimension="术语一致性",
                        description=f'{msg}（当前混用：{", ".join(sorted(unique_terms))}）',
                        location=f"段落 {i+1}",
                        context=para[:100],
                    ))
    return issues


# ============================================================
# 维度 3: 格式规范 (Format)
# ============================================================

# F-01: 脚注占位
def check_footnote_placeholders(text: str) -> List[Issue]:
    """检查空脚注或占位符脚注"""
    issues = []
    # 查找 [待补充] 等占位符
    placeholders = re.finditer(r'\[待补充[^\]]*\]', text)
    for m in placeholders:
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        issues.append(Issue(
            rule_id="F-01",
            severity="error",
            dimension="格式规范",
            description="脚注占位符未补充",
            context=text[start:end],
            suggestion="请在定稿前补充具体出处"
        ))
    return issues

# F-02: 法律文件引注格式检查
LAW_CITATION_RULES = [
    # (模式, 缺失信息, 严重度)
    (r'《中华人民共和国[^》]+》[^第条]', '法律名称后缺少具体条款号', 'warning'),
    (r'《民法典》(?!第\d|（\d{4})', '《民法典》引用建议标注具体条款和施行版本', 'info'),
    (r'法释〔\d{4}〕\d+号(?!.*第\d+条)', '司法解释引用建议标注具体条款', 'info'),
]

def check_legal_citation_format(text: str) -> List[Issue]:
    """检查法律文件引注格式"""
    issues = []
    for pattern, missing, severity in LAW_CITATION_RULES:
        matches = re.finditer(pattern, text)
        for m in matches:
            context = text[max(0, m.start()-20):min(len(text), m.end()+50)]
            issues.append(Issue(
                rule_id="F-LEGAL-01",
                severity=severity,
                dimension="法学引注",
                description=missing,
                context=context.strip(),
            ))
    return issues

# F-03: 判例引注完整性检查
CASE_CITATION_PATTERNS = [
    (r'(?:参见|见|如)(?!.*\d{4}.*法.*\d+号)(?:[^。；]*判决[^。；]*)',
     '判例引用可能缺少案号：请标注"（20XX）X法XX字第XX号"格式', 'warning'),
    (r'指导案例第?\d+号(?!.*\d{4}年\d{1,2}月\d{1,2}日)',
     '指导性案例引用缺少发布日期', 'error'),
]

def check_case_citation(text: str) -> List[Issue]:
    """检查判例引注完整性"""
    issues = []
    for pattern, msg, severity in CASE_CITATION_PATTERNS:
        matches = re.finditer(pattern, text)
        for m in matches:
            context = text[max(0, m.start()-30):min(len(text), m.end()+50)]
            issues.append(Issue(
                rule_id="F-CASE-01",
                severity=severity,
                dimension="法学引注",
                description=msg,
                context=context.strip(),
            ))
    return issues

# F-04: 中文英文标点混用
def check_punctuation_mixing(text: str) -> List[Issue]:
    """检查中英文标点混用"""
    issues = []
    # 在中文字符后面出现英文逗号/句号
    cn_en_mix = re.finditer(r'[一-鿿],[^\n]*?[一-鿿]', text)
    for m in cn_en_mix:
        issues.append(Issue(
            rule_id="F-04",
            severity="warning",
            dimension="格式规范",
            description="中文上下文中使用了英文逗号",
            context=m.group()[:60],
            suggestion="将英文逗号替换为中文逗号（，）"
        ))
    return issues[:5]  # 限制数量避免过多


# ============================================================
# 维度 4: 学术语体 (Style)
# ============================================================

COLLOQUIAL_PATTERNS = [
    (r'说白了', '口语化表达："说白了"→ 学术替代"简言之""质言之"'),
    (r'大家[都就]{0,1}知道', '口语化表达：→ "如所周知""学界已普遍认识到"'),
    (r'笔者[觉感以为]{1,2}得', '口语化表达："笔者觉得"→"本文认为"（法学论文中"本文"比"笔者"更正式）'),
    (r'其实[,，]{0,1}', '口语化表达："其实"→"实则""究其实质"'),
    (r'这样一来', '口语化表达：→"由此""以此观之"'),
    (r'有意思的是', '口语化表达：→"值得关注的是""值得注意的是"'),
]

# 自称不一致检测
SELF_REFERENCE_PATTERNS = [
    (r'本文', '自称方式: 本文'),
    (r'笔者', '自称方式: 笔者'),
    (r'(?<![本笔])我们', '自称方式: 我们'),
]

def check_self_reference_consistency(text: str) -> List[Issue]:
    """检查自称是否一致"""
    issues = []
    found_styles = set()
    for pattern, style in SELF_REFERENCE_PATTERNS:
        if re.search(pattern, text):
            found_styles.add(style)
    if len(found_styles) > 1:
        issues.append(Issue(
            rule_id="S-02",
            severity="warning",
            dimension="学术语体",
            description=f'自称方式不统一（检测到：{", ".join(sorted(found_styles))}），请选择一种并保持一致',
            suggestion="法学论文推荐使用'本文'，全文统一"
        ))
    return issues


# ============================================================
# 维度 5: 论证逻辑 (Logic)
# ============================================================

# L-01: 引文后缺分析（引用法条/观点后直接跳到下一个观点）
def check_citation_without_analysis(text: str) -> List[Issue]:
    """检查引用后缺少分析"""
    issues = []
    # 简单启发式：引用法条后紧接着"因此""所以"但没有中间分析
    # 这里用超短段落检测
    paragraphs = text.split('\n\n')
    for i, para in enumerate(paragraphs):
        # 小于100字的段落如果同时包含引用和结论，可能缺分析
        if 10 < len(para) < 100:
            has_citation = bool(re.search(r'《[^》]+》第|"\s*[^"]{5,}\s*"|参见|见前注', para))
            has_conclusion = bool(re.search(r'因此|所以|故|可见|由此可见|综上', para))
            if has_citation and has_conclusion:
                # 检查引用和结论之间是否有分析文字（至少20字）
                citation_end = 0
                for m in re.finditer(r'(?:(?:《[^》]+》第\d+[条]?)|(?:参见[^；。]*[；。])|(?:见前注\[?\d+\]?))', para):
                    citation_end = m.end()
                conclusion_start = para.find('因此') if '因此' in para else \
                                   para.find('所以') if '所以' in para else \
                                   para.find('故') if '故' in para else 0
                if citation_end and conclusion_start:
                    gap = conclusion_start - citation_end
                    if gap < 20:
                        issues.append(Issue(
                            rule_id="L-03",
                            severity="warning",
                            dimension="论证逻辑",
                            description="引用后直接跳至结论，中间缺少分析环节",
                            context=para[:120],
                            suggestion="在引用和结论之间补充'这意味着'的分析"
                        ))
    return issues[:5]

# L-02: 法学特有逻辑谬误——但书条款检查
def check_but_clause_awareness(text: str) -> List[Issue]:
    """检查是否引用了法条但未考虑但书条款"""
    issues = []
    # 检测"第X条规定"但未提及"但"或"除外"
    article_mentions = re.finditer(r'第[一二三四五六七八九十\d]+条[规定]*[^。；]*(?!.*但书)(?!.*除外)(?!.*例外)', text)
    for m in article_mentions:
        ctx = m.group()
        if len(ctx) < 200:  # 简短引用
            # 检查附近是否有但书相关的讨论
            nearby = text[max(0, m.start()-200):min(len(text), m.end()+500)]
            if '但书' not in nearby and '除外规定' not in nearby and '例外情形' not in nearby:
                # 这不一定是问题——只是提醒
                pass
    return issues


# ============================================================
# 维度 6: 结构完整性 (Structure)
# ============================================================

def check_structure_completeness(text: str) -> List[Issue]:
    """检查论文结构要素是否齐全"""
    issues = []
    # 检查是否有摘要
    if not re.search(r'(?:摘\s*要|内容提要)', text[:500]):
        issues.append(Issue(
            rule_id="ST-01",
            severity="error",
            dimension="结构完整性",
            description="未检测到摘要/内容提要部分",
            suggestion="法学论文应包含摘要（150-300字）"
        ))
    # 检查是否有论点句标志
    has_thesis = re.search(r'本文(?:认为|主张|试图论证|尝试论证|论证|旨在)', text[:2000])
    if not has_thesis:
        issues.append(Issue(
            rule_id="ST-02",
            severity="warning",
            dimension="结构完整性",
            description="引言部分可能缺少明确的论点句（'本文认为/论证……'）",
            suggestion="请在引言末尾加入明确的论点句"
        ))
    # 检查是否有参考文献
    if not re.search(r'(?:参考文献|参考书目|主要参考文献)', text[-2000:]):
        issues.append(Issue(
            rule_id="ST-03",
            severity="info",
            dimension="结构完整性",
            description="未检测到参考文献部分（法学论文可能以脚注为主，视目标期刊要求）",
        ))
    return issues


# ============================================================
# 维度 7: 法学引注 (Legal Citation) - 专用规则
# ============================================================

def check_falv_shixiao(text: str) -> List[Issue]:
    """检查法条时效标注"""
    issues = []
    # 检查引用常用法律时是否标注了版本
    major_laws = [
        ('《民法典》', '2021年施行版本'),
        ('《刑法》', '标注修正年份'),
        ('《公司法》', '标注修订年份（如2023年修订）'),
        ('《行政诉讼法》', '标注修正年份'),
        ('《民事诉讼法》', '标注修正年份'),
        ('《刑事诉讼法》', '标注修正年份'),
    ]
    for law_name, version_hint in major_laws:
        # 查找引用
        citations = re.finditer(re.escape(law_name) + r'第[^。；\n]{5,80}', text)
        for m in citations:
            ctx = m.group()
            # 检查是否已有版本标注
            has_version = re.search(r'（\d{4}年(?:施行|修正|修订)）|（\d{4}年版本）', ctx)
            if not has_version:
                issues.append(Issue(
                    rule_id="LC-01",
                    severity="warning",
                    dimension="法学引注",
                    description=f'{law_name}引用可能缺少版本/时效标注',
                    context=ctx[:100],
                    suggestion=f'建议标注：{law_name}（{version_hint}）'
                ))
    return issues[:8]

def check_panli_format(text: str) -> List[Issue]:
    """检查判例引注格式"""
    issues = []
    # 检查"XX案"类型的判决引用是否有案号
    case_refs = re.finditer(r'(?:参见|如|例如)\s*(?:最高人民法院\s*)?(?:指导案例第?\d+号)?[^。；]*?[案判][^。；]*?(?:判决书|裁定书)?[^。；]*?(?:法院认为|认定|指出|裁判)', text)
    for m in case_refs:
        ctx = m.group()
        # 检查是否有案号
        has_case_number = re.search(r'（\d{4}）.*?字第?\d+号', ctx)
        has_court = re.search(r'(?:最高人民法院|高级人民法院|中级人民法院|基层人民法院)', ctx)
        has_date = re.search(r'\d{4}年\d{1,2}月\d{1,2}日', ctx)
        missing = []
        if not has_case_number:
            missing.append('案号')
        if not has_court:
            missing.append('审理法院全称')
        if not has_date:
            missing.append('裁判日期')
        if missing:
            issues.append(Issue(
                rule_id="LC-02",
                severity="error" if '案号' in missing else "warning",
                dimension="法学引注",
                description=f'判例引用缺少：{", ".join(missing)}',
                context=ctx[:120],
                suggestion='完整格式：案号 + 审理法院全称 + 裁判日期'
            ))
    return issues[:5]


# ============================================================
# 维度 8: 法学逻辑 (Legal Logic) - 专用规则
# ============================================================

def check_comparative_law_completeness(text: str) -> List[Issue]:
    """检查比较法论证的完整性"""
    issues = []
    # 检查是否提到了外国制度但没有说明法域选择理由
    foreign_refs = re.finditer(r'(?:借鉴|参照|参见|比较)\s*(?:德国|法国|日本|美国|英国|欧盟)', text)
    for m in foreign_refs:
        # 在前后500字范围内查找是否有选法域的理由
        nearby = text[max(0, m.start()-500):min(len(text), m.end()+500)]
        has_rationale = re.search(r'(?:之所以选择|选取.*?作为比较|为什么.*?法域|为比较对象|参考价值)', nearby)
        has_limitation = re.search(r'(?:限度|不能照搬|不能直接移植|差异|不同|限缩)', nearby)
        if not has_rationale:
            issues.append(Issue(
                rule_id="LL-01",
                severity="warning",
                dimension="法学逻辑",
                description="比较法论证可能缺少法域选择理由",
                context=m.group()[:80],
                suggestion="请说明为什么选择该法域作为比较对象"
            ))
            break  # 只报一次
        if not has_limitation:
            issues.append(Issue(
                rule_id="LL-02",
                severity="info",
                dimension="法学逻辑",
                description="比较法论证应明示借鉴的限度和条件",
                context=m.group()[:80],
                suggestion="请说明哪些要素不能直接移植及其原因"
            ))
            break
    return issues


# ============================================================
# 汇总所有规则
# ============================================================

ALL_RULES = []  # 将由 register_rules() 填充

def register_rules():
    """注册所有规则"""
    rules = []

    # 可信度
    for pattern, severity, desc in VAGUE_CITATION_PATTERNS:
        def make_fn(p=pattern, s=severity, d=desc):
            def fn(text):
                issues = []
                for m in re.finditer(p, text):
                    issues.append(Issue("R1-01", s, "可信度", d,
                                        context=m.group()[:80],
                                        suggestion=d.split('：')[1] if '：' in d else ''))
                return issues[:3]
            return fn
        rules.append(Rule("R1-01", "可信度", severity, desc, make_fn()))

    for pattern, severity, desc in PLACEHOLDER_PATTERNS:
        def make_fn2(p=pattern, s=severity, d=desc):
            def fn(text):
                issues = []
                for m in re.finditer(p, text):
                    issues.append(Issue("R1-02", s, "可信度", d, context=m.group()[:80]))
                return issues
            return fn
        rules.append(Rule("R1-02", "可信度", severity, desc, make_fn2()))

    for pattern, severity, desc in OVER_ASSERTION_PATTERNS:
        def make_fn3(p=pattern, s=severity, d=desc):
            def fn(text):
                issues = []
                for m in re.finditer(p, text):
                    issues.append(Issue("R1-03", s, "可信度", d, context=m.group()[:80]))
                return issues[:2]
            return fn
        rules.append(Rule("R1-03", "可信度", severity, desc, make_fn3()))

    rules.append(Rule("R1-04", "可信度", "error", "出版年份超过当前年份", check_future_year))

    # 术语
    rules.append(Rule("T-01", "术语一致性", "warning", "法律术语翻译/表述一致性", check_terminology_consistency))

    # 格式
    rules.append(Rule("F-01", "格式规范", "error", "占位符检测", check_footnote_placeholders))
    rules.append(Rule("F-LEGAL-01", "法学引注", "warning", "法律文件引注格式", check_legal_citation_format))
    rules.append(Rule("F-CASE-01", "法学引注", "warning", "判例引注完整性", check_case_citation))
    rules.append(Rule("F-04", "格式规范", "warning", "中英文标点混用", check_punctuation_mixing))

    # 学术语体
    for pattern, desc in COLLOQUIAL_PATTERNS:
        def make_fn4(p=pattern, d=desc):
            def fn(text):
                issues = []
                for m in re.finditer(p, text):
                    issues.append(Issue("S-01", "warning", "学术语体", d, context=m.group()[:80]))
                return issues[:3]
            return fn
        rules.append(Rule("S-01", "学术语体", "warning", desc, make_fn4()))

    rules.append(Rule("S-02", "学术语体", "warning", "自称方式一致性", check_self_reference_consistency))

    # 论证逻辑
    rules.append(Rule("L-03", "论证逻辑", "warning", "引文后缺分析", check_citation_without_analysis))

    # 结构
    rules.append(Rule("ST", "结构完整性", "warning", "结构要素检查", check_structure_completeness))

    # 法学引注
    rules.append(Rule("LC-01", "法学引注", "warning", "法条版本时效标注", check_falv_shixiao))
    rules.append(Rule("LC-02", "法学引注", "error", "判例引注要素完整性", check_panli_format))

    # 法学逻辑
    rules.append(Rule("LL", "法学逻辑", "warning", "比较法论证完整性", check_comparative_law_completeness))

    return rules


# ============================================================
# 主检查函数
# ============================================================

def review(text: str, min_severity: str = "info") -> List[Issue]:
    """
    对文本执行所有检查规则。

    Args:
        text: 论文文本
        min_severity: 最低严重级别 ("error" / "warning" / "info")

    Returns:
        Issue 列表
    """
    global ALL_RULES
    if not ALL_RULES:
        ALL_RULES = register_rules()

    severity_order = {"error": 0, "warning": 1, "info": 2}
    min_level = severity_order.get(min_severity, 2)

    all_issues = []
    for rule in ALL_RULES:
        try:
            issues = rule.check_fn(text)
            for issue in issues:
                if severity_order.get(issue.severity, 2) <= min_level:
                    all_issues.append(issue)
        except Exception as e:
            all_issues.append(Issue(
                rule_id=rule.id,
                severity="info",
                dimension="系统",
                description=f"规则 {rule.id} 执行出错: {str(e)}",
            ))

    return all_issues


def format_issues(issues: List[Issue], fmt: str = "text") -> str:
    """格式化输出"""
    if fmt == "json":
        return json.dumps({
            "total": len(issues),
            "by_severity": {
                "error": len([i for i in issues if i.severity == "error"]),
                "warning": len([i for i in issues if i.severity == "warning"]),
                "info": len([i for i in issues if i.severity == "info"]),
            },
            "issues": [i.to_dict() for i in issues],
        }, ensure_ascii=False, indent=2)

    # 文本输出
    lines = []
    lines.append("=" * 60)
    lines.append("法学论文质量检查报告")
    lines.append("=" * 60)
    lines.append(f"共发现问题: {len(issues)} 项\n")

    # 按严重度排序
    severity_order = {"error": 0, "warning": 1, "info": 2}
    sorted_issues = sorted(issues, key=lambda i: severity_order.get(i.severity, 2))

    # 统计
    counts = Counter(i.severity for i in issues)
    lines.append(f"🔴 Error:   {counts.get('error', 0)}")
    lines.append(f"🟡 Warning: {counts.get('warning', 0)}")
    lines.append(f"🔵 Info:    {counts.get('info', 0)}")
    lines.append("")

    # 分组输出
    current_severity = None
    for issue in sorted_issues:
        if issue.severity != current_severity:
            current_severity = issue.severity
            emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(current_severity, "⚪")
            lines.append(f"\n--- {emoji} {current_severity.upper()} ---")

        lines.append(f"\n[{issue.rule_id}] [{issue.dimension}]")
        lines.append(f"  {issue.description}")
        if issue.context:
            lines.append(f"  上下文: ...{issue.context[:80]}...")
        if issue.suggestion:
            lines.append(f"  建议: {issue.suggestion}")

    lines.append("\n" + "=" * 60)
    lines.append("检查完成。注意：本工具只检查确定性规则，不能替代同行评议。")
    return "\n".join(lines)


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="法学论文质量检查 (review_legal.py)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python review_legal.py paper.md
  python review_legal.py paper.md --format json
  python review_legal.py paper.md --severity error
  python review_legal.py paper.md --output report.md
        """
    )
    parser.add_argument("file", help="待检查的论文文件（.md / .txt / .docx暂不支持）")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    parser.add_argument("--severity", choices=["error", "warning", "info"], default="info",
                        help="最低严重度级别")
    parser.add_argument("--output", "-o", help="输出到文件")
    args = parser.parse_args()

    # 读取文件
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"错误: 文件不存在 - {args.file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取文件失败 - {e}", file=sys.stderr)
        sys.exit(1)

    # 检查
    issues = review(text, min_severity=args.severity)
    output = format_issues(issues, fmt=args.format)

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"报告已保存到: {args.output}")
    else:
        print(output)

    # 有 Error 级别问题时返回非零
    if any(i.severity == "error" for i in issues):
        sys.exit(1)


if __name__ == "__main__":
    main()
