# 06 - 完整 RAG 服务 API

## 学习目标

1. 理解 FastAPI 端点设计的完整模式
2. 掌握 /rag/query 的 3 步流程在代码中的串联
3. 学会设计文档上传 (/rag/documents) 和配置热加载 (/admin/reload) 端点
4. 能独立基于 FastAPI 构建一个最小可用的 RAG 服务

## 前置知识

- FastAPI 基础（路由、请求体、响应模型）
- 理解前面 5 节的所有 RAG 环节
- Python 的 Pydantic BaseModel

## 概念讲解

### FastAPI 端点设计模式

GrassSea 知识库服务的端点设计遵循三层结构：

```
                    /health     → 健康检查
                   /
    knowledge-svc ── /admin     → 管理端点
    (端口8003)      \
                    \          /rag/query   → 查询
                     \        /
                      \─ /rag ─ /rag/documents → 上传
                               \
                                \ /rag/documents/{id}/status → 状态
```

**设计原则**：
1. **/health**：所有微服务必备，用于 K3s 的 liveness probe（存活探针）
2. **/admin**：运维操作，如查看配置、热加载 API Key
3. **/rag**：业务功能，查询和文档管理

### RAG 查询的完整数据流

```
POST /rag/query
  │
  │  RAGQueryRequest { query, top_k, knowledge_bases, ... }
  │
  ├── Step 1: retriever.hybrid_search()
  │     │
  │     ├── _dense_search()  → Milvus 向量检索
  │     ├── _sparse_search() → BM25 关键词检索
  │     └── _merge_results() → 归一化融合 0.7:0.3
  │
  ├── Step 2: reranker.rerank()
  │     │
  │     ├── Cross-encoder 模型加载（延迟）
  │     ├── 逐对 (query, chunk) 评分
  │     └── Top-20 → Top-5
  │
  └── Step 3: generator.generate()
        │
        ├── _format_contexts() → 附来源标注
        ├── Prompt 模板填充
        └── _call_llm() → DeepSeek API → 答案
```

每一步在代码中都有计时日志，便于定位性能瓶颈。

## 项目代码精讲

打开 `services/knowledge_service/main.py`。

### 请求/响应模型

```python
class RAGQueryRequest(BaseModel):
    """RAG 查询请求"""
    query: str = Field(..., description="用户查询文本")
    top_k: int = Field(default=5, ge=1, le=20)
    knowledge_bases: list[str] = Field(
        default=["规范标准库", "船舶设计库"],
        description="检索的知识库列表"
    )
    stream: bool = Field(default=False)
    include_sources: bool = Field(default=True)
```

**Pydantic Field 的使用技巧**：
- `Field(...)` 的三个点表示**必填字段**（`...` 是 Python 的 Ellipsis 常量）
- `ge=1, le=20` 表示 top_k 的有效范围是 [1, 20]，超出范围 FastAPI 会自动返回 422 验证错误
- 默认知识库列表预选了最常用的两个库

```python
class RAGQueryResponse(BaseModel):
    query: str                          # 原始查询（回显）
    answer: str                         # 生成的答案
    sources: list[SearchResult]         # 引用来源
    retrieval_time_ms: float            # 检索耗时
    generation_time_ms: float           # 生成耗时
```

响应中包含耗时字段是一个好习惯：让前端可以展示"检索完成于 150ms，生成完成于 820ms"。

### 文档上传端点

```python
@app.post("/rag/documents", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    knowledge_base: str = Query(default="项目知识库"),
):
    # 1. 校验文件类型
    allowed_extensions = {".pdf", ".txt", ".md", ".markdown"}
    ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}",
        )

    # 2. 读取并处理
    content = await file.read()
    doc_id = str(uuid.uuid4())
    chunks_count = await ingestion_pipeline.process_and_index(
        document_id=doc_id,
        filename=file.filename,
        content=content,
        content_type=ext.lstrip("."),
        knowledge_base=knowledge_base,
    )

    # 3. 返回结果
    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename,
        status="indexed",
        chunks_count=chunks_count,
    )
```

**`file.filename.rsplit(".", 1)`** 的技巧：
- `"报告.pdf"` -> `["报告", "pdf"]`
- `"船舶.设计.规范.pdf"` -> `["船舶.设计.规范", "pdf"]`
- `rsplit(".", 1)` 从右边只切一次，正确获取最后一个点后的扩展名

**安全考虑**：文件类型校验使用白名单机制（只允许已知安全类型），而不是黑名单。

### 配置热加载端点

```python
@app.post("/admin/reload")
async def reload_config(config: dict[str, str]):
    """运行时重载配置，无需重启容器"""
    global retriever, generator, ingestion_pipeline

    updated = False
    for key, value in config.items():
        if hasattr(settings, key):
            old_value = getattr(settings, key, "")
            setattr(settings, key, value)
            os.environ[key] = value           # 同步到环境变量
            if old_value != value:
                updated = True

    if updated:
        # 重新创建所有依赖该配置的组件
        retriever = HybridRetriever(settings)
        await retriever.initialize()
        generator = AnswerGenerator(settings)
        ingestion_pipeline = DocumentIngestionPipeline(settings)
        await ingestion_pipeline.initialize()

    return {"status": "ok", "message": "配置已更新" if updated else "无变化"}
```

