# MWF 本地 MCP 改造评估

日期：2026-09-09。评估输入：用户提供的《MWF：从 Skill 改造为本地 MCP 的讨论结论》、当前仓库实现、官方文档与本机 Pi 文档。本文记录已讨论的设计依据；实现和验收结果见 [实施记录](mwf-implementation.md)。

## 结论

采用本地 Core + CLI + stdio MCP + 轻量 Harness Adapter。项目内 `.mwf` Markdown 协议继续作为事实源。根据用户补充的安装与启动痛点，建议将 TypeScript + npm 作为目标实现候选，先以安装和启动闭环验证价值，再迁移全部操作；不引入全局 SQLite 或 Git 自动同步。

可靠性的来源是可测试的 Core、稳定安装、明确项目边界、并发保护、恢复机制和运行诊断。MCP 提供结构化调用入口，但不保证模型主动召回和记录记忆。

## 仓库状态

已按用户要求执行 `git pull --ff-only origin main`。本地 main 与 origin/main 均为 ad9a4dfc7df4b54c2e8a7095f3aa2f202f99d316，领先/落后为 0/0。本文为本地新增评估文档，尚未提交推送。

## 对讨论文档的修正

| 文档观点 | 评估与建议 |
|---|---|
| 本地 stdio MCP 不需要 VPS | 成立。客户端启动子进程；无需公网服务。 |
| Core、CLI、MCP、Adapter 分层 | 成立。现有 CLI 已实现大量 Core 能力，应提取复用。 |
| npm + TypeScript | 可选的分发与技术方案，不是 MCP 要求。TS 可以统一运行时、分发与 Pi 适配工具链；建议以实际安装闭环和行为对照验证重写收益。 |
| 全局 SQLite 保存记忆 | 不适合作为当前项目记忆的直接替代。保留项目 `.mwf` 为事实源；全局目录仅用于运行配置、日志、可重建缓存。SQLite 可延后用于索引，避免双事实源。 |
| Pi 与 Codex 直接连接同一 MCP | Codex 支持 stdio；本机 Pi README 明确不内置 MCP，需要扩展桥接或通过 CLI 访问。 |
| Skill 仅保留快捷入口 | 还必须保留何时召回、何时记录、候选与冲突处置等语义策略，并维护 AGENTS 启动块。 |
| init/status/sync/update 工具 | 不应照搬名称。现有核心是 recall/add/propose/process-inbox/doctor 等；sync 和 update 的边界必须先定义。 |
| 整个系统完全离线 | 本地文件记忆操作可离线；首次安装和在线模型推理可能需要网络。 |
| 安装一次即可使用 | 运行包可共享；各 Harness 的注册和适配仍需安装流程自动处理并检查。 |

## 现有实现依据

- `skills/memory-with-files/scripts/mwf.py` 已包含初始化、召回、记录、候选、收件箱、查重、合并、索引、诊断、迁移和遗忘。
- `template_dir()` 依赖 Skill 相对目录，打包时需改用包资源定位，并测试实际分发包包含模板。
- `add_record()` 等直接接受 argparse.Namespace；Core 应改为明确的请求/结果类型，CLI 负责参数与输出适配。
- `main()` 使用 print 输出；不能直接充当 MCP handler。stdio 的 stdout 只能输出协议消息，日志进入 stderr。
- `discover_root()` 依赖 cwd 和向上搜索。MCP 请求必须显式携带 project_root，服务端解析真实路径并检查允许访问的根目录；避免会话切换及软链接越界。
- `next_record_id()` 扫描后递增，`add_record()` 用含 ID 和标题的文件名排他创建：并发不同标题可占用同一 ID。代码审查发现，尚未运行并发复现实验。
- `rebuild_index()` 直接 write_text；`compact_duplicate()` 连续改写多个文件。需项目级跨进程锁、临时文件原子替换，以及多文件操作日志/恢复；单个文件的原子替换不足以保证整个操作原子性。
- `initialize()` 在检查 schema 版本前已进行部分目录和模板操作。新版本应先验证兼容性、生成变更计划，再执行写入。
- 项目 AGENTS 启动块是当前会话触发与降级机制，不能随 Skill 瘦身丢弃。

