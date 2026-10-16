# 02 - RBAC 权限控制

## 学习目标

1. 理解 RBAC（基于角色的访问控制）的核心概念
2. 掌握 GrassSea 的五角色权限体系
3. 理解 Casbin 策略引擎的工作原理
4. 能够设计一个简单的 RBAC 权限模型

## 前置知识

- 理解阶段十第1章 JWT 认证的基本概念
- 了解 Python 字典（dict）的基本操作
- 了解什么是权限（Permission）

## 概念讲解

### 什么是 RBAC？

RBAC = Role-Based Access Control（基于角色的访问控制）。核心思想是：**将权限授予角色，再将角色授予用户。**

```
传统做法（直接授权）：
┌──────────────────────────────────────┐
│ 王工 → 能读项目文档                  │
│ 王工 → 能写项目文档                  │
│ 王工 → 能读知识库                   │
│ 李工 → 能读项目文档                  │
│ 李工 → 能写项目文档                  │
│ ...                                 │
│ 问题：每增加一个用户，要配 N 条权限  │
└──────────────────────────────────────┘

RBAC 做法（角色授权）：
┌──────────────────────────────────────┐
│ 角色 engineer → [读项目, 写项目, 读知识库, 用工具, 出报告]  │
│                                      │
│ 王工 → 角色 engineer（继承上面所有权限）│
│ 李工 → 角色 engineer（同上）          │
│ 张工 → 角色 guest（只有读权限）       │
│                                      │
│ 优势：新增用户只需分配角色，不用管权限 │
└──────────────────────────────────────┘
```

### RBAC 的三要素

```
    User (用户)              Role (角色)             Permission (权限)
    ┌──────────┐           ┌──────────┐           ┌──────────────┐
    │ 用户A    │────拥有───▶│ admin    │───拥有───▶│ * (所有)      │
    │ 用户B    │────拥有───▶│ engineer │───拥有───▶│ project:read │
    │ 用户C    │────拥有───▶│ guest    │───拥有───▶│ ...          │
    └──────────┘           └──────────┘           └──────────────┘

    关系：User → Role → Permission（多对多的桥梁关系）
```

### GrassSea 的五角色权限体系

```
                    GrassSea RBAC 权限金字塔

                         ┌─────────┐
                         │  admin  │  ← 超级管理员, "*" 通配符（万能）
                         ├─────────┤
                         │project  │  ← 项目负责人: 管理项目、知识库、成员、任务
                         │ lead    │
                         ├─────────┤
                         │engineer │  ← 工程师: 读写项目、读知识库、使用工具、生成报告
                         ├─────────┤
                         │  guest  │  ← 访客: 只读项目、只读知识库
                         ├─────────┤
                         │api_user │  ← API 用户: 仅限 API 调用
                         └─────────┘

权限逐层递减 — 上层角色比下层拥有更多权限
```

对应的权限映射（来自 `shared/middleware/security.py` 第20-27行）：

| 角色 | 权限 |
|------|------|
| admin | `["*"]` — 所有操作 |
| project_lead | `project:read`, `project:write`, `knowledge:read`, `knowledge:write`, `member:manage`, `task:assign` |
| engineer | `project:read`, `project:write`, `knowledge:read`, `tool:use`, `report:generate` |
| guest | `project:read`, `knowledge:read` |
| api_user | `api:access` — 仅 API 调用权限 |

### Casbin 策略引擎

GrassSea 使用 Casbin 作为额外的策略引擎。虽然代码中也用 `ROLE_PERMISSIONS` 字典做了内建检查，但 Casbin 提供了更灵活的策略管理和动态更新能力。

Casbin 的核心是一个策略文件（`.csv` 格式）和一个模型文件（`.conf` 格式）。

**模型配置文件**（`infrastructure/k3s/casbin-rbac.yaml`）：

```
[request_definition]
r = sub, obj, act        ← 请求格式: (主体, 资源, 操作)
                           例: ("王工程师", "project", "read")

[policy_definition]
p = sub, obj, act        ← 策略格式: (角色, 资源, 操作)
                           例: ("engineer", "project", "read")

[role_definition]
g = _, _                 ← 用户-角色映射: (用户, 角色)
                           例: ("王工程师", "engineer")

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
    ↑                   ↑                   ↑
  "用户是否属于       "资源是否匹配"     "操作是否匹配"
  该角色？"
```

**策略数据文件**（`infrastructure/k3s/casbin-policy.csv`）：

```csv
# 格式: p, 角色, 资源, 操作
p, admin, *, *
p, project_lead, project, read
p, engineer, tool, use

# 格式: g, 用户, 角色
g, admin_user_1, admin
g, engineer_user_1, engineer
g, guest_user_1, guest
```

`p, admin, *, *` 表示 admin 角色对任意资源（`*`）有任意操作（`*`）权限。

## 项目代码精讲

### 权限检查核心函数

```python
# shared/middleware/security.py 第32-35行
def check_permission(role: str, required: str) -> bool:
    """检查角色权限"""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or required in perms
```

**逐段解析**：

1. `ROLE_PERMISSIONS.get(role, [])` — 从角色-权限字典中查找该角色的权限列表。如果角色名不存在（如拼写错误），`get` 方法安全返回空列表 `[]`，而不是抛出 KeyError 异常。这是一种防御性编程——即使传入错误的角色名，程序也不会崩溃。

