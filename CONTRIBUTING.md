# Contributing

感谢参与 Git Terminal。提交变更时请优先保证 Git 行为透明、可测试、可回滚。

## 基本原则

- 不重新实现 Git 核心语义。
- 不隐藏实际执行命令。
- 不绕过高风险命令确认流程。
- 不在仓库中提交 token、私钥、密码或平台凭据。
- UI 便利性不能牺牲命令可审计性。

## 开发流程

1. Fork 或创建功能分支。
2. 安装开发依赖。
3. 修改代码。
4. 补充测试。
5. 运行测试。
6. 更新文档和变更记录。
7. 提交 Pull Request。

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
python -m pytest
```

## 提交信息建议

建议使用简洁前缀：

```text
feat: add branch operation
fix: handle invalid cwd
refactor: split provider actions
docs: update release guide
test: cover force push risk
```

## 新增 Git 命令入口

新增 Git 操作入口时，请检查：

- 命令是否可能删除数据。
- 命令是否可能改写历史。
- 命令是否可能影响远程仓库。
- 是否需要新增风险分类测试。
- UI 上是否展示了真实命令。

## 新增平台能力

平台 API/CLI 能力应保持为增强功能，不应被包装成 Git 原生命令。凭据处理应优先使用：

- 平台 CLI 自带认证。
- 系统 Keychain / Credential Manager / Secret Service。
- `keyring`。

不得提交硬编码 token。

## 文档要求

涉及用户可见行为变化时，请同步更新：

- `README.md`
- `docs/USAGE.md`
- `CHANGELOG.md`

涉及内部结构变化时，请同步更新：

- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT.md`
