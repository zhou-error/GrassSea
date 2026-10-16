# 02 - 会话状态机 FSM

## 学习目标

1. 理解有限状态机（FSM）的核心概念
2. 掌握 `transitions` 库在异步环境中的使用
3. 读懂 GrassSea 的 18 种会话状态和状态迁移表
4. 能设计简单的状态机来处理对话流程

## 前置知识

- Python 枚举（Enum）、类
- 了解状态机的概念（如果不知道，本节会从零讲起）
- 异步编程基础（async/await）

## 概念讲解

### 什么是有限状态机（FSM）？

状态机是一种数学模型，用来描述一个系统在"有限个状态"之间如何切换。

```
生活中的状态机——交通信号灯：

    ┌─────────┐
    │  绿灯    │ ← 当前状态
    │  (通行)  │
    └────┬────┘
         │ 超时触发
         ▼
    ┌─────────┐
    │  黄灯    │
    │  (警告)  │
    └────┬────┘
         │ 超时触发
         ▼
    ┌─────────┐
    │  红灯    │
    │  (停止)  │
    └────┬────┘
         │ 超时触发
         └──────→ 回到绿灯

三个状态，一个触发器（超时），循环往复。
```

### 为什么对话系统需要状态机？

如果没有状态机，对话逻辑会变成"意大利面条代码"：

```
# 坏代码：用 if-else 堆砌状态
if searching:
    do_search()
elif generating:
    do_generate()
elif waiting:
    wait()
elif error:
    handle_error()
elif ...  # 50个 elif 之后你就找不到北了
```

有了状态机，逻辑变成声明式的：

```python
# 声明式：定义"什么条件下从哪个状态切换到哪个状态"
transitions = [
    {"trigger": "start_searching", "source": "KNOWLEDGE", "dest": "SEARCHING"},
    {"trigger": "rank_results",    "source": "SEARCHING",  "dest": "RANKING"},
    {"trigger": "start_generating","source": "RANKING",    "dest": "GENERATING"},
]
```

### GrassSea 的 18 种会话状态

```
                    会话 FSM 完整状态图
                    ═══════════════════

                        ┌─────────┐
                        │  IDLE   │ ◄──────────────────────────┐
                        │ （空闲）  │                            │
                        └────┬────┘                            │
                             │ 用户发送消息                      │
                             ▼                                  │
                        ┌─────────┐                            │
                        │ PARSING │                            │
                        │（意图解析）│                            │
                        └────┬────┘                            │
                             │                                  │
              ┌──────────────┼──────────────┐                  │
              ▼              ▼              ▼                  │
        ┌──────────┐  ┌──────────┐  ┌──────────┐              │
        │ CHITCHAT │  │KNOWLEDGE │  │TOOL_TASK │              │
        │（闲聊）   │  │（知识检索）│  │（工具/任务）│              │
        └────┬─────┘  └────┬─────┘  └────┬─────┘              │
             │              │              │                    │
             ▼              ▼              ▼                    │
        ┌──────────┐  ┌──────────┐  ┌──────────┐              │
        │RESPONDING│  │SEARCHING │  │ PLANNING │              │
        │（回复中）  │  │（检索中）  │  │（任务规划）│              │
        └────┬─────┘  └────┬─────┘  └────┬─────┘              │
             │              │              │                    │
             │              ▼              ▼                    │
             │        ┌──────────┐  ┌──────────┐              │
             │        │ RANKING  │  │EXECUTING │              │
             │        │（结果排序）│  │（执行中）  │              │
             │        └────┬─────┘  └────┬─────┘              │
             │              │              │                    │
             │              ▼              ▼                    │
             │        ┌──────────┐  ┌───────────┐             │
             │        │GENERATING│  │AGGREGATING│             │
             │        │（答案生成）│  │（结果聚合） │             │
             │        └────┬─────┘  └────┬──────┘             │
             │              │              │                    │
             └──────────────┼──────────────┘                    │
                            ▼                                   │
                      ┌──────────┐                             │
                      │STREAMING │                             │
                      │（流式输出）│                             │
                      └────┬─────┘                             │
                           │                                    │
                           ▼                                    │
                      ┌──────────┐                             │
                      │COMPLETED │─────────────────────────────┘
                      │（已完成）  │      自动回到 IDLE
                      └──────────┘

特殊状态（可从任何状态进入）：
  ERROR     → 异常处理，回到 IDLE
  CANCELLED → 用户取消，回到 IDLE
  TIMEOUT   → 超时，回到 IDLE
  WAITING_USER → 需要用户补充信息
```

