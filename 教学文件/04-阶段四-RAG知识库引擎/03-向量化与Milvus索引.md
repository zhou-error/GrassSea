# 03 - 向量化与 Milvus 索引

## 学习目标

1. 理解 Embedding（向量嵌入）的基本原理
2. 掌握 Milvus Collection 的创建流程和 Schema 设计
3. 理解 GrassSea 的双路向量策略（稠密 + 稀疏）
4. 能独立完成"文本 -> Embedding -> Milvus 存储"的完整流程

## 前置知识

- Python 基础（列表、字典、HTTP 请求）
- 了解 API 调用的基本格式
- 阅读过前面两节

## 概念讲解

### 什么是 Embedding（向量嵌入）？

Embedding 是将文本"翻译"成一串数字（向量），使语义相近的文本在向量空间中距离也相近。

```
文本 → Embedding 模型 → 向量

"散货船舱壁间距要求" → [0.23, -0.45, 0.78, ...]  (1536维)
"油船舱壁间距规定"   → [0.21, -0.43, 0.75, ...]  (1536维)
"今天天气真不错"     → [-0.10, 0.55, -0.30, ...]  (1536维)

余弦相似度：
  "散货船舱壁" vs "油船舱壁"  → 0.92  (很接近！)
  "散货船舱壁" vs "今天天气"  → 0.12  (不相关)

                   向量空间中的可视化（降维到2D）：
                            ↑
                    "今天天气真不错"
                       ·
                              ·
                          "散货船舱壁" "油船舱壁"
                                ··
                         ─────────────────→
```

**为什么这个"翻译"能保留语义？**

Embedding 模型在海量文本上训练，学会了"上下文相似的词，在向量空间中靠在一起"。就好比你学会了"苹果"和"香蕉"都是水果，所以把它们放在相近的概念区域。

### Milvus 是什么？

Milvus 是一个专门存储和检索向量数据的数据库。类比：

```
传统数据库       向量数据库
──────────      ──────────
MySQL           Milvus
存储行和列      存储向量+元数据
WHERE 精确匹配  相似度检索（找最接近的K个）
索引 B-Tree     索引 IVF_FLAT/HNSW
```

Milvus 的核心优势：
- **近实时检索**：插入数据后几乎立即可搜索
- **混合检索**：向量相似度 + 标量过滤（如 `knowledge_base == "规范标准库"`）
- **水平扩展**：数据量大时可分布式部署

### 双路向量策略

GrassSea 使用双路检索，对应两种 Embedding：

```
                      ┌──────────────────────┐
                      │   用户的查询问题       │
                      └──────────┬───────────┘
                                 │
              ┌──────────────────┴───────────────────┐
              ▼                                      ▼
    ┌──────────────────┐                  ┌──────────────────┐
    │   稠密向量(Dense) │                  │   稀疏向量(Sparse)│
    │                  │                  │                  │
    │ text-embedding   │                  │ BM25 / TF-IDF    │
    │ -3-large         │                  │                  │
    │                  │                  │                  │
    │ 擅长：语义相似度   │                  │ 擅长：关键词精确匹配│
    │ "舱壁间距" 能匹配  │                  │ 必须包含"舱壁"    │
    │ "壁板间隔"        │                  │ 才可能匹配       │
    └────────┬─────────┘                  └────────┬─────────┘
             │                                     │
             └──────────────┬──────────────────────┘
                            ▼
                  ┌──────────────────┐
                  │   融合：70%稠密   │
                  │       + 30%稀疏  │
                  └──────────────────┘
```

**为什么需要两路？**

稠密向量擅长"理解意思"但不擅长精确匹配。比如你问"CCS 规范第3.2.1条"，稠密向量可能返回各种相关内容，而稀疏向量能直接锁定包含"3.2.1"的文档。两路互补，效果最佳。

## 项目代码精讲

打开 `services/knowledge_service/ingestion.py`，阅读后半部分。

### Embedding 生成

