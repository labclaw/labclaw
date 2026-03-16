# LabClaw Monorepo — 全面项目审查报告

**日期**: 2026-03-11
**审查范围**: 4个子项目 + 3个OpenAI开源参考项目
**审查工具**: Claude Opus 4.6 深度代码分析 + Codex CLI (GPT-5.4, xhigh reasoning) 自动化验证

---

## 一、项目整体健康度

| 子项目 | 成熟度 | 测试数 | 架构评分 | 代码质量 | 最大风险 |
|--------|--------|--------|----------|----------|----------|
| **device-use** | MVP | ~120 (6文件) | ★★★★☆ | ★★★★☆ | GPT-5.4 CU路径有5个运行时bug |
| **labclaw** | Pre-v0.1 | 47 BDD + 集成 | ★★★★★ | ★★★★☆ | 事件系统双通道分裂 |
| **labwork** | 活跃开发 | 68+ vitest | ★★★★☆ | ★★★☆☆ | 2000行God文件 |
| **device-skills** | 2台设备 | ~825行 | ★★★★☆ | ★★★★☆ | 无BaseDriver ABC |

---

## 二、Codex CLI 验证发现（运行时确认的bug）

Codex用GPT-5.4在沙箱中实际执行了`_map_cu_action()` + `parse_action()`，以下bug是**运行时验证**的，不是静态分析猜测：

### device-use: 5个P1/P2 CUA运行时bug

| 编号 | 严重性 | 文件:行号 | 问题 | 验证方式 |
|------|--------|-----------|------|----------|
| C1 | **P1** | `openai_compat.py:132-138` | `pending_safety_checks`被当作独立output item检查，但SDK将其作为`computer_call`的字段。**安全检查永远不会被检测到。** | Codex通过SDK `ResponseComputerToolCall.model_fields` 确认字段在item上 |
| C2 | **P1** | `openai_compat.py:374-379` | `call_id`在turns之间丢失——`DeviceAgent`只存储`plan["action"]`到history，顶层`call_id`被丢弃。**多步CU会话每轮都退回到初始调用路径**而非使用`previous_response_id`续传。 | 逻辑追踪agent.py |
| C3 | **P1** | `openai_compat.py:409-413` | 非左键点击(`right_click`, `middle`)被忽略——`cu["button"]`只在action_type为`right_click`时检查。**右键菜单操作静默变成左键点击。** | `_map_cu_action({"action_type":"right_click",...})` 确认 |
| C4 | **P1** | `openai_compat.py:421-429` | `scroll`/`drag`/`move`映射成无效action shape：scroll缺少`clicks`字段，drag缺少`start_x/end_x`，move不是合法`ActionType`。**这些常用操作会ValidationError崩溃。** | Codex运行`parse_action()`得到`ValidationError`和`ValueError` |
| C5 | **P2** | `openai_compat.py:383-389` | 批量`actions[]`被截断——只执行第一个action，其余存入`_remaining_actions`但`DeviceAgent`忽略该字段。**多动作computer_call只执行第一个。** | 逻辑追踪 |

### labclaw: 5个P1/P2 端到端集成bug

Codex审查了最近5个commit（agentic steps, plugin wiring, memory KG），发现新功能**未被端到端连接**：

