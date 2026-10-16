# SQLAlchemy 异步 ORM — 数据库操作的核心

## 学习目标

- 理解 ORM（对象关系映射）的概念和价值
- 掌握 SQLAlchemy 2.0 声明式模型定义
- 理解 `async_sessionmaker` 异步会话管理
- 能定义一对多、多对多关系并正确使用外键
- 了解 Alembic 数据库迁移的基本概念

## 前置知识

- Python 类与继承
- 异步编程基础（`async`/`await`）
- Pydantic 数据模型基础
- 关系型数据库基本概念（表、行、列、主键、外键）

---

## 1. 概念讲解

### 1.1 为什么需要 ORM？

直接写 SQL 操作数据库：

```python
# 原始 SQL 方式
cursor.execute("SELECT * FROM projects WHERE status = 'active'")
rows = cursor.fetchall()
for row in rows:
    print(row[1])  # 哪个索引对应 name？容易搞混！
```

问题很明显：
1. 字符串拼 SQL 容易出错，有 SQL 注入风险
2. 查询结果没有类型提示，IDE 无法帮你补全
3. 表结构改了（加了一列），所有 SQL 都得检查一遍
4. Python 对象和数据库行之间需要手动转换

ORM 的作用就是**把数据库表映射为 Python 类**：

```python
# ORM 方式 — 用 Python 对象操作数据库
async with session_factory() as session:
    result = await session.execute(
        select(Project).where(Project.status == ProjectStatus.ACTIVE)
    )
    projects = result.scalars().all()
    for p in projects:
        print(p.name)   # IDE 有智能提示！类型明确！
```

### 1.2 核心概念图解

```
┌──────────────────────────────────────────────────────┐
│              SQLAlchemy ORM 架构                      │
│                                                      │
│   Python 代码层         ORM 映射层      数据库层       │
│  ┌─────────────┐     ┌───────────┐   ┌──────────┐  │
│  │ class Project│ ←→  │ Declarative│ ←→ │ projects │  │
│  │  name: str   │     │   Base     │   │  表      │  │
│  │  status: Enum│     │ (映射器)   │   │  name列  │  │
│  │  owner_id:.. │     └───────────┘   │  status列│  │
│  └─────────────┘                      └──────────┘  │
│                                                      │
│  异步引擎 (create_async_engine)                       │
│    │                                                 │
│    └──→ async_sessionmaker                           │
│           │                                          │
│           └──→ AsyncSession (async with ...)         │
│                  │                                   │
│                  └──→ execute(select(...))            │
└──────────────────────────────────────────────────────┘
```

**三个核心组件**：

| 组件 | 作用 | GrassSea 中的位置 |
|------|------|-------------------|
| `DeclarativeBase` | 所有模型的基类 | `shared/models/database.py` |
| `create_async_engine` | 创建异步数据库连接池 | 同上 |
| `async_sessionmaker` | 工厂函数，创建异步会话 | 同上 |

---

## 2. 项目代码精讲

> 🔗 **参考文件**：`shared/models/database.py`、`shared/models/postgres/base.py`、`shared/models/postgres/project.py`、`shared/models/postgres/task.py`

### 2.1 异步引擎与会话工厂

打开 `shared/models/database.py`：

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

settings = get_settings()

# 1. 创建异步引擎 — 管理数据库连接池
pg_engine = create_async_engine(
    settings.POSTGRES_URI,       # 连接字符串 (asyncpg 驱动)
    echo=settings.APP_DEBUG,     # DEBUG 模式下打印 SQL 语句
    pool_size=20,                # 连接池大小
    max_overflow=10,             # 最大溢出连接数
    pool_pre_ping=True,          # 使用前测试连接是否有效
)

# 2. 创建会话工厂
pg_session_factory = async_sessionmaker(
    pg_engine,
    class_=AsyncSession,         # 指定会话类
    expire_on_commit=False,      # 提交后不过期对象
)

# 3. 声明式基类
class Base(DeclarativeBase):
    """所有 ORM 模型都继承自这个类"""
    pass
