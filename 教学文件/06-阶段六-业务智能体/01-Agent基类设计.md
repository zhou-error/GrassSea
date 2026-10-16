# 01 - Agent 基类设计

## 学习目标

1. 理解 ABC 抽象基类在智能体框架中的作用
2. 掌握 AgentMetadata、AgentCapability、AgentCallbacks 数据类的设计
3. 理解 AgentStatus 状态生命周期
4. 能用 BaseAgent 创建自己的智能体

## 前置知识

- Python 类的继承（ABC、abstractmethod）
- 数据类（dataclass）
- 类型注解（`dict[str, Any]`、`| None`）

## 概念讲解

### 为什么需要基类？

基类（Base Class）定义了"成为 Agent 的最低要求"。就像合同一样——任何人都可以声称自己是 Agent，但只有实现了规定的接口，系统才能与之协作。

```
                    BaseAgent（抽象基类）
                   ═══════════════════════
                   
    要求每个 Agent 必须提供：
    1. metadata    → 我是谁？我能做什么？
    2. handle_task() → 接到任务后怎么做？
    3. health_check() → 我还活着吗？
    
         │              │              │
         ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ PM Agent  │  │Naval Arch│  │CAD Agent │
    │           │  │  Agent   │  │          │
    │实现:      │  │实现:      │  │实现:      │
    │分解任务   │  │稳性计算   │  │图纸绘制   │
    │分配资源   │  │阻力计算   │  │图纸解析   │
    │聚合结果   │  │型线设计   │  │          │
    └──────────┘  └──────────┘  └──────────┘
```

没有基类的话，每个 Agent 实现方式百花齐放，编排器无法统一调度。

### 数据类：Agent 的"名片"

```
AgentMetadata（元信息）         AgentCapability（能力声明）
───────────────────────        ─────────────────────────
agent_id: "naval_arch"         name: "stability_calc"
name: "船舶工程师 Agent"        description: "稳性计算"
role: "型线设计、稳性计算"      input_schema: {...}
capabilities: [...]            output_schema: {...}
model_preference: "deepseek"   tools: ["hydrostatics", ...]
max_concurrent_tasks: 3        estimated_latency_ms: 5000
version: "0.1.0"
```

### AgentStatus 状态生命周期

```
  ┌─────────────┐
  │ UNREGISTERED │  初始状态
  └──────┬──────┘
         │ 注册成功
         ▼
  ┌─────────────┐
  │ REGISTERED  │  已在注册中心
  └──────┬──────┘
         │ 健康检查通过
         ▼
  ┌─────────────┐    接收任务    ┌─────────────┐
  │    IDLE     │◄──────────────│   WORKING   │
  │   （空闲）   │──────────────►│  （工作中）   │
  └──────┬──────┘  任务完成/出错  └─────────────┘
         │
         │ 连续心跳超时
         ▼
  ┌─────────────┐    人工确认    ┌─────────────┐
  │  UNHEALTHY  │──────────────►│  DESTROYED  │
  │  （不健康）  │               │  （已销毁）   │
  └─────────────┘               └─────────────┘
```

## 项目代码精讲

打开 `shared/protocols/agent.py`。

### 数据类定义

```python
@dataclass
class AgentCapability:
    """能力声明 -- Agent 告诉世界"我能做什么" """
    name: str                              # "stability_calc"
    description: str                       # "完整稳性与破舱稳性计算"
    input_schema: dict                     # 输入参数的 JSON Schema
    output_schema: dict                    # 输出结果的 JSON Schema
    tools: list[str] = field(default_factory=list)    # 关联工具
    estimated_latency_ms: int = 500        # 预估耗时
```

**为什么需要 input_schema 和 output_schema？**

它们的作用是让编排器**自动判断**某个 Agent 能否处理特定任务。例如：
- 任务需要的输入是 `{"L": float, "B": float, "T": float}`
- Naval Arch Agent 的 stability_calc 能力的 input_schema 包含这些字段
- 编排器自动匹配，无需硬编码判断逻辑

```python
@dataclass
class AgentMetadata:
    """智能体元信息 -- Agent 的完整"自我介绍" """
    agent_id: str                          # 唯一标识
    name: str                              # 显示名称
    role: str                              # 角色描述
    capabilities: list[AgentCapability]    # 能力列表
    model_preference: str = "deepseek-chat"
    max_concurrent_tasks: int = 5
    version: str = "0.1.0"
```

`model_preference` 表示该 Agent 偏好使用哪个 LLM（文本为主的用 deepseek-chat，报告生成可能偏好 claude-opus）。

### 回调接口

```python
@dataclass
class AgentCallbacks:
    """智能体回调接口 -- Agent 在执行中向外"汇报" """
    on_progress: Any = None   # 进度回调 (task_id, progress: float)
    on_message: Any = None    # 消息回调 (task_id, message: str)
    on_error: Any = None      # 错误回调 (task_id, error: str)
```

回调模式让 Agent 在执行长任务时能持续向外汇报状态，而不是"闷头算完再一次性返回"。

### 抽象基类