**热加载的实现要点**：

1. **`global` 声明**：修改模块级全局变量
2. **`hasattr` + `setattr`**：动态检查属性是否存在并修改，而不是硬编码字段名
3. **`os.environ[key] = value`**：同步到环境变量，确保子进程也能读取新值
4. **重新初始化**：不只是改配置值，而是重建整个依赖组件

这个端点解决了运维中的常见痛点：更新 API Key 后需要重启整个服务。有了热加载，密钥轮换变成了秒级操作。

### 完整 RAG 查询流程（代码主线）

回顾 `/rag/query` 的核心逻辑（169-222行），用一张流程图表示：

```
request 进入
    │
    ▼
┌─────────────────────────────────────┐
│  retriever.hybrid_search()          │
│  top_k = request.top_k × 4          │  ← 多取，为重排序留余量
│  → 返回约 20 条候选                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  reranker.rerank()                  │
│  candidates → Cross-encoder 评分     │
│  → 返回 Top-5                       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  generator.generate()               │
│  contexts → 格式化 → Prompt → LLM   │
│  → 返回答案 + 来源标注              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  RAGQueryResponse(...)              │
│  + 计时信息 + 来源列表              │
└─────────────────────────────────────┘
```

### 微服务架构中的服务发现

agent_service 调用 knowledge_service 的方式：

```python
# services/agent_service/main.py 第234-248行
async def _handle_knowledge_query(message: str, session_id: str) -> dict:
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"http://localhost:{settings.KNOWLEDGE_SERVICE_PORT}/rag/query",
            json={"query": message, "top_k": 5},
        )
```

注意使用 `settings.KNOWLEDGE_SERVICE_PORT` 而不是硬编码端口号——这是微服务间通信的良好实践。

## 手把手实践

### 实验一：搭建最小 RAG 服务

```python
# mini_rag.py -- 最简化的 RAG 服务（不到100行）
from fastapi import FastAPI
from pydantic import BaseModel
import httpx

app = FastAPI()

class QueryRequest(BaseModel):
    query: str

# 模拟知识库
knowledge = {
    "稳性": "船舶稳性是指船舶在外力作用下发生倾斜而不致倾覆...",
    "排水量": "排水量是船舶在水中所排开的水的重量...",
    "方型系数": "方型系数Cb是船体水下部分的排水体积与...",
}

@app.post("/search")
async def search(req: QueryRequest):
    # 最简单的关键词匹配
    results = []
    for keyword, content in knowledge.items():
        if keyword in req.query:
            results.append({"text": content, "keyword": keyword})
    return {"results": results}

# 运行: uvicorn mini_rag:app --port 8003
```

### 实验二：测试完整流程

1. 启动知识库服务
2. 先上传一个文档：`curl -F "file=@sample.txt" http://localhost:8003/rag/documents`
3. 查询：`curl -X POST http://localhost:8003/rag/query -d '{"query":"你的问题"}' -H "Content-Type: application/json"`
4. 在返回的 JSON 中观察 `retrieval_time_ms` 和 `generation_time_ms`
5. 用 `/admin/status` 查看当前配置
6. 用 `/admin/reload` 热更新一个配置（如修改 API Key）

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "FastAPI 完整项目教程 从头搭建" -- 学习 FastAPI 端点设计
- "FastAPI 文件上传 UploadFile" -- 掌握文件上传
- "Pydantic 数据验证 教程" -- 深入理解请求模型
- "微服务 服务发现 架构设计" -- 了解微服务间通信

## 常见问题与排错

**Q1：上传大文件时超时怎么办？**

A：当前代码使用 `await file.read()` 将整个文件读入内存，对于大文件（>100MB）可能 OOM。改进方案：
1. 使用 `file.read(chunk_size)` 流式读取
2. 设置更大的超时时间（`httpx.Timeout(300.0)`）
3. 先存储到 MinIO，再异步处理索引

**Q2：为什么 `/admin/reload` 要用 `global` 声明？**

A：因为函数内部需要修改模块级的 `retriever`、`generator` 等变量。如果没有 `global`，Python 会认为你在函数内创建新的局部变量，模块级变量保持不变。

**Q3：`response_model=RAGQueryResponse` 的作用是什么？**

A：FastAPI 会：
1. 将返回的字典/对象自动序列化为 RAGQueryResponse 的格式
2. 过滤掉不在模型中的额外字段
3. 在 Swagger 文档中自动生成响应示例

这是 FastAPI 的一大便利功能。

## 练习任务

1. **架构题**：画出知识库服务的完整端点结构图，标注每个端点调用的内部组件。
2. **代码题**：为 `/rag/query` 添加一个 `min_score` 参数，用于过滤低分检索结果。
3. **实践题**：基于 `mini_rag.py`，添加一个 `/admin/reload` 端点，能动态修改"知识库"内容。
4. **综合题**：思考——如果要在 `/rag/query` 中增加流式输出（`stream=True` 时逐字推送），需要改动哪些地方？（提示：FastAPI 支持 `StreamingResponse`，LLM API 通常支持 `stream=True` 参数）