| 编号 | 严重性 | 文件:行号 | 问题 | 影响 |
|------|--------|-----------|------|------|
| C6 | **P1** | `orchestrator/steps.py:171-181` | `ObserveStep`只评估`row_count`/`null_rate`/`numeric_column_count`，**不检查插件提供的sentinel指标**（如`baseline_fluorescence`、`peak_fluorescence`）。插件贡献的QC规则永远不会触发报警。 | 插件安全/QC规则形同虚设 |
| C7 | **P1** | `daemon.py:381-385` | Daemon构建`AskStep()`和`HypothesizeStep()`时**不传入`SessionMemoryManager`**。`store_finding()`和`retrieve_findings()`从未被调用。重复运行无历史去重、无`context_findings`、`/api/memory/findings`始终为空。 | 记忆持久化功能完全断路 |
| C8 | **P1** | `api/routers/memory.py:146-153` | KG API路由每次请求创建**全新的空`TierBBackend`**，不读SQLite持久化后端。`/api/memory/kg/nodes`始终返回空图，`/api/memory/kg/neighbors/{node_id}`始终404。 | KG API无法展示持久化数据 |
| C9 | **P2** | `plugins/sentinel.py:19-25` | Sentinel规则翻译器丢弃`severity`字段（用`level`替代），操作符映射缺少`==`。`fluorescence_saturation`规则降级为warning，`running_speed_zero`被静默跳过。 | 插件安全语义被削弱 |
| C10 | **P2** | `discovery/hypothesis.py:144-149` | `_from_plugin_template()`期望`statement`字段，但neuroscience plugin模板提供的是`description`/`variables`/`statistical_test`。`statement`始终为空，**所有插件假设模板被丢弃**，领域特定假设功能无输出。 | 插件假设生成功能断路 |

---

## 三、深度代码审查发现（Claude Opus 4.6）

### A. device-use — 仪器中间件

#### 架构优势 ✅
1. **5层安全架构（L1→L5）**：白名单→边界→状态验证→人工确认→文件杀开关。安全检查在执行边界强制执行（`ActionExecutor`），不可绕过。**生产级设计。**
2. **VisionBackend Protocol**：`@runtime_checkable`协议，Claude/GPT-5.4后端可无缝切换，代码零变更
3. **DeviceProfile YAML系统**：声明式定义允许的actions、安全边界、禁止区域、UI元素提示。新仪器无需写代码
4. **Pipeline编排器**：支持顺序/并行步骤、retry、超时、上下文传播、中间件hooks
5. **MCP集成完整**：FastMCP暴露仪器工具为MCP tools，支持动态pipeline编排

#### 关键问题 ❌

| 编号 | 严重性 | 问题 | 位置 |
|------|--------|------|------|
| D1 | **严重** | `TopSpinGUIAutomation.send_to_computer_use()`是空壳——向Claude发送截图并要求描述动作，但**从不解析或执行**任何GUI操作。返回文本字符串而非可执行action。 | `instruments/nmr/gui_automation.py:182-229` |
| D2 | **严重** | 两套GUI自动化系统并存但未连接：`DeviceAgent`（正常工作的CU循环）和`TopSpinGUIAutomation`（空壳stub）。`TopSpinAdapter._process_via_gui()`调用空壳而非DeviceAgent。 | `instruments/nmr/adapter.py` → `gui_automation.py` |
| D3 | **严重** | CLAUDE.md描述了完全不同的代码库（355个测试、15个demos——都不存在）。误导所有贡献者和AI代理。 | `CLAUDE.md` |
| D4 | **高** | `WindowManager`在macOS上所有方法抛`NotImplementedError`——而部署环境就是macOS。`capture_window()`是死代码。 | `core/window_manager.py` |
| D5 | **高** | `OpenAICompatBackend`（GPT-5.4 Responses API路径）零测试覆盖——项目中最复杂、最新的代码。 | `tests/` |
| D6 | **高** | `actions/registry.py`的`@register_handler`装饰器和`get_handler()`从未被生产代码使用。`ActionExecutor`用`isinstance`分发。**完整的死代码模块。** | `actions/registry.py` |
| D7 | **中** | `_strip_markdown_fences()`在`claude.py`和`openai_compat.py`中重复。 | 两个backend文件 |
| D8 | **中** | `gui_automation.py`硬编码模型名`"claude-sonnet-4-20250514"`。 | `gui_automation.py:63` |
| D9 | **中** | `_minimal_png()`在3个测试文件中复制粘贴。应放在`conftest.py`。 | 3个test文件 |
| D10 | **低** | `DeviceAgent.__init__`顶层导入`pyautogui.FailSafeException`——即使只用orchestrator/offline路径也需要pyautogui安装。 | `core/agent.py:14` |

