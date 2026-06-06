# 学习循环集成指南

> hermes-agent 的核心能力之一是 skill_manage——允许 skill 在执行中自我更新。以下为 lawpaper-skill 设计的学习循环钩子。

---

## 一、学习循环的原理

```
使用 skill → 发现不足 → skill_manage patch → skill 更新 → 下次执行更好
```

hermes-agent 在以下时机检查是否需要更新 skill：
1. 用户明确纠正 skill 的错误行为
2. skill 执行中遇到持续失败的任务
3. 外部信息变化（如数据库 API 变更、法律更新）

---

## 二、预设的反馈钩子

### 钩子 1：法学数据库检索语法变更

**触发条件**：用户反复反馈某数据库的检索语法不再有效

**触发操作**：
```
skill_manage patch lawpaper
  file: references/literature-search.md
  old: [原来描述的检索语法]
  new: [用户报告的新语法]
  reason: "[数据库名称]平台于[日期]更新了检索界面，旧语法不再有效"
```

**边界说明**：
- ✅ 适合自动更新：检索语法、导出步骤、网址变更
- ❌ 不适合自动更新：数据库选择策略（方法论问题，需要人工判断）

---

### 钩子 2：引注规则变化

**触发条件**：新法颁布/新司法解释发布导致引注规则实际变化

**触发操作**：
```
skill_manage patch lawpaper
  file: references/legal-citation.md
  section: "## 二、法律文件引注"
  change: "新增：[新法类型]的引注格式为……"
  reason: "[新法名称]于[日期]颁布/施行，根据《法学引注手册》原则，其引注格式为……"
```

**边界说明**：
- ✅ 适合更新：新增法律类型的引注示例
- ❌ 不适合自动更新：《法学引注手册》版本更新后的重大规则变化（需要整体重写对应章节，而非 patch）

---

### 钩子 3：常见错误库扩充

**触发条件**：用户反复纠正同一种论证错误（不在现有 common-mistakes.md 中）

**触发操作**：
```
skill_manage patch lawpaper
  file: references/common-mistakes.md
  action: append
  section: "## [对应篇章]常见错误"
  content: |
    ### 错误 N：[错误名称]
    **症状**：[描述]
    **反面例子**：[模拟]
    **正确做法**：[说明]
  reason: "用户在使用过程中多次出现此类错误，该模式具有普遍性"
```

**触发阈值**：同一错误模式被纠正 ≥ 3 次后触发（避免过度敏感）

**边界说明**：
- ✅ 适合追加：新的错误病例
- ❌ 不适合修改：已有的错误诊断标准（那是方法论问题，不是使用数据能改变的）

---

### 钩子 4：法学期刊信息更新

**触发条件**：法学核心期刊目录变化（如CSSCI目录更新、期刊更名）

**触发操作**：
```
skill_manage patch lawpaper
  file: references/topic-selection.md
  section: "## 四、法学核心期刊选题趋势速览"
  change: "更新期刊列表和趋势描述"
  reason: "[年份]版CSSCI来源期刊目录更新 / [期刊名]更名为[新刊名]"
```

---

## 三、不自动更新的内容

以下内容**不接受 skill_manage 自动修改**，必须人工审查后更新：

| 内容 | 原因 |
|------|------|
| 硬性规则 (R1-R6) | 学术伦理底线，不应由使用模式决定 |
| 方法论原则（3条） | 法学写作的哲学基础，不应被频率数据改变 |
| 理论框架描述（theory-frameworks.md） | 涉及对学术流派的定性判断 |
| 范例拆解（model-papers.md） | 涉及对已发表论文的评价 |
| 子代理角色设计（subagent-roles.md） | 影响 skill 的整体架构 |

---

## 四、skill_manage 使用示例

### 查看当前 skill 状态
```
# 无需 skill_manage，直接通过 skills_list 或 skill_view
```

### 局部修改（patch）
```
skill_manage patch lawpaper
  file: references/literature-search.md
  search: "裁判文书网检索语法：案由 + 法院层级 + 审理法院地域 + 裁判日期 + 关键词"
  replace: "裁判文书网检索语法：案由 + 法院层级 + 审理法院地域 + 裁判日期 + 关键词 + 审判程序（注意：2025年改版后增加了'审判程序'筛选条件）"
  reason: "裁判文书网于2025年3月改版"
```

### 追加内容（append）
```
skill_manage patch lawpaper
  file: references/common-mistakes.md
  action: append_after "## 论证篇常见错误"
  content: [新错误条目]
  reason: "发现新的常见错误模式"
```

---

## 五、学习循环的边界与伦理

1. **学习不是无限的。** skill 自我更新的目标是"更准确地执行已有方法"，而不是"改变方法论本身"。
2. **用户始终拥有最终编辑权。** skill_manage 的修改应在用户了解并同意后进行。
3. **透明的更新日志。** 每次 skill_manage patch 后应在文件末尾追加更新记录：
   ```
   > [日期] 由 skill_manage patch 更新：[更新内容摘要]。原因：[触发原因]。
   ```
4. **如果更新后的 skill 行为不符合预期，用户可以通过 git revert 或手动编辑回退。**
