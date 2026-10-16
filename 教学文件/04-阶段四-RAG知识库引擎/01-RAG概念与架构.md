# 01 - RAG 概念与架构

## 学习目标

1. 理解 RAG（Retrieval-Augmented Generation，检索增强生成）的核心原理
2. 掌握 RAG Pipeline 的完整流程：预处理 -> 向量化 -> 检索 -> 重排序 -> 生成
3. 清晰区分"直接问大模型"与"RAG 检索增强"的适用场景
4. 了解 GrassSea 知识库服务的整体架构

## 前置知识

- 基础 Python（函数、类、异步 async/await）
- 了解什么是 API（尤其是 RESTful API）
- 用过或听说过 ChatGPT/DeepSeek 等大语言模型

## 概念讲解

### 为什么需要 RAG，而不能直接问 LLM？

大语言模型（如 GPT-4、DeepSeek-V3）虽然知识渊博，但有三个致命的局限：

```
问题一：知识截止日期
┌──────────────────────────────────────────┐
│ LLM 训练数据截止于某个时间点，           │
│ 例如"2024年的CCS规范最新修订"它不知道。  │
└──────────────────────────────────────────┘

问题二：幻觉（Hallucination）
┌──────────────────────────────────────────┐
│ LLM 有时会"编造"不存在的事实。          │
│ 你问"CCS §3.2.5条写了什么？"            │
│ 它可能返回一段听起来合理但完全虚构的内容。│
└──────────────────────────────────────────┘

问题三：领域知识不足
┌──────────────────────────────────────────┐
│ 通用 LLM 对船舶与海洋工程的专业细节      │
│ 掌握有限。船体结构的具体参数、           │
│ 复杂的稳性计算公式等，它可能答非所问。   │
└──────────────────────────────────────────┘
```

RAG 的核心思路：**先检索，再生成**。就像考试时给你一本参考书，先翻书找到相关段落，再基于那些段落作答。

### RAG Pipeline 全景图

```
                    RAG Pipeline（检索增强生成流水线）
 ═══════════════════════════════════════════════════════════

 用户提问："散货船舱壁间距有什么要求？"
     │
     ▼
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │  ① 文档预处理  │    │  ② 向量化索引  │    │  ③ 混合检索   │
 │  (Ingestion) │───▶│ (Embedding)  │───▶│ (Retrieval)  │
 │              │    │              │    │              │
 │ PDF/TXT/MD   │    │ 文本→向量    │    │ 稠密+BM25    │
 │ → 清洗分块    │    │ → Milvus存储 │    │ → Top-20候选  │
 └──────────────┘    └──────────────┘    └──────┬───────┘
                                                │
                     ┌──────────────────────────┘
                     ▼
 ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │  ④ 重排序     │    │  ⑤ 上下文融合  │    │  ⑥ 答案生成   │
 │ (Re-ranking) │───▶│ (Fusion)     │───▶│ (Generation) │
 │              │    │              │    │              │
 │Cross-encoder │    │ 拼接+引用标注 │    │ LLM 生成回答 │
 │Top-20 → Top-5│    │              │    │ + 引用来源   │
 └──────────────┘    └──────────────┘    └──────────────┘
                                                │
                                                ▼
                     ┌──────────────────────────────────┐
                     │  "根据CCS《钢质海船入级规范》       │
                     │   第2篇第5章，散货船舱壁间距         │
                     │   应不小于600mm。                   │
                     │   [来源: CCS规范2024, chunk_3]"    │
                     └──────────────────────────────────┘
```

### 和"直接问 LLM"的对比

```
场景：询问"Holtrop 法阻力计算中，形状因子 (1+k) 的经验公式是什么？"

直接问 LLM：
┌─────────────────────────────────────────────┐
│ 用户 → LLM → 可能正确的回答                  │
│ 风险：公式细节可能记错，数值系数不精确       │
│ 无法溯源："你这段话是哪本教材第几页写的？"   │
└─────────────────────────────────────────────┘

RAG 检索增强：
┌─────────────────────────────────────────────┐
│ 用户 → 检索"阻力计算"相关文档 ──────────┐   │
│       → 找到《船舶阻力》P89 段落         │   │
│       → LLM 基于该段落生成回答           │   │
│       → 附带来源标注 [来源: 船舶阻力, P89]│   │
│ 优势：准确、可溯源、不会胡编              │   │
└─────────────────────────────────────────────┘
```

## 项目代码精讲

GrassSea 的知识库服务由四个核心模块组成，定义在 `services/knowledge_service/` 下。

### 服务入口：main.py

打开 `services/knowledge_service/main.py`，先看架构总览。

```python
# 从第1-8行可以看到服务的职责说明
"""知识库服务 (Knowledge Service)

提供 RAG 检索增强生成能力。
- 文档上传与预处理
- 向量化索引
- 混合检索（稠密 + 稀疏）
- 重排序
- 答案生成（带引用标注）
"""
```

**逐段解析**：

```python
# 第21-25行：导入四大核心组件
from services.knowledge_service.ingestion import DocumentIngestionPipeline  # ①预处理
from services.knowledge_service.retrieval import HybridRetriever            # ③检索
from services.knowledge_service.reranker import Reranker                    # ④重排序
from services.knowledge_service.generator import AnswerGenerator             # ⑥生成
```

这就是我们在 Pipeline 全景图中看到的六个步骤的具体实现。

```python
# 第32-35行：全局组件变量
ingestion_pipeline: DocumentIngestionPipeline | None = None
retriever: HybridRetriever | None = None
reranker: Reranker | None = None
generator: AnswerGenerator | None = None
```

