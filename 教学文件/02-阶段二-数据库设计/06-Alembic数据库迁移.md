# 06 - Alembic 数据库迁移

## 学习目标

学完本文件后，你将能够：
1. 理解数据库迁移的概念和必要性
2. 掌握 Alembic 的基本使用（生成迁移、执行迁移、回滚）
3. 理解 `env.py` 的异步配置
4. 能够在 GrassSea 中独立完成数据库变更流程

## 前置知识

- 了解数据库表的基本操作（CREATE TABLE、ALTER TABLE）
- 使用过 Git 版本控制（理解"版本"的概念）
- 了解 PostgreSQL 的基本操作

## 概念讲解

### 一、什么是数据库迁移

在开发过程中，数据模型会不断变化：

```
版本 1：用户表只有 id, name, email
版本 2：加了一个 avatar_url 字段
版本 3：加了一个 role 字段，删除了 age 字段
版本 4：拆出了 profiles 表，加了外键
```

如果没有迁移工具，每次变更都需要手动执行 SQL：

```sql
-- 版本1 → 版本2：手动执行
ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500);

-- 但是：别人怎么知道要执行这条 SQL？
-- 如果忘了执行呢？
-- 如果执行错了怎么撤销？
```

**Alembic** 就是解决这些问题的工具。它用 Python 脚本记录每次数据库变更，像 Git 管理代码版本一样管理数据库版本。

```
Git 管理代码:                            Alembic 管理数据库:

git log                                 alembic history
commit abc: 添加登录功能                 revision 001: 创建 users 表
commit def: 修复登录 bug                revision 002: 添加 avatar_url 列
commit ghi: 添加注册功能                 revision 003: 添加 role 列

git checkout abc                        alembic downgrade 001
(回到 abc 版本的代码)                    (回到 001 版本的数据库结构)

git pull                                alembic upgrade head
(更新到最新代码)                          (更新到最新数据库结构)
```

### 二、Alembic 的核心概念

```
迁移脚本 (Migration Script)      版本链 (Revision Chain)         迁移环境 (env.py)

┌────────────────────┐          ┌────────────────────┐       ┌────────────────────┐
│ a1b2c3_create_users│          │ 001                 │      │ env.py             │
│                    │          │  ↓ (downgrade)     │      │                    │
│ def upgrade():     │          │ 002                 │      │ - 数据库连接配置     │
│   create_table()   │          │  ↓                  │      │ - 自动发现模型变化    │
│                    │          │ 003 (head)          │      │ - 在线/离线模式      │
│ def downgrade():   │          └────────────────────┘      └────────────────────┘
│   drop_table()     │
└────────────────────┘
```

每个迁移脚本包含两个函数：
- `upgrade()`：执行变更（向前）
- `downgrade()`：撤销变更（向后）

这就保证了数据库变更的**可逆性**。如果新版本有问题，可以回滚到上一个版本。

### 三、Alembic 的两种工作模式

**1. 自动生成模式（autogenerate）**：
```bash
# Alembic 比对 Python 模型和当前数据库，自动生成迁移脚本
alembic revision --autogenerate -m "添加 ship_specs 表"
```

**2. 手动编写模式**：
```bash
# 生成空白迁移脚本，自己写 upgrade/downgrade
alembic revision -m "手动修改索引"
```

GrassSea 主要使用自动生成模式——修改 SQLAlchemy 模型后，运行 autogenerate，Alembic 自动检测变化。但对于复杂变更（如数据迁移、索引重命名），需要手动编写。

## 项目代码精讲

### Alembic 目录结构

```
alembic.ini                   # 配置文件（位于项目根目录）
shared/models/alembic/
├── env.py                  # 迁移环境（Python）
├── script.py.mako          # 迁移脚本模板
└── versions/               # 迁移版本文件
    ├── __init__.py
    └── xxxx_create_xxx.py  # 具体迁移脚本
```

### alembic.ini —— 配置文件

```ini
[alembic]
script_location = %(here)s/shared/models/alembic
prepend_sys_path = .
sqlalchemy.url =          # 留空：由 env.py 从 .env 的 POSTGRES_URI 注入
```

| 配置项 | 含义 |
|--------|------|
| `script_location` | 迁移脚本目录位置（`%(here)s/shared/models/alembic`） |
| `prepend_sys_path` | 将当前目录加入 Python 搜索路径 |
| `sqlalchemy.url` | 留空；实际连接串由 `env.py` 从 `.env` 读取 |

**注意（本项目实际做法）**：`alembic.ini` 位于项目根目录，且**不维护连接串**。`shared/models/alembic/env.py` 会先用 `Settings.POSTGRES_URI`（异步驱动 `postgresql+asyncpg://`）覆盖 `sqlalchemy.url`，再通过 `async_engine_from_config` 异步执行迁移。因此数据库配置只需在 `.env` 中维护一份。

**另一个坑**：Alembic 以**系统区域编码**读取 `alembic.ini`，在中文 Windows 上会按 GBK 解码。请保持该文件为纯 ASCII（不要写中文注释），否则会报 `UnicodeDecodeError`。

### env.py —— 迁移环境配置

```python
# 从项目配置中获取数据库 URL
from shared.models.database import Base
from shared.models.postgres import *  # 导入所有模型
from shared.models.timescale import *  # 导入时序模型

target_metadata = Base.metadata
```

**关键行**：`from shared.models.postgres import *` 和 `from shared.models.timescale import *`

这两行确保 Alembic 能读取所有模型的元数据。如果新模型没有在这里导入，autogenerate 就无法检测到变化。

#### 离线模式

```python
def run_migrations_offline() -> None:
    """离线模式 — 生成 SQL 脚本而不实际执行"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
```

