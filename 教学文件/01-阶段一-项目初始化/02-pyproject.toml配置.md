# 02 - pyproject.toml 配置详解

## 学习目标

学完本文件后，你将能够：
1. 理解 `pyproject.toml` 的作用和结构
2. 读懂 GrassSea 的完整 `pyproject.toml` 配置
3. 理解依赖管理、开发依赖、工具配置的关系
4. 能够为新项目编写完整的 `pyproject.toml`

## 前置知识

- 了解 Python 的 `pip install` 命令
- 知道什么是 "依赖"（一个项目需要用到哪些第三方库）
- 听说过 linting（代码检查）、格式化、类型检查的概念

## 概念讲解

### 一、pyproject.toml 是什么 —— Python 项目的"身份证"

传统上，Python 项目配置分散在多个文件中：

```
setup.py          — 打包信息
setup.cfg         — 打包参数
requirements.txt  — 依赖列表
tox.ini           — 测试配置
.flake8           — lint 配置
.mypy.ini         — 类型检查配置
```

每次新建项目都要创建一堆文件，非常繁琐。**`pyproject.toml` 的目标是把所有这些配置统一到一个文件中。**

```
传统方式（散落各处）:          现代方式（一个文件搞定）:

setup.py                       ┌─────────────────────┐
setup.cfg                      │                     │
requirements.txt               │   pyproject.toml    │
requirements-dev.txt           │                     │
.flake8                        │  [project]          │
.mypy.ini                      │  [project.optional] │
pytest.ini                     │  [tool.ruff]        │
                               │  [tool.mypy]        │
                               │  [tool.pytest]      │
                               │  [tool.setuptools]  │
                               │  [build-system]     │
                               └─────────────────────┘
```

**TOML 格式简介**：TOML 是一种配置文件格式，比 JSON 和 YAML 更易读。基本语法：

```toml
# 这是注释
key = "value"                   # 简单键值对
number = 42
flag = true

[section]                       # 区块标题
section_key = "section_value"   # 区块内的键值对

[section.subsection]            # 嵌套区块
nested_key = "nested_value"

list_item = ["a", "b", "c"]     # 数组
```

### 二、GrassSea 的 pyproject.toml 全景图

GrassSea 的配置文件包含以下主要区块：

```
pyproject.toml
│
├── [project]                       项目元信息
├── [project.optional-dependencies] 开发依赖
├── [tool.ruff]                     代码检查
├── [tool.ruff.lint]                代码检查规则
├── [tool.pytest.ini_options]       测试配置
├── [tool.mypy]                     类型检查
├── [tool.alembic]                  数据库迁移
├── [tool.setuptools.packages.find] 包发现
└── [build-system]                  构建系统
```

## 项目代码精讲

### [project] 区块 —— 项目元信息

```toml
[project]
name = "grasssea"
version = "0.1.0"
description = "白草沧智（GrassSea AI）— 面向船舶与海洋工程领域的 AI 原生多智能体协作平台"
requires-python = ">=3.11"
authors = [
    { name = "GrassSea AI Team" }
]
readme = "README.md"
license = { text = "MIT" }
```

| 字段 | 含义 | 必填？ |
|------|------|--------|
| `name` | 包名，`pip install` 时使用 | 是 |
| `version` | 版本号，遵循语义化版本 | 是 |
| `description` | 一句话描述 | 否 |
| `requires-python` | 最低 Python 版本 | 是 |
| `authors` | 作者列表 | 否 |
| `readme` | README 文件路径 | 否 |
| `license` | 许可证 | 否 |

**版本号约定**（语义化版本 Semantic Versioning）：

```
主版本.次版本.修订版本
MAJOR.MINOR.PATCH
  │     │     └── 修复 bug，不影响 API
  │     └──────── 新增功能，向后兼容
  └────────────── 不兼容的 API 变更

0.1.0  = 开发初期，API 不稳定
1.0.0  = 第一个正式版本
```

### dependencies —— 项目依赖

