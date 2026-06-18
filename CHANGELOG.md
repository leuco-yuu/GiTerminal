# Git Terminal 更新日志

## v1.0.0

- 项目结构升级为发布级结构：
  - 源码迁移为标准 `src/` 布局。
  - 应用包路径变为 `src/git_terminal/`。
  - 测试目录保留为 `tests/`。
  - 新增 `docs/` 文档目录。
  - 新增 `scripts/` 脚本目录。
  - 清理发布包中的 `__pycache__`、`.pyc`、`.pytest_cache` 等非源码缓存文件。
  - v0.8.8 到 v1.0.0 的业务源码在路径归一化后保持一致，主要变化是工程结构和发布文件。

- Python 包构建配置新增：
  - 新增 `pyproject.toml`。
  - 使用 `setuptools` 作为构建后端。
  - 新增项目依赖声明。
  - 新增开发依赖声明。
  - 新增 console script：`git-terminal`。
  - 新增 GUI script：`git-terminal-gui`。
  - 配置 `src` 作为 package-dir。
  - 配置 package data，确保语言配置和 SVG 图标进入发布包。
  - 配置 pytest 的 testpaths 和 pythonpath。

- 包数据与发布清单新增：
  - 新增 `MANIFEST.in`。
  - 确保 `language_config.json` 进入源码包。
  - 确保 `assets/*.svg` 进入源码包。
  - 确保 README、LICENSE、CHANGELOG、SECURITY、CONTRIBUTING 等文档进入源码包。
  - 确保 docs 文档进入源码包。
  - 排除缓存、pyc、pytest cache、构建产物等不应发布的文件。

- 启动入口适配 `src/` 布局：
  - `run.py` 新增 `src` 路径注入逻辑。
  - 未安装包时仍可直接执行 `python run.py`。
  - `run.py` 使用 `raise SystemExit(main())` 返回主程序退出码。
  - 无扩展名 `run` 同步适配 `src` 布局。
  - 保留本地开发直接启动方式。

- 文档体系成熟化：
  - 重写发布版 `README.md`。
  - 新增 `docs/ARCHITECTURE.md`。
  - 新增 `docs/USAGE.md`。
  - 新增 `docs/DEVELOPMENT.md`。
  - 新增 `docs/RELEASE.md`。
  - 新增 `CONTRIBUTING.md`。
  - 新增 `SECURITY.md`。
  - 新增 `CHANGELOG.md`。
  - 新增 `LICENSE` 占位说明。
  - README 中补充安装、运行、测试、构建、故障排查和文档索引。

- 开发规范文件新增：
  - 新增 `.editorconfig`。
  - 新增 `.gitattributes`。
  - 扩展 `.gitignore`。
  - 新增 `requirements-dev.txt`。
  - 新增 GitHub Actions CI workflow。
  - 新增 `.github/workflows/ci.yml`。
  - CI 覆盖安装开发依赖并执行测试。

- 发布前检查脚本新增：
  - 新增 `scripts/check_project.py`。
  - 支持检查关键文件是否存在。
  - 支持检查关键资源是否存在。
  - 支持执行 pytest。
  - 支持执行包构建。
  - 用于发布前快速验证项目结构和测试状态。

- 测试体系保留：
  - 保留 `tests/test_safety.py`。
  - 保留 `tests/test_runner_workflows.py`。
  - 测试路径适配 `src` 布局。
  - 发布结构下可通过 pytest 运行测试。

- 版本号注意：
  - `src/git_terminal/__init__.py` 中 `__version__` 已更新为 `1.0.0`。
  - 如果 `pyproject.toml` 中 `[project].version` 未同步为 `1.0.0`，正式发布前应一并修改。

---

## v0.8.8

- 远程页新增固定 Tracking / Upstream 面板：
  - 远程页顶部新增 `Tracking / Upstream` 分组。
  - 跟踪分支入口不再隐藏在按钮网格或滚动区域里。
  - 新增本地分支输入框、remote 输入框、远程分支输入框。
  - 默认 remote 为 `origin`。
  - 远程分支为空时默认等于本地分支。

- 新增远程跟踪分支快捷操作：
  - 新增 `Fetch remote branches`。
  - 新增 `Track existing remote branch`。
  - 新增 `Publish local branch + track (Push -u)`。
  - 新增 `Show upstream`。
  - 支持直接执行 `git fetch <remote> --prune`。
  - 支持直接执行 `git branch --set-upstream-to <remote>/<branch> <local>`。
  - 支持直接执行 `git push -u <remote> <local>`。
  - 支持直接查看当前分支 upstream。

- 远程跟踪字段自动同步：
  - 新增 `_current_branch_name()`。
  - 新增 `_sync_remote_tracking_fields()`。
  - 新增 `_remote_tracking_values()`。
  - 刷新 remote 列表后自动同步当前本地分支。
  - 选中 remote tree 项后自动同步 remote 名称。
  - 远程分支字段可根据本地分支自动填充。

- Track Existing 行为增强：
  - 执行 Track Existing 前先通过 `git ls-remote --heads <remote> <branch>` 检查远程分支是否存在。
  - 如果远程分支存在，则设置 upstream。
  - 如果远程分支不存在，提示该操作只适用于远程分支已存在的场景。
  - 远程分支不存在时提示用户改用 Push -u。
  - 用户确认后可直接执行 `git push -u <remote> <local>`。
  - 用户取消后写入日志提示可先 Fetch 或使用 Push -u。

- 右侧 ACTIONS 远程操作增强：
  - 右侧 ACTIONS > Remote 新增 `Track Existing`。
  - 右侧 ACTIONS > Remote 新增 `Push -u`。
  - 原 `Set Track` 入口替换为更清晰的分场景操作。
  - 远程页按钮网格同步使用 `Track Existing` 和 `Push -u`。

---

## v0.8.7

- Git 代理清空行为修复：
  - 清空 `http.proxy` / `https.proxy` / `http.noProxy` 时，不再把 key 不存在误判为失败。
  - 新增 `_git_config_key_exists()` 检查配置项是否存在。
  - 不存在的代理项显示“未配置，无需删除”。
  - 只有存在的项才执行 `git config --unset-all`。
  - 避免无害返回码污染整个代理配置结果。

- 代理设置流程改为逐项执行：
  - 新增 `apply_proxy_settings()`。
  - 每个代理配置项单独执行 set 或 unset。
  - 每个配置项单独记录成功、失败、无需删除状态。
  - 任一项失败会汇总失败 key。
  - 所有项执行完后统一输出当前配置状态。

- Git config 作用域处理增强：
  - 新增 `_git_config_cwd_for_scope()`。
  - local 作用域使用当前仓库目录。
  - global/system 作用域不强制使用仓库目录。
  - 新增 `_format_git_config_scope_list()`。
  - 设置或清空代理后会列出当前作用域的 Git config。
  - local 作用域未打开仓库时直接取消操作。

- 代理配置页面说明更新：
  - 代理配置表单说明明确：留空会删除对应 key。
  - 代理配置表单说明明确：不存在的 key 不会被当成错误。
  - 配置完成后自动刷新 Git config 列表。

---

## v0.8.6

- 底部状态行配色修正：
  - 底部状态行不再直接使用主题强调色。
  - 深色模式下使用深灰背景。
  - 浅色模式下使用浅灰背景。
  - 减少状态栏抢占视觉焦点的问题。

- Git config 列表支持直接编辑：
  - 新增 `_git_config_tree_item_changed()`。
  - Git config tree 的 Key / Value 支持双击编辑。
  - 修改 Value 后自动执行对应 `git config --<scope> <key> <value>`。
  - 修改 Key 时会先 unset 原 key，再 set 新 key。
  - Scope / Origin 列为只读信息。
  - 误改只读列时会自动恢复原值。
  - key 为空时自动回滚。
  - local 作用域未打开仓库时阻止编辑。
  - git config 更新失败时自动回滚界面。
  - 更新成功后刷新对应 scope 的配置列表。

- Custom 按钮点击闪退修复：
  - 修复 PyQt `clicked(bool)` 信号参数覆盖自定义命令字符串的问题。
  - 自定义按钮连接 lambda 时显式接收 `_checked=False`。
  - 避免点击 Custom 按钮时把 bool 当作 commands 执行。
  - 降低用户自定义按钮执行时的崩溃概率。

- Windows CLI 安装命令过长修复：
  - 移除超长 `PowerShell -EncodedCommand` 执行方式。
  - 新增 `_powershell_script_file_command()`。
  - 将 Windows portable 安装脚本写入临时 `.ps1` 文件。
  - 通过 `powershell.exe -File` 执行临时脚本。
  - 避免 Windows `cmd.exe` 命令行长度限制。
  - 临时安装脚本路径记录到 `_cli_install_scripts`。
  - 安装提示中明确说明脚本已写入临时 `.ps1`。

- SSH 配置脚本变量替换修复：
  - 修正 SSH 配置 Python 脚本中的 payload 替换占位。
  - 使用 `PAYLOAD` 替换原占位文本。
  - 避免脚本生成后 JSON payload 无法正确载入。

---

## v0.8.5

- Git 配置列表能力增强：
  - 新增 `refresh_git_config_list_scope()`。
  - 新增 `refresh_git_config_list_all()`。
  - 新增 `_parse_git_config_lines()`。
  - 新增 `_set_git_config_tree_rows()`。
  - 支持按 global/local/system 作用域刷新配置。
  - 支持一次列出 global/local/system 所有配置。
  - 支持解析 `git config --list --show-origin` 输出。
  - Git config tree 显示作用域、来源、Key、Value 四列。
  - 选中配置项后可自动填入下方编辑区。

- Git 配置编辑体验增强：
  - 新增 `_copy_selected_git_config_to_editor()`。
  - 选中配置项后自动同步 scope。
  - 选中配置项后自动同步 key。
  - 选中配置项后自动同步 value。
  - 常用 config key 下拉选项更便于编辑代理、credential、SSH、pull、core 等配置。

- 代理配置入口新增：
  - 新增 `configure_proxy_from_page()`。
  - 支持设置 `http.proxy`。
  - 支持设置 `https.proxy`。
  - 支持设置 `http.noProxy`。
  - 支持选择 global/local/system 作用域。
  - 支持留空删除对应代理配置。
  - 配置完成后刷新 Git config 列表。

- SSH key 管理增强：
  - 新增 `list_local_ssh_keys()`。
  - 支持列出 `~/.ssh` 下的私钥候选。
  - 支持标记私钥是否存在对应 `.pub` 公钥。
  - 支持列出公钥文件。
  - 支持显示 SSH config 文件内容。
  - 新增 `create_provider_ssh_key_from_page()`。
  - 支持按 provider/account 创建平台独立 SSH 私钥。
  - 支持设置 key 注释邮箱。
  - 支持自定义 key path。
  - 支持选择是否覆盖已有 key。
  - 生成完成后输出公钥内容。