```

逐行解析：
- **连接池**：`pool_size=20` + `max_overflow=10` 意味着最多 30 个并发数据库连接。异步引擎会自动管理连接的创建、复用和释放
- **会话工厂**：`pg_session_factory()` 每次调用创建一个新的数据库会话（事务上下文）
- **`expire_on_commit=False`**：提交后不清理对象状态，避免在异步上下文中触发延迟加载

### 2.2 依赖注入获取会话

```python
async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    """获取 PostgreSQL 异步会话 (用于 FastAPI 依赖注入)"""
    async with pg_session_factory() as session:
        try:
            yield session        # 提供会话给路由函数
            await session.commit()     # 请求成功，提交事务
        except Exception:
            await session.rollback()   # 请求失败，回滚
            raise                       # 重新抛出异常
```

> 💡 **提示**：这个函数是 FastAPI `Depends` 的标准用法。在路由中写 `session: AsyncSession = Depends(get_pg_session)` 就能自动获得会话。

### 2.3 模型定义 — Mixin 模式

打开 `shared/models/postgres/base.py`：

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from shared.models.database import Base

class TimestampMixin:
    """时间戳 mixin — 自动记录创建和更新时间"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

class UUIDMixin:
    """UUID 主键 mixin — 使用 UUID 而非自增 ID"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
```

**Mixin 模式**的好处：多个模型共享相同的字段定义（如每个表都需要 `id`、`created_at`、`updated_at`），通过继承即可复用，避免重复代码。

**`Mapped` 类型注解**：SQLAlchemy 2.0 的新写法，替代了旧的 `Column()` 风格。`Mapped[datetime]` 告诉类型检查器这个字段的类型，同时 `mapped_column()` 提供数据库列的详细配置。

### 2.4 模型定义 — Project 表

打开 `shared/models/postgres/project.py`：

