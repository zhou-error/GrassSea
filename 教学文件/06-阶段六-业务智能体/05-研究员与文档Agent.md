# 05 - 研究员与文档 Agent

## 学习目标

1. 理解 Research Agent 的文献检索和简报生成能力
2. 了解 Doc Agent 的报告排版和 PDF 生成机制
3. 掌握两个 Agent 在信息流中的"输入-加工-输出"角色
4. 理解 Agent 元数据中 model_preference 的选择逻辑

## 前置知识

- Python 类继承和字典操作
- 了解 Agent 基类
- 了解 HTTP API 调用的基本概念

## 概念讲解

### Research Agent：信息的"猎人与厨师"

Research Agent 的角色是从海量信息中"狩猎"相关内容，然后"烹饪"成可读的摘要。

```
         信息获取流程
        ═══════════════

  用户："搜索最新的船舶减排技术"
         │
         ▼
  ┌─────────────────────────────────────┐
  │        Research Agent（研究员）       │
  │                                     │
  │  ① 文献检索 ─────────────────────   │
  │     调用 web_search 工具             │
  │     搜索关键词: "船舶 减排 IMO 2025" │
  │     返回: 15条相关文献               │
  │                                     │
  │  ② 信息提炼 ─────────────────────   │
  │     阅读文献摘要，提取关键信息        │
  │     去重、分类、按时间排序            │
  │                                     │
  │  ③ 简报生成 ─────────────────────   │
  │     将提炼的信息组织成结构化简报      │
  │     标注来源、时间、可信度            │
  └─────────────────────────────────────┘
```

### Doc Agent：文档的"排版师"

Doc Agent 负责将各种原始内容转化为格式规范的最终文档。

```
         报告生成流程
        ═══════════════

  输入: 审查结果 JSON + 图纸截图 + 条文原文
         │
         ▼
  ┌─────────────────────────────────────┐
  │        Doc Agent（文档工程师）         │
  │                                     │
  │  ① 模板匹配 ─────────────────────   │
  │     根据报告类型选择模板              │
  │     (审查报告/计算报告/研究简报)      │
  │                                     │
  │  ② 内容排版 ─────────────────────   │
  │     封面、目录、正文、附录            │
  │     图表嵌入、引用标注                │
  │     字体规范 (宋体/Time New Roman)    │
  │                                     │
  │  ③ PDF 生成 ─────────────────────   │
  │     Markdown → Pandoc → PDF         │
  │     A4, 12pt, 页眉页脚              │
  └─────────────────────────────────────┘
```

### model_preference 的选择逻辑

观察不同 Agent 的 model_preference：

| Agent | model_preference | 原因 |
|-------|-----------------|------|
| PM Agent | deepseek-chat | 逻辑推理为主，速度快 |
| Naval Arch | deepseek-chat | 代码生成和计算分析 |
| Review | deepseek-chat | 条文匹配和逻辑判断 |
| CAD | deepseek-chat | 指令生成 |
| **Research** | deepseek-chat | 文本理解和摘要 |
| **Doc** | **claude-opus-4-8** | 长文本结构化输出 |

Doc Agent 选择了 Claude Opus 而不是 DeepSeek！为什么？因为 Claude 在长文本的结构化排版方面表现更好——它能更好地理解复杂的格式要求并生成整洁的 Markdown/LaTeX。

## 项目代码精讲

### Research Agent

打开 `agents/research_agent/agent.py`。

#### 元数据

```python
RESEARCH_AGENT_METADATA = AgentMetadata(
    agent_id="research_agent",
    name="研究员 Agent",
    role="文献检索、信息提炼、报告撰写、趋势分析",
    capabilities=[
        AgentCapability(name="literature_search",
            description="文献检索与信息提炼",
            tools=["web_search", "pdf_parser"],
            estimated_latency_ms=3000),
        AgentCapability(name="daily_brief",
            description="每日简报生成",
            tools=["web_search", "report_gen"],
            estimated_latency_ms=5000),
        AgentCapability(name="trend_analysis",
            description="技术趋势分析",
            tools=["web_search"],
            estimated_latency_ms=4000),
    ],
    max_concurrent_tasks=5,  # 检索任务可并发较多
)
```

