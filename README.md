# lawpaper-skill

> 法学论文写作全流程协作 Skill — 知识库来自何海波《法学论文写作》

## 概述

本 skill 为 Claude Code 提供法学论文写作的系统方法指导，涵盖**选题、文献、调查、论证、行文、格式规范与学术伦理**的全流程。既是写作教练（诊断→追问→讨论→下笔→回顾），也是你的代笔——和你讨论清楚后，帮你把论文写出来。

## 适用范围

- 法教义学论文 / 案例分析 / 立法评述 / 比较法论文 / 实证研究 / 法哲学论文
- 本科毕业论文 / 硕士论文 / 博士论文 / 期刊投稿

## 目录结构

```
lawpaper-skill/
├── SKILL.md                  # 主 skill 定义（工作流、硬性规则、方法论）
├── references/               # 参考知识库（16 个文件）
│   ├── topic-selection.md        # 选题篇
│   ├── literature-search.md      # 文献篇
│   ├── investigation-methods.md  # 调查篇
│   ├── legal-argumentation.md    # 论证篇
│   ├── legal-writing.md          # 行文篇
│   ├── legal-citation.md         # 格式篇
│   ├── legal-ethics.md           # 伦理篇
│   ├── theory-frameworks.md      # 法学理论框架速查
│   ├── model-papers.md           # 范例论文拆解
│   ├── common-mistakes.md        # 常见错误病例
│   ├── stage-checklists.md       # 阶段关卡检查清单
│   ├── decision-tree.md          # 论文类型决策树
│   ├── academic-expressions.md   # 法学常用表达词库
│   ├── collaboration-patterns.md # 协作场景模式库
│   ├── subagent-roles.md         # 子代理角色设计
│   └── learning-loop.md          # 学习循环集成
├── scripts/                  # 质检脚本
│   ├── review_legal.py           # 8 维质量检查
│   └── check_stage.py            # 关卡自动化检查
├── templates/                # 论文模板
│   ├── paper-outline.md          # 6 类型大纲模板
│   ├── argument-map.md           # 论证骨架图模板
│   └── citation-checklist.md     # 引注自查表
└── .gitignore
```

## 安装

将此 skill 安装到 Claude Code：

```
# 方式一：通过 skill-installer
/skill-installer cxylancelot/lawpaper-skill

# 方式二：手动安装
# 将本仓库克隆到 .claude/skills/lawpaper-skill/ 目录下
```

## 核心方法论

**原则**：
1. **问题从规范/判例中生长出来** — 好问题是"被材料逼出来的"
2. **论证以法教义学为基础，兼收社科方法** — 先穷尽规范分析再引入外部视角
3. **引注即论证** — 每个引注都在回答"这个主张的规范基础在哪里"

**硬性规则**：不编造文献、不虚构引文、不混淆"作者观点"和"引用的观点"、法条必须核验现行有效版本、判例引用必须标注案号/法院/日期。

## 知识来源

何海波《法学论文写作》，全书七篇体系。

## License

MIT