离线模式生成 SQL 文件，可以在生产环境中由 DBA 审查后再手动执行：

```bash
alembic upgrade head --sql > migration.sql
# 审查 migration.sql 的内容
# 确认无误后手动执行
```

#### 在线模式（异步）

```python
async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # 迁移时不使用连接池
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

GrassSea 使用异步连接执行迁移（通过 `async_engine_from_config` 和 `asyncio.run`）。`poolclass=pool.NullPool` 确保迁移结束后连接立即释放。

### 一个典型的迁移脚本

```python
"""create users table

Revision ID: a1b2c3d4e5f6
Revises: (none)
Create Date: 2026-07-01 10:00:00
"""
from alembic import op
import sqlalchemy as sa

# 每个迁移版本有一个唯一 ID（Revision ID）
revision = 'a1b2c3d4e5f6'
down_revision = None  # 第一个迁移，没有前驱
branch_labels = None
depends_on = None

def upgrade() -> None:
    """执行迁移：创建表"""
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('email', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])

def downgrade() -> None:
    """回滚迁移：删除表"""
    op.drop_index('ix_users_email')
    op.drop_table('users')
```

## 手把手实践

### 任务：执行一次完整的迁移流程

**步骤 1**：确认数据库可用

```bash
docker compose up -d postgres
docker exec -it grasssea-postgres psql -U grasssea -d grasssea -c "\dt"
```

**步骤 2**：查看当前迁移状态

```bash
cd F:/GrassSea
alembic current
# 如果还没有执行过迁移，会显示空
```

**步骤 3**：生成初始化迁移（如果还没有 migration）

```bash
# 检查 versions 目录
ls shared/models/alembic/versions/

# 如果有模型但还没迁移脚本，生成一个
alembic revision --autogenerate -m "initial schema"
```

**步骤 4**：执行迁移

```bash
alembic upgrade head
# head 表示最新版本
```

**步骤 5**：验证

```bash
# 查看迁移历史
alembic history

# 查看当前版本
alembic current

# 在 PostgreSQL 中确认表已创建
docker exec -it grasssea-postgres psql -U grasssea -d grasssea -c "\dt"
```

**步骤 6**：回滚测试

```bash
# 回滚一步
alembic downgrade -1

# 确认表已删除
docker exec -it grasssea-postgres psql -U grasssea -d grasssea -c "\dt"

# 重新升级
alembic upgrade head
```

### 完整的工作流

```
修改模型 → 生成迁移 → 审查脚本 → 执行迁移 → 测试 → 提交 Git

具体步骤:
1. 修改 shared/models/postgres/xxx.py
2. 在 __init__.py 中添加导出
3. alembic revision --autogenerate -m "描述性注释"
4. 审查 versions/ 下新生成的迁移脚本（重要！）
5. alembic upgrade head
6. 运行测试，确认功能正常
7. git add shared/models/alembic/versions/
8. git commit -m "数据库迁移: 描述性注释"
```

**第 4 步为什么重要？** autogenerate 可能漏掉一些变化（如索引重命名、默认值变更），或者生成不必要的操作。**生产环境在执行迁移前必须人工审查迁移脚本。**

## 视频学习资源

在 B 站搜索以下关键词：
1. "Alembic 数据库迁移教程" — Alembic 的安装和基本使用
2. "SQLAlchemy Alembic 实战" — 结合 FastAPI 的完整迁移流程
3. "数据库版本控制" — 理解数据库迁移在整个开发流程中的位置

## 常见问题与排错

### Q1: autogenerate 没检测到我的模型变化
**原因**：新模型没有在 `env.py` 中导入。
**解决**：确认 `env.py` 中有 `from shared.models.postgres import *` 和你的新模型在 `__init__.py` 的 `__all__` 列表中。

### Q2: alembic upgrade head 报错 `relation already exists`
**原因**：数据库中已经有同名表，但 Alembic 的版本记录显示还没创建。
**解决**：
```bash
# 手动标记当前数据库为最新版本
alembic stamp head
```

### Q3: 迁移脚本和模型不一致
**原因**：不同开发者在不同分支上生成了迁移脚本，合并时产生冲突。
**解决**：Alembic 的迁移是链式结构（每个版本指向前一个版本）。冲突时手动调整 `down_revision` 指向正确的父版本。团队应约定：**每次只允许一个人修改数据库结构，合并后再让其他人生成迁移。**

### Q4: timeseries schema 下的表如何迁移？
需要手动编写迁移脚本，因为 autogenerate 可能无法正确处理 TimescaleDB 的 hypertable 创建：

```python
def upgrade():
    op.create_table('token_usage_metrics', ..., schema='timeseries')
    op.execute("SELECT create_hypertable('timeseries.token_usage_metrics', 'time')")

def downgrade():
    op.drop_table('token_usage_metrics', schema='timeseries')
```

## 练习任务

1. **模拟迁移**：修改 `SystemConfig` 模型，添加一个 `is_public: bool` 字段。然后：
   - 生成 autogenerate 迁移脚本
   - 审查自动生成的脚本
   - 执行 upgrade
   - 执行 downgrade 验证回滚
   - 再执行 upgrade 恢复

2. **手动编写迁移**：为 TimescaleDB 的 4 张超表编写一个手动迁移脚本，在 upgrade 中使用 `op.execute("SELECT create_hypertable(...)")` 创建超表，在 downgrade 中删除超表。

3. **分析迁移历史**：查看 GrassSea 的 `alembic/versions/` 目录，分析每个迁移脚本的内容，理解每次数据库变更的意图。

4. **设计迁移规范**：为 GrassSea 团队制定一份数据库迁移规范，包括：命名约定、审查流程、生产执行流程、回滚策略。
