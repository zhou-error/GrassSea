# 02 - PostgreSQL 模型设计

## 学习目标

学完本文件后，你将能够：
1. 理解 SQLAlchemy ORM 模型的定义方式
2. 掌握 Mixin 模式（UUIDMixin、TimestampMixin）复用代码
3. 理解外键关联、枚举类型、JSONB 列的使用场景
4. 读懂 GrassSea 的 7 张 PostgreSQL 表设计

## 前置知识

- 基本 SQL 知识（CREATE TABLE、PRIMARY KEY、FOREIGN KEY）
- Python 类的继承和属性
- 了解 Python 枚举（enum）

## 概念讲解

### 一、SQLAlchemy ORM —— 用 Python 类描述数据库表

SQLAlchemy 是 Python 最流行的 ORM（Object-Relational Mapping，对象关系映射）。它的核心思想是：**用 Python 类来表示数据库表，用类的属性来表示表的列。**

```python
# SQL 语句方式                                      # SQLAlchemy ORM 方式
CREATE TABLE users (                                 class User(Base):
    id UUID PRIMARY KEY,         ←──对应——→             id: Mapped[uuid.UUID]
    name VARCHAR(100) NOT NULL,  ←──对应——→             name: Mapped[str]
    email VARCHAR(200) UNIQUE    ←──对应——→             email: Mapped[str]
);                                                   )

# 插入数据                                           # 插入数据
INSERT INTO users VALUES (...);                       user = User(name="张三", ...)
                                                     session.add(user)

# 查询数据                                           # 查询数据
SELECT * FROM users WHERE id=1;                       user = await session.get(User, 1)
```

ORM 的优势：
- **类型安全**：编译时就能发现字段名拼写错误
- **自动迁移**：配合 Alembic 自动生成 DDL
- **数据库无关**：换数据库（PG→MySQL）只需改连接串
- **Pythonic**：新手更容易理解

### 二、Mixin 模式 —— 避免重复代码

在 GrassSea 的 7 张表中，每张表都需要三个字段：`id`（主键）、`created_at`（创建时间）、`updated_at`（更新时间）。

如果每张表都重复写一遍这三个字段，代码又臭又长。GrassSea 使用了 **Mixin 模式**：

```python
# shared/models/postgres/base.py

class UUIDMixin:
    """UUID 主键 mixin"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

class TimestampMixin:
    """时间戳 mixin"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

# 使用：只需要多继承
class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"
    # 只需要写项目特有的字段
    name: Mapped[str] = mapped_column(String(200))
```

**Mixin 的工作原理**：Python 支持多继承。`Project` 同时继承 `Base`、`UUIDMixin`、`TimestampMixin`，自动获得 `id`、`created_at`、`updated_at` 三个字段。

```
继承关系:

          Base            UUIDMixin       TimestampMixin
  (DeclarativeBase)     (UUID 主键)      (创建/更新时间)
           │                 │                  │
           └────────┬────────┴────────┬─────────┘
                    │                 │
                    v                 v
               Project           TaskRecord
```

**UUID 主键 vs 自增整数主键**：

| 特性 | UUID | 自增整数 |
|------|------|---------|
| 示例 | `a1b2c3d4-e5f6-...` | `1, 2, 3, ...` |
| 全局唯一 | 是（分布式友好） | 否（单库唯一） |
| 安全性 | 不可猜测（无法遍历） | 可猜测（/users/1, /users/2） |
| 存储大小 | 16 字节 | 4-8 字节 |
| 索引性能 | 略低 | 高 |

GrassSea 选择 UUID 是因为：多服务环境中不会产生 ID 冲突，且对外 API 不暴露数据量。

### 三、SQLAlchemy 2.0 新式映射语法

GrassSea 使用 SQLAlchemy 2.0 的新式声明方式（Mapped 类型标注）：

```python
# 旧式写法（SQLAlchemy 1.x）               # 新式写法（SQLAlchemy 2.0）
name = Column(String(200))                  name: Mapped[str] = mapped_column(String(200))
status = Column(Enum(ProjectStatus))        status: Mapped[ProjectStatus] = mapped_column(SAEnum(ProjectStatus))
```