## 建议首版结构

```text
MWF package（目标候选：TypeScript，编译为 JavaScript 分发）
  core/       项目定位、协议、记录、召回、维护、锁与恢复
  assets/     兼容旧 .mwf 的模板与协议
  cli/        mwf 命令；稳定 JSON 输出
  mcp/        stdio 工具、输入 schema、结构化结果
  adapters/
    codex/    轻量 Skill、MCP 注册、AGENTS 启动规则
    pi/       Extension：命令、工具与生命周期资源管理
```

运行包固定发布版本，配置记录稳定的可执行文件绝对路径。TS 发布物包含编译后的 JavaScript 和模板，用户运行时不依赖 tsx/ts-node 或源码目录。发行名和包名需发布前检查可用性。

Pi 优先复用社区 `pi-mcp-adapter`，不自建通用 MCP 桥接。安装程序检查兼容版本，缺失时安装，合并 MWF 配置，然后验证握手与实际工具调用。MWF 特有命令或启动注入仍由很薄的适配层负责。

## 首版操作边界

| 操作 | 作用 |
|---|---|
| mwf_status / mwf_doctor | 分开报告项目状态、数据一致性与运行安装诊断 |
| mwf_init | 显式项目根与 Git 模式，支持变更预览、重复执行 |
| mwf_recall | 返回相关记录、命中理由和 incident 的适用/失效边界 |
| mwf_add / mwf_propose | 校验记录类型、作用域和敏感内容；幂等请求避免重试重复记录 |
| mwf_process_inbox | 显式列出或处置条目，保留来源 |
| mwf_handoff | 新增结构化交接更新，避免模型直接随意改文件 |
| mwf_rebuild_index | 明确表示重建派生数据，不命名为含义模糊的 sync |
| duplicates/compact/migrate/forget | 后续迁移现有维护能力；破坏性操作保留预览、恢复与授权语义 |

“程序升级”“数据迁移”“索引刷新”“Git 推拉”分别命名。第一阶段不增加 Git 自动同步，也不通过 MCP 自动更新自身可执行程序。

每个工具返回结构化数据：操作结果、项目根、修改文件、警告、稳定错误码、数据版本。读取与写入工具明确区分；权限在实际执行逻辑里约束，不能依赖工具注解代替。

## 安装与使用验收

1. 在干净临时环境安装发布包；模板完整，移走源码目录后 CLI 和 MCP 仍工作。
2. 从 GUI 类最小环境启动；不依赖 shell 配置，缺少运行时时错误可诊断。
3. 完成 MCP initialize、tools/list、tools/call、关闭与重启；stdout 无普通日志。
4. 保持现有 .mwf 数据兼容；CLI 与 MCP 相同输入产生等价语义结果。
5. 多进程同时写入不同标题记录仍保证 ID 唯一、索引完整；重试不产生重复。
6. 在合并、初始化等操作中注入进程中断；重启后可恢复或明确诊断。
7. 两项目/多 worktree 会话不串写，路径和软链接边界有效；未知新 schema 在写入前拒绝。
8. 新会话实际召回已有记忆，里程碑实际保存交接；MCP 不可用时明确降级。
9. 重复注册不覆盖其他配置；升级与卸载不删除项目记忆，可恢复原适配配置。

## 迁移顺序（按本轮反馈修订）

1. 明确安装、项目接入、会话启动三种状态与触发语义；冻结现有文件协议和行为样例。
2. 实现 TS 小规模完整路径：发布包安装 → setup 写入规则与配置 → stdio 握手 → bootstrap/recall；使用临时项目和真实 Harness 验证。
3. 在 TS Core 中完成跨进程写入协议、恢复与幂等，再迁移全部写操作。
4. 保留旧 Python 实现作为行为对照，比较召回、解析、迁移、隐私边界等；旧写入口退出或接入同一锁协议后才允许切换。
5. 通过版本固定的 pi-mcp-adapter 验证 Pi，完成新会话/恢复/切项目/重启场景。
6. 通过维护操作与故障注入验收后，替换 Skill 内脚本实现；轻量规则与项目数据继续保留。

