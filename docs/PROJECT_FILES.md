# GrassSea AI — 文件清单（已迁移）

> ⚠️ **本文件的内容已废弃**，请改看
> **[ARCHITECTURE-APPENDIX-INDEX.md](./ARCHITECTURE-APPENDIX-INDEX.md)**。

## 为什么改了

本文件原先是一份**手工维护**的文件清单（生成于 2026-07-04，当时记录 155 个文件 / ~16,000 行）。
手工清单有两个固有问题：

1. **会过期** —— 新增文件没人同步就失真（本次重构新增了 `app/`、`shared/vectorstore/`、
   `services/chat_service/attachments.py`、`shared/utils/workspace.py`、`tools/file/workspace.py` 等，
   手工清单已无法准确反映）。
2. **与代码重复** —— 文件数、行数、职责这些信息完全可以从源码得出。

因此改为**脚本从源码机械生成**的附录索引，随代码更新重新生成，不会失真。

## 现在看哪里

| 想了解 | 看 |
|---|---|
| 全部源文件（含行数、类别、职责） | [ARCHITECTURE-APPENDIX-INDEX.md](./ARCHITECTURE-APPENDIX-INDEX.md) 第 1 节「文件索引」 |
| 每个文件的类 / 函数签名与**行号** | 同上，第 2 节「逐文件符号明细」 |
| 模块划分、依赖图、调用链、接口契约 | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| 目录结构与各目录职责 | [ARCHITECTURE.md](./ARCHITECTURE.md) 第 1.4 节 |

## 如何重新生成附录

附录由结构化解析生成（Python：类 / 函数 / 多行签名；TS/TSX：导出符号），
改动代码后可重新运行生成逻辑（见 `ARCHITECTURE-APPENDIX-INDEX.md` 顶部的生成时间与统计）。

当前快照：**135 个代码文件 / 14,370 行 / 121 个类 / 685 个符号 / 43 条路由装饰器**。

---

## 项目结构速览（供快速定位）

~~~text
agents/            6 个业务智能体（继承 shared.protocols.agent.BaseAgent）
app/               桌面形态入口：launcher（单进程启动器）· desktop（窗口分级策略）
services/          4 个 FastAPI 服务
  agent_service/     编排：intent · planner · fsm · executor · registry · tool_loop
  chat_service/      BFF 代理 · config_api · attachments（附件解析）
  knowledge_service/ RAG：ingestion · retrieval · reranker · generator
  model_gateway/     模型路由与 OpenAI 兼容接口
tools/             17 个工具 + 注册中心 + bootstrap
  computation/       静水力 · 稳性 · 阻力 · 型线变换（真实计算）
  file/              解析器（诚实占位）+ workspace（工作文件夹读写）
shared/            共享内核
  protocols/         Agent / Tool 抽象协议
  utils/             config · logging · secrets · embedding · workspace
  vectorstore/       向量存储抽象：local（SQLite+numpy）/ milvus
  models/            ORM 模型与 Alembic
frontend/          React 18 SPA（4 页面 + 7 组件 + 2 store）
scripts/           初始化与运维脚本
docs/              本文档目录
教学文件/           非代码资产：13 阶段教程
~~~