## 项目代码精讲

打开 `services/agent_service/fsm.py`。

### 导入 transitions 库

```python
from transitions.extensions.asyncio import AsyncMachine
```

`transitions` 是一个 Python 状态机库，`AsyncMachine` 是其异步扩展版本。它提供了声明式状态迁移、进入/离开回调等功能。

### SessionState 枚举

```python
class SessionState(str, Enum):
    IDLE = "idle"
    PARSING = "parsing"
    CHITCHAT = "chitchat"
    KNOWLEDGE = "knowledge"
    TOOL_TASK = "tool_task"
    RESPONDING = "responding"
    SEARCHING = "searching"
    PLANNING = "planning"
    RANKING = "ranking"
    GENERATING = "generating"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    STREAMING = "streaming"
    COMPLETED = "completed"
    WAITING_USER = "waiting_user"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
```

18 种状态分为三组：
- **主流程**（12种）：IDLE -> PARSING -> ... -> COMPLETED -> IDLE
- **分支等待**（1种）：WAITING_USER
- **异常处理**（3种）：ERROR、CANCELLED、TIMEOUT

### 状态迁移表（TRANSITIONS）

```python
TRANSITIONS = [
    # IDLE → PARSING
    {"trigger": "receive_message", "source": "IDLE", "dest": "PARSING"},

    # PARSING → 三个分支
    {"trigger": "classify_chitchat",   "source": "PARSING", "dest": "CHITCHAT"},
    {"trigger": "classify_knowledge",  "source": "PARSING", "dest": "KNOWLEDGE"},
    {"trigger": "classify_tool_task",  "source": "PARSING", "dest": "TOOL_TASK"},

    # 知识查询路径：SEARCHING → RANKING → GENERATING
    {"trigger": "rank_results",      "source": "SEARCHING", "dest": "RANKING"},
    {"trigger": "start_generating",  "source": "RANKING",   "dest": "GENERATING"},

    # 任务路径：PLANNING → EXECUTING
    {"trigger": "start_executing",   "source": "PLANNING",  "dest": "EXECUTING"},

    # EXECUTING 可能暂停等待用户输入
    {"trigger": "need_user_input",   "source": "EXECUTING",  "dest": "WAITING_USER"},
    {"trigger": "user_provided",     "source": "WAITING_USER", "dest": "EXECUTING"},

    # 万能跳转（source="*" 表示从任何状态）
    {"trigger": "handle_error",      "source": "*", "dest": "ERROR"},
    {"trigger": "user_cancel",       "source": "*", "dest": "CANCELLED"},
    {"trigger": "handle_timeout",    "source": "*", "dest": "TIMEOUT"},
]
```

`source="*"` 是 transitions 库的特殊语法，表示"从任何状态都可以触发此迁移"。这非常适合处理异常、取消、超时等全局事件。

### SessionFSM 类

```python
class SessionFSM:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.error_count = 0
        self.max_errors = 3
        self.timeout_seconds = 1800  # 30分钟

        # 核心：创建 AsyncMachine 实例
        self.machine = AsyncMachine(
            model=self,                    # 状态附着在这个对象上
            states=list(SessionState),     # 所有可能的状态
            transitions=TRANSITIONS,       # 状态迁移规则
            initial=SessionState.IDLE,     # 初始状态
        )
```

`model=self` 意味着状态机直接附着在 `SessionFSM` 实例上。之后你可以这样使用：