## TypeScript 的价值与代价

对当前目标有实质价值：CLI、MCP、安装程序和 Pi 薄扩展可采用同一工具链，npm 可分发预编译运行产物与模板。对已有 Node 环境的 Pi 用户，可减少额外 Python 环境的维护。共享运行时 schema 能约束 CLI/MCP 的输入输出一致性；TS 类型本身不能替代外部输入校验。

TS 和 Python 都有官方 MCP SDK，不能以“只有 TS 支持 MCP”为迁移理由。TS 不会自动解决触发、文件锁、崩溃恢复或 GUI PATH。当前约 1200 行 Python 实现和 10 项测试使迁移规模可控，但测试未覆盖全部语义；必须补充黄金样例与故障测试。不要长期形成 TS 包装 Python 的双运行时生产依赖。

判断门槛：干净环境只安装目标运行时即可使用；搬离源码目录仍可启动；setup 无需模型参与便完成 AGENTS 写入；两 Harness 实际召回成功；旧数据与关键行为兼容。以上通过后，TS 重写才有可验证收益。此为技术建议，尚未执行重写。

## 安装与启动的确定性闭环

现有 `scripts/install-skill.py` 只安装 Skill，`scripts/_skill_tools.py:install_skill` 只复制/链接资源；写入 AGENTS 的逻辑在 `mwf.py:initialize`。目前用户的失败点是两步之间依赖模型触发，不能仅靠增加 MCP server 消除。

建议入口（拟议接口，尚未实现）：

```sh
mwf setup --root /absolute/project --harness codex,pi --git-mode track
```

setup 按步骤执行并返回机器可读验收结果：检查运行时与插件 → 安装/注册适配 → 校验项目路径和旧 schema → 生成并应用受管 AGENTS 块、Git 忽略规则和项目数据 → 测试 MCP 连接与 bootstrap → 报告是否需重新加载 Harness。缺少项目路径时只能报告“运行包已安装”，不能谎报“项目已接入”。不在 npm postinstall 中猜测项目或遍历修改所有仓库。

规则块使用稳定标记与版本，重复执行幂等；保留块外用户内容；标记损坏或用户同时修改时返回明确冲突；配置只合并本工具负责的条目。安装失败记录已完成阶段并支持继续/撤销自身变更。诊断分开显示 runtime、adapter、project rules、MCP connection、session bootstrap，不能把握手成功等同于记忆已载入。

触发规则改成明确事件：

- 项目未接入：只有显式 setup/init 接入，普通召回不得偷偷初始化。
- 新任务、恢复任务、切换项目：在首次规划/项目操作前 bootstrap，加载 index/handoff；用会话和项目键去重，而非每轮对话初始化。
- 工作范围转向新的文件/组件：按范围增量 recall。
- 用户稳定约束、重要决策或可复用故障解决：add/propose；不是每条消息都写。
- 完成里程碑或交接：更新 handoff。

Pi 可以在其生命周期事件中增加确定性 bootstrap，但应验证该结果确实进入当前会话上下文。Codex 继续使用 AGENTS 启动规则与轻量 Skill，并通过新会话评估测量遵循情况；本轮没有验证一个通用的 Codex 自动调用钩子，故不承诺 100% 自动召回。MCP 初始化只声明能力和通用指引，不在握手阶段修改项目或注入错误项目记忆。

## Pi 社区适配器

候选：nicobailon/pi-mcp-adapter。README 文档化安装命令 `pi install npm:pi-mcp-adapter`；正式安装脚本应固定经过兼容验收的版本，尊重已有兼容安装。