```python
async def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
    """批量生成 Embedding，使用 text-embedding-3-large 模型"""

    # 开发环境：如果未配置 API key，使用占位向量
    if not self.settings.OPENAI_API_KEY:
        import hashlib
        embeddings = []
        for text in texts:
            h = hashlib.sha256(text.encode()).digest()
            vec = [float(b) / 255.0 for b in h[:self.settings.EMBEDDING_DIM]]
            # 补齐维度
            if len(vec) < self.settings.EMBEDDING_DIM:
                vec += [0.0] * (self.settings.EMBEDDING_DIM - len(vec))
            embeddings.append(vec[:self.settings.EMBEDDING_DIM])
        return embeddings

    # 生产环境：调用 OpenAI 兼容 API
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self.settings.OPENAI_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.EMBEDDING_MODEL,  # 如 "text-embedding-3-large"
                "input": texts,                          # 支持批量输入
            },
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]
```

**逐段解析**：

1. **占位向量（开发环境）**：使用 SHA256 哈希将文本转为固定长度的伪向量。这不是真正的语义向量，但能让开发流程跑通，无需配置付费 API。

2. **OpenAI 兼容 API**：`httpx.AsyncClient()` 是异步 HTTP 客户端，比 `requests` 更高效，适合 FastAPI 异步环境。`raise_for_status()` 表示 HTTP 错误（4xx/5xx）会直接抛异常。

3. **批量处理**：一次发送多个文本的 embedding 请求，比逐个请求效率高很多。API 同时支持最多 2048 个输入。

### Milvus Collection 创建

```python
async def _insert_to_milvus(self, chunks, embeddings):
    from pymilvus import Collection, DataType, FieldSchema, CollectionSchema, utility

    collection_name = "grasssea_knowledge"

    # 如果 collection 不存在则创建
    if not utility.has_collection(collection_name):
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR,
                        max_length=100, is_primary=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR,
                        max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR,
                        dim=len(embeddings[0])),
            FieldSchema(name="knowledge_base", dtype=DataType.VARCHAR,
                        max_length=256),
            FieldSchema(name="filename", dtype=DataType.VARCHAR,
                        max_length=500),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(fields, description="GrassSea Knowledge Base")
        collection = Collection(name=collection_name, schema=schema)
```

**Schema 设计解读**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | VARCHAR(100) | 主键，格式如 `doc_abc_chunk_5` |
| `text` | VARCHAR(65535) | chunk 的完整文本内容 |
| `embedding` | FLOAT_VECTOR | 核心字段：文本的向量表示 |
| `knowledge_base` | VARCHAR(256) | 所属知识库，用于过滤查询 |
| `filename` | VARCHAR(500) | 源文件名，用于来源标注 |
| `chunk_index` | INT64 | 序号，用于精确引用定位 |

```python
        # 创建索引 -- 决定检索效率的核心配置
        index_params = {
            "metric_type": "COSINE",      # 余弦相似度
            "index_type": "IVF_FLAT",     # 倒排文件索引
            "params": {"nlist": 128},     # 聚类中心数
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()  # 将 collection 加载到内存
```

**索引参数解释**：

- **metric_type: COSINE**：计算两个向量夹角的余弦值。范围为 [-1, 1]，越接近 1 越相似。适合文本语义相似度。

- **index_type: IVF_FLAT**：倒排文件索引（Inverted File）。将向量空间划分为 128 个聚类（nlist），检索时先找最近的几个聚类，再在其中精确查找。大幅减少搜索范围。

- **为什么先 load()？**：Milvus 的 collection 默认不加载到内存，需要显式调用 `load()` 后才能检索。

```python
    # 插入数据
    entities = [
        [c.chunk_id for c in chunks],             # id 列
        [c.text for c in chunks],                  # text 列
        embeddings,                                  # embedding 列
        [c.metadata.get("knowledge_base", "") for c in chunks],
        [c.metadata.get("filename", "") for c in chunks],
        [c.chunk_index for c in chunks],
    ]

    collection.insert(entities)
    collection.flush()  # 确保持久化到磁盘
```

