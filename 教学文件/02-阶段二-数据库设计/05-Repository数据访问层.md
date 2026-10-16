# 05 - Repository 数据访问层

## 学习目标

学完本文件后，你将能够：
1. 理解 Repository 模式的目的和价值
2. 掌握 Python 泛型（Generic）在 Repository 中的应用
3. 理解 SQLAlchemy 异步会话的生命周期
4. 能够为任意模型编写专用的 Repository 子类

## 前置知识

- 了解 SQLAlchemy ORM 的基本查询（SELECT、WHERE、INSERT）
- 理解 Python 类继承
- 了解类型提示中的 `TypeVar`（泛型）概念

## 概念讲解

### 一、什么是 Repository 模式

在直接使用 ORM 的代码中，SQL 查询散落在各处：

```python
# 直接使用 ORM —— 查询代码到处都是

# 在 main.py 中
result = await session.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()

# 在 auth.py 中
result = await session.execute(select(User).where(User.email == email))
user = result.scalar_one_or_none()

# 在 admin.py 中
result = await session.execute(select(User).where(User.role == "admin"))
admins = result.scalars().all()
```

问题：
1. **重复代码**：同一个查询逻辑写了三遍
2. **难以修改**：如果要加软删除过滤，需要改三处
3. **难以测试**：无法 mock 数据访问逻辑
4. **职责不清**：业务代码混合了 SQL 细节

**Repository 模式**将数据访问逻辑封装到一个专门的类中：

```
业务代码                          Repository                   数据库
(Service/Agent)                  (数据访问层)                   (PG/Mongo)

┌──────────┐                    ┌──────────────┐             ┌──────────┐
│ getUser  │ ──── get_by_id ──> │ UserRepo     │ ──── SQL ──> │PostgreSQL│
│          │ <── User 对象 ──── │              │ <── 结果 ─── │          │
│ create   │ ──── create ─────> │ BaseRepo     │             │          │
│          │ <── User 对象 ──── │ (通用CRUD)    │             │          │
└──────────┘                    └──────────────┘             └──────────┘

好处:
- 业务代码不知道底层是 SQL 还是 Mongo
- SQL 逻辑集中管理，改一处生效全局
- 测试时只需 mock Repository
```

### 二、Python 泛型（Generic）简介

GrassSea 的 `BaseRepository` 使用了泛型，让一个类能适用于任何模型。

```python
from typing import TypeVar, Generic

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    model: type[ModelType]
    # ...
```

**`TypeVar` 的工作原理**：

```python
# 不使用泛型 —— 每张表都要写一个 Repository
class UserRepository:
    async def get_by_id(self, id) -> User: ...

class ProjectRepository:
    async def get_by_id(self, id) -> Project: ...

# 使用泛型 —— 一个基类通用
class BaseRepository(Generic[ModelType]):
    async def get_by_id(self, id) -> ModelType | None: ...

# 使用时指定具体的 ModelType
class UserRepository(BaseRepository[User]):      # ModelType = User
    model = User                                 # get_by_id 返回 User | None

class ProjectRepository(BaseRepository[Project]):  # ModelType = Project
    model = Project                               # get_by_id 返回 Project | None
```

这就好比一个"模具"，填入不同的模型类型，就自动生成对应的 Repository。

## 项目代码精讲

### BaseRepository —— 通用 CRUD 模板

```python
class BaseRepository(Generic[ModelType]):
    """通用 Repository 基类"""

    model: type[ModelType]          # 子类必须定义

    def __init__(self, session: AsyncSession):
        self.session = session
```

**注意**：`model` 没有在 `__init__` 中赋值，而是在子类的类体中定义。这意味着每个具体的 Repository 类绑定到一个特定的模型。

#### get_by_id —— 根据 ID 查询

```python
    async def get_by_id(self, id: UUID | str) -> Optional[ModelType]:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
```

**SQLAlchemy 异步查询的固定模式**：

```
1. select(模型)                 → 构造 SELECT 语句
2. .where(条件)                 → 添加 WHERE 过滤
3. session.execute(stmt)        → 异步执行
4. result.scalar_one_or_none()  → 提取结果（单条或 None）
5. result.scalars().all()       → 提取结果（多条列表）
```

**`scalar_one_or_none()` vs `scalars().all()`**：

