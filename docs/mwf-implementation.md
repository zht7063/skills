# MWF 本地 CLI/MCP 实施记录

> Historical implementation/review snapshot. The Python MWF runtime was retired on 2026-09-09; current setup and compatibility behavior are documented in [the runtime guide](../packages/mwf/README.md). Earlier Python test counts below describe the pre-retirement state.


日期：2026-09-09。实现位置：`packages/mwf/`。用户批准的设计依据见 [改造评估](mwf-local-mcp-review.md)。

## 已实现

- TypeScript Core 与独立 CLI，发布为含编译产物、模板、薄适配器和捆绑的运行依赖 的本地 npm 包；无需 Python 或 TS 运行加载器。
- 15 个 stdio MCP 工具：初始化、状态、诊断、bootstrap、召回、记录、候选、更新/晋升、交接、收件箱、查重、合并、索引重建、迁移、遗忘。
- 显式 `setup --root ... --harness codex,pi --git-mode track|ignore`：校验配置，安装项目启动规则、适配器与客户端连接，然后实际握手和读取记忆。
- Pi 自动安装固定 `pi-mcp-adapter@2.32.1`，核验本地安装版本；薄扩展在首轮 agent loop 前通过 CLI 调用同一 Core 注入记忆，在恢复/压缩/树切换后重新加载。
- Codex 项目配置及轻量 `memory-with-files`、`mwf-init`、`mwf-status` Skill；实际新会话验证了自动 bootstrap。
- 项目 `.mwf` schema 1 和 Markdown 事实源保持兼容。旧 Python writer 对已接入 TS 的项目拒写；旧数据只读召回无需迁移。
- `detach` 预览/恢复自身适配文件，保留项目记忆、AGENTS 降级规则、Git 忽略保护与共享 Pi 插件。

## 可靠性与边界

新操作使用项目级跨进程锁。实现采用 Node 内置 SQLite 的操作系统文件锁，仅在 `.mwf/local/runtime.sqlite` 放运行协调文件，**不将记忆、索引或业务状态迁入数据库**。锁文件不能在进程运行时被删除或替换。

文件变更先持久化前向恢复日志，再对各文件原子替换；下一次调用恢复未完成事务。旧内容哈希和目标哈希均不匹配时，保留现场并报冲突。恢复也清理原子写入中断遗留的临时文件，避免遗忘后留下隐藏副本。新 CLI/MCP 的读取同样参与锁；外部编辑器不具备多文件事务视图。

幂等请求回执持久化在本地忽略目录。遗忘清除 MWF 迁移备份并把引用该记忆的历史回执改成不含旧标题/路径的墓碑；重试旧新增请求不会重新创建已遗忘记录。

首版保证单机本地文件系统。旧版脚本副本无法被远程禁用，采用新运行时前应停止旧会话。不同 Git 分支合并可能产生 ID 冲突，需由 doctor 检测后显式解决；没有自动 Git 同步。遗忘不自动清理其他记录中的引用、外部备份或 Git 历史。

setup 的文件阶段有事务恢复；Pi 依赖安装作为独立阶段，后续失败时保留已安装依赖供重试。受管文件冲突会拒绝覆盖，错误会说明已安装但未完成验证的状态。更换 Node/CLI 安装路径后重跑 setup。

## 验证证据

| 验证 | 结果 |
|---|---|
| TypeScript/Core/CLI/MCP 自动测试 | 22 项通过 |
| 并发写入 | 12 个独立进程，不同标题，ID 唯一且索引完整 |
| 中断恢复 | SIGKILL 写进程后锁释放；下一次调用恢复并重放原结果 |
| 提交阶段故障 | prepared、每个写入边界、清理前中断均恢复一致状态 |
| 外部改动/路径边界 | 恢复拒绝覆盖第三方修改；拒绝符号链接越界 |
| 旧实现兼容 | Python 生成文件，TS 召回分数、理由与 incident 边界一致 |
| 原 Python 测试 | MWF 10 项通过；仓库安装工具 7 项通过；两项 Skill 结构校验通过 |
| 真实 stdio | tools/list、初始化、写入、bootstrap、错误项目根拒绝 |
| 实际 npm tarball | 临时目录、空 npm 缓存离线安装，空 PATH、不依赖源码/Python，setup/写读/doctor 通过 |
| Pi 0.83.0 + 插件 2.32.1 | 使用真实 loader/ExtensionRunner；15 个直接工具可调用；首轮注入、后续去重、恢复注入通过 |
| Codex CLI 0.153.4 新会话 | 隔离配置/临时项目，未在用户提示中点名工具；实际调用 mwf_bootstrap，并召回预置 crimson-moon-731 约定 |

Codex 一次成功的新会话是行为验证证据，不等于未来所有模型/客户端都必然遵循启动规则。Pi 验收使用真实扩展运行器，无模型请求；Codex 验收使用一次实际只读模型会话。用户现有全局配置没有被修改。

## 运行与复现

安装、命令、迁移及恢复说明见 [运行指南](../packages/mwf/README.md)。常规验证：

```sh
npm ci --prefix packages/mwf
npm test --prefix packages/mwf
npm run test:package --prefix packages/mwf
node --experimental-strip-types scripts/validate-all.ts --tests
npm run test:tools
```

Pi 隔离验收：先对临时项目运行 `setup --harness pi`，设置临时 `PI_CODING_AGENT_DIR`，然后：

```sh
node --experimental-strip-types packages/mwf/scripts/check-pi.ts /absolute/test-project /absolute/pi-package-directory
```

本次交付是本地实现和可安装包，尚未发布 npm，也未将 MWF 接入用户的真实业务项目。