三个能力分别对应不同的信息处理深度：
- **literature_search**：基础能力，找到并提炼单条信息
- **trend_analysis**：中级能力，分析多个来源的趋势
- **daily_brief**：高级能力，综合多个来源生成简报

#### 任务处理

```python
class ResearchAgent(BaseAgent):
    async def handle_task(self, task, context, callbacks) -> dict:
        query = task.get("inputs", {}).get("query",
                    task.get("description", ""))

        return {
            "status": "completed",
            "query": query,
            "sources": [
                {
                    "title": "示例文献",
                    "url": "https://example.com",
                    "relevance": 0.95,       # 相关度 95%
                }
            ],
            "summary": f"关于 '{query[:50]}' 的研究综述（模拟结果）",
            "citation_count": 15,
        }
```

**返回结果的关键字段**：
- `sources`：文献来源列表，每条包含标题、URL 和相关度
- `summary`：提炼后的摘要
- `citation_count`：引用数量，帮助用户判断信息的广泛性

当前是模拟实现。生产环境中 `_handle_task` 应该根据 action 字段分发到不同的处理方法（类似 PM Agent 的模式）。

### Doc Agent

打开 `agents/doc_agent/agent.py`。

#### 元数据

```python
DOC_AGENT_METADATA = AgentMetadata(
    agent_id="doc_agent",
    name="文档工程师 Agent",
    role="报告排版、PDF 生成、格式规范校验",
    capabilities=[
        AgentCapability(name="report_gen",
            description="报告排版与PDF生成",
            tools=["report_gen"],
            estimated_latency_ms=2000),
        AgentCapability(name="format_check",
            description="格式规范校验",
            tools=[],
            estimated_latency_ms=500),
    ],
    model_preference="claude-opus-4-8",  # 注意这里！
    max_concurrent_tasks=3,
)
```

`format_check`（格式校验）是一个元能力——它不生成新文档，而是检查已有文档是否符合规范。这展示了 Agent 可以有"检查"类的能力，而不仅是"生成"类。

#### 报告生成

```python
class DocAgent(BaseAgent):
    async def handle_task(self, task, context, callbacks) -> dict:
        template = task.get("inputs", {}).get("template", "default")

        return {
            "status": "completed",
            "output": "报告已生成",
            "format": "PDF (A4, 12pt, 宋体/Time New Roman)",
            "sections": ["封面", "摘要", "正文", "结论", "附录"],
            "template_used": template,
            "file": "report_output.pdf",
        }
```

**template 参数**允许用户指定报告模板。不同的任务类型（稳性分析报告、规范审查报告、文献综述等）需要不同的组织结构。Doc Agent 应根据模板选择对应的排版方案。

**PDF 生成的技术路径**（代码中未展示，但项目架构文档中有说明）：

```
方案一：Pandoc + WeasyPrint
  Markdown → Pandoc → HTML → WeasyPrint → PDF
  优点：纯文本驱动，无需 Office

方案二：Typst
  Typst 模板 + 数据 → Typst 编译器 → PDF
  优点：比 LaTeX 更现代，排版专业性高

GrassSea 采用方案一（不依赖本机 Office）
```

## 手把手实践

### 实验：模拟文献检索的处理