插件默认 lazy 连接、默认代理工具模式。MWF 可配置 `lifecycle: "eager"`，并将 bootstrap/recall/status 等高频工具列入 `directTools`，减少额外工具发现步骤。eager 文档不承诺断线自动重连，需单测/端到端验证 stdio 断线恢复；连接完成本身不会自动调用 bootstrap。

插件支持 MCP prompts 映射命令，因此自定义命令可以先试用该能力。不能在实际验证前保证映射后名称正好是 `/mwf:init`；若需要固定命令名，再加薄命令扩展。

本轮只核实文档，未安装或验证该插件与本机 Pi 的实际兼容。实施前以固定版本测试最小配置、工具名称、工具参数、规则加载及进程回收。

## 并发与中断恢复具体方案

保留 `.mwf` 文件事实源，操作元数据放在忽略的 `.mwf/local/` 内。主要支持单机本地文件系统；跨主机/NFS 锁不在首版保证范围。

1. 所有新 CLI/MCP 写操作使用同一项目级跨进程锁；锁覆盖 ID 分配、记录变更与索引发布。进程内 mutex 不足够。锁实现需有所有者身份、超时和可靠失效判断，不能只因时间长或 PID 数字复用就抢锁。
2. 保留当前 ID 格式，在锁内分配并查重，避免无必要数据迁移。两个 worktree 或离线分支合并后仍可能 ID 冲突：doctor 必须检测，并在显式重编号时更新引用；单机锁不被描述为 Git 合并全局唯一性保证。
3. 同目录暂存完整内容，校验并刷盘后原子替换目标；必要时同步目录元数据。读取也遵守项目锁，或使用版本一致性检查，避免通过新 API 读到维护操作中间态。外部直接读文件仍不能获得多文件事务保证。
4. 多文件变更先持久化事务清单、预期旧哈希、目标内容和必要恢复材料，再应用；最后标记完成。启动时先持锁检查未完成事务：目标等于旧哈希则继续，等于目标哈希则跳过，出现第三种哈希则报告冲突，避免覆盖用户手改。
5. 请求携带幂等键；日志在同一事务记录结果。相同键且相同输入重试返回原结果，相同键但不同输入拒绝。不要仅在进程内缓存，响应丢失后重启仍应避免重复写。
6. index 是派生文件，事务最后重建；失败时诊断并重建，不从损坏索引推断丢失记录。
7. 敏感遗忘需清理事务暂存、备份和可能包含正文的幂等结果；日志尽量仅保留哈希与操作元数据，避免“已删除”内容留在本地恢复材料中。

锁只约束遵循协议的写入者。切换期旧 Python 脚本必须停止写入或升级到同一锁协议；用户手改/Git 操作通过哈希冲突检测处理。验收包含不同标题并发写、重复请求、持锁进程终止、事务每阶段中断、外部修改、新版本 schema 拒写等。

## 方案评估阶段的验证与限制

现有单元测试：`python3 -m unittest discover -s skills/memory-with-files/tests -p 'test_*.py'`，10 项通过。未实施新 MCP、安装新包或改变用户 Harness 配置。并发、中断与新客户端验收是后续工作，不包含在现有通过结论里。

## 参考资料

- [Codex MCP 官方文档](https://developers.openai.com/codex/mcp)：stdio 配置、启动参数、server instructions。
- [MCP stdio 规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)：子进程与标准流约束。
- [Pi 官方扩展文档](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md)：registerCommand 与会话生命周期。
- 本机 Pi 文档：`/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/README.md`（No MCP 段）与 `docs/extensions.md`。Pi 能力结论以此已安装版本为依据。

补充来源：
- [Pi MCP Adapter README](https://github.com/nicobailon/pi-mcp-adapter)：安装、lifecycle、directTools、prompts。
- [官方 TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) 与 [官方 Python SDK](https://github.com/modelcontextprotocol/python-sdk)：两种语言均具备 MCP 实现基础。

## 实施状态

用户已批准实施，现已完成本地 TypeScript CLI/MCP、确定性 setup、Pi 适配、事务恢复与兼容测试。最终范围和限制以 [实施记录](mwf-implementation.md) 为准。