2. `"*" in perms` — 通配符检查。admin 角色的权限是 `["*"]`，表示拥有所有权限。当检测到 `"*"` 时，直接返回 `True`。

3. `required in perms` — 精确匹配。例如 `required` 是 `"tool:use"`，检查 engineer 角色是否包含此权限。

### 权限字符串的命名规范

GrassSea 的权限使用 `资源:操作` 的命名格式：

```
project:read       — 项目资源的读权限
project:write      — 项目资源的写权限
knowledge:read     — 知识库资源的读权限
knowledge:write    — 知识库资源的写权限
tool:use           — 工具的使用权限
member:manage      — 成员的管理权限
task:assign        — 任务的分配权限
report:generate    — 报告的生成权限
api:access         — API 的访问权限
```

这种 `resource:action` 的命名方式清晰易懂，一眼就能看出是什么资源的什么操作。

### Casbin 策略匹配过程（图解）

```
请求: 王工程师想要 "读项目文档"
翻译为 Casbin 请求: ("王工程师", "project", "read")

匹配过程:
┌─────────────────────────────────────────────────────┐
│ Step 1: 查找用户角色                                  │
│ g("王工程师", ?) → ("engineer")                     │
│                                                      │
│ Step 2: 查找角色权限                                  │
│ p("engineer", "project", ?) → ("read")              │
│                                                      │
│ Step 3: 验证                                         │
│ r.obj ("project") == p.obj ("project") ✓            │
│ r.act ("read") == p.act ("read") ✓                  │
│                                                      │
│ 结果: 允许访问 ✓                                     │
└─────────────────────────────────────────────────────┘

假设: 王工程师想要 "删除用户"
翻译为: ("王工程师", "user", "delete")

匹配过程:
│ Step 1: g("王工程师", ?) → ("engineer")
│ Step 2: p("engineer", "user", ?) → 找不到匹配策略
│ Step 3: 无匹配策略 → 默认拒绝
│ 结果: 拒绝访问 ✗
└─────────────────────────────────────────────────────┘
```

## 手把手实践

### 实验一：追踪权限检查

1. 打开 `shared/middleware/security.py`
2. 找到 `ROLE_PERMISSIONS` 字典
3. 分别对以下场景运行 `check_permission`（在脑海里或写测试代码执行）：
   - 角色 `admin`，要求权限 `"project:read"` → 应该返回 `True`（因为 `"*"` 在权限列表中）
   - 角色 `engineer`，要求权限 `"tool:use"` → 应该返回 `True`
   - 角色 `guest`，要求权限 `"project:write"` → 应该返回 `False`
   - 角色 `"fake_role"`，要求权限 `"anything"` → 应该返回 `False`（角色不存在，返回空列表）

### 实验二：阅读 Casbin 策略文件

1. 打开 `infrastructure/k3s/casbin-policy.csv`
2. 回答以下问题：
   - `project_lead` 有哪些权限？（数一数 `p, project_lead` 开头的行）
   - 如果要把一个用户的角色从 `engineer` 改为 `admin`，需要修改哪一行？
   - 如果要新增一个 `viewer` 角色（只有 `project:read`），需要添加哪些行？

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "RBAC 权限管理 原理" -- 理解基于角色的访问控制
- "Casbin 权限引擎 入门" -- 学习 Casbin 的 ACL/RBAC 模型
- "Web 权限系统设计" -- 了解前端+后端的完整权限方案
- "Kubernetes RBAC 权限" -- 学习 K8s 中的 RBAC 机制（与 Casbin 思想相通）

## 常见问题与排错

**Q1：权限使用 `"*"` 通配符安全吗？**

A：`"*"` 只分配给 admin 角色，而 admin 账户应由严格的审计和 MFA 保护。在代码中（`check_permission` 函数的第2行），一旦检测到 `"*"`，直接返回 `True`，无需逐个匹配，这也是一个性能优化。

**Q2：为什么既用 `ROLE_PERMISSIONS` 字典又用 Casbin？**

A：`ROLE_PERMISSIONS` 字典是"硬编码"的快速检查，适用于简单的角色-权限映射。Casbin 是"软编码"的策略引擎，支持动态更新策略文件而不重启服务，并且支持更复杂的规则（如条件表达式、域隔离等）。

**Q3：如果有人修改了 JWT Payload 中的 role 字段？**

A：JWT 的签名机制会阻止这种篡改。如果修改了 Payload，签名就对不上了，服务端验证时会直接拒绝该 Token。这就是 JWT 的安全核心。

## 练习任务

1. **概念题**：解释 RBAC 的三个核心元素（User、Role、Permission）之间的关系。
2. **设计题**：如果 GrassSea 要增加一个 `auditor`（审计员）角色，该角色可以读所有资源但不能写，请写出这个角色的权限列表。
3. **代码题**：在 `shared/middleware/security.py` 中，为 `ROLE_PERMISSIONS` 字典添加你设计的 `auditor` 角色及其权限。
4. **挑战题**：阅读 `infrastructure/k3s/casbin-rbac.yaml` 中的 `matchers` 配置，解释 `g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act` 三个条件的含义。