#### 测试覆盖评估
- ✅ 测试良好：安全层（test_safety.py）、坐标缩放（test_actions.py）、agent循环mock（test_agent.py）、profile加载（test_models.py）
- ❌ 零覆盖：`OpenAICompatBackend` GPT-5.4路径、`ScreenObserver`、`WindowManager`、`TopSpinAdapter`、`NMRProcessor`、`mcp_server.py`

---

### B. labclaw — 科学方法引擎

#### 架构优势 ✅
1. **不可变Pipeline上下文**：`StepContext.model_copy(update=...)`——优秀的函数式模式，数据流可追踪
2. **内容稳定的Pattern ID**：SHA1(`pattern_type:description`)生成确定性8字符ID——跨cycle的相同pattern得到相同ID
3. **4阶段进化提升管线**：BACKTEST→SHADOW→CANARY→PROMOTED，带自动回归回滚
4. **治理引擎**：RBAC角色权限 + 安全规则注册 + 只追加审计日志
5. **SQLite Tier B KG**：FTS5全文搜索（porter分词器）+ aiosqlite异步操作
6. **Provenance追踪**：每步嵌入`context.provenance_steps`，在ConcludeStep组装为`ProvenanceChain`

#### 关键问题 ❌

| 编号 | 严重性 | 问题 | 位置 |
|------|--------|------|------|
| L1 | **严重** | `EventRegistry.emit()`和`EventBus.publish()`是**并行分发路径**，各自维护独立handler注册表。通过bus订阅的handler收不到registry发出的事件，反之亦然。**静默事件丢失。** | `core/events.py` + `core/event_bus.py` |
| L2 | **严重** | `BayesianOptimizer`实际上是**均匀随机采样**。`suggest(n=1)`在参数边界内生成随机值。名称严重误导——EXPERIMENT步骤没有在做任何优化。 | `optimization/optimizer.py` |
| L3 | **高** | `_uuid()`/`_now()`辅助函数在**19个源文件中各自重复**。应从`core/schemas.py`导入。 | 19个文件 |
| L4 | **高** | 未找到`tests/unit/`目录——CLAUDE.md要求"TDD单元测试：100%覆盖"。所有测试在`tests/features/`(BDD)和`tests/integration/`中。 | `tests/` |
| L5 | **高** | Graphiti依赖存在于`pyproject.toml`但**从未被导入**——Tier B KG是手工构建的，非Graphiti。 | `memory/`, `pyproject.toml` |
| L6 | **高** | `StepContext.patterns: list[Any]`和`hypotheses: list[Any]`——应为`list[PatternRecord]`和`list[HypothesisOutput]`。导致下游大量防御性`getattr(pattern, ..., default)`调用。 | `orchestrator/steps.py` |
| L7 | **中** | `APIConfig.port = 8000`，但CLAUDE.md说API在18800端口。默认值不一致。 | `config.py` |
| L8 | **中** | `_sync_llm_complete()`每次LLM调用创建新`ThreadPoolExecutor`。应用单个后台线程池或`asyncio.to_thread()`。 | `orchestrator/steps.py` |
| L9 | **中** | `disallow_untyped_defs = false`在mypy配置中——削弱类型安全。 | `pyproject.toml` |
| L10 | **中** | `EvolutionEngine.load_state()`用`except Exception`吞掉解析错误。 | `evolution/engine.py:407` |
| L11 | **低** | `SubjectNode`标记为deprecated但仍在`NODE_TYPES`注册表中。 | `core/graph.py` |
| L12 | **低** | 模块级可变`_PROPOSAL_TEMPLATES`的浅拷贝——当前值是原语所以安全，但脆弱。 | `evolution/engine.py` |