```python
class Project(Base, UUIDMixin, TimestampMixin):
    """项目表"""
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

关键点：
- `__tablename__` 指定数据库中对应的表名
- `Base, UUIDMixin, TimestampMixin` 三重继承，分别提供：SQLAlchemy 基类能力、UUID 主键、时间戳
- `String(200)` 限制列长度
- `unique=True` 唯一约束
- `index=True` 为字段创建索引（加速查询）
- `ForeignKey("users.id")` 外键关联到 `users` 表的 `id` 列
- `str | None` 类型注解表示该字段可为 NULL

### 2.5 多对多关系 — 关联表

同一个文件中定义了一个多对多关联表：

```python
# 项目-成员关联表
project_members = Table(
    "project_members",
    Base.metadata,
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), nullable=False, default="engineer"),
)
```

这是一个**关联表**（Association Table），用于实现 `Project` 和 `User` 之间的多对多关系：
- 一个项目可以有多个成员
- 一个用户可以参与多个项目
- 关联表中额外存储了 `role`（角色）信息

`ondelete="CASCADE"` 意味着删除项目时，自动删除所有关联记录。

### 2.6 Task 模型 -- 包含 JSONB 字段

打开 `shared/models/postgres/task.py`：

```python
class TaskRecord(Base, UUIDMixin, TimestampMixin):
    """任务执行记录表"""
    __tablename__ = "task_records"

    task_type: Mapped[TaskType] = mapped_column(SAEnum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dag_definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
```

**JSONB 字段**：PostgreSQL 特有的 JSON 类型，支持索引和查询。适合存储结构不固定的数据（如任务的输入输出、DAG 定义）。

---

## 3. 手把手实践

### 3.1 定义你的第一个模型

```python
from datetime import datetime
from sqlalchemy import String, Text, Float, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import enum

class Base(DeclarativeBase):
    pass

class ShipStatus(str, enum.Enum):
    DESIGN = "design"
    CONSTRUCTION = "construction"
    DELIVERED = "delivered"

class Ship(Base):
    __tablename__ = "ships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    imo_number: Mapped[str] = mapped_column(String(7), unique=True)
    ship_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[ShipStatus] = mapped_column(
        SAEnum(ShipStatus), default=ShipStatus.DESIGN
    )
    length_m: Mapped[float] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### 3.2 异步创建表和执行查询

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

async def main():
    # 使用 SQLite 内存数据库（方便测试，不需要 PostgreSQL）
    engine = create_async_engine("sqlite+aiosqlite:///test.db", echo=True)

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 创建会话工厂
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 插入数据
    async with session_factory() as session:
        ship = Ship(name="东方红", imo_number="1234567", ship_type="油轮", length_m=200.0)
        session.add(ship)
        await session.commit()
        print(f"创建了船舶: {ship.name}, ID={ship.id}")

    # 查询数据
    async with session_factory() as session:
        result = await session.execute(select(Ship).where(Ship.ship_type == "油轮"))
        ships = result.scalars().all()
        for s in ships:
            print(f"  {s.name} (IMO: {s.imo_number})")

    await engine.dispose()

asyncio.run(main())
```

### 3.3 一对多关系

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped

class DesignCompany(Base):
    __tablename__ = "design_companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # 关系属性
    ships: Mapped[list["Ship"]] = relationship(back_populates="company")

class Ship(Base):
    __tablename__ = "ships"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    company_id: Mapped[int] = mapped_column(ForeignKey("design_companies.id"))
    # 反向关系
    company: Mapped["DesignCompany"] = relationship(back_populates="ships")
```

> ⚠️ **注意**：在异步模式下，`relationship` 的懒加载可能触发隐式 I/O。推荐使用 `selectinload()` 显式预加载关联数据。

---

## 4. 视频学习资源

在 B站搜索以下关键词：

- [B站搜索: SQLAlchemy 2.0 异步](https://search.bilibili.com/all?keyword=SQLAlchemy+2.0+异步) -- 异步 ORM 入门
- [B站搜索: SQLAlchemy ORM 入门教程](https://search.bilibili.com/all?keyword=SQLAlchemy+ORM+入门教程) -- ORM 基础概念
- [B站搜索: Alembic 数据库迁移](https://search.bilibili.com/all?keyword=Alembic+数据库迁移) -- 数据库版本管理

> 💡 **提示**：SQLAlchemy 官方文档（https://docs.sqlalchemy.org/en/20/）是必读资料，尤其是 ORM 部分和 asyncio 扩展部分。

---

## 5. 常见问题与排错

### Q1: `greenlet_spawn` 错误

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't use await_() here
```

**原因**：在非异步上下文中调用了异步 ORM 方法。

**解决**：确保在 `async with session_factory() as session:` 块内使用 `await`。

### Q2: 表已存在 / 表不存在

开发阶段快速迭代时，使用以下方式：

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.drop_all)   # 先删除所有表
    await conn.run_sync(Base.metadata.create_all)  # 再创建
```

> ⚠️ **警告**：`drop_all` 会删除所有数据！仅在开发环境使用。

### Q3: `Mapped` 类型注解报错

需要 Python 3.10+ 以及 SQLAlchemy 2.0+：

```bash
pip install sqlalchemy>=2.0
```

### Q4: 事务已关闭错误

```python
# 错误写法 — session 上下文已退出
async with session_factory() as session:
    ship = Ship(name="test")
    session.add(ship)
# session 已关闭，无法再操作 ship 对象

# 正确写法 — 在同一次会话内操作
async with session_factory() as session:
    ship = Ship(name="test")
    session.add(ship)
    await session.commit()  # 提交后才生效
    print(ship.id)          # 提交后可以访问生成的 id
```

### Q5: Alembic 是什么？

Alembic 是 SQLAlchemy 官方提供的数据库迁移工具。它的作用是：
- 记录数据库结构的每次变更（创建版本文件）
- 自动比较模型定义和实际数据库结构的差异
- 安全地升级/回滚数据库结构

在 GrassSea 项目中，首次创建表是通过 `Base.metadata.create_all`，但在生产环境中应使用 Alembic 管理迁移。

---

## 6. 练习任务

### 练习1：定义一个一对多模型
设计两个 SQLAlchemy 模型：
- `Shipyard`（造船厂）：id, name, location, established_year
- `Order`（订单）：id, shipyard_id（外键）, ship_name, contract_amount, order_date

要求每个 `Shipyard` 可以有多个 `Order`，建立一对多关系并使用 `relationship`。

### 练习2：阅读项目模型
打开 `shared/models/postgres/task.py`，逐行解释每个字段的类型、约束和业务含义。特别关注 `JSONB` 类型的 `input_data` 和 `output_data` 字段的设计思路。

### 练习3：编写异步查询
使用 `async_sessionmaker` 和 `select()` 编写一个异步函数 `get_active_tasks(session, user_id)`：
- 查询指定用户的所有状态为 RUNNING 或 PENDING 的任务
- 按 `created_at` 降序排列
- 限制返回前 10 条

---

*上一篇：[02-Pydantic数据模型.md](./02-Pydantic数据模型.md)*
*下一篇：[04-FastAPI框架进阶.md](./04-FastAPI框架进阶.md)*
