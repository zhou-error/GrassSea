# 04 - CAD 与报告工具

## 学习目标

1. 理解 GrassSea 中 CAD 操作工具（cad_draw, cad_parse, dwg_converter）和报告生成工具（report_gen）的设计
2. 掌握不同类别工具的 Manifest 差异化配置策略
3. 理解 CAD 工具与 SolidWorks MCP 集成的架构设计
4. 学会设计"格式转换类"和"生成类"工具的输出 schema

## 前置知识

- 掌握 `BaseTool` 和 `ToolManifest` 的基本用法
- 了解船舶工程中常用的 CAD 格式：DWG、DXF、PDF、PNG
- 对 Markdown 有基本了解（报告工具使用 Markdown 作为中间格式）

## 概念讲解

### CAD 工具与报告工具在系统中的位置

```
                    +--------------------------------+
                    |       工具注册中心              |
                    |  CATEGORY: CAD / FILE / REPORT  |
                    +--------------------------------+
                    /           |            \
                   /            |             \
          +-----------+  +-----------+  +-----------+
          | cad_draw  |  | cad_parse |  | dwg_conv  |
          | (CAD=生成) |  | (CAD=解析) |  | (FILE=转换)|
          +-----------+  +-----------+  +-----------+
                    |
                    |       +-----------+
                    \------>| report_gen |
                            | (REPORT)   |
                            +------------+
```

注意 dwg_converter 的类别是 `ToolCategory.FILE` 而不是 `ToolCategory.CAD`。设计思考：
- `cad_draw` 和 `cad_parse` 是"专业 CAD 操作"，需要鉴权和限频
- `dwg_converter` 是"通用的格式转换"，和 xlsx_parser 一样属于文件处理

这种分类体现了"功能能力"与"使用场景"的区分。

### 四工具配置对比表

| 工具 | 类别 | 超时 | 鉴权 | 限频 | 版本 |
|------|------|------|------|------|------|
| CadDraw (生成) | CAD | 120s | **是** | **10/min** | 0.1.0 |
| CadParse (解析) | CAD | 60s | **是** | 20/min | 0.1.0 |
| DwgConverter (转换) | FILE | 60s | 否 | 60/min | 0.1.0 |
| ReportGen (报告) | REPORT | 30s | 否 | 60/min | 0.1.0 |

**关键差异分析**：

1. **CadDraw 超时 120 秒** — CAD 图形生成是四个工具中最耗时的。型线图绘制需要计算曲线光顺、生成大量图形元素，这个120秒的预算很合理。

2. **CadDraw 和 CadParse 需要鉴权** — CAD 操作涉及专业图纸数据，设置 `requires_auth=True` 确保只有授权用户才能使用。dwg_converter 因为只做格式转换（不产生新图纸），可以不设鉴权。

3. **CadDraw 限频仅 10/分钟** — CAD 生成非常消耗计算资源，严格限频防止过载。

4. **ReportGen 超时仅 30 秒** — 报告生成主要是 Markdown 转 PDF，处理时间相对可控。

### CAD 工具与 SolidWorks MCP 架构

```
   GrassSea CadDraw / CadParse
           |
           | (MCP 协议)
           v
   +-------------------+
   | SolidWorks MCP    |
   | (Model Context    |
   |  Protocol 桥接)   |
   +-------------------+
           |
           v
   +-------------------+
   | SolidWorks        |
   | (CAD 引擎)        |
   +-------------------+
```

GrassSea 的 CAD 工具目前处于"协议层"阶段——已定义好输入输出 schema 和工具框架，返回模拟数据。实际对接 SolidWorks MCP 时，只需修改 `execute` 方法中的实现，不需要改变工具的外部接口。这就是"协议先行"的优势。

## 项目代码精讲

### 1. CadDrawTool — CAD 图纸生成

**文件位置**: `tools/cad/cad_draw.py`

```python
CAD_DRAW_MANIFEST = ToolManifest(
    tool_id="cad_draw",
    name="CAD 图纸生成",
    description="型线图绘制、曲线光顺、支持 AutoCAD/SolidWorks MCP",
    category=ToolCategory.CAD,
    input_schema={
        "type": "object",
        "properties": {
            "drawing_type": {"type": "string"},
            "parameters": {"type": "object"}
        }
    },
    output_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "format": {"type": "string"}
        }
    },
    timeout_ms=120000,        # 120秒
    requires_auth=True,        # 需要鉴权
    rate_limit_per_min=10,    # 每分钟限10次
    version="0.1.0",
)
```