插入数据的格式是按**列**组织的（列式存储）。`flush()` 确保数据写入磁盘，防止意外丢失。

## 手把手实践

### 实验一：直观感受向量相似度

```python
# cosine_demo.py -- 理解余弦相似度
import numpy as np

def cosine_similarity(a, b):
    """计算两个向量的余弦相似度"""
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return dot_product / (norm_a * norm_b)

# 用3维向量模拟（实际 embedding 是 1536 维）
# 模拟：两个相似的船舶概念 vs 无关概念
ship_a = np.array([0.8, 0.5, 0.1])  # "散货船舱壁"
ship_b = np.array([0.7, 0.6, 0.2])  # "油船舱壁"
weather = np.array([0.1, 0.2, 0.9]) # "今天天气"

print(f"船舶相关: {cosine_similarity(ship_a, ship_b):.3f}")   # 应该接近 1
print(f"船舶vs天气: {cosine_similarity(ship_a, weather):.3f}") # 应该比较低
```

### 实验二：用 httpx 调用 OpenAI Embedding API

```python
# embedding_demo.py -- 调用真实 API
import httpx
import asyncio

async def get_embedding(text: str, api_key: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "text-embedding-3-small", "input": [text]},
        )
        data = resp.json()
        embedding = data["data"][0]["embedding"]
        print(f"文本长度: {len(text)} 字符")
        print(f"向量维度: {len(embedding)}")
        print(f"前5个值: {embedding[:5]}")
        return embedding

# asyncio.run(get_embedding("船舶稳性是指船舶在外力作用下发生倾斜...", "your-key"))
```

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "Milvus 向量数据库 入门教程" -- 学习 Milvus 基础操作
- "Embedding 嵌入向量 原理通俗" -- 直观理解向量化
- "余弦相似度 机器学习 基础" -- 理解相似度计算

## 常见问题与排错

**Q1：OpenAI Embedding API 太贵了，有没有免费的替代方案？**

A：有！可以考虑：
- **BGE 系列**（BAAI/bge-large-zh）：开源中文 embedding 模型，本地部署
- **text2vec-large-chinese**：shibing624 的中文 embedding 模型
- **硅基流动 SiliconFlow**：提供免费的 embedding API 额度

本地部署需要 GPU，但 API 方案通常有免费额度。

**Q2：Milvus 连接不上怎么办？**

A：检查三步：
1. `docker ps | grep milvus` -- 确认 Milvus 容器在运行
2. `MILVUS_HOST` 和 `MILVUS_PORT` 环境变量是否正确
3. `curl http://localhost:19530/health` 测试连接

代码中有降级处理：Milvus 连接失败时，ingestion 仍能解析文档但无法索引（会打印 warning）。

**Q3：IVF_FLAT 和 HNSW 索引有什么区别？**

A：简单对比：

| 特性 | IVF_FLAT | HNSW |
|------|----------|------|
| 构建速度 | 快 | 慢 |
| 检索速度 | 中等 | 快 |
| 内存占用 | 低 | 高 |
| 精度 | 高 | 高 |
| 适合场景 | 中小规模（<10万向量） | 大规模 |

GrassSea 初期选择 IVF_FLAT 是因为数据量不大，优先保证精度和构建速度。

## 练习任务

1. **代码题**：在 `_insert_to_milvus` 方法中，给 `knowledge_base` 字段也创建索引（提示：使用 `collection.create_index` 的 `field_name` 参数）。
2. **实践题**：安装 Docker，拉取并启动 Milvus Standalone，用 `pymilvus` 创建 collection 并插入几条测试数据。
3. **思考题**：如果一个 chunk 超过 65535 字符（VARCHAR 上限），`_insert_to_milvus` 会怎样？如何解决？
4. **扩展题**：阅读 `_generate_embeddings` 中的占位向量实现。这种 hash-based 方法的局限性是什么？（提示：两个语义相近的文本会生成相近的向量吗？）