- 平台配置页补强：
  - Git 配置页启动时可自动刷新全部 Git config。
  - 平台输出区可展示 Git config 列表、SSH key 列表、SSH config 内容。
  - 用户与账号配置区可集中展示 Git identity、credential helper、Gitee Token 状态。

- 外部命令执行封装新增：
  - 新增 `run_external_command_with_callback()`。
  - 外部命令执行后可回调处理结果。
  - 外部命令 stdout/stderr 使用统一 UTF-8 容错解码。
  - 外部命令异常时会转换为 `GitResult`。
  - 回调异常会写入日志，不直接导致 UI 崩溃。

- 底部终端环境说明新增：
  - 新增 `_terminal_environment_text()`。
  - Windows 下显示 `cmd.exe /d /s /c`、UTF-8 code page、解码 fallback 信息。
  - Unix/macOS 下显示 `/bin/sh -lc`、UTF-8 env、解码 fallback 信息。
  - 终端输入栏新增环境说明标签和 tooltip。

---

## v0.8.4

- 新增 VS Code 风格底部状态行：
  - 新增 `_build_bottom_status_strip()`。
  - 主窗口底部新增固定高度状态栏。
  - 原本显示在工作区顶部的仓库状态信息迁移到底部。
  - 底部状态行拆分为多个状态段。
  - 状态段支持 tooltip 展示完整信息。

- 底部状态行内容增强：
  - 显示当前仓库名称、当前分支、当前 HEAD、upstream。
  - 显示 ahead / behind、dirty 状态、暂存数量、工作区修改数量、未跟踪文件数量、冲突数量。
  - 显示仓库 mode、remote 列表、Push 目标、本地仓库路径、Git 版本。

- Push 目标展示增强：
  - 新增 `_repo_target_details()`。
  - 支持根据 upstream 推断 push 目标。
  - 有 upstream 时显示 upstream。
  - 没有 upstream 但有 remote 时优先显示 `origin/(未设置跟踪分支)`。
  - 没有 origin 时使用第一个 remote。
  - 支持读取 `git remote get-url --push <remote>`。
  - 状态栏 tooltip 展示提交/推送目标、Push URL、当前提交和本地路径。

- 状态栏长文本处理增强：
  - 新增 `_short_middle()`。
  - 长仓库名、remote、Push 目标、本地路径会中间省略。
  - 完整内容保留在 tooltip。
  - Push URL、本地路径、仓库路径等长文本不再撑爆底部状态行。

- HTTPS URL 脱敏：
  - 新增 `_sanitize_url_for_status()`。
  - 状态行显示 HTTPS URL 时会隐藏明文凭据。
  - 形如 `https://user:password@host/repo.git` 的 URL 会显示为 `https://user:***@host/repo.git`。
  - 降低始终可见状态栏泄露凭据的风险。

- 工作区状态统计增强：
  - `update_top_status()` 内部改为更新底部状态行。
  - 通过 `parse_status()` 统计暂存、修改、未跟踪、冲突数量。
  - 新增 `_is_conflict_status()` 判断冲突状态。
  - 冲突数量会直接显示在底部状态行。

- Git 版本展示新增：
  - 环境检测后保存 Git 版本文本。
  - 底部状态行显示简短 Git 版本。
  - tooltip 保留完整 `git version ...` 输出。

---

## v0.8.3

- 工作区覆盖表单对齐优化：
  - 修正表单标签列和输入列对齐问题。
  - 同一表单内所有输入框左边界统一。
  - 同一表单内所有输入框右边界统一。
  - 标签右对齐并与控件垂直居中。
  - Clone / Remote 等表单中的 URL、父目录字段统一宽度。
  - 文件夹选择按钮继续嵌入输入框尾部，不再额外占据布局列。

- 表单建议逻辑修复：
  - URL 字段不再因为 label 包含“远程”而错误显示 remote 名称下拉建议。
  - remote 名称建议与 URL 输入场景区分处理。
  - 降低 Clone、Remote URL、HTTPS URL 输入时的误导性建议。

- 新增 Git 配置页面：
  - 平台页新增“Git 配置”页面。
  - 支持读取 Git config。
  - 支持设置 Git config。
  - 支持删除 Git config。
  - 支持列出 global/local/system 作用域配置。
  - 支持配置 `http.proxy`、`https.proxy`、`credential.helper`、`core.sshCommand`。
  - 支持查看和设置 `pull.*`、`core.*` 等常用配置项。
  - local 作用域操作会检查是否已打开仓库。

- SSH Host / 端口配置新增：
  - 新增 SSH Host 配置入口。
  - 支持写入 `~/.ssh/config`。
  - 支持配置 Host、HostName、Port、User、IdentityFile。
  - 同时保留 `core.sshCommand` 配置入口。
  - 便于处理非 22 端口、自定义 SSH alias、多账号平台场景。

- 平台页面结构优化：
  - 合并 GitHub 与 GitHub CLI 页面。
  - 合并 GitLab 与 GitLab CLI 页面。
  - 避免平台页出现重复标签页。
  - CLI 安装成功后跳转到合并后的 GitHub / GitLab 页。
  - GitHub / GitLab 页面同时承载认证配置和 CLI 常用功能。

- 远程页功能入口补强：
  - 远程页新增 Set Tracking、Push -u、SSH Auth、HTTPS Auth、Test Auth。
  - 配置 Git remote 认证不再要求先登录 GitHub/GitLab。
  - 本地 Git remote 认证配置和平台 CLI 登录状态解耦。

- 自定义按钮输入增强：
  - Custom 按钮的 commands 输入改为多行输入框。
  - 支持一行或多行 shell/git 指令。
  - 多命令自定义按钮更适合保存 fetch、status、branch、log 等组合操作。

- 应用图标更新：
  - 替换应用图标为更简洁的单色风格 SVG。
  - 图标风格更接近当前 VS Code Shell 界面。

---

## v0.8.2

- Windows CLI 安装 fallback 新增：
  - Windows 安装 `gh` / `glab` 时，优先使用已有包管理器。
  - 支持检测 `winget`、`choco`、`scoop`。
  - 如果没有任何包管理器，则改为从官方 latest release 下载 Windows zip。
  - 下载后解压到 `%LOCALAPPDATA%\GitTerminal\bin`。
  - 安装目录会写入当前用户 PATH。
  - 支持检测已存在的便携安装文件。
  - 如果便携安装文件已存在，只执行版本检查。

- 安装结果校验增强：
  - 安装完成后必须执行 `gh --version` 或 `glab --version`。
  - 版本检查成功才认为 CLI 可用。
  - 版本检查失败时保留错误输出。
  - 失败时不再提示“流程结束”。
  - 失败时不跳转到 GitHub CLI / GitLab CLI 页面。

- Windows portable 安装脚本增强：
  - 支持访问 GitHub CLI latest release。
  - 支持访问 GitLab CLI latest release。
  - 支持筛选 Windows amd64/x86_64 zip 资产。
  - 支持下载、解压、查找 exe、复制到用户目录。
  - 支持将用户目录加入 PATH。
  - 脚本输出使用 UTF-8 设置，减少中文输出乱码。

---

## v0.8.1

- 新增统一命令输出编码模块：
  - 新增 `git_terminal/core/encoding.py`。
  - 新增 `decode_command_output()`、`completed_process_text()`、`timeout_output_text()`、`utf8_subprocess_env()`。
  - 统一 subprocess 输出解码逻辑。

- 命令输出解码增强：
  - subprocess 不再依赖 `text=True + encoding="utf-8"` 的单一解码路径。
  - 改为读取 bytes 后统一容错解码。
  - 解码优先级覆盖 UTF-8、UTF-8-SIG、系统 locale、GB18030、GBK、CP936。
  - 改善 Windows 中文环境、Git 输出、SSH 输出、平台 CLI 输出的兼容性。
  - `GitResult` 统一通过编码工具清洗 stdout/stderr。

- GitRunner 与 Shell Worker 稳定性增强：
  - `GitRunner.run()` 使用统一 UTF-8 子进程环境。
  - `GitRunner.run()` 使用 bytes 输出并统一解码。
  - `ShellCommandWorker` 使用统一 UTF-8 子进程环境。
  - `ShellCommandWorker` 使用 bytes 输出并统一解码。
  - `git help -a` 动态命令发现改用统一解码逻辑。

- 平台认证状态读取修复：
  - `gh auth status` 改为 bytes 输出后统一解码。
  - `glab auth status` 改为 bytes 输出后统一解码。
  - 避免平台 CLI 输出非标准编码时造成 UI 读取失败。

- SSH 配置脚本输出修复：
  - SSH 测试脚本新增 fallback 解码函数。
  - `ssh -T` 的 stdout/stderr 不再强制按 UTF-8 单一路径解析。
  - 降低 Windows/中文区域设置下 SSH 测试输出乱码或异常的概率。

- 工作区表单紧凑化：
  - 新增 `_compact_field_width()`、`_set_compact_field_size()`、`_attach_folder_picker_action()`。
  - 表单字段高度压缩到更适合桌面工具的尺寸。
  - 表单字段宽度根据默认值、label、key 自动计算。
  - 目录选择按钮从独立按钮改为嵌入输入框尾部。
  - 表单标签统一右对齐并垂直居中。

- 文件夹选择行为优化：
  - Clone Dialog 的目标目录选择会根据当前输入路径推断起始目录。
  - 如果选择的目录不存在，会尝试自动创建。
  - 创建失败时弹出错误提示，而不是继续执行后续命令。
  - 工作区表单中的目录字段也复用相同的选择和创建逻辑。

- CLI 安装流程更稳健：
  - 新增 `_cli_install_command()` 和 `_install_cli_tool()`。
  - 安装 `gh` / `glab` 前先检测工具是否已存在。
  - 已存在时只执行版本检查，不重复安装。
  - Windows 下优先选择已有的 `winget` / `choco` / `scoop`。
  - macOS 下使用 Homebrew。
  - Linux 下尝试 brew、apt-get、dnf、yum、pacman、snap。
  - 如果没有可用安装器，会停止并提示。
  - 安装或版本检查失败时不再跳转到 CLI 页面。
  - 只有安装成功或版本检查成功后才跳转到 GitHub CLI / GitLab CLI 页面。

---

## v0.8.0

- 平台认证能力大幅增强：
  - GitHub / GitLab / Gitee 支持多账号 SSH Host alias 配置。
  - 支持为不同平台、不同账号生成独立 ed25519 SSH key。
  - 支持自动写入 `~/.ssh/config`。
  - 支持尝试执行 `ssh-add`。
  - 支持输出生成的公钥，便于复制到平台 SSH Keys 页面。
  - 支持执行 `ssh -T` 测试平台 SSH 连通性。
  - 支持根据平台和账号生成默认 SSH key 路径。
  - 支持根据 provider 推断 GitHub / GitLab / Gitee 的 SSH host。

- HTTPS remote 配置增强：
  - 支持配置 `credential.helper`。
  - 支持更新当前仓库 remote URL。
  - 支持配置后自动执行 `git ls-remote` 测试 remote 访问。
  - 支持在平台输出区展示 HTTPS 配置与测试结果。