**代码精讲**：

`parameters` 字段的类型是 `"object"`（而不是具体的属性定义），这是一种"开放扩展"的设计——不同类型的图纸有不同的参数集：

- 型线图: `{"stations": 21, "waterlines": 8}`
- 总布置图: `{"decks": 5, "holds": 3}`
- 结构图: `{"frame_spacing": 0.6, "material": "steel"}`

如果每种图纸都定义固定的参数，Manifest 会变得臃肿。用 `"type": "object"` 保持灵活性，具体的参数验证可以放在 `validate_params` 中处理。

```python
class CadDrawTool(BaseTool):
    def __init__(self): super().__init__(CAD_DRAW_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        drawing_type = params.get("drawing_type", "lines_plan")
        return {
            "status": "completed",
            "drawing_type": drawing_type,
            "file_path": f"output/{drawing_type}.dwg",
            "format": "DWG",
            "preview": f"output/{drawing_type}.png",
            "curves": {
                "stations": 21,
                "waterlines": 8,
                "buttocks": 5
            },
        }
```

**返回结果设计精讲**：

- `drawing_type` — 回传图纸类型（方便调用方做分支处理）
- `file_path` — DWG 文件路径
- `preview` — PNG 预览图路径。这个设计很实用——大型 DWG 文件在浏览器中无法直接预览，提供 PNG 缩略图让用户快速确认生成效果
- `curves` — 曲线元信息。返回"21个站、8条水线、5条纵剖线"，让用户了解生成内容

### 2. CadParseTool — CAD 图纸解析

**文件位置**: `tools/cad/cad_parse.py`

```python
CAD_PARSE_MANIFEST = ToolManifest(
    tool_id="cad_parse",
    name="CAD 图纸解析",
    description="从 DWG/DXF 提取尺寸、标注、图层信息",
    category=ToolCategory.CAD,
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string"}
        }
    },
    output_schema={
        "type": "object",
        "properties": {
            "dimensions": {"type": "array"},
            "layers": {"type": "array"}
        }
    },
    timeout_ms=60000,
    requires_auth=True,
    rate_limit_per_min=20,   # 解析比生成快，限频宽松
    version="0.1.0",
)
```

**代码精讲**：

CadParse 比 CadDraw 的限频高一倍（20/min vs 10/min），因为"读取解析"比"生成绘制"快得多。

```python
class CadParseTool(BaseTool):
    def __init__(self): super().__init__(CAD_PARSE_MANIFEST)

    async def execute(self, params: dict, context: dict) -> dict:
        return {
            "status": "completed",
            "file": params.get("file_path", ""),
            "dimensions": [],
            "layers": ["0", "hull", "deck", "dimensions", "text"],
            "annotations": [],
            "blocks": [],
        }
```

**返回的 layers 列表**：

```python
"layers": ["0", "hull", "deck", "dimensions", "text"]
```

这模拟了真实 DWG 文件的图层结构：
- `"0"` — AutoCAD 默认图层
- `"hull"` — 船体线图层
- `"deck"` — 甲板图层
- `"dimensions"` — 尺寸标注图层
- `"text"` — 文字图层

如果你有船舶设计经验，可能会注意到这正是一张典型船舶结构图纸的图层结构。

### 3. DwgConverterTool — 格式转换

**文件位置**: `tools/cad/dwg_converter.py`

```python
DWG_CONVERTER_MANIFEST = ToolManifest(
    tool_id="dwg_converter",
    name="DWG 格式转换",
    description="DWG <-> DXF <-> PDF <-> PNG 格式互转",
    category=ToolCategory.FILE,  # 注意：属于 FILE 而不是 CAD！
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "target_format": {"type": "string"}  # "pdf" / "dxf" / "png"
        }
    },
    ...
)
```

**为什么 dwg_converter 属于 FILE 而不是 CAD？**

设计哲学：CAD 类别用于"专业工程操作"（生成图纸、解析尺寸），FILE 类别用于"通用文件操作"（格式转换、文本提取）。一个工具是"改图纸内容"还是"改文件格式"，决定了它的分类。这种细粒度分类让注册中心可以做更精准的工具筛选。

