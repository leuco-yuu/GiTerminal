# Security Policy

Git Terminal 会执行本机 Git、shell、SSH 和平台 CLI 命令。安全边界必须清晰：应用负责展示、确认和调用命令；实际 Git 行为由本机 Git 决定。

## 支持范围

当前项目处于桌面工具阶段，安全修复优先覆盖：

- 高风险 Git 命令误执行。
- 命令参数处理异常。
- 凭据泄露风险。
- SSH key / token 处理不当。
- UI 绕过确认流程的问题。

## 高风险命令

以下类型命令应触发确认：

- 删除文件或清理未跟踪文件。
- 改写提交历史。
- 强制推送或删除远程引用。
- 删除/覆盖 tag。
- 修改底层引用。
- 清理 reflog、prune、立即 gc。

风险分类实现位于：

```text
src/git_terminal/core/safety.py
```

测试位于：

```text
tests/test_safety.py
```

## 凭据处理

不得在源码、配置示例或日志中写入真实凭据，包括：

- GitHub / GitLab / Gitee token。
- SSH 私钥。
- OAuth token。
- personal access token。
- 密码。

建议使用：

- Git credential helper。
- GitHub CLI / GitLab CLI 自带登录。
- 操作系统安全存储。
- `keyring` 支持的后端。

## 报告安全问题

如果发现安全问题，请在公开 issue 中避免粘贴 token、私钥或敏感仓库信息。建议报告内容包括：

- 受影响版本。
- 操作系统和 Python 版本。
- Git 版本。
- 复现步骤。
- 预期行为和实际行为。
- 已脱敏的命令、stdout/stderr。

## 本地使用注意

- 不要在不可信仓库中执行不理解的 shell 命令。
- 不要复制执行来源不明的 `git alias` 或 hook。
- 对 force push、reset hard、clean、prune 等命令保持二次确认。
- 对平台 token 使用最小权限。