```python
fsm = SessionFSM("sess_001")
print(fsm.state)           # SessionState.IDLE

await fsm.receive_message()  # 触发 "receive_message"
print(fsm.state)           # SessionState.PARSING
```

### 状态进入回调

```python
async def on_enter_ERROR(self):
    """进入 ERROR 状态时自动调用"""
    self.error_count += 1
    if self.error_count >= self.max_errors:
        await self.recover_error()  # 超过最大错误次数，强制恢复

async def on_enter_TIMEOUT(self):
    """进入 TIMEOUT 状态时自动调用"""
    await asyncio.sleep(5)  # 等待5秒后自动恢复
    if self.state == SessionState.TIMEOUT:
        await self.recover_timeout()
```

`on_enter_<STATE>()` 是 transitions 库的命名约定方法。当状态机进入某个状态时，自动调用对应的方法。这是一种优雅的回调机制。

### 超时检测

```python
def touch(self):
    """更新最后活动时间"""
    self.last_activity = datetime.utcnow()

@property
def is_timed_out(self) -> bool:
    return self.idle_duration_seconds > self.timeout_seconds
```

`touch()` 应在每次用户交互时调用，`is_timed_out` 用于外部定时检查。

## 手把手实践

### 实验：构建一个简单的点餐状态机

```python
# order_fsm.py -- 用 transitions 实现点餐流程
from transitions import Machine

class OrderFSM:
    states = ['waiting', 'ordering', 'confirming', 'paying', 'completed']

    def __init__(self):
        self.machine = Machine(
            model=self,
            states=OrderFSM.states,
            initial='waiting',
        )
        # 添加状态迁移
        self.machine.add_transition('start_order', 'waiting', 'ordering')
        self.machine.add_transition('confirm', 'ordering', 'confirming')
        self.machine.add_transition('pay', 'confirming', 'paying')
        self.machine.add_transition('finish', 'paying', 'completed')

order = OrderFSM()
print(order.state)  # waiting

order.start_order()
print(order.state)  # ordering

order.confirm()
print(order.state)  # confirming
```

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "有限状态机 FSM 原理 通俗" -- 入门状态机概念
- "Python transitions 库 状态机" -- 学习 transitions 库
- "对话系统状态管理 架构设计" -- 了解对话状态管理

## 常见问题与排错

**Q1：为什么不直接用 if-else 管理状态？**

A：项目初期也许可以，但状态超过 5 种后维护成本爆炸。状态机的好处是：
- **可读性**：一张图就能看懂全部状态流转
- **安全性**：非法的状态转移会自动报错（如从 IDLE 直接跳到 GENERATING）
- **可扩展**：新增状态只需加一行迁移规则

**Q2：`source="*"` 会不会导致状态机失控？**

A：不会。`source="*"` 只是说触发条件不限制当前状态，但目标状态是确定的（ERROR、CANCELLED、TIMEOUT），且从这些状态恢复后都回到 IDLE。这是一个标准的"全局复位"模式。

**Q3：18 种状态是不是太多了？**

A：状态的粒度是权衡。太粗（3-5种）：信息不足，无法区分"正在搜索"和"正在生成"；太细（50种+）：维护困难。18 种状态对应了对话系统的完整生命周期，每个阶段都有明确的业务含义。

## 练习任务

1. **概念题**：画出 RAG 检索流程对应的状态迁移路径（从 IDLE 到 COMPLETED 经过哪些状态）。
2. **代码题**：在 `TRANSITIONS` 中新增一条规则：从 `RANKING` 状态可以直接回到 `SEARCHING` 状态（触发条件：检索结果质量不够需要重新搜索）。
3. **分析题**：`on_enter_ERROR` 中 `error_count >= max_errors` 后就强制恢复。这种设计有什么风险？如何改进？
4. **实践题**：基于 `OrderFSM` 实验代码，添加一个"取消订单"的全局触发（类似 source="*"），从任何状态直接跳到 `cancelled` 状态。
