# 待办清单（Backlog）

> 本文记录**已明确但暂时不做**的事项。每条都写清：现状、为什么延后、动手时要做什么、怎么验证。
> 目的是一段时间后回来能直接开工，不必重新调研。
>
> 最后更新：2026-10-17

---

## 1. pyproject 依赖切分到 `server` 可选组 ⏸ 暂缓

**现状**

`pyproject.toml` 中 9 个**仅服务器形态需要**的包仍是硬依赖：

```
celery · aio-pika · neo4j · minio · pymilvus · motor · asyncpg · redis · opentelemetry-*
```

桌面形态（`VECTOR_BACKEND=local`，无 PostgreSQL/MongoDB/Redis/RabbitMQ/Milvus/MinIO）
实际上一个都用不到，但 `uv sync` 仍会把它们全部拉下来。

**为什么延后**

改动必须**与 `infrastructure/docker/Dockerfile` 同步**：Docker 镜像走 `pip install -e .`，
若把这些包移出主依赖而 Dockerfile 不同步安装 `[server]` 组，服务器形态会直接构建失败。
验证需要一次完整镜像重建（约 5 分钟）＋ 容器回归，**不适合在无法完整验证时半途改**。

**动手时要做**

1. 在 `pyproject.toml` 新增：
   ```toml
   [project.optional-dependencies]
   server = ["celery>=5.3.0", "aio-pika>=9.3.0", "neo4j>=5.14.0", "minio>=7.2.0",
             "pymilvus>=2.4.0", "motor>=3.3.0", "asyncpg>=0.29.0", "redis>=5.0.0",
             "opentelemetry-api>=1.22.0", "opentelemetry-sdk>=1.22.0",
             "opentelemetry-instrumentation-fastapi>=0.43b0"]
   ```
2. 从 `dependencies` 移除上述包（保留 `sqlalchemy`——ORM 模型与 Alembic 还要用）
3. 改 `infrastructure/docker/Dockerfile`：`pip install -e ".[server]"`
4. 检查代码里的**顶层**导入是否会在桌面形态报 `ModuleNotFoundError`
   （已知：`shared/models/database.py` 已懒加载，`shared/vectorstore/milvus.py` 只在 `VECTOR_BACKEND=milvus` 时导入）
5. 清理未调用的残留逻辑：`init_redis()` / `init_mongodb()` / `init_milvus()` 四个服务都没有调用

**验证**

- 桌面：全新虚拟环境 `uv sync && uv run python -m app.launcher --check` 应通过，且不安装上述包
- 服务器：`docker compose -f docker-compose.yml -f docker-compose.app.yml build` 成功，
  起容器后 4 个 `/health` 正常，知识库（milvus 后端）能列文档与检索

---

## 2. OCR 兜底（扫描版 PDF） ⏸ 暂缓

**现状**

PDF 解析走 PyMuPDF（失败回退 PyPDF2），只能取**文本层**。
扫描件（大量规范手册、旧图纸）会解析出空字符串，目前抛
「未能从该文件中提取到文本内容」，不会静默产出空文档。

**为什么延后**

需要引入 OCR 引擎（`paddleocr` 体积大、`tesseract` 需另装系统组件），
会显著增加安装体积与首次安装失败率——与「桌面形态开箱即用」的目标冲突。
**应先决策：是否接受为了扫描件而增加 ~500MB 依赖**。

**动手前需确认**

- 用 `paddleocr`（纯 Python 但重）还是 `tesseract`（需装系统程序）？
- 只对「文本层为空」的 PDF 触发 OCR（推荐），还是允许用户强制？
- OCR 是入库时同步跑（慢，但简单）还是后台任务？

**验证**：拿一份真实扫描 PDF，入库后检索能召回关键句。

---

## 3. RAG 与编排的三类测试 ⏸ 暂缓

**现状**

`tests/unit` 5 个文件 377 行；`tests/integration`、`tests/e2e` 是空壳。
桌面形态没有服务器端监控与日志聚合，回归全靠手动点，成本随工具数量指数上升。

**建议补的三类**（按性价比排序）