```python
# 查询单条：最多返回 1 行
user = result.scalar_one_or_none()    # User | None

# 查询多条：返回列表
users = list(result.scalars().all())  # list[User]
```

#### get_all —— 分页查询

```python
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())
```

分页参数约定：
- `skip`：跳过多少条（也常叫 `offset`）
- `limit`：取多少条

```python
# 第1页：skip=0, limit=20  → 取 1-20 条
# 第2页：skip=20, limit=20 → 取 21-40 条
# 第3页：skip=40, limit=20 → 取 41-60 条
```

#### count —— 统计

```python
    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one()
```

`**filters`（关键字参数展开）允许灵活过滤：

```python
await repo.count(status="active")                # 统计活跃项目
await repo.count(status="active", owner_id=uid)  # 统计某用户的活跃项目
```

`getattr(self.model, key)` 动态获取模型类的属性，将字符串 `"status"` 转换为 `Project.status`。

#### create —— 创建

```python
    async def create(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        await self.session.flush()    # 发送 SQL 但不提交
        await self.session.refresh(obj)  # 刷新对象（获取数据库生成的默认值）
        return obj
```

**`flush` vs `commit`**：

| 操作 | 效果 | 事务 |
|------|------|------|
| `flush()` | 发送 SQL 到数据库，但不提交 | 仍可回滚 |
| `commit()` | 提交事务，数据永久保存 | 不可回滚 |

GrassSea 在 Repository 层使用 `flush()`，在 FastAPI 的依赖注入层统一 `commit()`：

```python
# shared/models/database.py
async def get_pg_session():
    async with pg_session_factory() as session:
        try:
            yield session
            await session.commit()     # 请求结束后统一提交
        except Exception:
            await session.rollback()   # 出错统一回滚
            raise
```

#### update —— 更新

```python
    async def update(self, obj: ModelType, **values: Any) -> ModelType:
        for key, value in values.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
```

使用方式：

```python
project = await repo.get_by_id(project_id)
await repo.update(project, status=ProjectStatus.ARCHIVED, name="新项目名")
```

`hasattr(obj, key)` 的安全检查防止向模型对象设置不存在的属性。

#### delete —— 删除

```python
    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def delete_by_id(self, id: UUID | str) -> bool:
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.flush()
        return result.rowcount > 0
```

两种删除方式：
- `delete(obj)`：先查出对象，再删除（两次查询，但可以触发 ORM 事件）
- `delete_by_id(id)`：直接发 DELETE SQL（一次查询，性能更好）

### ProjectRepository —— 专用 Repository

```python
class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def get_by_code(self, code: str) -> Optional[Project]:
        result = await self.session.execute(
            select(Project).where(Project.code == code)
        )
        return result.scalar_one_or_none()
```

`model = Project` 是关键行——告诉 `BaseRepository` 这个 Repository 操作的是 `Project` 表。之后所有继承的 CRUD 方法（`get_by_id`、`create`、`update`...）都自动针对 `Project` 模型。

#### 业务专用查询

```python
    async def get_by_owner(self, owner_id: UUID, skip: int = 0, limit: int = 50) -> list[Project]:
        result = await self.session.execute(
            select(Project)
            .where(Project.owner_id == owner_id)
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def archive_project(self, project_id: UUID) -> Optional[Project]:
        project = await self.get_by_id(project_id)
        if project:
            project.status = ProjectStatus.ARCHIVED
            await self.session.flush()
        return project
```

`archive_project` 组合了两个基础操作：`get_by_id` + `update`。Repository 除了封装 SQL，还可以封装业务操作。

### TaskRepository —— 任务专用操作

```python
class TaskRepository(BaseRepository[TaskRecord]):
    model = TaskRecord

    async def update_status(self, task_id: UUID, status: TaskStatus, error_message: str | None = None) -> None:
        values = {"status": status}
        if error_message:
            values["error_message"] = error_message
        await self.session.execute(
            update(TaskRecord).where(TaskRecord.id == task_id).values(**values)
        )
        await self.session.flush()

    async def update_progress(self, task_id: UUID, progress: float) -> None:
        await self.session.execute(
            update(TaskRecord).where(TaskRecord.id == task_id).values(progress=progress)
        )
        await self.session.flush()
```