---

### C. labwork — Electron桌面应用

#### 架构优势 ✅
1. **RAF批处理流式传输**：`requestAnimationFrame`缓冲高频`stream.partial`事件，防止React重渲染洪流
2. **MCP客户端Shell环境解析**：生成login shell捕获完整PATH——解决打包Electron应用的经典问题
3. **配置指纹**：MCPManager防止配置未变时不必要的teardown/reconnect
4. **双集成路径**：HTTP轮询用于状态显示 + MCP stdio用于agent工具调用
5. **导航服务器**：localhost:19888 HTTP让CLI工具（包括Claude Code）驱动Electron UI

#### 关键问题 ❌

| 编号 | 严重性 | 问题 | 位置 |
|------|--------|------|------|
| W1 | **严重** | `src/main/index.ts`——**2000+行、80+个IPC handler**，所有领域混在一个文件中。不可维护、不可测试。 | `src/main/index.ts` |
| W2 | **高** | `SettingsPanel.tsx`约**1500行覆盖8个标签页**——应拆分为独立组件。 | `src/renderer/components/SettingsPanel.tsx` |
| W3 | **高** | Preload中MCP API全部使用`any`——在最关键的外部集成点上打败了TypeScript的目的。 | `src/preload/index.ts:127-136` |
| W4 | **高** | `sandbox: false`带"暂时禁用"注释——安全缺口，无跟踪。 | Electron主窗口配置 |
| W5 | **中** | `MCPServerConfig`类型在`mcp-manager.ts`和`SettingsPanel.tsx`中重复定义。应移至`src/shared/`。 | 两个文件 |
| W6 | **中** | `SciencePanels.tsx`调用`window.electronAPI.science.getConfig()`不检查`isElectronEnv`——浏览器模式会崩溃。 | `SciencePanels.tsx` |
| W7 | **中** | MCPManager和MCPConfigStore中方法内部使用`require()`而非顶层import。 | MCP模块 |
| W8 | **中** | 无React Error Boundary——任何组件崩溃导致整个UI白屏。 | `App.tsx` |
| W9 | **低** | 代码注释中英混用（`useIPC.ts`中有中文注释在英文代码中）。 | `useIPC.ts` |
| W10 | **低** | Science集成无测试覆盖（只有类型shape验证）。 | `tests/` |

---

### D. device-skills — 设备技能清单

#### 架构优势 ✅
1. **SOUL.md文档**是AI解释的核心素材——化学位移范围、安全注意事项等直接供agent使用
2. **三模式适配器**产生相同输出（`NMRSpectrum`），无论哪个backend执行
3. **离线优先 + 缓存demo响应**——无硬件、无API key也能工作
4. **pyproject.toml可选extras**——设备特定依赖精确隔离（`[bruker-topspin]`才拉`nmrglue`）

#### 关键问题 ❌

| 编号 | 严重性 | 问题 | 位置 |
|------|--------|------|------|
| S1 | **高** | 无`BaseDriver` ABC——`TopSpinDriver`和`Gen5Driver`鸭子类型实现协议。错误在运行时而非定义时暴露。 | `base.py` |
| S2 | **高** | `_DEFAULT_DEVICES_DIR`用`Path(__file__).parent.parent.parent`——wheel安装时路径计算会断裂。应用`importlib.resources`。 | `loader.py` |
| S3 | **高** | `BaseAdapter`是同步的，driver层是异步的，`BaseBrain`同步阻塞HTTP调用。**在任何异步消费者中会阻塞事件循环。** | `base.py` 跨项目 |
| S4 | **中** | `SkillManifest`无`skill_dir`路径字段。`discover_skills()`返回后无法从manifest定位源目录、profile.yaml或driver模块。 | `schema.py` |
| S5 | **中** | `models.py`用`dataclass`而非Pydantic——与核心库的Pydantic约定不一致。`NMRSpectrum`和`NMRPeak`也是dataclass。 | `biotek-gen5/models.py` |
| S6 | **中** | `version`字段接受任何字符串，无semver验证。`platform`是字符串而非枚举。 | `schema.py` |
| S7 | **中** | `_template/`目录只有YAML/MD，无Python stub。新贡献者无从开始实现adapter/processor。 | `devices/_template/` |
| S8 | **低** | 硬编码`/opt/topspin5.0.0/examdata`和`/opt/topspin5.0.0`路径。应通过环境变量或配置可覆盖。 | 多个文件 |

