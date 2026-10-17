# Word 文档功能使用说明

> 需求方确认的能力范围：**新建** / **修改** / **按模板排版** / **转 PDF**。
> 明确的**不支持项**：脚注（需求方决定取消）。

---

## 1. 四个工具

| 工具 | 作用 | 关键参数 |
|---|---|---|
| `docx_create` | 按结构化描述新建 .docx | `path`、`document` |
| `docx_edit` | 修改已有 .docx（四种方式） | `path`、`mode`、`output_path` |
| `docx_to_pdf` | .docx → PDF | `path`、`pdf_path` |
| `report_gen` | Markdown → docx（可同时出 PDF） | `markdown`、`title`、`to_pdf` |

四个工具都已加入**模型可调用白名单**，你可以直接在对话里说：
> "帮我写一份符合规范的稳性计算书，包含封面、目录、参数表和结论，最后导出 PDF。"

---

## 2. `document` 结构化描述格式

```json
{
  "template": "report",
  "cover": {
    "title": "稳性计算书",
    "subtitle": "某散货船方案设计",
    "fields": [{"label": "项目编号", "value": "GS-2026-001"}],
    "date": "2026年10月"
  },
  "toc": true,
  "header": "稳性计算书",
  "footer_note": "内部资料",
  "page_number": true,
  "sections": [
    {"type": "heading", "level": 1, "text": "第一章 总则"},
    {"type": "paragraph", "text": "正文…", "align": "justify",
     "first_line_indent": true, "line_spacing": 1.5},
    {"type": "list", "ordered": true, "items": ["第一条", "第二条"]},
    {"type": "table",
     "header": ["参数", "符号", "数值"],
     "rows": [["垂线间长", "L", "120.0"]],
     "merged": [{"row": 0, "cols": [0, 1]}],
     "header_repeat": true,
     "caption": "表1 主尺度参数"},
    {"type": "image", "path": "images/fig1.png", "width_cm": 12, "caption": "图1"},
    {"type": "formula", "text": "GM = KM - KG"},
    {"type": "formula", "omml": "<m:oMathPara xmlns:m=\"…\">…</m:oMathPara>"},
    {"type": "page_break"},
    {"type": "section_break", "orientation": "landscape"}
  ]
}
```

**内容块类型**：`heading` / `paragraph` / `list` / `table` / `image` / `formula` / `page_break` / `section_break`

---

## 3. 修改已有文档的四种方式

| mode | 说明 | 需要参数 |
|---|---|---|
| `append` | 在末尾追加内容，不动原有内容 | `sections` |
| `replace` | 占位符替换（正文 / 表格 / 页眉页脚都覆盖） | `values` |
| `rewrite` | 找到指定标题，重写其下到下一个同级标题之前 | `heading`、`sections` |
| `reformat` | 保留文本、丢弃原格式，按模板整体重排 | `template` |

**占位符写法**：`{{项目名称}}`、`{{日期}}`。

```json
{
  "path": "报告/模板.docx",
  "mode": "replace",
  "values": {"项目名称": "某散货船", "日期": "2026-10-16"},
  "output_path": "报告/已填写.docx"
}
```

---

## 4. 排版模板（可自行修改）

| 位置 | 作用 |
|---|---|
| `<DATA_DIR>/templates/report.yaml` | **用户覆盖**（优先级更高） |
| `templates/report.yaml`（仓库根） | 仓库默认 |

查找顺序：**用户覆盖 → 仓库默认 → 内置常量**。改完下次生成即生效，**无需重启**。

可调项：页边距、正文字体/字号/行距/首行缩进、各级标题字体字号与段前后距、封面字号。

**在界面上查看与打开**：设置页 →「Word 文档能力」→ 显示模板路径，点「打开模板文件夹」直接跳到目录（仅桌面模式）。

---

## 5. PDF 转换

由配置项 `PDF_CONVERTER` 决定：

| 取值 | 行为 |
|---|---|
| `auto`（默认） | 先试 Word，失败再试 LibreOffice |
| `word` | 仅 Word（COM 自动化），需装 Office |
| `libreoffice` | 仅 LibreOffice 无头模式 |
| `none` | 禁用转换，调用时返回明确错误 |

**重要**：Word 与 LibreOffice 都是**本机程序**，Docker 容器里没有它们。
因此**服务器形态下 PDF 转换不可用**——会返回中文原因并提示安装 LibreOffice，不会产出空文件。

实测：本机安装 Office 2021 时，单份文档转换约 **6 秒**。

---

## 6. 文件保存位置

优先级：**用户选定的工作文件夹** → 否则 `<DATA_DIR>/outputs`。
所有路径都做越界校验，`../../` 之类会被拒绝。

目标文件已存在时默认**拒绝覆盖**，需显式 `overwrite=true`。

---

## 7. 已知限制

| 项 | 说明 |
|---|---|
| 脚注 | **不支持**（需求方决定取消） |
| 自动目录（TOC） | 插入的是 Word 域，**首次打开需在 Word 里右键「更新域」**才能显示页码；文档已设置"打开时更新域" |
| 首页/奇偶页不同 | 未实现 |
| 公式 | 支持 OMML 原生公式对象；纯文本公式会以斜体文本呈现 |
| .doc 格式 | 不支持，请先用 Word 另存为 .docx |

---

## 8. 自检命令

```bash
# 查看转换引擎与模板路径
curl http://127.0.0.1:8001/doc/status

# 查看工具是否暴露给模型
curl http://127.0.0.1:8001/tools | findstr docx
```