- GitHub / GitLab CLI 页面增强：
  - GitHub 页面新增 CLI 操作入口。
  - GitLab 页面新增 CLI 操作入口。
  - 支持一键安装 `gh` / `glab`。
  - 安装完成后可跳转到对应平台页面。
  - GitHub 支持 repo clone、repo create、PR create、PR checkout、Issue create 等入口。
  - GitLab 支持 repo clone、repo create、MR create、MR checkout、Issue create 等入口。
  - 支持平台认证状态刷新。
  - 支持平台账号状态集中展示。

- 工作区表单增强：
  - 所有目录类字段新增文件夹选择按钮。
  - Clone 父目录不存在时可自动创建。
  - CLI clone 父目录不存在时可自动创建。
  - Worktree / Submodule 相关父目录不存在时可自动创建。
  - 表单字段支持下拉建议。
  - remote、branch、tag、路径等字段增加上下文建议。
  - 输入框改为内容优先的紧凑宽度，避免横向撑满页面。
  - 表单标签右对齐，提升多字段表单对齐效果。

- Diff 展示升级：
  - Diff 标签页改为树形结构。
  - 支持按文件分组展示 diff。
  - 支持 file/header/hunk/具体变更行分层展示。
  - 新增行、删除行、hunk 行、元信息行使用不同颜色高亮。
  - 支持自动调整 diff tree 列宽。

- 提交图交互增强：
  - 有向图普通滚轮不再滚动画布。
  - 仅保留 `Ctrl + 鼠标滚轮` 缩放。
  - 右侧信息树保留独立纵向和横向滚动条。
  - 提交图右键菜单新增 `Create tag here`。
  - 从提交图节点创建 tag 时会检测已有 tag。
  - 如果 tag 已存在，会拒绝重复创建并提示。

- 右侧 ACTIONS 栏增强：
  - 右侧操作区改为分组式结构。
  - ACTIONS 分组支持折叠。
  - 新增 `Custom` 自定义按钮分组。
  - 用户可以新增自定义按钮。
  - 用户可以删除自定义按钮。
  - 自定义按钮可持久化保存。

- 新增自定义按钮 API：
  - 暴露 `MainWindow.register_custom_button(name, commands, persist=True)`。
  - `commands` 支持单行命令。
  - `commands` 支持多行 shell/git 指令。
  - 自定义按钮执行结果会进入底部终端日志。
  - 自定义按钮可选择是否写入持久配置。

- 外部命令异步执行能力增强：
  - 新增 Python 脚本临时写入与异步执行流程。
  - 支持平台认证配置、CLI 操作、SSH 配置等长流程在后台执行。
  - 外部流程完成后可回调刷新平台页面或测试 remote 状态。

- 版本号注意：
  - 目录为 v0.8.0，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.7.0

- 顶部菜单和右侧 ACTIONS 栏深度精简：
  - 删除重复、低频、容易造成视觉拥挤的操作入口。
  - 保留打开、克隆、初始化、add、commit、diff、分支、fetch、pull、push、tag、stash、平台账户等高频操作。
  - 高级/低频功能统一保留在“全部 Git 命令”、Object Inspector 和 Raw Terminal 中。
  - 右侧栏按钮分组更短，视觉负担更低。
  - 完整 Git 能力仍通过高级命令入口兜底。

- 右侧 ACTIONS 分组重排：
  - Repository 分组保留 Open、Clone、Init、Folder、Refresh、Status。
  - Changes 分组保留 Add All、Unstage、Commit、Add+Commit、Diff。
  - History 分组保留 Log、Graph、Show、Checkout、Branch。
  - Branch 分组保留 Refresh、New、Switch、Merge、Rebase、Merge To、Rebase To、Push -u。
  - Remote 分组保留 Fetch、Pull、Push、Remote -v、Add Remote、SSH / Credential。
  - Tags / Stash 分组保留 New Tag、Push Tags、Stash、Stash Pop。
  - Advanced 分组保留 All Commands、Object Inspector、Maintenance。
  - Platform 分组保留 Accounts、Refresh、Providers。

- 顶部模板菜单精简：
  - 文件菜单保留打开仓库、Clone、初始化、打开仓库文件夹、刷新、退出。
  - 更改菜单保留 `git add -A`、Add + Commit、Commit Only、Diff、Diff --staged、Clean。
  - 分支菜单保留新建分支、切换分支、分支图、Merge、Rebase。
  - 远程菜单保留 Fetch --all --prune、Pull --ff-only、Push、Push -u、远程配置。
  - 工具菜单集中承载全部 Git 命令、Object Inspector、平台账户和 Raw Terminal。

- 语言配置补充：
  - `language_config.json` 新增一批顶部菜单、右侧 ACTIONS 和界面控件的翻译条目。
  - 精简后的菜单文案同步进入语言配置。

- 版本号注意：
  - 目录为 v0.7.0，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.9

- 新增多语言与文案配置能力：
  - 新增 `git_terminal/i18n.py`。
  - 新增 `git_terminal/language_config.json`。
  - 新增 `LanguageService` 语言服务。
  - 新增 `LANGUAGE_MODES`，支持中文、英文、默认、中英双语模式。
  - 新增 `make_key()`，可根据默认文案生成稳定语言 key。
  - 新增内置常用中英文文案映射。
  - 支持读取项目内置语言配置和用户级语言配置。
  - 支持写入 `~/.git_terminal/language_config.json`。

- 主窗口接入语言切换：
  - 新增 `t()`，用于按 key 获取当前语言文案。
  - 新增 `_is_translatable_text()`，用于过滤可翻译文本。
  - 新增 `_language_key()`，用于为 UI 文案生成 key。
  - 新增 `_apply_text_property()`，统一处理 window title、action、widget、placeholder、tooltip 等文案属性。
  - 新增 `apply_language()`，可批量刷新菜单、按钮、标签、输入框、Tab 文案。
  - 新增 `change_language_mode()`，切换语言后立即保存配置并刷新界面。

- 设置菜单新增语言入口：
  - 设置菜单新增“语言”子菜单。
  - 支持选择中文、英文、默认、中英双语。
  - 当前语言模式会写入用户配置。
  - 下次启动时读取并恢复语言模式。

- 工作区覆盖表单接入翻译：
  - 覆盖表单标题、提示信息、字段标签使用语言 key。
  - 动态输入流程也可进入语言配置体系。

- README 调整：
  - README 内容被重新整理为基础说明结构。
  - 部分前序版本记录未继续保留在 README 中；本 CHANGELOG 以源码差异和前序 README 记录为准。

- 版本号注意：
  - 目录为 v0.6.9，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.8

- 终端输出编码处理增强：
  - GitRunner 和 ShellCommandWorker 设置 `PYTHONIOENCODING=utf-8`。
  - 设置 `LANG` / `LC_ALL`。
  - 设置 `LESSCHARSET`。
  - Windows shell 命令执行前调用 `chcp 65001`。
  - 降低中文路径、中文输出、Git 输出在终端日志中乱码的概率。

- 终端日志展示升级：
  - 终端日志改为富文本显示。
  - 命令、成功、失败、警告分别使用不同背景和文字颜色。
  - 提升命令执行过程和结果状态的可读性。

- 分支有向图布局优化：
  - 分支有向图页面不再被外层工作区滚动条包裹。
  - 图区域会随侧边栏和底部栏变化自动拉伸。
  - 仅右侧详情树和图视图本身保留滚动。
  - 有向图右侧详情改为可展开/折叠的树形结构。
  - 详情树包含 Commit、Message、Author、Committer、Parents、Changed files 等分组。

- Diff 输出结构化：
  - Diff 输出按 File / Hunk / META / ADD / DEL 分段。
  - 新增 `_format_diff_output()`。
  - 差异内容不再只是原始文本输出，可读性提升。

- 输入表单体验增强：
  - 覆盖输入框高度和 padding 增大。
  - 修复输入字体显示不完整的问题。
  - 需要输入分支、tag、remote 等字段时自动使用可编辑下拉框。
  - 下拉框会填充已有本地分支、远程分支、tag 或 remote 建议。
  - 新增 `_field_suggestions()`。

- 分支操作入口增强：
  - 右侧 ACTIONS > Branch 新增 `Merge To`。
  - 右侧 ACTIONS > Branch 新增 `Rebase To`。
  - 支持选择已有分支作为 merge/rebase 目标。
  - 新增 `merge_to_target_from_menu()`。
  - 新增 `rebase_to_target_from_menu()`。

- Remote / SSH / Credential 能力增强：
  - Remote 区新增 SSH 信息入口。
  - 支持生成 ed25519 SSH key。
  - 支持执行 ssh-add。
  - 支持测试 GitHub SSH。
  - 支持配置 `credential.helper`。
  - 新增 `show_ssh_remote_info()`。
  - 新增 `generate_ssh_key_from_menu()`。
  - 新增 `ssh_add_key_from_menu()`。
  - 新增 `configure_credential_helper()`。

- 用户账户页接入：
  - 左下角用户图标接入 User 页面。
  - 可集中查看和配置 Git `user.name`、`user.email`。
  - 可查看 GitHub / GitLab / Gitee 状态。

- 版本号注意：
  - 目录为 v0.6.8，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.7

- 工作区页面拆分为内部标签页：
  - 新增 `Status` 标签页。
  - 新增 `Diff` 标签页。
  - `Status` 页面使用 Changed / Staged / Untracked 三列列表填满区域。
  - `Diff` 页面单独显示 diff 输出。
  - 工作区内容与差异输出的职责更清晰。

- 提交流程入口补充：
  - 右侧 ACTIONS > Changes 新增 `Commit Only...`。
  - 用于只提交已暂存内容，不自动执行 `git add -A`。
  - 保留 Add All + Commit 流程。
  - 新增 `commit_staged_only()`。

- 有向图节点时间修正：
  - 节点日期改为使用 committer date，即 `%cd`。
  - 不再使用 author date，即 `%ad`。
  - 新提交节点显示实际提交时间。
  - 节点标签显示为简短 `MM-DD HH:mm`。

- 提交详情展示结构化：
  - 有向图右侧详情改为结构化展示。
  - 分块显示 Commit、Message、Author、Committer、Parents、Changed files。
  - 不再直接整段打印 `git show --pretty=fuller`。

- 版本号注意：
  - 目录为 v0.6.7，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.6

- 长文本导致布局撑爆的问题修复：
  - 修复打开仓库后布局被长路径撑爆的问题。
  - 修复 Push URL 过长导致布局被撑宽的问题。
  - 修复 upstream 信息过长导致顶部区域撑宽的问题。
  - 顶部状态栏和提交目标栏改为可裁剪显示。
  - 完整内容通过 tooltip 查看。

- 刷新时布局状态保持：
  - `refresh_all()` 会保存左右栏、工作区、终端的 splitter 尺寸。
  - 刷新后恢复原 splitter 尺寸。
  - 打开仓库、刷新状态、切换分支时不再把布局重置回旧比例。