新式写法的好处：
- IDE 能提供类型提示和自动补全
- mypy 能检查类型错误
- 代码更简洁

## 项目代码精讲

### 表 1：projects（项目表）

```python
class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    ship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ship_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

设计要点：

| 字段 | 类型 | 特殊约束 | 设计原因 |
|------|------|---------|---------|
| `code` | String(50) | UNIQUE | 项目编号全局唯一，如 "GS-2026-001" |
| `status` | Enum | 默认 ACTIVE | 状态机：ACTIVE → COMPLETED/ARCHIVED |
| `owner_id` | UUID → FK | 外键到 users | 每个项目有唯一负责人 |
| `ship_type` | String(100) | 可空 | 船舶类型，如"散货船""油船" |

**`str | None` 语法**：Python 3.10+ 的联合类型，等价于 `Optional[str]`。表示该字段可以为 NULL。

**SQLAlchemy 枚举**：使用 `SAEnum(ProjectStatus)` 而非 `String`，在数据库层存储为枚举类型，避免无效值（如 `"deleted"`）写入。

### 关联表：project_members（项目成员）

```python
project_members = Table(
    "project_members",
    Base.metadata,
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), nullable=False, default="engineer"),
)
```

这是多对多关联的**中间表**。一个项目有多个成员，一个成员参与多个项目：

```
Project ──┐                    ┌── User
          │                    │
          ├── project_members ──┤
          │  project_id (FK)    │
          │  user_id (FK)       │
          │  role               │
          └─────────────────────┘
```

**级联删除 `ondelete="CASCADE"`**：当删除一个项目时，自动删除该项目所有的成员关联记录。

### 表 2：task_records（任务记录表）

```python
class TaskRecord(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "task_records"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),
        ForeignKey("projects.id"), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dag_definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
```

**任务类型枚举**：

```python
class TaskType(str, enum.Enum):
    SIMPLE_CHAT = "simple_chat"                # 简单对话
    KNOWLEDGE_QA = "knowledge_qa"              # 知识库问答
    TOOL_CALL = "tool_call"                    # 工具调用
    PROFESSIONAL_TASK = "professional_task"    # 专业任务（如稳性计算）
    SUB_AGENT_ORCHESTRATION = "sub_agent_orchestration"  # 子智能体编排
```

**任务状态枚举**：

```python
class TaskStatus(str, enum.Enum):
    PENDING = "pending"         # 等待执行
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消
    WAITING_USER = "waiting_user"  # 等待用户输入
