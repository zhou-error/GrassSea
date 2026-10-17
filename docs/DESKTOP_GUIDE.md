# 桌面版使用指南（Windows）

> GrassSea AI 支持两种运行形态：**桌面形态**（本机、零 Docker）与**服务器形态**（Docker Compose）。
> 本文只讲桌面形态；服务器形态见 [README](../README.md) 与 [DOCKER_GUIDE](./DOCKER_GUIDE.md)。

---

## 1. 快速开始

~~~bash
# 1) 安装依赖（首次）
$env:UV_DEFAULT_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"   # 国内网络建议
uv sync --extra dev

# 2) 启动桌面应用
uv run python -m app.launcher --desktop
~~~

窗口打开后即可使用。关闭窗口即自动停止服务。

### 常用参数

| 命令 | 作用 |
|---|---|
| §uv run python -m app.launcher --desktop§ | 启动服务并打开桌面窗口（推荐） |
| §uv run python -m app.launcher§ | 只启动服务，浏览器访问 §http://127.0.0.1:8001§ |
| §uv run python -m app.launcher --check§ | 只做导入与配置自检，不监听端口 |
| §--desktop --no-window§ | 桌面模式能力（工作文件夹等）但不打开窗口 |
| §--prefer pywebview§ / §browser-app§ / §web§ | 指定窗口方式 |

---

## 2. 桌面形态与服务器形态的差别

| | 🖥️ 桌面形态 | 🐳 服务器形态 |
|---|---|---|
| 启动 | §uv run python -m app.launcher --desktop§ | §docker compose ... up -d§ |
| 向量后端 | §VECTOR_BACKEND=local§（内置 SQLite + numpy） | §VECTOR_BACKEND=milvus§ |
| 外部依赖 | **无**（不需要 PostgreSQL / MongoDB / Redis / RabbitMQ / Milvus / MinIO） | 需要上述 6 个中间件 |
| 数据位置 | §<项目根>/data/§ | §./docker-data/§ |
| 服务形态 | 一个进程内 4 个 asyncio 任务（端口 8001–8004） | 4 个容器 |
| 界面来源 | chat_service 直接托管 §frontend/dist§ | nginx 托管 |
| 工作文件夹 | ✅ 可用 | ❌ 不可用（DESKTOP_MODE=false） |

**同一个代码库**，靠配置切换；服务器形态的行为**完全没变**。

---

## 3. 数据目录

桌面形态的数据都在 §data/§（已 gitignore）：

~~~text
data/
├── vectorstore/knowledge.sqlite3   # 知识库向量（内置后端）
├── uploads/                        # 对话附件
├── models/                         # 本地向量模型缓存
└── window-profile/                 # 桌面窗口的浏览器配置
~~~

> 清空知识库：§uv run python scripts/reset_knowledge_base.py§，然后重新上传文档。

---

## 4. 两个本机专属功能

### 4.1 对话附件

在「项目」页输入框左侧点 📎，或**直接拖文件进来**，或**粘贴截图**。

| 类型 | 处理 |
|---|---|
| txt / md / csv / json / 源码 | 直接读取正文 |
| PDF | PyMuPDF 提取（失败回退 PyPDF2） |
| xlsx / xlsm | openpyxl 转文本（单表最多 500 行） |
| 图片 | **接收并保存，但不解析** —— 当前模型（DeepSeek）不支持图片理解，界面与回答中都会如实说明 |
| 其它 | 仅接收保存 |

单文件上限 50MB；注入模型的正文字符上限 20,000/文件、60,000/次对话。

### 4.2 工作文件夹

桌面模式下页面顶部会出现「工作文件夹」栏：

1. 点「选择文件夹」→ 弹出**系统原生文件夹对话框**
2. 选定后，模型可以在对话中**自主**：
   - §workspace_list§ 查看目录
   - §workspace_read§ 读取文件
   - §workspace_write§ 保存产出（**扩展名由模型按内容自行决定**：说明用 §.md§、表格用 §.csv§、结构化数据用 §.json§）
3. 覆盖已有文件需要模型显式声明 §overwrite=true§，否则拒绝