- 工作区按钮隐藏逻辑加固：
  - 每次刷新后再次执行中央工作区按钮隐藏逻辑。
  - 确保打开仓库、刷新状态、切换分支后仍保持“中央只展示内容，操作在右侧 ACTIONS”的布局。

- 版本号注意：
  - 目录为 v0.6.6，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.5

- 工作区页面比例重新调整：
  - Changed / Staged / Untracked 三个列表在初始工作区中占主要空间。
  - 三个列表等宽展开。
  - Diff 区域缩小为辅助区域。

- 历史页面比例重新调整：
  - 提交历史列表占满主要工作区。
  - 提交详情保留在下方辅助区域。

- 有向图页面布局增强：
  - 固定保留右侧 commit 详情区域。
  - 设置最小详情宽度。
  - 避免提交图把详情区挤没。

- 远程页面比例重新调整：
  - Remote 列表占主要区域。
  - 输出日志作为下方辅助区域。

- 标签 / Stash 页面重构：
  - 标签 / Stash 页面改为内部标签页。
  - Tags 和 Stash 分开展示。

- 平台状态展示增强：
  - 平台页新增登录状态信息。
  - GitHub 自动检测 `gh` 登录状态。
  - GitLab 自动检测 `glab` 登录状态。
  - 未登录时显示登录指引。
  - Gitee 根据 Token 和用户/组织输入状态提示配置步骤。
  - 右侧 ACTIONS 增加 Refresh Status。
  - 新增 `refresh_platform_statuses()`。

- 滚动条视觉收敛：
  - 全局滚动条进一步收窄为 6px。
  - 滚动条改为半透明样式。
  - 减少界面压迫感。

- 版本号注意：
  - 目录为 v0.6.5，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.4

- 启动崩溃修复：
  - 修复 v0.6.3 中 `theme.py` 的 QSS 构建错误。
  - `contextActionButton` QSS 块中的 f-string 大括号完成转义。
  - 解决 `build_qss()` 抛出 `NameError: name 'height' is not defined` 的问题。

- 主题构建检查补充：
  - 新增主题构建检查思路。
  - 使用 PyQt stub 导入 `theme.py`。
  - 对深色/浅色模式执行 `build_qss()`。
  - 对蓝色、紫色、绿色、橙色全部 accent 配色执行 `build_qss()`。
  - 确认不会再因 QSS f-string 大括号导致崩溃。

- 右侧 ACTIONS 绑定复查：
  - 重新检查右侧 ACTIONS 栏所有绑定方法。
  - 确认没有缺失方法引用。

- 版本号注意：
  - 目录为 v0.6.4，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.3

- 启动崩溃修复：
  - 修复 v0.6.2 右侧 ACTIONS 栏引用不存在方法导致的启动崩溃。
  - 将不存在的 `push_selected_tag` 改为现有的 `push_tag`。
  - 将不存在的 `delete_selected_tag` 改为现有的 `delete_tag`。

- 静态引用检查补充：
  - 新增右侧 ACTIONS 构建块的静态引用检查。
  - 确认按钮绑定的方法均存在。

- 布局保持：
  - 保持中央工作区无按钮。
  - 保持右侧操作栏滚动。
  - 保持短按钮一行两个、长按钮一行一个的布局。

- 版本号注意：
  - 目录为 v0.6.3，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.2

- 操作入口迁移到右侧 ACTIONS 栏：
  - 中央工作区不再展示操作按钮。
  - 工作区内保留列表、文本框、输出框、静态提示和表单字段。
  - 操作入口统一移动到右侧 ACTIONS 栏。
  - 中央工作区更专注于内容展示。

- 右侧 ACTIONS 栏重构：
  - 新增 `_build_context_actions()`。
  - 右侧 ACTIONS 栏改为可滚动操作面板。
  - 操作按 Repository / Changes / History / Branch / Remote / Tags / Advanced / Platform 分组。
  - 短按钮一行两个。
  - 长按钮一行一个。
  - 操作项较多时通过滚轮访问，不再挤压中央工作区。

- 工作区按钮清理：
  - 新增 `_strip_workspace_buttons()`。
  - 隐藏中央工作区原有按钮。
  - 所有核心功能仍保留在右侧 ACTIONS 栏和顶部菜单中。

- 滚动条样式调整：
  - 全局滚动条宽度从 12px 收窄为 8px。
  - 水平和垂直滚动条都更轻。

- 版本号注意：
  - 目录为 v0.6.2，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.1

- 左右侧栏压缩能力增强：
  - 左侧栏和右侧栏取消最小宽度限制。
  - `SidePanel` 允许被 splitter 压缩到接近 0。
  - 标题栏、标题文本、头部按钮、导航树也允许压缩。

- 左侧导航树适配长文本：
  - 左侧导航树启用横向滚动条。
  - 仓库路径或长文本不再强制撑宽侧栏。
  - 侧栏变窄后仍可通过横向滚动查看完整文本。

- 侧栏标题和头部按钮尺寸策略调整：
  - 折叠按钮、刷新按钮等固定尺寸控件不再限制侧栏最短宽度。
  - 侧栏更容易被收窄和隐藏。

- 工作区按钮继续压缩：
  - 普通按钮限制最大宽度。
  - 降低按钮最小宽度和高度。
  - 避免按钮在网格中横向铺满导致界面拥挤。

- 工作区列表收缩能力增强：
  - Changed / Staged / Untracked 区块允许收缩。
  - 内部内容通过滚动查看。
  - 避免整体布局被列表最小宽度撑爆。

- 视觉样式继续收敛：
  - 按钮、GroupBox、滚动区边框更轻。
  - 减少大块深色按钮造成的压迫感。

- 版本号注意：
  - 目录为 v0.6.1，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.6.0

- 全局静态文本主题适配补齐：
  - `QLabel` 文本颜色随深色/浅色主题切换。
  - `QGroupBox` 文本、背景和边框随主题切换。
  - `QCheckBox`、`QComboBox`、`QLineEdit`、`QTextEdit` 等控件补充主题样式。
  - Header、滚动区等控件统一适配深色/浅色主题。
  - 降低浅色主题下文字不可读或边框不一致的问题。

- 按钮尺寸策略调整：
  - 普通按钮限制最大宽度。
  - 避免按钮被布局过度横向拉伸。
  - 功能区按钮网格从过密列数收敛为更松散的 3 列布局。
  - 减少高级页面按钮重叠和挤压。
  - 新增 `add_command_grid()` 帮助构建按钮网格。

- 工作区页面统一放入可滚动容器：
  - 新增 `_add_scrollable_tab()`。
  - 拖动终端边界扩大终端时，工作区内容不会被压缩变形。
  - 被遮挡或变窄的内容可通过滚动查看。

- 最近仓库能力新增：
  - 左侧栏新增 `Recent Repositories` 区域。
  - 最近仓库路径保存到 `~/.git_terminal/config.json`。
  - 点击最近仓库即可重新打开。
  - 打开、初始化、clone 成功后会自动记录最近仓库。
  - 最近仓库变更后会刷新左侧导航。
  - 新增 `_default_config_path()`、`_load_config()`、`_save_config()`。
  - 新增 `_load_recent_repositories()`、`_save_recent_repositories()`、`_remember_repository()`。
  - 新增 `open_recent_repository()`。

- 平台页面重构：
  - 平台页面重构为标签页。
  - 新增 GitHub 标签页。
  - 新增 GitLab 标签页。
  - 新增 Gitee 标签页。
  - 新增高级配置标签页。
  - 分别提供认证初始化、仓库列表、PR/MR、Issue、Release、CI、Remote 检查、SSH/credential 等入口。

- 版本号注意：
  - 目录为 v0.6.0，但源码 `__version__` 仍为 `0.4.2`。

---

## v0.5.9

- 打开仓库文件夹入口新增：
  - 新增 `open_repo_folder()`。
  - 顶部文件菜单新增“打开仓库文件夹”。
  - 右侧上下文操作区新增“打开仓库文件夹”。
  - 工作区按钮区新增“Open Folder”入口。
  - Windows 下使用 `os.startfile()` 打开仓库目录。
  - macOS 下使用 `open` 打开仓库目录。
  - Linux/Unix 下使用 `xdg-open` 打开仓库目录。
  - 未打开仓库时提示无法打开。
  - 仓库路径无效时写入错误日志。
  - 打开成功或失败都会更新终端状态并写入日志。

- 添加全部操作语义明确化：
  - 将 `Stage All` 明确改为 `git add -A / 添加全部`。
  - 工作区按钮、菜单和右侧操作入口统一使用 `git add -A` 语义。
  - 避免用户误以为只添加当前选中文件。
  - `git add -A` 会包含新增、修改、删除文件。

- 提交流程改为 Add All + Commit：
  - Commit 按钮改为 `Add All + Commit...`。
  - 默认先执行 `git add -A`。
  - `git add -A` 成功后再执行 `git commit -m <message>`。
  - 新增 `_commit_after_stage()`。
  - 如果 `git add -A` 失败，则停止 commit 并写入终端日志。
  - 防止 add 失败后继续提交造成错误状态。

- 提交表单增强：
  - `Add All + Commit...` 表单包含 commit message 输入。
  - 表单包含“提交前执行 git add -A?”选项。
  - 默认值为 `yes`。
  - 用户输入 `no` 时只提交已经暂存的内容。
  - 支持 `y / yes / 1 / true / 是 / 全部` 等值作为执行 `git add -A` 的确认。
  - 提交信息为空时取消提交并写入日志。

- 测试覆盖增强：
  - `tests/test_runner_workflows.py` 新增多未跟踪文件测试。
  - 覆盖中文路径文件。
  - 覆盖包含空格的文件名。
  - 覆盖多文件一次性 `git add -A`。
  - 覆盖 `git add -A` 后 commit。
  - 验证 commit 后工作区 clean。
  - 确认新增文件、中文路径、空格文件名均可被 add 和 commit 流程覆盖。

- 稳定性保持：
  - 继续保留工作区表单回调异常保护。
  - 继续保留命令完成回调异常保护。
  - commit 后刷新异常不会导致窗口直接崩溃。

---

## v0.5.8

- 初始界面继续收窄：
  - 初始窗口调整为 `1040x620`。
  - 中央 Splitter 默认尺寸调整为 `[400, 140]`。
  - 中央工作区设置最小高度，防止被终端完全挤没。
  - 中央 Splitter 设置为子组件不可被任意折叠。

- 终端输入行位置调整：
  - 终端输入行移动到终端顶部固定显示。
  - 避免终端全屏时输入行被 Windows 任务栏遮挡。
  - 终端输入栏成为终端区域顶部固定操作区。
  - 终端输出区位于输入栏下方。

- 终端拖拽行为修正：
  - 拖拽终端只会增大终端区域。
  - 不再因为轻微向上拖动自动进入全局终端。
  - 全局终端只通过放大/缩小按钮或菜单进入。
  - 拖动到底部区域很小时仍可触发收起。