```

**JSONB 列**：`input_data`、`output_data`、`dag_definition` 使用 JSONB 类型。JSONB 是 PostgreSQL 特有的二进制 JSON 格式，支持索引和查询：

```python
# 存储复杂结构
task.input_data = {
    "question": "计算这艘船的稳性",
    "parameters": {"ship_id": "xxx", "load_condition": "full_load"},
    "attachments": ["file1.pdf", "file2.xlsx"],
}
```

### 表 3：offset_tables（型值表）

```python
class OffsetTable(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "offset_tables"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("users.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    num_stations: Mapped[int] = mapped_column(Integer, nullable=True)
    num_waterlines: Mapped[int] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    offset_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

型值表是船舶工程特有的概念。它记录船体表面的三维坐标点。`num_stations`（站数）和 `num_waterlines`（水线数）描述型值表的规模。数据可以存在 MinIO 文件中（`file_path`）或直接存为 JSONB（`offset_data`）。

### 表 4：todo_items（待办事项表）

```python
class TodoItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "todo_items"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
        ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),
        ForeignKey("projects.id"), nullable=True, index=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),
        ForeignKey("users.id"), nullable=True)
    priority: Mapped[TodoPriority] = mapped_column(
        SAEnum(TodoPriority), default=TodoPriority.MEDIUM, nullable=False)
    status: Mapped[TodoStatus] = mapped_column(
        SAEnum(TodoStatus), default=TodoStatus.PENDING, nullable=False, index=True)
    due_date: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_records.id"), nullable=True)
```

设计亮点：
- `assignee_id` 和 `user_id` 分离：创建者和执行者可以是不同人
- `is_ai_generated`：标记 AI 自动生成的待办
- `source_task_id`：追溯待办的来源任务

### 表 5：system_configs（系统配置表）

```python
class SystemConfig(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False)
```

这是 Key-Value 模式的设计，允许运行时动态修改系统配置，不需要重启服务。

### 表 6：prompt_templates（Prompt 模板表）

```python
class PromptTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prompt_templates"

    template_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    model_family: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    few_shot_examples: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    output_format: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_limit: Mapped[int] = mapped_column(Integer, default=4096)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False)
```

Prompt 模板的核心字段：
- `template_id` + `version`：支持模板的版本管理
- `model_family`：不同模型族（DeepSeek/Claude/GPT）可能需要不同格式的 Prompt
- `user_prompt_template`：支持 `{{variable}}` 占位符
- `few_shot_examples`：少样本示例，JSONB 存储

## 手把手实践

### 任务：为 GrassSea 新增一张表

假设需要新增一张 `ship_specs`（船舶规格参数表）。

**步骤 1**：创建模型文件 `shared/models/postgres/ship_spec.py`

```python
"""船舶规格参数模型"""
from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from shared.models.database import Base
from shared.models.postgres.base import TimestampMixin, UUIDMixin


class ShipSpec(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ship_specs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    loa: Mapped[float] = mapped_column(Float, nullable=True)   # 总长
    b: Mapped[float] = mapped_column(Float, nullable=True)     # 型宽
    d: Mapped[float] = mapped_column(Float, nullable=True)     # 型深
    draft: Mapped[float] = mapped_column(Float, nullable=True) # 吃水
    displacement: Mapped[float] = mapped_column(Float, nullable=True) # 排水量
```

**步骤 2**：在 `__init__.py` 中注册

```python
from shared.models.postgres.ship_spec import ShipSpec

__all__ = [..., "ShipSpec"]
```

**步骤 3**：生成迁移

```bash
alembic revision --autogenerate -m "add ship_specs table"
alembic upgrade head
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "SQLAlchemy 2.0 教程" — 学习新式 Mapped 语法的完整用法
2. "PostgreSQL JSONB 实战" — JSONB 列的查询和索引优化
3. "Python Enum 枚举" — 理解枚举在数据模型中的应用

## 常见问题与排错

### Q1: `Mapped` 是什么？和 `Column` 有什么区别？
`Mapped` 是 SQLAlchemy 2.0 引入的类型标注方式，配合 `mapped_column()` 使用。它提供了更好的类型提示支持。旧项目用 `Column`，新项目推荐用 `Mapped`。

### Q2: JSONB 和 JSON 列类型有什么区别？
- `JSON`：存储为文本，每次读写都要解析
- `JSONB`：存储为二进制，支持索引和高效查询

GrassSea 统一使用 JSONB。

### Q3: 为什么要用 Enum 而不是 String？
使用 String 存状态值的问题是：任何人都可以写入 `"deleted"` 这样的无效值。Enum 在数据库层约束了只能写入预定义的值。

### Q4: `nullable=True` 和 `Optional[...]` 的关系？
`Mapped[str | None]` 表示 Python 类型可为 None，`nullable=True` 表示数据库列允许 NULL。两者通常一起使用。如果 Python 类型标注了 `str | None` 但数据库列设置了 `nullable=False`，运行时可能出错。

## 练习任务

1. **画出 ER 图**：根据 7 张表的外键关系，手绘 GrassSea PostgreSQL 数据库的 ER 图（实体-关系图）。

2. **分析索引策略**：检查每张表的 `index=True` 设置，分析每个索引的查询场景（即"什么查询会用到这个索引"）。

3. **设计新表**：GrassSea 需要一个"消息通知"功能。设计一张 `notifications` 表，包含消息类型（comment/mention/system）、接收用户、关联项目、已读状态、内容等字段。使用 UUIDMixin 和 TimestampMixin。