这些组件在服务启动时初始化（`lifespan` 函数中），并在整个服务生命周期中复用。这里的 `| None` 是 Python 3.10+ 的类型联合语法，表示变量可以是该类型或 `None`。

```python
# 第38-58行：lifespan 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ingestion_pipeline, retriever, reranker, generator
    # 启动时初始化
    ingestion_pipeline = DocumentIngestionPipeline(settings)
    retriever = HybridRetriever(settings)
    reranker = Reranker()
    generator = AnswerGenerator(settings)

    await ingestion_pipeline.initialize()
    await retriever.initialize()

    yield  # 服务运行期间在这里暂停

    # 关闭时清理
    if ingestion_pipeline:
        await ingestion_pipeline.close()
```

`@asynccontextmanager` 装饰器将函数变为异步上下文管理器。`yield` 之前的代码在服务启动时执行，之后的代码在服务关闭时执行。这是 FastAPI 推荐的生命周期管理模式。

### 核心查询端点：/rag/query

这是整个知识库服务的核心接口，完整实现了 RAG 的三步流程：

```python
# 第169-222行
@app.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    # Step 1: 混合检索
    t0 = time.time()
    search_results = await retriever.hybrid_search(
        query=request.query,
        top_k=request.top_k * 4,  # 先取 Top-20，再重排序
        knowledge_bases=request.knowledge_bases,
    )
    retrieval_time = (time.time() - t0) * 1000

    # Step 2: 重排序
    t0 = time.time()
    if request.top_k < len(search_results):
        search_results = await reranker.rerank(
            query=request.query,
            candidates=search_results,
            top_k=request.top_k,
        )

    # Step 3: 构建上下文并生成答案
    t0 = time.time()
    answer = await generator.generate(
        query=request.query,
        contexts=[r.text for r in search_results],
        sources=search_results if request.include_sources else [],
    )
```

**关键设计细节**：

1. **"先多取，后精选"策略**：检索时取 `top_k * 4`（默认20条），重排序后缩减到 `top_k`（默认5条）。这保证了召回率（不遗漏相关内容），又保证了精确率（最终只返回最相关的）。

2. **时间计量**：每个步骤都记录了耗时（毫秒），便于性能监控和优化。

3. **来源标注**：`include_sources` 参数控制是否在回答中附带引用来源。

## 手把手实践

### 实验一：追踪一次完整的 RAG 查询

1. 确认项目环境已配置（参考阶段一的 setup 指南）
2. 启动知识库服务：`uvicorn services.knowledge_service.main:app --port 8003`
3. 访问 `http://localhost:8003/docs` 查看自动生成的 Swagger API 文档
4. 使用 `/rag/query` 端点发送一个测试请求：

```json
{
  "query": "什么是船舶稳性？",
  "top_k": 5,
  "knowledge_bases": ["船舶设计库"]
}
```

5. 观察返回的 `sources` 字段，里面有每条参考资料的来源信息

### 实验二：理解检索-生成的"接力"关系

想象你在参加开卷考试，而 RAG 就像你的考试策略：

- **Step 1 检索**：翻书找相关章节（你可能翻到3-5个相关段落）
- **Step 2 重排序**：判断哪几个段落最相关，挑出最重要的2-3个
- **Step 3 生成**：基于挑出的段落组织答案

代码中 `top_k * 4` 的设计，就相当于你在考试时多翻几页，确保不遗漏重要信息，然后再精选出最核心的内容写入答卷。

## 视频学习资源

由于搜索服务暂时不可用，请在 B站（bilibili.com）自行搜索以下关键词：

- "RAG 检索增强生成 原理" -- 了解 RAG 基础理论
- "LangChain RAG 实战" -- 动手实现 RAG
- "Milvus 向量数据库 入门" -- 学习向量存储
- "Embedding 向量嵌入 通俗解释" -- 理解文本如何变成向量

## 常见问题与排错

**Q1：RAG 和"给 ChatGPT 贴一段长文本"有什么区别？**

A：本质思想相同，但 RAG 是**自动化**的。你不需要手动复制粘贴——系统自动从海量文档中检索出最相关的片段，自动拼接后发给 LLM。而且 RAG 支持持续更新知识库，新文档上传后立即生效。

**Q2：为什么需要重排序？直接用检索分数不行吗？**

A：检索阶段的分数（如余弦相似度）衡量的是"向量在空间中的距离"，它偏向于语义相近但不一定是"能回答问题的"。重排序使用 Cross-encoder 模型，同时读入问题和候选段落，判断"这个段落能否回答这个问题"，精度更高。

**Q3：`top_k * 4` 会不会太多，导致速度变慢？**

A：20条候选的检索通常在几十毫秒内完成，而重排序将20条缩减到5条后再发给 LLM 生成（这一步才是耗时大头）。所以"多检索 + 精选"的策略是用极小的检索成本，换取生成质量的显著提升。

## 练习任务

1. **概念题**：用自己的话解释 RAG Pipeline 的六个步骤，画出你理解的流程图。
2. **代码题**：在 `main.py` 中找到每个 RAG 步骤对应的代码行号，用注释标注。
3. **思考题**：如果用户问"昨天发生了什么新闻"，RAG 能回答吗？为什么？提示：这与知识库中有什么内容有关。
4. **扩展题**：查看 `RAGQueryRequest` 的定义（第72-81行），思考如果要把 `stream` 参数改为支持流式输出，需要在 `generator.generate()` 中做什么修改？