- 终端状态提示新增：
  - 新增 `set_terminal_state()`。
  - 终端输入行支持状态属性：`neutral`、`running`、`success`、`error`、`warning`。
  - 状态标签默认显示 READY。
  - 命令运行中显示 RUN。
  - 命令成功显示 OK。
  - 命令失败显示 ERR。
  - 命令超时显示 TIMEOUT。
  - 取消或警告状态显示 WARN / CANCEL。
  - 不同状态对应不同背景色。

- 终端主题样式增强：
  - 新增 `QFrame#terminalInputBar[state="running"]` 样式。
  - 新增 `QFrame#terminalInputBar[state="success"]` 样式。
  - 新增 `QFrame#terminalInputBar[state="error"]` 样式。
  - 新增 `QFrame#terminalInputBar[state="warning"]` 样式。
  - 新增 `QLabel#terminalStateLabel` 样式。

- 提交图刷新体验优化：
  - 提交图刷新时保留当前缩放。
  - 提交图刷新时保留当前视图中心。
  - 提交图刷新时保留当前选中节点。
  - 如果原选中节点仍存在，刷新后继续保持选中状态。
  - 节点操作后不会强制 fit 到全局视角。
  - 只有首次加载或无历史图状态时才自动 fitInView。

---

## v0.5.7

- 工作区表单回调异常保护：
  - 修复创建新分支等输入确认后，如果回调内部异常会导致窗口闪退的问题。
  - 工作区表单提交后执行 callback 时增加异常捕获。
  - 回调异常会写入底部日志。
  - 不再直接抛出到 Qt 事件循环导致窗口关闭。

- Git 命令完成回调异常保护：
  - 命令执行完成后调用 callback 时增加异常捕获。
  - 命令回调异常会写入底部日志。
  - 防止刷新、状态更新或后续 UI 操作异常导致闪退。

- 测试覆盖增强：
  - 新增 `tests/test_runner_workflows.py`。
  - 覆盖真实 Git 仓库中的基础工作流。
  - 覆盖 init、config、add、commit、branch、switch、merge、tag、stash、remote、push、worktree、object inspector、count-objects、fsck 等操作。
  - 保留无效工作目录测试，确认 Windows `WinError 267` 类问题不会再直接抛出到 UI 线程。

- 测试数量扩展：
  - README 记录当前测试数从 4 个扩展到 6 个。

---

## v0.5.6

- 仓库目标信息栏新增：
  - 工作区顶部新增 `repo_target_label`。
  - 显示当前提交/分支将推送到哪个 upstream。
  - 显示 Push URL、当前 HEAD、本地仓库路径。
  - 无仓库时显示未打开仓库提示。
  - 未设置 upstream 时明确显示未设置 upstream。
  - 已有 remote 但无 upstream 时显示 `<remote>/(未设置跟踪分支)`。

- 顶部状态栏中文化：
  - 顶部状态栏显示仓库、分支、HEAD、远程、Upstream、Ahead、Behind、Dirty、Mode。
  - 状态信息更适合中文用户直接阅读。
  - 更清晰地展示当前仓库基础参数。

- Push 目标解析增强：
  - 新增 `_build_repo_target_text()`。
  - 根据 upstream 推断 remote 名称。
  - 有 upstream 时读取对应 remote 的 push URL。
  - 无 upstream 但有 remote 时优先使用 origin。
  - 没有 origin 时使用第一个 remote。
  - 使用 `git remote get-url --push <remote>` 获取 Push URL。

- 终端缩小行为修正：
  - “缩小终端”固定恢复到初始底部终端高度。
  - 不再恢复到拖拽前的任意高度。
  - 新增 `_initial_center_sizes`。
  - 新增 `_initial_horizontal_sizes`。
  - 最大化终端恢复时使用初始布局，减少窗口状态混乱。

- 主题样式补充：
  - 新增 `QLabel#RepoTargetLabel` 样式。
  - 提交目标信息栏在深色/浅色主题下保持明显可读。
  - 信息栏使用加粗小字号和底部边框。

---

## v0.5.5

- Windows 无效工作目录崩溃修复：
  - 修复 Windows 下 Git 命令工作目录无效时后台线程直接抛出 `NotADirectoryError / WinError 267` 的问题。
  - `GitRunner.run()` 捕获 `NotADirectoryError`。
  - `GitRunner.run()` 捕获通用 `OSError`。
  - 无效工作目录错误会转成 `GitResult` 返回 UI。
  - 错误会写入底部日志，不再导致 UI 线程崩溃。

- Git 命令 Worker 稳定性增强：
  - `GitCommandWorker` 增加兜底异常捕获。
  - 未预期异常会转为失败的 `GitResult`。
  - 避免 worker 内异常直接中断线程或闪退。

- Clone 目标路径校验：
  - Clone 前校验目标父目录。
  - 目标父目录不存在时取消 Clone 并写入日志。
  - 目标路径不是目录时取消 Clone 并写入日志。
  - 避免把无效路径设置为 Git 工作目录。

- Qt 字体警告过滤：
  - 新增 `_qt_message_handler()`。
  - 过滤 Windows / Anaconda 环境中常见的无害 `QFont::setPointSize: Point size <= 0` 警告。
  - 避免无害 Qt 字体警告污染终端输出。
  - 其他 Qt 消息仍写入 stderr。

- 界面尺寸继续压缩：
  - 初始窗口调整为 `1040x660`。
  - 中央 Splitter 默认尺寸调整为 `[440, 150]`。
  - 水平 Splitter 默认尺寸调整为 `[200, 640, 200]`。
  - 左右侧栏、中央工作区和底部终端初始比例进一步收紧。

---

## v0.5.4

- 工作区覆盖表单主题修复：
  - 修复工作区覆盖输入框中的表单标签文字颜色不随主题变化的问题。
  - 覆盖层内所有 QLabel 改为跟随主题文本色。
  - 深色/浅色模式下表单标签均保持可读。

- Activity Bar 图标主题化：
  - 新增 `_apply_activity_icon_theme()`。
  - `ActivityBar` 新增 `apply_icon_theme()`。
  - `IconButton` 新增 `apply_icon_theme()`。
  - Activity Bar SVG 图标运行时按主题重绘。
  - 深色主题使用浅色描边。
  - 浅色主题使用深色描边。
  - SVG 中的强调色会跟随当前 accent 配色。
  - 主题重绘后的图标写入临时目录缓存。

- 界面尺寸继续压缩：
  - 初始窗口调整为 `1080x700`。
  - 顶部栏高度进一步压缩。
  - Activity Bar 图标尺寸调整为更紧凑的 `48x42`。
  - 顶部搜索/命令中心宽度调整为 260。
  - 侧栏标题栏和顶部栏间距收紧。
  - 中央区域和底部终端默认比例调整为更紧凑布局。

- Splitter 默认尺寸调整：
  - 中央 Splitter 默认尺寸调整为 `[480, 160]`。
  - 水平 Splitter 默认尺寸调整为 `[210, 660, 210]`。
  - 左右侧栏显示/隐藏时使用新的紧凑尺寸恢复。

- 主题样式补充：
  - `workspaceOverlay QLabel` 改为显式使用主题文本色。
  - 工作区覆盖卡片最小宽度和按钮 padding 调整。

---

## v0.5.3

- 输入体验再次调整为工作区覆盖层：
  - 所有输入提示重新改为覆盖中央工作区域。
  - 不再覆盖底部终端。
  - 底部终端保留命令输出和 Raw 输入，避免被交互表单遮挡。
  - 单字段输入入口 `request_terminal_text()` 保留兼容，但内部统一委托到工作区覆盖表单。

- 新增通用工作区表单：
  - 新增 `request_workspace_form()`。
  - 支持一次展示多个输入框。
  - 支持字段 key、label、默认值、是否密码输入。
  - 支持返回多个字段值组成的字典。
  - 新增 `_clear_workspace_prompt_form()` 清理旧表单行。
  - 新增工作区表单字段缓存 `workspace_prompt_fields`。
  - 提交时统一收集表单字段值并回调。
  - 取消时隐藏覆盖层并清理表单。

- 多参数操作改为一次性填写：
  - Clone 改为一次填写远程 URL 和目标路径。
  - 创建 GitHub 仓库改为一次填写仓库名和 visibility。
  - Push -u 改为一次填写 remote 和分支名。
  - Worktree Add 改为一次填写 worktree 路径和 ref。
  - Submodule Add 改为一次填写 URL 和本地路径。
  - Add Remote 改为一次填写 remote 名称和 URL。
  - Set Remote URL 改为一次填写 remote 名称和新 URL。
  - Delete Remote Branch 改为一次填写 remote 和 branch。
  - 创建 Tag 改为一次填写 tag 名称和 message。

- 工作区覆盖层按钮规范化：
  - 左上角固定显示“← 返回”。
  - 底部固定显示“取消 / 确定”。
  - 输入框使用 `workspacePromptInput` 对象名。
  - 返回、取消、确定按钮使用独立对象名，便于主题控制。

- 兼容旧接口：
  - `_submit_terminal_prompt()` 委托到 `_submit_workspace_prompt()`。
  - `_cancel_terminal_prompt()` 委托到 `_cancel_workspace_prompt()`。
  - 旧调用方无需重写即可继续工作。

- 主题样式补充：
  - 新增 `QLineEdit#workspacePromptInput` 样式。
  - 新增 `workspacePromptBackButton`、`workspacePromptCancelButton`、`workspacePromptOkButton` 样式。
  - 工作区覆盖输入框获得 focus 时使用当前 accent 边框。

---

## v0.5.2

- 终端覆盖输入面板修复：
  - 修复终端覆盖输入面板中按钮被全局压缩策略挤没的问题。
  - 返回、取消、确定按钮设置固定高度和最小宽度。
  - 全局控件压缩逻辑排除终端覆盖输入按钮。

- 终端输入覆盖层交互明确化：
  - 左上角固定显示“← 返回”按钮。
  - 底部固定显示“取消 / 确定”按钮。
  - 确定按钮使用强调色。
  - 返回/取消按钮使用普通面板色。
  - 提升输入面板在小窗口下的可点击性。

- 旧工作区覆盖层清理：
  - `request_terminal_text()` 执行前会先清理旧的工作区覆盖层。
  - 避免旧提示层残留导致点击无响应。
  - 输入结束或取消后恢复终端内容区域。
  - 取消后焦点回到 Raw 命令输入框。

- 输入流程统一：
  - commit message、clone URL / 目标路径、remote URL、分支名、tag、worktree、submodule、bisect 等输入走终端覆盖输入逻辑。

- 主题样式补充：
  - 新增 `terminalPromptBackButton`、`terminalPromptCancelButton`、`terminalPromptOkButton` 样式。
  - 终端输入提示按钮在深色/浅色主题下保持可读。

---

## v0.5.1

- 高级 Git 工作流入口扩展：
  - 高级菜单新增 Worktree Add、Worktree Remove。
  - 高级菜单新增 Submodule Add、Submodule Update --init --recursive。
  - 高级菜单新增 LFS Track。
  - 高级菜单新增 Bisect Start、Bisect Good、Bisect Bad、Bisect Reset。
  - 顶部模板菜单同步新增上述高级操作入口。