```python
async def execute(self, params: dict, context: dict) -> dict:
    target = params.get("target_format", "pdf")
    return {
        "status": "completed",
        "source": params.get("file_path", ""),
        "target_format": target,
        "output_path": f"converted.{target}",
    }
```

代码非常简洁——核心逻辑就是取 `target_format` 参数，生成对应的输出文件名。在实际实现中，这里会调用 libreoffice-convert 或相应的 DWG 转换库。

### 4. ReportGenTool — 报告生成

**文件位置**: `tools/report/report_gen.py`

```python
REPORT_GEN_MANIFEST = ToolManifest(
    tool_id="report_gen",
    name="报告生成",
    description="Markdown -> PDF 报告生成（规范排版）",
    category=ToolCategory.REPORT,
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"},
            "template": {"type": "string"},
            "format": {"type": "string"}
        }
    },
    timeout_ms=30000,
    version="0.1.0",
)
```

**代码精讲**：

`content` 字段接受 Markdown 格式的字符串。为什么用 Markdown？因为：
1. Markdown 是轻量级的标记语言，易于人类编写和 AI 生成
2. 前端可以实时渲染 Markdown 预览
3. 转换成 PDF 有成熟的工具链（如 Pandoc、WeasyPrint）

```python
async def execute(self, params: dict, context: dict) -> dict:
    title = params.get("title", "报告")
    fmt = params.get("format", "pdf")
    return {
        "status": "completed",
        "title": title,
        "format": fmt,
        "file_path": f"reports/{title}_{hash(title) % 10000}.{fmt}",
        "pages": max(1, len(params.get("content", "")) // 2000),
        "template": params.get("template", "default"),
        "sections": ["封面", "目录", "正文", "结论", "附录"],
    }
```

**几个设计细节**：

1. **文件路径**: `f"reports/{title}_{hash(title) % 10000}.{fmt}"` — 用 hash 确保同一标题的多次生成不会覆盖（hash 值可能不同），又给了一个有意义的前缀。

2. **页数估算**: `max(1, len(content) // 2000)` — 假设每 2000 个字符约 1 页，`max(1, ...)` 保证至少返回 1 页。

3. **sections 列表**: `["封面", "目录", "正文", "结论", "附录"]` — 这是典型工程报告的标准章节结构，返回这个列表让调用方了解报告包含哪些部分。

## 手把手实践

### 实践1: 模拟一次 CAD 图纸生成流程

```python
import asyncio
from tools.cad.cad_draw import CadDrawTool
from tools.cad.cad_parse import CadParseTool
from tools.cad.dwg_converter import DwgConverterTool

async def main():
    # 1. 生成型线图
    draw = CadDrawTool()
    result = await draw.execute(
        {"drawing_type": "lines_plan", "parameters": {"stations": 25}},
        {"user_id": "designer_01"}
    )
    print(f"生成图纸: {result['file_path']}")
    print(f"预览图: {result['preview']}")
    print(f"曲线: {result['curves']}")

    # 2. 解析已生成的图纸
    parse = CadParseTool()
    result2 = await parse.execute(
        {"file_path": result['file_path']},
        {}
    )
    print(f"\n解析图层: {result2['layers']}")

    # 3. 转换为 PDF
    conv = DwgConverterTool()
    result3 = await conv.execute(
        {"file_path": result['file_path'], "target_format": "pdf"},
        {}
    )
    print(f"\n转换为: {result3['output_path']}")

asyncio.run(main())
```

**预期输出**:
```
生成图纸: output/lines_plan.dwg
预览图: output/lines_plan.png
曲线: {'stations': 25, 'waterlines': 8, 'buttocks': 5}

解析图层: ['0', 'hull', 'deck', 'dimensions', 'text']

转换为: converted.pdf
```

### 实践2: 生成一份工程报告

```python
import asyncio
from tools.report.report_gen import ReportGenTool

async def main():
    tool = ReportGenTool()

    report_content = """
# 船舶稳性分析报告

## 概述
本报告对某散货船的完整稳性进行了计算分析。

## 计算结果
- 排水量: 15230 吨
- GM: 2.15 m
- 横摇周期: 8.2 秒

## 结论
满足 IMO 完整稳性要求。
"""

    result = await tool.execute({
        "title": "稳性分析报告_2026Q3",
        "content": report_content,
        "template": "engineering_report",
        "format": "pdf",
    }, {})

    print(f"文件: {result['file_path']}")
    print(f"页数: {result['pages']}")
    print(f"章节: {result['sections']}")

asyncio.run(main())
```