注意这里使用了**批量 UPDATE**（`update(TaskRecord).where(...).values(...)`），而不是先查后存。对于高频更新（如进度从 0% 到 100%），批量 UPDATE 只需要一条 SQL。

### ConversationRepository —— MongoDB 的 Repository

MongoDB 的 Repository 模式与 PostgreSQL 类似，但 API 不同：

```python
class ConversationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db[self.collection_name]

    async def add_message(self, session_id: str, role: str, content: str, sources=None) -> None:
        await self.collection.update_one(
            {"session_id": session_id},
            {"$push": {"messages": message}, "$set": {"updated_at": datetime.utcnow()}},
        )

    async def get_recent_sessions(self, user_id: str, limit: int = 20) -> list[dict]:
        cursor = self.collection.find({"user_id": user_id}).sort("updated_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
```

## 手把手实践

### 任务：为 ShipSpec 模型编写 Repository

承接上一节创建的 `ShipSpec` 模型。

```python
# shared/models/repository/ship_spec.py
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.postgres.ship_spec import ShipSpec
from shared.models.repository.base import BaseRepository

class ShipSpecRepository(BaseRepository[ShipSpec]):
    model = ShipSpec

    async def get_by_project(self, project_id: UUID) -> list[ShipSpec]:
        result = await self.session.execute(
            select(ShipSpec).where(ShipSpec.project_id == project_id)
        )
        return list(result.scalars().all())

    async def get_latest(self, project_id: UUID) -> Optional[ShipSpec]:
        result = await self.session.execute(
            select(ShipSpec)
            .where(ShipSpec.project_id == project_id)
            .order_by(ShipSpec.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
```

使用方式（在 FastAPI 路由中）：

```python
@app.get("/projects/{project_id}/specs")
async def get_specs(project_id: UUID, session: AsyncSession = Depends(get_pg_session)):
    repo = ShipSpecRepository(session)
    specs = await repo.get_by_project(project_id)
    return specs
```

## 视频学习资源

在 B 站搜索以下关键词：
1. "Repository 模式 Python" — 数据访问层的设计模式
2. "Python 泛型 TypeVar" — 理解泛型在代码复用中的作用
3. "SQLAlchemy 异步查询" — async session 的使用方式

## 常见问题与排错

### Q1: BaseRepository 和具体 Repository 的关系是什么？
BaseRepository 是"模板"，提供通用的 CRUD（增删改查）。具体 Repository（如 ProjectRepository）继承模板，加上自己特有的查询。使用哪种取决于需求。

### Q2: 为什么 Repository 用 flush 而不是 commit？
事务控制放在更上层（FastAPI 依赖注入或 Service 层），Repository 只负责数据操作。这保证了"一个请求 = 一个事务"的语义。

### Q3: MongoDB 的 Repository 不用 BaseRepository？
因为 MongoDB 的 API（insert_one、update_one）与 SQLAlchemy 完全不同，无法共享基类。但设计思想相同——封装数据访问逻辑。

### Q4: 能否在 Repository 中进行 JOIN 查询？
可以。Repository 是 Python 类，方法内可以写任意复杂的 SQLAlchemy 查询：

```python
async def get_project_with_owner(self, project_id: UUID):
    result = await self.session.execute(
        select(Project, User)
        .join(User, Project.owner_id == User.id)
        .where(Project.id == project_id)
    )
    return result.one_or_none()
```

## 练习任务

1. **完善 BaseRepository**：在 `BaseRepository` 中添加 `find_by` 方法，接受 `**filters` 参数，支持按任意字段过滤查询。

2. **编写新 Repository**：为 `PromptTemplate` 模型编写 `PromptTemplateRepository`，包含 `get_active_templates`（返回 `is_active=True` 的模板）、`get_by_category`（按类别过滤）、`get_by_model_family`（按模型族过滤）。

3. **MongoDB Repository 泛化**：尝试为 MongoDB 也设计一个通用的 `BaseMongoRepository`，包含 `find_one`、`find_many`、`insert_one`、`update_one`、`delete_one` 通用方法。

4. **对比分析**：对比 `TaskRepository.update_status`（批量 UPDATE）和 `ProjectRepository.archive_project`（查后改），分析两种更新方式的适用场景和性能差异。