---

## 四、跨项目架构缺口

| 编号 | 涉及项目 | 缺口 | 影响 |
|------|----------|------|------|
| X1 | device-use ↔ device-skills | `DeviceAgent`（正常工作的CU循环）未被`TopSpinAdapter`使用。两套独立的GUI自动化路径，一套坏的。 | GUI模式端到端不通 |
| X2 | device-use ↔ labwork | device-use MCP服务器未在labwork中注册配置 | Agent无法通过MCP控制仪器（已知缺口，~55行修复） |
| X3 | device-skills ↔ labclaw | `BaseAdapter`同步 / driver异步 / `BaseBrain`阻塞HTTP | 异步消费者中事件循环阻塞 |
| X4 | device-skills ↔ labclaw | 无共享`DeviceDriver` ABC | 鸭子类型协议，运行时失败 |
| X5 | labclaw 内部 | `StepContext.patterns: list[Any]` | 类型安全缺失，防御性代码泛滥 |

---

## 五、从OpenAI开源项目中学到的可应用改进

### 来源1: openai/openai-cua-sample-app（官方CUA参考实现）

| 改进 | 当前状态 | 官方模式 | 代码量 |
|------|----------|----------|--------|
| 首轮消息带初始截图 | 仅发prompt，截图在首次action时 | prompt + screenshot一起发送 | 1行 |
| 120ms动作间延迟 | 无延迟 | 每个action间120ms（wait/screenshot除外） | 3行 |
| `reasoning: { effort: "low" }` | 默认effort | 低effort更快更便宜 | 已应用 ✅ |
| `truncation: "auto"` | 未设置 | 防止长会话上下文溢出 | 已应用 ✅ |
| 最大24轮上限 | 无限制 | 默认24轮，可配置 | 5行 |
| `pending_safety_checks` → 抛异常 | 检查逻辑有bug（C1） | 拒绝执行，要求操作员确认 | 5行 |
| 验证与agent循环解耦 | 验证在循环内 | 循环完成后读最终状态 | 架构调整 |
| Code模式（模型写代码而非GUI点击） | 无 | `exec_js`工具让模型写Playwright JS | 新模式 |

### 来源2: openai/skills（Codex技能目录）

| 改进 | 应用于 | 描述 |
|------|--------|------|
| **SKILL.md + scripts/ + references/ 文件夹结构** | device-skills | 直接可采用的技能清单结构，progressive disclosure防止上下文窗口膨胀 |
| **screenshot技能的`take_screenshot.py`** | device-use | `--app "TopSpin"`参数 + macOS权限预检 + 多显示器支持，替代mss方案 |
| **jupyter-notebook实验模板** | labclaw | 目标→设置→假设→基线→结果→下一步，映射到OBSERVE→CONCLUDE循环 |
| **playwright-interactive的Electron QA** | labwork | Electron会话管理 + 视觉QA清单 + 截图归一化 |
| **FastAPI安全最佳实践** | labclaw | 框架特定安全指南，注意局域网环境中的HSTS/TLS |

### 来源3: openai/symphony（自主编排规范）