### 实践3: 对比工具权限配置

```python
from tools.cad.cad_draw import CAD_DRAW_MANIFEST
from tools.cad.cad_parse import CAD_PARSE_MANIFEST
from tools.cad.dwg_converter import DWG_CONVERTER_MANIFEST
from tools.report.report_gen import REPORT_GEN_MANIFEST

manifests = [
    ("CAD生成", CAD_DRAW_MANIFEST),
    ("CAD解析", CAD_PARSE_MANIFEST),
    ("格式转换", DWG_CONVERTER_MANIFEST),
    ("报告生成", REPORT_GEN_MANIFEST),
]

for name, m in manifests:
    print(f"{name}:")
    print(f"  类别={m.category.value}, 超时={m.timeout_ms}ms, "
          f"鉴权={m.requires_auth}, 限频={m.rate_limit_per_min}/min")
    print()
```

思考输出结果：
- CAD 生成和解析都需要鉴权，为什么格式转换不需要？
- 为什么报告生成的超时时间最短？

## 视频学习资源

通过 WebSearch 搜索到的 B 站学习资源：

1. **AutoCAD 图层管理基础** — 理解 DWG 文件的图层结构
   - 搜索关键词: `AutoCAD 图层管理 教程`
   - 推荐在 B 站搜索 "AutoCAD 图层" 观看

2. **SolidWorks 二次开发入门** — 了解 MCP 桥接的原理
   - 搜索关键词: `SolidWorks 二次开发 Python`
   - 推荐在 B 站搜索 "SolidWorks API" 观看

3. **Markdown 转 PDF 工具链** — Pandoc / WeasyPrint 使用教程
   - 搜索关键词: `Markdown 转 PDF Python`
   - 推荐在 B 站搜索 "Pandoc 转 PDF" 或 "WeasyPrint" 观看

4. **DWG 格式详解** — AutoCAD 的文件格式标准
   - 搜索关键词: `DWG DXF 格式 区别`
   - 推荐在 B 站搜索 "DWG 格式" 观看

## 常见问题与排错

### Q1: CAD 生成的图纸为什么不是真的 DWG 文件？

当前教学阶段返回的是模拟数据。真实 DWG 生成需要对接 AutoCAD 或 SolidWorks 的 API。GrassSea 通过 MCP（Model Context Protocol）与 SolidWorks 集成——工具层定义协议，MCP 桥接层负责调用实际的 CAD 引擎。

### Q2: 鉴权机制是如何工作的？

`requires_auth=True` 只是一个标记。实际的鉴权逻辑在 `ToolRegistry.execute_tool()` 中检查 `context` 参数中的用户认证信息，或通过 FastAPI 中间件在 HTTP 层面拦截。具体实现参见"配置管理API"和"服务间通信"章节。

### Q3: 限频（rate_limit_per_min）是如何实现的？

和鉴权类似，`rate_limit_per_min` 是 Manifest 中的声明值。限频的实际执行逻辑在注册中心或 API 网关层，通常用 Redis 实现滑动窗口计数。

### Q4: 为什么报告生成不用 Word 格式而用 Markdown？

Markdown 是纯文本格式，易于：
- AI 模型生成（LLM 天然擅长输出 Markdown）
- 版本管理（Git 可以 diff）
- 前端实时预览（react-markdown）
- 交叉转换（Pandoc 支持 Markdown -> PDF/DOCX/HTML）

而 Word 格式（DOCX）是二进制格式，不适合 AI 生成和编程处理。

## 练习任务

1. **基础练习**: 为 `DwgConverterTool` 增加支持格式列表（目前隐含支持 pdf/dxf/png），在 `describe` 字段中明确列出，并更新 `output_schema`。

2. **进阶练习**: 模仿 `ReportGenTool` 编写一个 `ReportCompareTool`（报告对比工具），输入两份报告的内容，输出差异对比结果。设计好 `ToolManifest` 和 `execute` 方法。

3. **挑战练习**: 阅读 CadDrawTool 的 `parameters` 字段设计（`"type": "object"` 的开放扩展模式），编写一个 `validate_params` 方法覆盖，根据 `drawing_type` 的不同（lines_plan / general_arrangement / structural）分别校验 `parameters` 中必须包含的字段。