```toml
dependencies = [
    "fastapi>=0.110.0",              # Web 框架
    "uvicorn[standard]>=0.27.0",     # ASGI 服务器
    "sqlalchemy[asyncio]>=2.0.25",   # ORM（支持异步）
    "asyncpg>=0.29.0",              # PostgreSQL 异步驱动
    "alembic>=1.13.0",              # 数据库迁移
    "motor>=3.3.0",                 # MongoDB 异步驱动
    "redis>=5.0.0",                 # Redis 客户端
    "pymilvus>=2.4.0",              # 向量数据库
    "pydantic>=2.6.0",              # 数据验证
    "pydantic-settings>=2.1.0",     # 配置管理
    "structlog>=24.0.0",            # 结构化日志
    "httpx>=0.27.0",                # HTTP 客户端（异步）
    "langchain>=0.1.0",             # LLM 框架
    "openai>=1.12.0",               # OpenAI SDK
    # ... 省略其余
]
```

**版本号的写法含义**：

| 写法 | 含义 | 示例 |
|------|------|------|
| `>=0.110.0` | 不小于 0.110.0 | 可以安装 0.110.0、0.111.0、0.200.0 |
| `~=0.110.0` | 兼容版本（主次版本不变） | 只能装 0.110.x |
| `==0.110.0` | 精确锁定 | 只能装 0.110.0 |

GrassSea 使用 `>=` 是因为：项目处于快速开发期，希望自动获得依赖的 bug 修复和功能更新。生产环境应该使用 `poetry.lock` 或 `pip freeze > requirements.txt` 固定版本。

### `[project.optional-dependencies]` —— 开发依赖

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",               # 测试框架
    "pytest-asyncio>=0.23.0",      # 异步测试支持
    "pytest-cov>=4.1.0",           # 测试覆盖率
    "ruff>=0.2.0",                 # 代码检查（替代 flake8）
    "mypy>=1.8.0",                 # 类型检查
    "bandit>=1.7.0",               # 安全检查
    "pre-commit>=3.6.0",           # Git 提交前自动检查
]
```

这是 GrassSea 中非常有价值的设计。注意区分：

```
dependencies            → pip install grasssea（用户安装）
optional-dependencies   → pip install "grasssea[dev]"（开发者安装）
                         → pip install -e ".[dev]"（开发模式安装）
```

`dev` 是一个"特征名"（extra），可以自定义任意名称：

```toml
[project.optional-dependencies]
dev = ["pytest", "ruff"]           # 开发工具
test = ["pytest", "pytest-cov"]    # 仅测试
docs = ["sphinx", "myst-parser"]   # 文档生成
all = ["pytest", "ruff", "sphinx"] # 全量安装
```

安装方式：
```bash
pip install -e ".[dev]"           # 安装开发依赖
pip install -e ".[dev,test]"      # 同时安装多个特征
pip install -e ".[all]"           # 安装所有可选依赖
```

### `[tool.ruff]` —— 代码检查与格式化

```toml
[tool.ruff]
target-version = "py311"       # 目标 Python 版本
line-length = 100              # 每行最大长度

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]   # 启用的规则
```

ruff 是新一代 Python linter（用 Rust 编写，速度极快）。规则代码含义：

| 规则 | 含义 | 示例 |
|------|------|------|
| `E` | pycodestyle 错误 | 缩进、空格、空行 |
| `F` | Pyflakes 逻辑错误 | 未使用的变量、未定义的名称 |
| `I` | isort 导入排序 | 导入顺序不规范 |
| `N` | pep8-naming 命名 | 变量/类/函数命名 |
| `W` | pycodestyle 警告 | 建议性改进 |
| `UP` | pyupgrade 升级 | 可用新语法替代旧语法 |

运行方式：
```bash
ruff check .          # 检查代码
ruff check --fix .    # 自动修复
ruff format .         # 格式化代码
```

### `[tool.mypy]` —— 类型检查

```toml
[tool.mypy]
python_version = "3.11"
strict = true                      # 严格模式（推荐）
ignore_missing_imports = true      # 忽略没有类型标注的第三方库
```

`strict = true` 启用了 mypy 的所有严格检查。这意味着项目中所有函数必须有类型标注：

```python
# mypy 会报错
def add(a, b):
    return a + b

# mypy 不会报错
def add(a: int, b: int) -> int:
    return a + b
