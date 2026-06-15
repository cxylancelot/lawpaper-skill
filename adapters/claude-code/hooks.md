# Claude Code 适配说明

## 与原 Hermes 平台的差异

lawpaper-skill 最初为 Hermes-agent 平台设计，使用了 `skill_view()` 渐进加载、`delegate_task` 子代理等平台特有功能。在 Claude Code 中，这些功能的等效实现如下：

### 渐进加载 → 按需引用
Hermes 的 `skill_view("lawpaper", "references/xxx.md")` 在 Claude Code 中对应：Claude 直接使用 Read 工具读取 references/ 目录下的对应文件。SKILL.md 中的 Quick Reference 表提供了完整的文件索引。

### 子代理 → 角色切换
Hermes 的 `delegate_task` 子代理在 Claude Code 中通过对话内角色切换实现。5个子代理角色的设计保留在 `adapters/hermes/subagent-roles.md`，Claude 可在对话中模拟这些角色。

### 自我更新 → 手动编辑
Hermes 的 `skill_manage patch` 在 Claude Code 中对应：用户授权后直接编辑文件。

### 路径解析
- Hermes: `${HERMES_SKILL_DIR}/references/xxx.md`
- Claude Code: 使用相对于 skill 目录的相对路径 `references/xxx.md`

## 权限建议

此 skill 需要以下权限（建议在 settings.json 中预先授权）：
- Read: references/ 目录下所有 .md 文件
- Read: templates/ 目录下所有 .md 文件
- Bash: 运行 scripts/review_legal.py 和 scripts/check_stage.py