- 新增 Worktree 操作：
  - 新增 `worktree_add_from_menu()`。
  - 支持输入 worktree 路径。
  - 支持输入分支 / commit / ref。
  - 执行 `git worktree add <path> [ref]`。
  - 新增 `worktree_remove_from_menu()`。
  - 支持输入 worktree 路径并执行 `git worktree remove <path>`。

- 新增 Submodule 操作：
  - 新增 `submodule_add_from_menu()`。
  - 支持输入子模块 URL。
  - 支持输入本地路径。
  - 执行 `git submodule add <url> [path]`。
  - 新增 `git submodule update --init --recursive` 菜单入口。

- 新增 Git LFS 操作：
  - 新增 `lfs_track_from_menu()`。
  - 支持输入匹配模式。
  - 执行 `git lfs track <pattern>`。

- 新增 Bisect 操作：
  - 新增 `bisect_good_from_menu()` 和 `bisect_bad_from_menu()`。
  - 支持输入 good / bad commit 或 ref。
  - 新增 Bisect Start 和 Bisect Reset 菜单入口。
  - 高级页常用命令中新增 `bisect log`。

- 终端输入覆盖层调整：
  - `request_terminal_text()` 改为通过底部终端区域的 `terminal_stack` 切换到输入覆盖层。
  - 输入提示卡片包含左上角返回按钮、标题、提示信息、输入框和确定按钮。
  - 提交/取消后恢复终端内容区域。
  - 取消后把焦点恢复到 Raw 命令输入框。
  - 新增 `terminalPromptOverlay` 和 `terminalPromptCard` 样式。

- 终端拖拽行为调整：
  - 终端拖拽时允许自然增大。
  - 只有拖到极端边界时才触发收起或最大化。
  - 防止轻微拖动导致终端状态突变。

- 视图菜单调整：
  - “放大终端”入口改为“放大/缩小终端”。

---

## v0.5.0

- 样式构建崩溃修复：
  - 修复 `build_qss()` 中 QSS 大括号未转义导致的 `NameError: name 'background' is not defined`。
  - 将工作区覆盖层相关 QSS 的 `{}` 修正为 f-string 安全写法。
  - 修复深色/浅色主题构建时可能因 QSS 字面量被 Python 当作变量解析而崩溃的问题。

- 旧输入组件清理：
  - 清理已迁移掉的 `QInputDialog` 引用。
  - 避免旧弹窗式输入逻辑与工作区覆盖层逻辑混用。

- 静态检查说明补充：
  - README 增加静态检查说明：检查 `connect(self.xxx)` 引用的方法是否存在。
  - 检查主题 QSS 在 dark/light 与全部 accent 配色下能否正常生成。
  - 降低缺失槽函数和 QSS 构建错误再次进入版本的概率。

---

## v0.4.9

- 启动崩溃修复：
  - 新增兼容性 `_submit_terminal_prompt()`。
  - 新增兼容性 `_cancel_terminal_prompt()`。
  - 修复 v0.4.8 启动时 `_submit_terminal_prompt` 方法缺失导致的 AttributeError。

- 旧输入提示残留清理：
  - 底部内嵌输入提示区域已经迁移到工作区覆盖层。
  - 本版本删除旧版底部内嵌输入提示区域的残留连接。
  - 输入提示只保留工作区覆盖层。
  - 保留兼容性空方法，避免旧信号残留再次造成启动崩溃。
  - 当工作区覆盖层可见时，旧方法会转发到工作区覆盖层的提交/取消逻辑。

---

## v0.4.8

- 启动崩溃修复：
  - 新增 `_on_horizontal_splitter_moved()`。
  - 新增 `_on_center_splitter_moved()`。
  - 修复 v0.4.7 启动时因 `_on_horizontal_splitter_moved` / `_on_center_splitter_moved` 方法缺失导致的 AttributeError。

- 拖拽折叠逻辑落地：
  - 拖动左侧栏宽度到 48px 以下时自动隐藏左侧栏。
  - 拖动右侧栏宽度到 48px 以下时自动隐藏右侧栏。
  - 拖动底部终端高度到 72px 以下时自动隐藏底部终端。
  - 拖动中央工作区高度到 48px 以下时自动最大化底部终端。
  - 如果终端已经处于最大化状态，拖拽处理会直接跳过，避免重复状态切换。

- 启动文件补充：
  - 新增无扩展名 `run` 启动文件。
  - 支持 `python run` 启动项目。
  - 保留 `python run.py` 启动方式。

- README 恢复完整内容：
  - v0.4.7 的 README 仅保留了版本摘要。
  - 本版本恢复完整 README 功能说明、安装运行、安全策略、项目结构、设计取舍和常见命令示例。
  - 保留 v0.4.7 的工作区覆盖输入、终端全局覆盖和拖拽折叠说明。

---

## v0.4.7

- 输入交互从底部终端迁移到工作区覆盖层：
  - 新增 `QStackedLayout` 工作区叠层。
  - 新增 `workspace_overlay`。
  - 新增 `workspaceOverlayCard`。
  - 输入提示不再显示在底部终端内部。
  - 所有交互输入统一覆盖中央工作区显示。
  - 覆盖层包含标题、提示信息、输入框、确定按钮和返回按钮。
  - 提交信息、分支名、远程、tag 等输入流程走工作区覆盖层。

- 工作区 Commit 输入优化：
  - 删除工作区常驻 commit message 输入框。
  - 点击 Commit 时才弹出工作区覆盖层输入提交信息。
  - 提交信息为空时取消提交并写入日志。

- 终端全局覆盖能力增强：
  - 视图菜单新增“放大终端”。
  - 底部输入栏的最大化/恢复按钮可切换全局终端与普通布局。
  - 底部终端可覆盖整个中央工作区域。
  - 恢复后回到工作区 + 底部终端布局。

- 拖拽折叠逻辑接入：
  - 水平 Splitter 设置为可折叠。
  - 垂直 Splitter 设置为可折叠。
  - 连接 `_on_horizontal_splitter_moved`。
  - 连接 `_on_center_splitter_moved`。
  - 设计目标是拖动左右侧栏边界到很窄时自动收起侧栏。
  - 设计目标是拖动底部终端边界到很窄时自动收起终端，拖到接近顶部时自动进入全局终端。

- 工作区覆盖层主题新增：
  - 新增 `QFrame#workspaceOverlay` 样式。
  - 新增 `QFrame#workspaceOverlayCard` 样式。
  - 新增 `QLabel#workspacePromptTitle` 样式。
  - 新增 `QLabel#workspacePromptMessage` 样式。
  - 覆盖层使用半透明遮罩和卡片式输入界面。

- 已知问题：
  - 本版本连接了 `_on_horizontal_splitter_moved` 和 `_on_center_splitter_moved`，但方法本身缺失。
  - 该问题导致启动时可能出现 AttributeError。
  - v0.4.8 修复该问题。

---

## v0.4.6

- 底部终端升级为真实命令终端：
  - 底部 Raw 输入框不再只限定 Git 子命令。
  - 用户可以输入任意 shell 命令。
  - 输入 `git ...` 时仍走 Git 安全执行流程，并在完成后刷新仓库状态。
  - 输入非 Git 命令时通过 shell worker 执行。
  - Raw 输入执行后自动清空输入框。

- 新增 Shell 命令执行 Worker：
  - 新增 `ShellCommandWorker`。
  - Windows 下通过 `cmd.exe /c` 执行命令。
  - Unix/macOS 下通过 `/bin/sh -lc` 执行命令。
  - stdout/stderr 统一以 UTF-8 容错解码。
  - shell 命令结果包装为 `GitResult` 返回 UI。
  - shell 命令异常时不会直接抛出到 UI，而是返回失败结果。

- 底部终端最大化能力新增：
  - 新增 `toggle_bottom_maximized()`、`maximize_bottom_panel()`、`restore_bottom_panel()`。
  - 底部输入栏新增最大化按钮。
  - 终端可展开占领整个中央工作区域。
  - 终端可恢复为“工作区 + 底部终端”的普通布局。
  - 隐藏底部终端时，如果当前处于最大化状态，会先恢复普通布局。

- 底部终端布局调整：
  - 底部栏移除 “TERMINAL” 标题文字。
  - 日志区域直接占用底部空间。
  - 折叠和最大化控制移动到底部输入栏右侧。
  - 终端提示符从 `git >` 调整为 `$ >`。
  - Raw 输入 placeholder 改为支持任意命令，例如 `git status -sb / python --version / dir / ls`。

- 内联输入提示新增：
  - 原先依赖 `QInputDialog` 的输入操作改为底部终端上方的内联提示区。
  - 创建 GitHub 远程仓库、设置 user.name/user.email、创建/切换分支、merge、rebase、cherry-pick、revert、reset --hard、push -u、创建 tag、删除远程分支等操作改为内联输入。

- 高风险命令确认流程调整：
  - 高风险 Git 命令确认从弹窗式确认转为内联输入确认。
  - 界面会显示风险标题、风险原因、即将执行的真实命令和确认词。
  - 用户输入确认词后才执行命令。
  - 输入不匹配时取消执行并写入日志。

- Clone 流程调整：
  - Clone 改为先输入远程 URL，再输入目标父目录。
  - Clone 执行前会把目标父目录设置为工作目录。
  - Clone 完成后继续执行后续打开/刷新逻辑。

---

## v0.4.5

- 多页面按钮布局统一网格化：
  - 提交历史页、分支页、远程页、标签/Stash 页、冲突页、高级页、平台页按钮改为网格布局。
  - 避免一行按钮过多导致工作区横向溢出。

- 折叠/展开入口恢复：
  - 保留顶部栏左侧栏、右侧栏、底部栏开关。
  - 保留左侧栏标题按钮、右侧栏标题按钮、底部终端标题按钮。
  - 修复模板式折叠/展开入口缺失的问题。

- 提交图布局改为横向：
  - 提交图从纵向布局调整为 Mermaid-like 横向布局。
  - 旧提交在左，新提交在右。
  - 箭头以直线方式明确指向新提交。
  - lane 纵向堆叠，时间横向流动。
  - 分支图更接近 LR 有向图风格。

- 提交图主题适配：
  - 新增 `CommitGraphView.set_theme()`。
  - 深色主题背景为 `#1e1e1e`。
  - 浅色主题背景为 `#ffffff`。
  - 节点标签、背景、边框颜色跟随深色/浅色主题调整。
  - 主题切换后自动刷新分支图。

- 设置菜单弹出位置修正：
  - 左下角设置菜单弹出位置改为按程序窗口底部对齐。
  - 避免菜单按屏幕底部对齐导致位置异常。

---

## v0.4.4

- 窗口尺寸压缩：
  - 初始窗口从约 `1500x930` 调整为 `1180x760`。
  - 顶部命令栏高度压缩。
  - 搜索/命令中心宽度压缩。
  - 左右侧栏和底部终端默认尺寸收紧，减少首次启动时界面过大的问题。

