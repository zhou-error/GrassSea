# 工程状态卡（Session State）

> 用途：**上下文丢失、换新会话、或隔很久回来**时，读这一个文件就能接上。
> 原则：本文件只写**实测过**的数字与**已验证**的结论；不确定的一律标注。
> 最后更新：2026-10-20

---

## 1. 当前基线

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/zhou-error/GrassSea |
| 分支 | `develop`（与 `master` 同步） |
| 起点 commit | `8f96a3a9` |
| 工作区 | 干净（仅 `.deckbuild/` 与 PPT 为未跟踪，**按要求不提交**） |
| OS | Windows 11 (10.0.26200) |
| Python | 3.12.5（`.venv`） |
| uv | 0.11.14 |
| Rhino | 8.35.26251.13001，安装在 `E:\Program Files\Rhino 8\` |

---

## 2. 关键数值（改代码后请重新实测，勿凭记忆）

| 项 | 值 |
|---|---|
| 业务 Agent | **7** |
| 工具总数 | **21** |
| 对模型可见的工具 | **13** |
| 未实现（不下发） | **8** |
| 可编辑配置项 | **30**（8 分类） |
| Rhino 操作数 | **12** |
| 契约测试 | **34**（`tests/contract/`，全量 119 通过） |
| MCP 试点 | **已完成**（`rhino/mcp_server.py`，stdio，12 个工具） |

**Agent 列表**：`pm_agent, review_agent, naval_arch_agent, cad_agent, rhino_agent, research_agent, doc_agent`

**复测命令**（改完代码跑一次，数字以此为准；脚本见 `scripts/status_counts.py`）：

```bash
uv run python scripts/status_counts.py
```

输出样例（2026-10-20 实测）：

```
agents      7
tools       21
exposed     13
unimpl      8  cad_draw, cad_parse, dwg_converter, ocr_engine, pdf_parser, todo_manager, web_search, xlsx_parser
config      30  (8 类: CAD, LLM, RAG, 会话, 工具调用, 搜索, 文档, 模型)
rhino_ops   12
```

---

## 3. 必须遵守的规矩（用户明确定下的）

1. **先读后改**：完全理解前不动文件；**最小改动**；**可验证**
2. **不臆测**：不确定的标 ⚠️，不把猜的写成结论
3. **分阶段汇报**：结构性调整、删除/重命名、依赖升级、接口变更**先征求同意**
4. **破坏性操作必须确认**：Rhino 的 `boolean` / `delete` 需 `confirm=true`；
   `split` / `join` 在 `keep_input=false` 时同样需要
5. **数字必须实测**，不能靠记忆（曾把「121 行」写错，实际 59 行）
6. **PPT 相关一律不处理、不提交**，等用户下次明确提出
7. **桌面形态优先**，稳妥做法；不引入 Docker 依赖
8. **保护敏感信息**：不打印、不导出行密钥；诊断包必须无明文密钥

---

## 4. 本次会话修掉的 bug（含成因，避免重犯）

### 启动与服务

| 成因 | 修复 |
|---|---|
| 新增函数插到 `@asynccontextmanager` 与 `lifespan` 之间，装饰器错位 → 启动 TypeError → uvicorn `sys.exit(3)` 拖垮 4 个服务 | `e9e2691f` |
| `--check` 只做导入检查，不跑 lifespan；单服务启动失败会终止整个进程 | `3c3e5088`（加 lifespan 冒烟 + 拦截 SystemExit） |
| **`app/launcher.py` 从未定义 logger**：看护协程与合并路径引用 `logger`，平时不触发，服务真挂/合并启动时 NameError 二次崩溃 | `本次`（补 stdlib logger，并把 3 处 structlog 风格调用改成 %-style） |
| 合并形态用 Starlette `mount` 挂子应用，**lifespan 不会自动执行** → 注册表为空、`/agents` 返回 0，但 `/health` 照样 200 | `本次`（AsyncExitStack 手动进入四个子应用 lifespan） |

### 文档与工作区

| 成因 | 修复 |
|---|---|
| `workspace_read` 编码回退含 `latin-1`（永不失败）→ 二进制被「成功」解成乱码 | `5590493e`（按后缀分派解析器） |
| 系统提示词只写「计算与核查」，未告知写文件能力 → 模型声称「没有导出能力」 | `a37d86c4` |
| 生成的文件只落盘，后端无下载接口、前端无入口 | `fc4be455`（`/files` + `/files/download` + 文件面板） |
| 排版模板用浅合并 → 只改 `top` 会把 `bottom/left/right` 整块覆盖 | `81368b41`（递归深合并） |

### 会话与配置

| 成因 | 修复 |
|---|---|
| `ToolCallLoop` 只发 `[system, 当前句]`，历史从未参与 | `ea45bd51` |
| 历史只存内存 → 重启后「继续」无上下文 → 模型突然讲 LangChain | `99809316`（落盘 `<DATA_DIR>/sessions/*.json` + 前端 localStorage + 提示词规则） |
| `_read_env` 把整个 `os.environ` 合并后写回 → `.env` 被系统变量灌满，键名带空格导致 dotenv 解析失败 | `bf82a669`（已清理，备份 `.env.bak-2026-10-19-12-03-51`） |

### Rhino 桥接（全部由真机测试暴露，mock 无法发现）

| 成因 | 修复 |
|---|---|
| `ThreadingHTTPServer.allow_reuse_address=True` + Windows `SO_REUSEADDR` → 重复启动是幽灵监听；令牌每次运行被覆盖 | `4c9136c4` |
| `_guid` 用了不存在的 `Rhino.Geometry.Guid`（应为 `System.Guid`）；`bake=false` 仍写入文档 | `bc0929f8` |
| `System.Guid` 对非法串抛 `ArgumentException`，绕过 `ValueError` 分支被归为 internal | `9ab361e0` |
| `EndUndoRecord()` 缺 `BeginUndoRecord` 返回的序号 → **所有 bake=true 写入全失败** | `0d2406a8` |
| `RhinoDoc.Transform` 不存在；失败分支调 `doc.Undo()` 会撤销**上一次成功**的几何（数据丢失） | `9c47b89d`（改 `Objects.Transform` + 精确回滚） |
| `Objects.Transform(...,True)` 并未复制，而是原地镜像并返回原 id；且「到另一舷」应是 `xz` 而非 `yz` | `431de0c3` |

---

## 5. Rhino 桥接状态

### ✅ 已真机验证

- `/hello` 返回 protocol / rhino_version / units
- 令牌复用（重启桥接不作废）
- `query` 不存在的 GUID → `not_found`
- `create_curve` `bake=false` → `object_ids=[]`、`dry_run=true`、返回真实长度
- 两段式 submit/poll + 幂等（同 `request_id` 只执行一次）
- 失败精确回滚（只删本次创建的对象）

### ⬜ 代码已写，未真机跑通

| 项 | 说明 |
|---|---|
| `loft_sections` 完整船体 | 只验证过预览，未验证 bake=true 的实体质量 |
| `join` | `Brep.JoinBreps` 未真机执行 |
| `split` | `Brep.Split` 重载未验证 |
| `offset_srf` | `Brep.Offset` 重载未验证 |
| `mass_properties` 体积 | 只在非实体上验证过（体积为空） |

### 已知限制

- 不支持 Grasshopper；一次一个 operation；只支持单一活动文档
- 放样曲面会在控制点之间鼓出（NURBS 固有），需加密断面（建议 19~21 条）
- 预览不返回 `object_ids`（设计如此）；链式建模用 `loft_sections` 这类批处理

---

## 6. 待办（优先级从高到低）

| # | 项 | 出处 |
|---|---|---|
| 1 | Rhino 5 个操作的真机验证（loft_sections / join / split / offset_srf / mass_properties 体积） | 本文 `5 |
| ~~2~~ | ~~让 pytest 可跑~~ ✅ 已完成（2026-10-23，pytest 9.1.1 + pytest-asyncio 1.4.0，116 用例通过） | 审计 S2-2 已关闭 |
| 3 | 计算工具数值守卫（拒 nan/inf/负值/1e12） | 审计 S2-1 |
| 4 | 提交前端锁文件 | 审计 S2-3 |
| 5 | 路径前缀 `/etc/passwd` 静默重写、select 枚举未校验、默认值未标记 | 审计 S3-1/2/3 |
| 6 | `pyproject` 服务器依赖切到 `[server]` 组（需重建镜像验证） | BACKLOG §1 |
| 7 | 上下文缺失时的**后端硬提示**（不只靠提示词） | BACKLOG `9 |
| 8 | 附录索引重新生成（新代码文件未纳入） | BACKLOG `5 |

**已明确暂缓**：OCR、教学文件逐章修正、pywebview 嵌入窗口（见 `docs/BACKLOG.md`）。

---

## 6.4 运行形态（2026-10-23 变更）

| 形态 | 启动 | 端口 |
|---|---|---|
| 桌面（默认） | `python -m app.launcher` / `--desktop` | **单端口 8001**，子服务挂 `/agent` `/knowledge` `/gateway` |
| 桌面回滚 | 加 `--split` | 8001~8004 四端口（原行为） |
| 服务器 | docker compose | 四服务四容器 |

合并形态三个必须注意的点：
1. **子应用 lifespan 要手动进入**（`AsyncExitStack` + `sub.router.lifespan_context`）；
   否则注册表全空，而健康检查仍然返回 200 —— 最危险的那种「看起来正常」。
2. **对话应用必须最后挂到 `/`**，它的 SPA 兜底路由会吞掉所有前缀。
3. **端口自检只查对话端口**（`preflight.run_all(["chat_service"])`）。

## 6.5 端口层与契约测试（2026-10-23 新增）

`shared/ports/` 把边界显式化：`LLMPort` / `CADBridgePort` / `ConversationStorePort`。
**价值不在解耦，而在于把 17 个真机 bug 变成可断言的契约**：

| 契约文件 | 固化的历史 bug |
|---|---|
| `test_cad_bridge_contract.py` | 预览仍写入、破坏性操作未确认、退化断面、mirror 平面语义、白名单 |
| `test_history_contract.py` | 重启丢历史、会话串号、超限清空 |
| `test_text_extract_contract.py` | latin-1 静默乱码、.doc/.dwg 无提示 |
| `test_prompt_contract.py` | 提示词未告知能力、未实现工具被下发 |
| `test_template_contract.py` | 浅合并丢页边距 |

运行：`uv run pytest tests/contract -q`

**MCP 试点（2026-10-23）**：`rhino/mcp_server.py` 以 stdio 暴露 12 个 `rhino_*` 工具，
执行层复用 `RhinoBridgeTool`，因此 bake/confirm/诚实失败语义与主程序一致。
关键约束：`stdout` 是协议通道，server 启动第一件事就是把 `sys.stdout` 指向 stderr；
契约测试 `test_mcp_stdio_contract.py` 断言了「stdout 无日志污染」。

## 7. 恢复流程（新会话从这一步开始）

1. 读本文件 + `docs/BACKLOG.md` + `docs/AUDIT-2026-10-17.md`
2. 跑第 2 节的复测命令，确认数字与本文一致（不一致说明代码已变，先看 git log）
3. 跑 `uv run python -m app.launcher --check`，确认 4 服务与 lifespan 正常
4. 需要 Rhino 时：确认 Rhino 已开、ScriptEditor 里跑着 `rhino/bridge.py`、
   设置页「CAD」开关已开、令牌路径对齐

---

## 8. 方法论教训（值得保留）

1. **mock 测不出真机 bug**：Rhino 的 6 个 bug 全部由真机交互暴露，
   `--check` 与 mock 桥接一个都没抓到。凡是调用外部原生 API，必须真机验收。
2. **静默失败比报错危险**：`latin-1` 解码、`bake=false` 仍写入、`doc.Undo()` 误删、
   `.env` 污染——四者都不报错，但都在毁数据。
3. **数字要实测**：文档里每个计数都应有一条可执行的复测命令。
4. **上下文是易失的**：会话历史曾只存内存，导致用户说「继续」时模型凭空发挥。