| 改进 | 应用于 | 描述 |
|------|--------|------|
| **WORKFLOW.md作为单一配置** | labclaw实验协议 | YAML frontmatter结构化配置 + markdown正文agent提示，版本控制 |
| **协调循环** | labclaw无人值守实验 | 停滞检测 + 状态刷新 + 终端清理 |
| **指数退避重试** | device-use仪器操作 | `delay = min(10s × 2^(attempt-1), max)` |
| **确定性工作空间隔离** | labclaw并行实验 | 路径从experiment ID派生，sanitized命名，生命周期hooks |

---

## 六、优先级排序的修复计划

### 🔴 立即修复（P1 — 运行时崩溃/安全漏洞/功能断路）

| 序号 | 编号 | 子项目 | 修复内容 | 工作量 |
|------|------|--------|----------|--------|
| 1 | C4 | device-use | `_map_cu_action()` scroll/drag/move映射修复 | 30行 |
| 2 | C1 | device-use | `pending_safety_checks`检测修复（检查item字段而非output类型） | 10行 |
| 3 | C3 | device-use | 非左键点击button字段传递 | 5行 |
| 4 | C2 | device-use | `call_id`在history中保留 | 10行 |
| 5 | C5 | device-use | 批量actions全部执行（或排队） | 20行 |
| 6 | C8 | labclaw | KG API路由使用共享持久化backend而非每请求新建空图 | 15行 |
| 7 | C7 | labclaw | Daemon构建步骤时传入SessionMemoryManager，循环中调用store_finding() | 25行 |
| 8 | C6 | labclaw | ObserveStep检查插件sentinel指标，不仅仅是QC计数器 | 20行 |

### 🟠 尽快修复（P2 — 架构问题/功能断裂）

| 序号 | 编号 | 子项目 | 修复内容 | 工作量 |
|------|------|--------|----------|--------|
| 9 | C10 | labclaw | `_from_plugin_template()`接受插件实际schema（description/variables而非statement） | 10行 |
| 10 | C9 | labclaw | Sentinel翻译器保留severity字段，添加`==`操作符 | 10行 |
| 11 | D1+D2 | device-use | 将`DeviceAgent`连接到`TopSpinAdapter._process_via_gui()` | 50行 |
| 12 | L1 | labclaw | 统一EventRegistry和EventBus为单一分发路径 | 40行 |
| 13 | D3 | device-use | 重写CLAUDE.md匹配当前代码库 | 文档 |
| 14 | W1 | labwork | 拆分index.ts为领域模块（registerMcpHandlers等） | 重构 |
| 15 | S1 | device-skills | 添加BaseDriver ABC到base.py | 20行 |

### 🟡 下一个Sprint（P3 — 代码质量/技术债）

| 序号 | 编号 | 子项目 | 修复内容 |
|------|------|--------|----------|
| 11 | L2 | labclaw | 将BayesianOptimizer重命名或实现真正的GP优化 |
| 12 | L3 | labclaw | `_uuid()`/`_now()`提取到core/schemas.py |
| 13 | W2 | labwork | SettingsPanel.tsx拆分为8个独立组件 |
| 14 | W3 | labwork | MCP API surface类型化 |
| 15 | D5 | device-use | 为OpenAICompatBackend GPT-5.4路径编写测试 |
| 16 | S2 | device-skills | 用importlib.resources替代Path计算 |
| 17 | X2 | 跨项目 | 在labwork中注册device-use MCP配置 |

### ⚪ 可延后（P4 — 改进型）

| 编号 | 子项目 | 内容 |
|------|--------|------|
| L5 | labclaw | 评估是否真需要Graphiti，或删除未用依赖 |
| L6 | labclaw | StepContext字段类型化 |
| W4 | labwork | 解决sandbox: false问题 |
| W8 | labwork | 添加React Error Boundary |
| D6 | device-use | 删除死代码registry.py |
| S7 | device-skills | 为_template/添加Python stub文件 |
| 新 | device-use | 从OpenAI CUA参考实现应用quick wins（初始截图、120ms延迟、24轮上限） |

---

## 七、各子项目完成度评估