- 中央主标签栏隐藏：
  - 中央 `QTabWidget` 的标签栏被隐藏。
  - 主功能入口移动到左侧 Activity Bar。
  - Activity Bar 承担工作区、历史、分支、远程、标签/Stash、高级、平台、终端、帮助等入口。

- Activity Bar 功能入口扩展：
  - 新增工作区、历史、分支、远程、标签/Stash、高级、平台等主功能入口。
  - 点击对应入口时会切换中央页并触发相应刷新逻辑。

- 工作区按钮布局压缩：
  - 工作区按钮行从横向单行改为 2 行网格布局。
  - 避免按钮过多导致中央区域被横向撑爆。
  - 降低小窗口下按钮拥挤问题。

- 提交有向图方向修正：
  - Git log 原始顺序为 newest → oldest，本版本绘制时反转为 oldest → newest。
  - 图中箭头明确表示旧提交 → 新提交。
  - 提交图曲线改为更明显的强 S 曲线。
  - 垂直父子关系也会强制弯折，避免边线难以识别。
  - 提交图 layout 简化为稳定 lane：第一个子提交保留父提交 lane，后续子提交开启新 lane。

---

## v0.4.3

- 顶部 UI 修复：
  - 隐藏原生 `QMenuBar`。
  - 清理原生菜单栏可能留下的空白占位行。
  - 顶部只保留自定义模板菜单栏，避免出现两套菜单或顶部空行。

- 底部终端修复：
  - 删除底部面板中无实际作用的多标签页。
  - 底部栏改为终端专用区域。
  - 去除 PROBLEMS / OUTPUT / DEBUG CONSOLE 等占位底部页。
  - 恢复底部终端的折叠按钮入口。

- Activity Bar 图标升级：
  - 新增多枚自绘 SVG 图标。
  - Activity Bar 从 emoji/文字图标切换为项目内置 SVG 图标。
  - 图标作为布局/导航入口，不再与中央工作区标签重复。
  - 工作区入口点击后会切换到工作区并刷新状态。

- 顶部模板菜单补强：
  - 新增“标签”菜单入口。
  - 新增“平台”菜单入口。
  - 新增“视图”菜单入口。
  - 高级菜单新增 cherry-pick、revert、reset --hard 等操作。
  - 高级菜单新增 worktree、submodule、LFS 相关入口。
  - 平台菜单新增 GitHub / GitLab 相关操作入口。
  - 视图菜单支持显示/隐藏左侧栏、右侧栏、底部终端，并可切换工作区、历史、分支、远程页。

- 高级 Git 操作新增：
  - 新增 `cherry_pick_from_menu()`。
  - 新增 `revert_from_menu()`。
  - 新增 `reset_hard_from_menu()`。
  - 支持通过菜单输入 commit hash / ref 后执行对应 Git 操作。

- 提交图视觉修正：
  - 提交图背景改为与主模板一致的深色背景。
  - 提交图边线改为 S 形曲线。
  - 提交图箭头方向调整为 parent → child。
  - 分支标签通过连线指向提交节点。
  - 节点仍保留日期短标签，详细信息继续在侧边栏显示。
  - 新增 `_branch_label()`，用于从 refs 中提取适合显示的分支/标签名。
  - 分支/标签名过长时自动截断。

- 测试恢复：
  - 恢复 `tests/test_safety.py`。

---

## v0.4.2

- 顶部模板菜单可见化：
  - 新增 `_build_visible_top_menus()`。
  - 将完整 Git 菜单直接渲染到自定义顶部命令栏中。
  - 解决原生 `QMenuBar` 在某些系统或主题下不明显的问题。
  - 顶部模板菜单新增“文件、仓库、更改、分支、远程、高级”等入口。
  - 顶部模板菜单可直接执行打开仓库、初始化仓库、Clone、创建 GitHub 仓库、刷新、Status、Git Config、Stage、Commit、Diff、分支、远程、Pull、Push、fsck、gc 等操作。

- 顶部栏组件增强：
  - `TopCommandBar` 新增 `topMenuHost`。
  - `TopCommandBar` 新增 `menu_layout`，用于承载模板内菜单按钮。
  - 顶部菜单按钮使用 `QToolButton` 和弹出式菜单。

- 主题样式补充：
  - 新增 `QWidget#topMenuHost` 样式。
  - 新增 `QToolButton#topMenuButton` 样式。
  - 顶部菜单按钮支持 hover 状态。
  - 隐藏菜单按钮默认 indicator，保持模板顶部栏简洁。

- 测试目录变化：
  - 本版本移除了 `tests/test_safety.py`。
  - 该安全测试文件在 v0.4.3 中恢复。

---

## v0.4.1

- 顶层菜单体系补强：
  - 新增“文件”菜单，支持打开仓库、初始化仓库、Clone、创建 GitHub 远程仓库、刷新全部、退出程序。
  - 新增“仓库”菜单，支持 status、Raw Git 终端、Git 配置、设置 user.name/user.email、刷新仓库状态。
  - 新增“更改”菜单，支持 Stage All、Unstage All、Commit、Amend、Diff、Diff --staged、Clean -fd。
  - 新增“分支”菜单，支持创建分支、切换分支、分支列表、Fetch 后刷新图、Merge、Rebase、Reflog。
  - 新增“远程”菜单，支持 Remote -v、添加 Remote、设置 Remote URL、Fetch、Pull、Push、Push -u、Push --tags、删除远程分支。
  - 新增“标签/Stash”菜单，支持创建标签、Push --tags、Stash Push -u、Stash List、Stash Pop Selected。
  - 新增“高级”菜单，支持全部 Git 命令、Object Inspector、fsck、gc、count-objects、复制最后命令。
  - 新增“视图”菜单，支持显示/隐藏侧栏和底部栏、快速切换工作区/历史/分支/远程页。
  - 新增“平台”菜单，支持 GitHub auth status、GitHub repo list、GitHub create repo、GitLab auth status。
  - 新增“帮助”菜单，支持快捷键、原生命令示例、关于 Git Terminal。

- 设置与外观能力增强：
  - 新增 `show_settings_menu()`。
  - 左下角设置按钮可打开设置菜单。
  - 设置菜单支持深色/浅色主题切换。
  - 设置菜单支持蓝色、紫色、绿色、橙色 accent 配色切换。
  - 设置菜单支持恢复左侧栏、右侧栏、底部栏显示。
  - 设置菜单提供“关于 Git Terminal”入口。

- 快捷 Git 操作新增：
  - 新增从菜单创建 GitHub 远程仓库。
  - 新增设置全局 `user.name`。
  - 新增设置全局 `user.email`。
  - 新增从菜单创建分支、切换分支、merge、rebase、`push -u`、创建 annotated tag。

- Activity Bar 定位调整：
  - Activity Bar 不再重复中央工作台标签功能。
  - Activity Bar 改为布局/导航工具入口，包括 Explorer、Command Search、Raw Git Terminal、Context Side Bar、Help / Shortcuts。

---

## v0.4.0

- 主界面从 `QMainWindow + QDockWidget` 结构继续演进为自定义 VS Code 风格 Shell：
  - 新增 `git_terminal/ui/vscode_shell.py`。
  - 新增 `TopCommandBar` 顶部命令栏。
  - 新增 `ActivityBar` 左侧活动栏。
  - 新增 `SidePanel` 左右侧边栏组件。
  - 新增 `BottomPanel` 底部面板组件。
  - 用自定义组件替代上一版 Dock 面板结构，形成“顶部命令栏 + 左侧 Activity Bar + 左侧导航栏 + 中央工作区 + 右侧上下文栏 + 底部终端面板”的整体布局。

- 顶部命令中心能力新增：
  - 新增顶部 Command Center 输入框。
  - 支持输入 `status` / `git status` 快速执行状态命令。
  - 支持输入 `branch` / `branches` 快速切换到分支页。
  - 支持输入 `remote` / `remotes` 快速切换到远程页。
  - 支持输入 `git ...` 直接转到底部 Raw Git Terminal 执行。
  - 非 `git` 前缀命令会补全为 `:git ...` 后执行。

- Activity Bar 交互新增：
  - Activity Bar 提供工作区、搜索、终端、上下文栏、帮助等入口。
  - 支持点击 Activity Bar 按钮切换中央功能页。
  - 支持通过顶部按钮显示/隐藏左侧栏、右侧栏和底部面板。
  - 支持左侧栏标题按钮快速打开仓库、刷新仓库和查看帮助。

- 底部面板扩展：
  - 底部面板初始包含 TERMINAL、PROBLEMS、OUTPUT、DEBUG CONSOLE 等标签页。
  - TERMINAL 保留命令日志与 Raw Git 输入。
  - PROBLEMS / OUTPUT / DEBUG CONSOLE 提供占位信息和扩展入口。

- 提交图交互增强：
  - `CommitGraphView` 新增 `commitHovered` 信号。
  - 鼠标悬浮提交节点时可触发提交详情显示。
  - 分支图节点标签更紧凑，节点旁只保留日期短标签，详细信息通过侧边详情面板展示。

- 主题样式适配：
  - `theme.py` 大幅调整，新增 VS Code Shell 相关样式。
  - 增加顶部命令栏、活动栏、侧边栏、底部面板、终端输入栏等控件样式。
  - 整体视觉从 DockWidget 风格切换到更统一的编辑器式布局。

---

## v0.3.0

- 主界面布局重构：
  - 从普通 Splitter 布局调整为 `QMainWindow + QDockWidget` 布局。
  - 左侧导航、右侧上下文、底部终端改为可停靠 Dock 面板。
  - Dock 支持移动、关闭、浮动。
  - 中央区域保留状态栏和主标签页，更接近桌面 IDE 的工作方式。

- 新增 Activity Bar：
  - 新增左侧垂直 Activity Bar。
  - 提供 `NAV`、`CTX`、`TERM` 三个入口。
  - 支持快速显示/隐藏左侧导航、右侧上下文和底部终端。
  - 底部终端隐藏后可通过 Activity Bar 恢复。

- 面板标题栏优化：
  - 新增自定义 Dock 标题栏。
  - 标题栏包含大写标题和关闭按钮。
  - 左右栏、底部栏的显示/隐藏逻辑改为 Dock 可见性控制。

- 编码稳定性修复：
  - `git help -a` 调用增加 `encoding="utf-8"` 和 `errors="replace"`。
  - GitRunner 执行 subprocess 时增加 UTF-8 解码容错。
  - `GitResult` 增加 `__post_init__`，统一将 stdout/stderr 规范化为字符串。
  - 避免 Windows 或旧区域设置下 stdout/stderr 解码失败导致 UI 崩溃。
  - 避免 stdout/stderr 为 `None` 时后续 `.splitlines()` 等 UI 逻辑出错。

- 样式更新：
  - 新增 Activity Bar、DockWidget、DockTitleBar、DockTitleButton 等样式。
  - 进一步优化底部终端、侧边栏和标题栏视觉一致性。
  - 主题中增加更适合终端显示的字体配置。

