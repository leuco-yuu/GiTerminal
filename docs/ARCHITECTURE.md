# 架构说明

Git Terminal 采用分层结构：UI 层负责交互和展示，Core 层负责命令建模、风险分类、Git CLI 调用和结果解析。项目不直接解析或写入 `.git` 内部对象数据库，避免与 Git 原生命令行为产生不一致。

## 总体数据流

```text
用户操作
  ↓
PyQt6 UI / 表单 / 菜单 / Raw Terminal
  ↓
命令构造与风险分类
  ↓
GitRunner / ShellCommandWorker
  ↓
本机 git / shell / gh / glab
  ↓
stdout / stderr / returncode
  ↓
GitResult
  ↓
UI 输出、状态刷新、列表更新、确认提示
```

## 模块职责

### `src/git_terminal/app.py`

应用启动入口。职责：

- 安装 Qt message handler。
- 创建 `QApplication`。
- 初始化并展示 `MainWindow`。

### `src/git_terminal/core/runner.py`

Git CLI 调用封装。职责：

- 管理当前工作目录。
- 执行 `git` 子命令。
- 统一捕获 stdout/stderr/returncode。
- 处理无效工作目录、超时和异常场景。
- 提供仓库状态、分支、HEAD、upstream 等摘要能力。

### `src/git_terminal/core/models.py`

核心数据模型。职责：

- Git 命令执行结果。
- 工作区状态项。
- 仓库摘要。
- 风险等级枚举。

### `src/git_terminal/core/safety.py`

风险分类。职责：

- 接收命令字符串或命令参数列表。
- 识别 destructive / irreversible / high-impact Git 操作。
- 返回风险等级和确认提示信息。

该模块应保持纯逻辑，便于测试。

### `src/git_terminal/core/commands.py`

Git 命令目录。职责：

- 内置 fallback 命令目录。
- 调用 `git help -a` 动态发现本机 Git 支持的命令。
- 为高级命令面板提供分类、说明、示例和常用选项。

### `src/git_terminal/core/encoding.py`

跨平台输出解码。职责：

- 统一 subprocess 环境变量。
- 对 stdout/stderr 做 UTF-8 优先解码。
- 在 Windows/不同区域设置下尽量保留可读输出。

### `src/git_terminal/i18n.py`

多语言服务。职责：

- 读取内置语言配置。
- 读取用户级语言配置。
- 对未知 UI 文案生成稳定 key。
- 在 zh/en/default/all 模式之间切换。

### `src/git_terminal/ui/main_window.py`

主界面。职责：

- 组织菜单、活动栏、侧栏、工作区、底部终端。
- 绑定用户操作和命令执行。
- 处理状态刷新、表单、确认、输出展示。
- 协调 Git 工作流和 UI 更新。

该文件目前承载逻辑较多。后续重构时可优先拆分为：

- repository actions
- branch actions
- remote actions
- tag/stash actions
- platform actions
- conflict actions
- form/dialog service

拆分时应先补测试，再保持外部行为一致。

### `src/git_terminal/ui/workers.py`

后台任务执行。职责：

- 将 Git 命令或 shell 命令放入 Qt worker。
- 避免长耗时命令阻塞 UI 主线程。
- 将 `GitResult` 通过 signal 回传。

### `src/git_terminal/ui/theme.py`

主题样式。职责：

- 提供深色/浅色主题。
- 提供 accent 配色。
- 统一 Qt stylesheet。

### `src/git_terminal/ui/vscode_shell.py`

类 VS Code Shell 布局组件。职责：

- Activity Bar。
- 左右侧栏。
- 顶部命令栏。
- 底部面板。
- 图标按钮。

### `src/git_terminal/ui/commit_graph.py`

提交图组件。职责：

- 表达 commit node 和 parent/child 关系。
- 负责图形布局和绘制。
- 提供 fit view、刷新、节点交互等能力。

## 资源文件

```text
src/git_terminal/assets/*.svg
src/git_terminal/language_config.json
```

资源通过 `Path(__file__)` 相对包路径定位。由于项目采用 `src/` 布局，打包时必须把这些资源包含进 wheel/sdist。对应配置位于：

- `pyproject.toml` 的 `[tool.setuptools.package-data]`
- `MANIFEST.in`

## 风险控制边界

风险分类只负责识别和提示，不负责代替 Git 决策。高风险命令仍由本机 Git 执行，项目只在执行前加确认门禁。

建议原则：

- 新增 destructive 命令入口时必须补 `tests/test_safety.py`。
- UI 中新增绕过 `GitRunner` 的执行路径时，需要明确风险分类是否覆盖。
- Raw Terminal 的 Git 命令也应经过同等风险判断。

## 平台能力边界

GitHub、GitLab、Gitee 等平台能力不属于 Git 原生命令。项目可以调用 `gh`、`glab` 或平台 API，但应继续保持：

- Git 原生命令与平台扩展入口分离。
- 平台凭据不硬编码。
- token/credential 优先走系统安全存储或平台 CLI 自带认证机制。

## 后续可维护性建议

在不改变用户可见行为的前提下，后续可以逐步进行以下内部重构：

1. 将 `main_window.py` 的命令动作拆到 action service。
2. 给 UI 表单请求封装单独服务。
3. 为 `GitRunner.summary()` 等摘要逻辑增加更多单元测试。
4. 将平台 CLI 相关能力拆到 `providers/` 包。
5. 为大仓库场景加入分页、缓存和取消任务机制。