```python
# research_demo.py
import json

def process_search_results(raw_results, query):
    """处理搜索结果：去重、排序、提取摘要"""
    processed = []

    for r in raw_results:
        # 简单的相关度评分（基于标题中是否包含查询词）
        relevance = (
            0.9 if query.lower() in r["title"].lower()
            else 0.5
        )
        processed.append({
            "title": r["title"],
            "snippet": r.get("snippet", "")[:200],
            "relevance": relevance,
            "url": r.get("url", ""),
        })

    # 按相关度降序排列
    processed.sort(key=lambda x: x["relevance"], reverse=True)

    # 生成摘要
    summary = f"找到 {len(processed)} 条与 '{query}' 相关的结果。"
    if processed:
        top = processed[0]
        summary += f" 最相关: '{top['title']}'(相关度 {top['relevance']:.0%})。"

    return {"summary": summary, "sources": processed}

# 模拟原始检索结果
raw = [
    {"title": "IMO 2025船舶减排新规解读", "snippet": "国际海事组织...", "url": "..."},
    {"title": "船舶废气处理技术综述", "snippet": "本文综述了...", "url": "..."},
    {"title": "全球航运碳排放趋势分析", "snippet": "根据最新数据...", "url": "..."},
]

result = process_search_results(raw, "船舶减排")
print(json.dumps(result, ensure_ascii=False, indent=2))
```

### 实验：理解 template 模式

```python
# template_demo.py
TEMPLATES = {
    "review_report": {
        "sections": ["封面", "审查摘要", "逐条审查详情", "修改建议", "附录"],
        "font": "宋体/Times New Roman",
        "page_size": "A4",
    },
    "calc_report": {
        "sections": ["封面", "计算概要", "输入参数", "计算过程", "结果分析", "附录"],
        "font": "宋体/Times New Roman",
        "page_size": "A4",
    },
    "brief": {
        "sections": ["标题", "核心要点", "详细内容", "数据来源"],
        "font": "微软雅黑",
        "page_size": "A4",
    },
}

def get_template(report_type):
    return TEMPLATES.get(report_type, TEMPLATES["calc_report"])

print("审查报告模板:", get_template("review_report")["sections"])
print("简报模板:", get_template("brief")["sections"])
print("未知类型(默认):", get_template("unknown")["sections"])
```

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "信息检索 搜索引擎 原理" -- 理解检索基础
- "Pandoc Markdown 转 PDF 教程" -- 学习文档生成
- "Python 自动化办公 报告生成" -- 了解自动化报告
- "学术写作 文献综述 方法" -- 理解文献综述方法论

## 常见问题与排错

**Q1：Research Agent 的搜索结果来自哪里？**

A：`tools=["web_search"]` 声明了对网络搜索工具的依赖。实际调用时会接入 Brave Search API 或 Bing Search API，返回真实的网络搜索结果。当前代码中的 `sources` 是模拟数据。

**Q2：Doc Agent 为什么偏好 Claude Opus 而不是 DeepSeek？**

A：这是基于模型特性的选择。Claude 在长文本生成（>2000 字）方面质量更高，特别是在需要结构化输出（如报告排版）时。但这不是绝对的——如果成本是首要考虑，可以使用 DeepSeek。

**Q3：PDF 生成的 `A4, 12pt` 是什么意思？**

A：
- A4：纸张尺寸（210mm × 297mm），国际标准办公纸
- 12pt：正文字号。1pt = 1/72 英寸。12pt 约等于中文的"小四号"
- 宋体/Time New Roman：中英文的标准衬线字体，适合正式报告

## 练习任务

1. **代码题**：扩展 `process_search_results` 函数，添加"去重"逻辑：如果两个结果的标题相似度超过 80%，只保留相关度更高的那个。
2. **设计题**：为 Research Agent 设计一个 `weekly_brief`（周报）能力，包括它的 AgentCapability 和假想的处理逻辑。
3. **分析题**：Doc Agent 的 `format_check` 能力没有关联任何 tools（`tools=[]`）。这意味着这个能力完全由 Agent 自身的逻辑实现。这合理吗？什么时候需要工具，什么时候不需要？
4. **综合题**（阶段回顾）：从用户提问"搜索最新的LNG船减排技术并生成一份综述报告"开始，追踪涉及的全部 Agent 及其协作流程。列出每个 Agent 的输入和输出。