1. **编排循环四路径归集**（成功 / 失败 / 超时 / `not_implemented`）
   断言 `completed` / `failed` / `skipped` 的归类与最终任务状态
2. **白名单与注册表一致性**
   断言 `MODEL_EXPOSED_TOOLS` ⊆ `ToolRegistry.list_tools()`，以及 planner 引用的
   `agent_id` / `tool_id` 都存在（当前只在启动时告警，没有测试兜底）
3. **RAG 最小闭环冒烟**
   用 fake embedding（不依赖外部 LLM）：入库 → 检索 → 断言命中

**为什么延后**：工作量约半天到一天，且需要先决定是否引入 `pytest-asyncio` 之外的夹具。

**验证**：`uv run pytest` 全绿；故意改错一个 `tool_id` 时测试能红。

---

## 4. 教学文件逐章修正 ⏸ 暂缓

**现状**

`教学文件/` 有 85 篇（约 27,776 行）、13 个阶段。架构已大幅演进：
向量后端可插拔、桌面形态、模型自主调用工具、Word 能力、26 项配置。

目前只在 `教学文件/README.md` 顶部加了一张「2026 年 10 月架构重构提示」对照表，
**正文未逐章修改**。

**为什么延后**：逐篇改工作量远超一次会话，且改动分散、易遗漏。

**建议做法**

- 分批：优先 **阶段一（项目初始化）**、**阶段二（数据库设计）**——受架构变更影响最大
- 每批改完在该章顶部标注「已对齐 commit `xxxxxxx`」
- 其余章节保留对照表提示即可

**验证**：按某章步骤从零操作能跑通，不出现已删除的文件/端口/命令。

---

## 5. 附带待办（小项）

| 项 | 说明 |
|---|---|
| **重新生成附录索引** | `docs/ARCHITECTURE-APPENDIX-INDEX.md` 在新增 `app/`、`shared/vectorstore/`、`tools/doc/`、`shared/utils/docx_render.py`、`pdf_convert.py`、`workspace.py`、`attachments.py` 后统计已过期，需重跑生成脚本 |
| **一致性校验的告警分支未实测** | `_validate_registration_consistency` 的「发现问题 → 打印警告」路径没有构造过真实场景验证（需故意删掉一个注册项） |
| **pywebview 路径未验证** | 本机 WebView2 控件是 .NET Framework 4.6.2，与 coreclr 不兼容，桌面窗口实际走 Edge `--app=`。若将来 pythonnet 修复，需回归一次嵌入窗口 |
| **launcher 退出时 Edge 窗口可能残留** | 正常关闭会随之退出；launcher 崩溃时窗口不会自动关，需手动关闭 |

---

## 6. 已完成（供对照，勿重复做）

- P0：启动自检（密钥/目录/端口）、日志落盘、一键备份/恢复、服务看护
- P1：启动一致性校验、向量维度校验、SQLite schema 版本化、诊断包
- P2：XLSX/DOCX 入库、`/admin/reload` 类型校验、前端备份与诊断按钮

---

## 7. 鲁棒性审计待处理项（2026-10-17）

完整报告：[AUDIT-2026-10-17.md](AUDIT-2026-10-17.md)（基于 commit `3c3e5088`）

| ID | 问题 | 严重性 | 状态 |
|---|---|---|---|
| S2-1 | 专业计算接受 NaN / 负值 / 1e12 并返回 completed | S2 | ⬜ 待修 |
| S2-2 | pytest / ruff 未安装，CI 无法执行 | S2 | ⬜ 待修 |
| S2-3 | 前端依赖无锁文件 | S2 | ⬜ 待修 |
| S3-1 | 前导斜杠路径被静默重写而非拒绝 | S3 | ⬜ 待修 |
| S3-2 | select 型配置不做枚举校验 | S3 | ⬜ 待修 |
| S3-3 | hydrostatics({}) 全默认值却返回 completed | S3 | ⬜ 待修 |

未覆盖项（DAG 环/超时/取消、工具循环上限、检索故障、磁盘满、并发写、恢复真实执行等）
见报告 `5，均标注了复现命令。