```

`ignore_missing_imports = true` 是必要的——很多第三方库（如 langchain）没有完整的类型标注，不忽略的话 mypy 会报大量误报。

### `[tool.pytest.ini_options]` —— 测试配置

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"              # 自动检测异步测试
testpaths = ["tests"]              # 测试文件目录
addopts = "-v --cov=shared --cov=services --cov=agents --cov=tools --cov-report=term-missing"
```

`asyncio_mode = "auto"` 让 pytest 自动处理 `async def test_xxx()` 函数，不需要手动加 `@pytest.mark.asyncio`。

`addopts` 是 pytest 的默认命令行参数，含义：

| 参数 | 含义 |
|------|------|
| `-v` | 详细输出 |
| `--cov=shared` | 统计 shared 目录的覆盖率 |
| `--cov-report=term-missing` | 在终端显示未覆盖的行号 |

### `[tool.setuptools.packages.find]` —— 包发现

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["shared*", "services*", "agents*", "tools*", "scripts*"]
```

这段配置告诉 setuptools："在项目根目录下，找所有匹配这些模式（shared*、services* 等）的 Python 包"。

**为什么需要手动指定？** 因为 setuptools 默认只会发现顶层包（如 `shared/`），不会自动发现 `services/` 下的子包。通过 `include` 明确列出，确保所有子包都被安装。

### `[build-system]` —— 构建系统声明

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

这告诉 pip："构建这个项目时，需要先安装 setuptools（版本 >= 68.0），然后调用 `setuptools.build_meta` 来执行实际的构建"。对于大多数 Python 项目，这两行是标准写法。

## 手把手实践

### 任务：为一个小项目编写 pyproject.toml

假设你要创建一个名为 `ship-calc` 的计算库，依赖 numpy 和 scipy。

**步骤 1**：创建项目目录和文件

```bash
mkdir ship-calc && cd ship-calc
mkdir ship_calc
touch ship_calc/__init__.py
touch ship_calc/hydrostatics.py
```

**步骤 2**：编写 `pyproject.toml`

```toml
[project]
name = "ship-calc"
version = "0.1.0"
description = "船舶静水力计算库"
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.26.0",
    "scipy>=1.12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.2.0",
]

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

**步骤 3**：安装并验证

```bash
pip install -e ".[dev]"
python -c "import ship_calc; print('成功!')"
ruff check .
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "pyproject.toml 教程" — 了解 TOML 格式和 Python 项目配置
2. "Python ruff 代码检查" — 学习使用 ruff 替代 flake8
3. "mypy 类型检查" — 理解 Python 类型标注的价值

## 常见问题与排错

### Q1: `pip install -e ".[dev]"` 报错 `zsh: no matches found`
**原因**：shell 把 `[...]` 解析为通配符。
**解决**：加引号 — `pip install -e ".[dev]"` 或 `pip install -e '.[dev]'`

### Q2: ruff 提示 `I001 Import block is un-sorted`
**原因**：导入语句顺序不符合规范。
**解决**：运行 `ruff check --fix .` 自动修复。规范顺序是：标准库 → 第三方库 → 本地模块，每组之间空一行。

### Q3: mypy 报大量第三方库的 `Cannot find module` 错误
**原因**：第三方库没有类型标注。
**解决**：在 `[tool.mypy]` 中设置 `ignore_missing_imports = true`。

### Q4: 修改 pyproject.toml 后依赖没有更新
**解决**：重新运行 `pip install -e ".[dev]"`。修改 `pyproject.toml` 不会自动触发依赖更新。

## 练习任务

1. **阅读完整文件**：打开 GrassSea 的 `pyproject.toml` 文件，逐行阅读每个依赖，尝试理解每个库的用途。对于不了解的库（如 `motor`、`alembic`、`pymilvus`），先去 PyPI 搜索它们的简介。

2. **研究一个工具配置**：选择一个你感兴趣的工具（ruff、mypy、或 pytest），查阅其官方文档，找出 GrassSea 配置中没有使用但可能很有用的选项。

3. **新增可选依赖组**：假设 GrassSea 新增一个 `docs` 依赖组，用于文档生成（sphinx、myst-parser），写出完整的 `[project.optional-dependencies]` 配置。

4. **理解依赖链**：画出 GrassSea 依赖关系图——哪些依赖是核心（被所有模块使用），哪些是特定场景（只用于某个服务）。