### device-use
```
安全架构     ████████████████████ 95%  — 生产级，L1-L5完整
VLM后端      ████████████████░░░░ 80%  — 双后端工作，GPT-5.4有bug
NMR离线模式  ████████████████████ 95%  — 端到端工作
NMR API模式  ████████░░░░░░░░░░░░ 40%  — 只能处理，不能采集
NMR GUI模式  ████░░░░░░░░░░░░░░░░ 20%  — stub，未连接DeviceAgent
MCP服务器    ████████████████░░░░ 80%  — 工具完整，无负面测试
Pipeline编排 ████████████████████ 95%  — 完整功能
测试覆盖     ████████████░░░░░░░░ 60%  — 安全/agent好，backend/NMR缺失
```

### labclaw
```
5层架构      ████████████████████ 95%  — 层边界清晰
科学循环     ████████████████░░░░ 80%  — 7步完整，类型安全弱
记忆系统     ████████████████░░░░ 80%  — 3层构建，Graphiti未用
进化引擎     ████████████████░░░░ 75%  — 4阶段管线，优化器是假的
事件系统     ████████████░░░░░░░░ 60%  — 双通道分裂
治理         ████████████████████ 95%  — RBAC + 审计完整
API层        ████████████████░░░░ 80%  — 12个路由，安全可用
BDD测试      ████████████████████ 90%  — 47个feature文件
单元测试     ████░░░░░░░░░░░░░░░░ 20%  — 目录不存在
```

### labwork
```
Electron安全  ████████████████░░░░ 75%  — contextIsolation好，sandbox关闭
IPC协议      ████████████████████ 95%  — 类型化discriminated union
MCP集成      ████████████████████ 90%  — stdio + SSE双传输
流式渲染     ████████████████████ 95%  — RAF批处理优秀
Science集成  ████████████░░░░░░░░ 60%  — 轮询工作，MCP未连device-use
代码组织     ████████░░░░░░░░░░░░ 40%  — God文件严重
测试覆盖     ████████████████░░░░ 75%  — 68+测试，science缺失
```

### device-skills
```
Schema设计    ████████████████░░░░ 80%  — 清晰，缺BaseDriver和类型验证
TopSpin技能   ████████████████░░░░ 85%  — 处理器成熟，GUI stub
Gen5技能      ████████████░░░░░░░░ 65%  — 仅离线模式
模板系统      ████████░░░░░░░░░░░░ 40%  — 只有YAML/MD，无Python stub
SOUL文档      ████████████████████ 95%  — AI解释的核心素材
测试          ████████████████░░░░ 75%  — 两个设备都有，driver层无
```

---

## 八、总结

### 项目整体判断

LabClaw的**架构设计是优秀的**——5层labclaw引擎、5层device-use安全模型、Electron process隔离、三模式仪器控制。这些是经过深思熟虑的设计决策。

**执行层面存在显著缺口**（共10个Codex验证的bug）：
- device-use: GPT-5.4 CU路径有**5个运行时bug**（scroll/drag崩溃、安全检查失效、call_id丢失）
- labclaw: 新功能（插件sentinel、记忆持久化、KG API）有**5个端到端集成bug**——功能已写但**未连接**
- 两套GUI自动化系统并存但未连接
- labwork主进程是2000行God文件

**最高ROI的修复方向**：
1. 修复5个CUA运行时bug（~75行，让GPT-5.4 GUI模式真正可用）
2. 修复3个labclaw P1集成bug（~60行，让KG API、记忆持久化、插件sentinel真正工作）
3. 连接DeviceAgent到TopSpinAdapter（~50行，让GUI模式端到端通）
4. 修复2个labclaw P2插件bug（~20行，让插件假设和sentinel severity生效）
5. 统一EventBus/EventRegistry（~40行，消除事件丢失）

**Codex + Claude联合审查的总计发现**：10个运行时验证bug + 16个高优先级架构问题 + 5个跨项目缺口