- 项目文件清理：
  - 移除了 v0.2.1 中额外引入的 `tests/qrcode-terminal/` 相关 JavaScript 示例、vendor 文件和 node_modules 静态文件。
  - 项目文件结构重新回到纯 Python/PyQt 项目范围。

---

## v0.2.1

- 提交图视觉增强：
  - 提交节点由普通椭圆项升级为自绘 `QGraphicsObject`。
  - 节点增加渐变、描边、阴影和高亮效果。
  - 节点 hover 和选中状态增加动画。
  - 提交图增加彩色 lane。
  - 增加 lane 背景色块，提升多分支关系的可读性。
  - 提交边线改为更明显的彩色曲线。
  - 提交标签改为富文本样式，支持 hash、refs、message 分段高亮。
  - 标签增加背景胶囊效果，增强深色背景下的可读性。

- 提交图交互保持增强：
  - 保留单击选中 commit。
  - 保留双击 checkout commit。
  - 保留右键上下文菜单。
  - 保留 Ctrl + 鼠标滚轮缩放。
  - 选中状态通过节点动画和 halo 效果更清晰地反馈。

- 底部终端/日志栏美化：
  - 底部栏标题改为 `TERMINAL / LOG`。
  - 新增 Clear、Copy、Run 等快捷按钮。
  - 底部栏增加独立 header 区域。
  - 折叠/展开按钮统一改为 `QToolButton`。
  - 左右侧栏和底部栏的折叠按钮符号改为更紧凑的视觉样式。

- 主题样式更新：
  - 新增 BottomPanel、BottomPanelHeader、GhostButton、PaneToggleButton 等样式。
  - 优化按钮渐变、透明按钮、底部栏边框和面板圆角。
  - 提升整体界面一致性。

- 项目文件变化：
  - 新增 `tests/qrcode-terminal/` 目录及其 JavaScript 示例、vendor 文件和 node_modules 静态文件。
  - 这些文件未形成 Python/PyQt 主程序功能的一部分，并在 v0.3.0 中被移除。

---

## v0.2.0

- 新增图形化提交关系视图：
  - 新增 `git_terminal/ui/commit_graph.py`。
  - 新增 `GraphCommit` 数据结构。
  - 新增 `CommitGraphView` 图形视图。
  - 支持将 Git log 结果渲染为提交节点和父子边关系。
  - 支持空历史提示。

- 分支页增强：
  - 分支页新增“列表”和“有向图”两个标签页。
  - 新增“刷新图”按钮。
  - 新增“适应视图”按钮。
  - 新增提交图说明提示：悬浮节点看信息，单击看详情，双击 checkout，右键更多操作，Ctrl + 滚轮缩放。
  - 新增提交图详情区域，单击节点后显示 commit 详情。

- 提交图数据来源增强：
  - 使用 `git log --all --topo-order --parents` 获取提交关系。
  - 使用格式化 log 输出解析 commit hash、parents、short hash、date、author、refs、message。
  - 支持 merge commit 的多 parent 关系展示。

- 提交图交互新增：
  - 单击节点查看 commit 详情。
  - 双击节点 checkout 到指定 commit。
  - 右键节点支持 checkout、创建分支、cherry-pick、revert、reset --hard、diff、复制 hash、cat-file 等操作。
  - 支持从图节点创建分支。
  - 支持提交图缩放和适应视图。

- 界面紧凑化：
  - 新增 `_compact_ui_controls()`，统一优化按钮、输入框、下拉框、树控件等组件的尺寸策略。
  - 降低复杂界面在较小窗口下的拥挤程度。

- 主题适配：
  - 主题中新增 `branch_graph_detail` 相关样式。
  - 提交图详情区域与整体深色主题保持一致。

---

## v0.1.2

- 主布局调整：
  - 主界面改为 `左侧栏 | 中央工作区 + 底部日志栏 | 右侧栏` 的布局。
  - 底部命令/日志栏放入中央垂直 Splitter。
  - 左侧栏和右侧栏可直接延伸到底部，界面结构更接近 IDE。
  - 去除左右侧栏固定最大宽度，提升窗口拉伸时的适配能力。
  - 主界面、左侧栏、右侧栏和底部日志栏均可通过 Splitter 自由调整尺寸。

- 新增面板折叠能力：
  - 左侧导航栏新增收起/展开按钮。
  - 右侧上下文操作栏新增收起/展开按钮。
  - 底部命令/日志栏新增收起/展开按钮。
  - 折叠时会记录上一次宽度/高度，展开后尽量恢复原尺寸。
  - 新增统一面板标题栏组件。

- 新增外观菜单：
  - 新增“外观”菜单。
  - 支持深色模式和浅色模式切换。
  - 支持蓝色、紫色、绿色、橙色四种配色。
  - 当前主题和配色会即时应用到主窗口。

- 主题系统升级：
  - `theme.py` 从固定深色 QSS 扩展为可生成动态 QSS 的主题构建函数。
  - 主题支持 mode 和 accent 参数。
  - 多个 UI 区域新增对象名，便于精确应用样式。
  - 增加 PaneHeader、PaneTitle、CollapseButton、LeftPane、RightPane 等样式支持。

- 应用图标新增：
  - 新增 `git_terminal/assets/git_terminal_icon.svg`。
  - 主窗口启动时加载 SVG 程序图标。

- README 更新：
  - 新增 v0.1.2 布局与外观更新说明。
  - 保留 v0.1.1 修复与美化说明。

---

## v0.1.1

- 修复后台线程生命周期问题：
  - 修复 Windows/PyQt 下后台命令完成后访问已删除 `QThread` 可能导致的 `RuntimeError: wrapped C/C++ object of type QThread has been deleted`。
  - 命令运行期间保留 thread 和 worker 的 Python 引用。
  - 新增 `_cleanup_thread()`，在线程结束后按对象身份清理引用。
  - 避免在 Qt 对象已进入删除流程后继续调用 `thread.isRunning()`。

- 新增统一深色主题：
  - 新增 `git_terminal/ui/theme.py`。
  - 新增 `apply_theme()`，统一应用应用级 QSS。
  - 优化主窗口、菜单、工具栏、按钮、输入框、列表、树、表格、Tab、Splitter、滚动条等样式。
  - 顶部状态栏新增 `TopStatusLabel` 对象名，用于主题样式精确控制。

- 输出区域视觉优化：
  - diff 输出、commit detail、命令日志、冲突预览、平台输出、高级命令输出等区域统一使用系统等宽字体。
  - 提升命令输出、diff 和日志内容的可读性。

- README 更新：
  - 新增 v0.1.1 修复与美化说明。

---

## v0.1.0

- 初始版本发布：
  - 基于 PyQt6 实现桌面 Git 管理终端。
  - 项目定位为本机 Git CLI 的可视化操作界面，不重新实现 Git。
  - 所有核心 Git 操作通过本机 `git` 可执行文件执行。
  - 执行前展示真实命令，执行后记录 stdout/stderr 输出。
  - 支持命令透明、安全确认、常用功能图形化和高级功能参数化。

- 环境检测：
  - 启动后检测 `git --version`。
  - 检测 `user.name`、`user.email`、`init.defaultBranch`、`credential.helper`。
  - 检测 SSH 可用性。
  - 检测 GitHub CLI `gh`。

- 仓库生命周期管理：
  - 支持打开本地仓库。
  - 支持非 Git 目录引导执行 `git init`。
  - 支持初始化仓库。
  - 支持克隆远程仓库。
  - 顶部状态栏展示仓库、分支、HEAD、upstream、ahead/behind、dirty 和 Git 状态机模式。

- 工作区、暂存区和提交：
  - 支持 `git status --porcelain` 状态解析。
  - 提供 Changed、Staged、Untracked 三栏视图。
  - 支持 Stage selected、Stage all、Unstage selected、Unstage all。
  - 支持 Restore selected。
  - 支持 Clean untracked，并对高风险操作进行二次确认。
  - 支持 `git diff` 和 `git diff --staged`。
  - 支持 `git commit -m`。
  - 支持 `git commit --amend --no-edit`。

- 提交历史和提交详情：
  - 支持 `git log --graph --decorate --all`。
  - 提供提交 graph 文本视图。
  - 支持单击 commit 查看详情。
  - 支持 `git show --stat --patch --pretty=fuller`。
  - commit 右键菜单支持 checkout、create branch、cherry-pick、revert、reset hard、diff、copy hash、cat-file。

- 分支管理：
  - 支持 `git branch -a -vv`。
  - 支持创建分支、切换分支、删除分支。
  - 支持 merge into current。
  - 支持 rebase onto branch。
  - 支持 push -u。
  - 支持 branch 右键菜单。

- Remote 管理：
  - 支持 `git remote -v`。
  - 支持 add remote、remove remote、set-url。
  - 支持 fetch、fetch --all --prune、push。
  - 支持删除远程分支，并进行高风险二次确认。

- Tag 和 Stash：
  - 支持 tag list。
  - 支持创建 annotated tag。
  - 支持删除 tag。
  - 支持 push tag。
  - 支持 push --tags。
  - 支持 stash list、stash push -u、stash apply、stash pop、stash drop、stash clear。

- 冲突解决：
  - 识别 `UU`、`AA`、`DU`、`UD` 等常见冲突状态。
  - 支持 use ours、use theirs、mark resolved。
  - 支持 merge continue / abort。
  - 支持 rebase continue / abort / skip。
  - 支持 cherry-pick continue / abort / skip。

- 专家模式：
  - 提供常用底层对象和维护命令入口。
  - 包含 `cat-file`、`hash-object`、`ls-tree`、`ls-files`、`rev-parse`、`show-ref`、`for-each-ref`、`write-tree`、`commit-tree`、`count-objects`、`fsck`、`gc`、`reflog`、`archive`、`bundle`、`maintenance`、`submodule`、`lfs`、`config` 等命令。

- 全部 Git 命令覆盖：
  - 内置常用 Git 命令目录。
  - 通过 `git help -a` 动态发现本机 Git 支持的命令。
  - 高级参数面板支持命令下拉框、常用选项 checkbox、参数输入框。
  - 底部 Raw Git Terminal 支持直接执行原生命令。

- 平台增强入口：
  - GitHub CLI 支持 `gh auth status`、`gh repo list`、`gh pr list`、`gh issue list`、`gh release list`。
  - GitLab CLI 支持 `glab auth status`、`glab mr list`、`glab issue list`。
  - Gitee 提供 token 查询仓库示例。
  - README 中明确说明生产环境 token 应接入系统 Keychain、Windows Credential Manager 或 Linux Secret Service。

- 安全策略：
  - 对 `reset --hard`、`clean -f/-fd`、`branch -D`、`push --force`、`push --force-with-lease`、`push --delete`、`update-ref`、`filter-branch`、`filter-repo`、`tag -f/-d`、`reflog expire`、`prune`、`gc --prune=now` 等高风险命令进行确认。
  - 新增 `core/safety.py` 风险识别逻辑。
  - 新增 `tests/test_safety.py` 测试安全分类行为。