```python
class BaseAgent(ABC):
    """智能体抽象基类 -- 所有业务 Agent 的"宪法" """

    def __init__(self, metadata: AgentMetadata):
        self._metadata = metadata
        self._status = AgentStatus.UNREGISTERED

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    @property
    def status(self) -> AgentStatus:
        return self._status

    @abstractmethod
    async def handle_task(
        self,
        task: dict[str, Any],          # 任务描述
        context: dict[str, Any],       # 上下文（对话历史、检索结果等）
        callbacks: AgentCallbacks,     # 回调接口
    ) -> dict[str, Any]:
        """执行任务并返回结果。子类必须实现此方法。"""
        ...

    async def health_check(self) -> bool:
        """健康检查。默认返回 True，子类可按需覆盖。"""
        return True

    def set_status(self, status: AgentStatus) -> None:
        self._status = status
```

**`@abstractmethod`** 是关键装饰器：任何继承 `BaseAgent` 的子类**必须**实现 `handle_task`，否则实例化时会报错。这保证了所有 Agent 都遵循统一的任务执行接口。

**`health_check` 不是抽象的**：它有一个默认实现（返回 True），子类可以覆盖来添加真实的健康检查逻辑（如检查依赖的外部 API 是否可用）。

### Protocol 接口

```python
class AgentRegistry(Protocol):
    """智能体注册中心协议"""
    async def register(self, agent: BaseAgent) -> bool: ...
    async def deregister(self, agent_id: str) -> bool: ...
    async def discover(self, capability: str) -> list[AgentMetadata]: ...
    async def heartbeat(self, agent_id: str) -> bool: ...
    async def get_agent(self, agent_id: str) -> AgentMetadata | None: ...
```

**Protocol 与 ABC 的区别**：

| 特性 | ABC | Protocol |
|------|-----|----------|
| 继承关系 | 必须显式继承 | 不需要继承 |
| 检查时机 | 实例化时报错 | 类型检查时报错 |
| 适合场景 | "必须按我的模板" | "只要长得像就行" |
| Python 版本 | 所有版本 | 3.8+ |

GrassSea 中 Agent 用 ABC（因为 Agent 必须继承基类），注册中心用 Protocol（因为可能有多种实现）。

## 手把手实践

### 实验：创建你的第一个 Agent

```python
# my_first_agent.py
from shared.protocols.agent import (
    BaseAgent, AgentMetadata, AgentCapability,
    AgentCallbacks, AgentStatus,
)

# 1. 定义元数据
MY_METADATA = AgentMetadata(
    agent_id="my_agent",
    name="我的第一个 Agent",
    role="演示用 Agent",
    capabilities=[
        AgentCapability(
            name="greet",
            description="打招呼并回复",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"greeting": {"type": "string"}}},
            tools=[],
            estimated_latency_ms=100,
        ),
    ],
)

# 2. 实现 Agent
class MyFirstAgent(BaseAgent):
    def __init__(self):
        super().__init__(MY_METADATA)

    async def handle_task(self, task, context, callbacks):
        name = task.get("inputs", {}).get("name", "世界")
        return {
            "status": "completed",
            "greeting": f"你好，{name}！我是 {self.metadata.name}。",
        }

# 3. 测试
import asyncio
async def test():
    agent = MyFirstAgent()
    print(f"Agent: {agent.metadata.name}")
    print(f"状态: {agent.status}")

    result = await agent.handle_task(
        {"inputs": {"name": "小明"}},
        context={},
        callbacks=AgentCallbacks(),
    )
    print(f"结果: {result['greeting']}")

asyncio.run(test())
```

## 视频学习资源

请在 B站（bilibili.com）自行搜索以下关键词：

- "Python ABC 抽象基类 面向对象" -- 理解抽象类
- "Python dataclass 数据类 教程" -- 学习数据类
- "设计模式 模板方法模式 Python" -- 理解基类设计模式

## 常见问题与排错

**Q1：为什么不直接在 BaseAgent 中定义 `handle_task` 的默认实现？**

A：因为每个 Agent 的行为完全不同——PM Agent 分解任务，Naval Arch Agent 做计算，CAD Agent 画图。一个"默认实现"没有意义。`@abstractmethod` 强制子类自己实现，确保不会漏掉。

**Q2：`AgentCallbacks` 的类型注解为什么用 `Any`？**

A：因为回调函数的具体签名因使用场景而异。`Any` 牺牲了类型检查的严格性，换来了灵活性。更严格的写法是使用 `Callable[[str, float], None]` 等具体类型。

**Q3：Protocol 和 ABC 可以同时使用吗？**

A：可以。一个类可以同时继承 ABC 和实现 Protocol。但 GrassSea 中 BaseAgent 用 ABC，AgentRegistry 用 Protocol，它们是分开的，各自适用于不同的设计需求。

## 练习任务

1. **代码题**：基于 `MyFirstAgent` 实验，添加一个 `health_check` 方法，随机返回 True/False 来模拟健康状态。
2. **设计题**：设计一个新的 `AgentCapability`：假设你要添加一个"翻译能力"到某个 Agent，填写完整的 AgentCapability 字段（name、description、input_schema、output_schema）。
3. **分析题**：`_metadata` 和 `_status` 前面有下划线，这是一种什么约定？如果在子类中直接访问 `self._metadata` 是否合适？
4. **思考题**：如果 Naval Arch Agent 在执行稳性计算时需要使用不同的 LLM 模型（计算用 deepseek-chat，报告用 claude-opus），当前的 `model_preference` 字段设计是否够用？如何改进？