**安全边界**：所有路径都归一化并校验必须落在所选文件夹内，§../../§ 之类的越界访问会被拒绝；读取限制 2MB、写入限制 5MB。

---

### 4.3 Word 文档与 PDF

桌面模式下模型可直接生成/修改 Word 文档：

- 新建：封面 + 自动目录 + 页眉页脚页码 + 表格（合并单元格 / 表头跨页重复）+ 图片 + 公式 + 分节横向页
- 修改：末尾追加 / 占位符替换（`{{项目名}}`）/ 按标题重写 / 保留文本重排
- 转 PDF：默认调用本机 Word（实测约 6 秒/份）；无 Office 时装 LibreOffice 亦可

**排版模板可在界面改**：设置页 →「排版模板」→ 直接编辑 YAML（页边距、正文/标题字体字号行距、封面字号），保存后下次生成即生效。

| 位置 | 作用 |
|---|---|
| `<DATA_DIR>/templates/report.yaml` | 用户覆盖（前端保存到这里） |
| `templates/report.yaml`（仓库根） | 仓库默认 |

> 详细用法见 [WORD_DOC_GUIDE](./WORD_DOC_GUIDE.md)。

### 4.4 配置全暴露

设置页列出 **26 项可编辑配置**（LLM / 模型 / RAG / 会话 / 搜索 / 工具调用 / 文档），每项同时显示**中文名与英文名**；
敏感 Key 走加密存储、前端脱敏显示，其余修改即时生效。

---
## 5. 已知限制与环境依赖

### 5.1 桌面窗口的三种方式

§app/desktop.py§ 会按可用性依次尝试：

| 顺序 | 方式 | 条件 |
|---|---|---|
| 1 | **PyWebView 嵌入窗口** | 需要 WebView2 运行时 **且** pythonnet 能加载 .NET |
| 2 | **Edge/Chrome §--app§ 无边框窗口** | 只要有 Edge 或 Chrome（Win10/11 必装），**零额外依赖** |
| 3 | 系统默认浏览器 | 兜底 |

**当前常见情况是走方式 2**，原因是一个上游兼容问题：
pywebview 自带的 §Microsoft.Web.WebView2.WinForms.dll§ 目标框架是 **.NET Framework 4.6.2**，
与 pythonnet 的 §coreclr§ 模式不兼容（引用了 coreclr 已移除的 §System.Windows.Forms.ContextMenu§）；
而 §netfx§ 模式在部分机器上无法加载 §Python.Runtime§。

方式 2 与方式 1 用的是**同一个 Chromium 内核**，区别只是独立进程 vs 嵌入控件；用户体验上都是
「点开就是一个无地址栏的独立窗口，任务栏独立图标」。若将来 pythonnet 问题解决，
**无需改代码**即可自动切回方式 1。

### 5.2 其它

| 项 | 说明 |
|---|---|
| 端口占用 | 默认 8001–8004；被占用时设 §CHAT_SERVICE_PORT§ 等环境变量（内部地址会自动跟随） |
| 换 embedding 模型 | 必须 §uv run python scripts/reset_knowledge_base.py§ 后重新入库 |
| 首次用知识库 | 会自动下载本地向量模型（约 95MB，走 §HF_ENDPOINT§），需等几分钟 |
| 多用户 / 多副本 | 单进程形态不支持；需要时改用服务器形态 |

---

## 6. 开发指引

~~~bash
# 后端：单进程 + 热重载
uv run python -m app.launcher --no-window

# 前端：Vite HMR（桌面壳指向 3000 即可）
cd frontend && npm run dev
~~~

- 新增工具见 [TOOL_DEVELOPMENT_GUIDE](./TOOL_DEVELOPMENT_GUIDE.md)
- 架构与模块边界见 [ARCHITECTURE](./ARCHITECTURE.md)
- 全文件与符号索引见 [ARCHITECTURE-APPENDIX-INDEX](./ARCHITECTURE-APPENDIX-INDEX.md)

**改动后**：前端需 §npm run build§ 才会被 §frontend/dist§ 托管；后端直接重启即可。
