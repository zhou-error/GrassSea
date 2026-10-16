# Pydantic 数据模型 — 类型安全的数据验证

## 学习目标

- 理解 Pydantic 在 FastAPI 项目中的作用
- 掌握 `BaseModel` 的基础用法和字段类型校验
- 学会使用 `Field` 添加字段验证约束
- 理解 `@property` 计算属性和嵌套模型
- 能读写 GrassSea 项目中的 Pydantic 请求/响应模型

## 前置知识

- Python 类型注解（`str`, `int`, `Optional[str]`, `list[dict]` 等）
- FastAPI 基础知识（路由、请求体）
- 完成 `01-Python异步编程.md` 的学习

---

## 1. 概念讲解

### 1.1 为什么需要 Pydantic？

在 Web 开发中，用户输入是不可信的。你需要验证：
- 这个字段是不是必填？
- 这个数字是不是在合理范围内？
- 这个字符串格式对不对？

传统做法是手写一堆 `if` 判断：

```python
# 传统写法 — 繁琐且容易遗漏
def create_user(data: dict):
    if "name" not in data:
        raise ValueError("缺少 name 字段")
    if not isinstance(data["name"], str):
        raise TypeError("name 必须是字符串")
    if len(data["name"]) < 2 or len(data["name"]) > 50:
        raise ValueError("name 长度必须在 2-50 之间")
    # ... 更多检查
```

Pydantic 把这个过程**声明化**了：

```python
from pydantic import BaseModel, Field

class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    age: int = Field(ge=0, le=150)
    email: str
    is_active: bool = True   # 默认值
```

当 FastAPI 接收到请求时，会自动用 Pydantic 模型验证请求体。如果数据不合法，FastAPI 会自动返回 422 错误，附带详细的错误说明。

> 💡 **核心价值**：Pydantic 让你用**类型注解**来描述数据规则，验证是自动的、声明式的、不依赖手写 if-else。

### 1.2 核心概念图解

```
┌───────────────────────────────────────────────────────┐
│                  Pydantic BaseModel                    │
│                                                       │
│  输入 (dict/JSON)          输出 (类型安全的对象)        │
│  ┌─────────────┐          ┌──────────────────┐       │
│  │ {"name":    │  解析+  │ user.name → "张三" │       │
│  │  "张三",    │  验证    │ user.age → 25     │       │
│  │  "age": 25, │ ──────▶ │ user.email → ".."  │       │
│  │  "email":"  │          └──────────────────┘       │
│  │  a@b.com"}  │                                     │
│  └─────────────┘                                     │
│                                                       │
│  验证功能:                                             │
│  ├── 类型检查: str, int, float, bool, list, dict      │
│  ├── 约束条件: min_length, ge, le, pattern(regex)     │
│  ├── 默认值: is_active: bool = True                   │
│  ├── 可选字段: Optional[str] = None                   │
│  └── 自定义验证: @field_validator                     │
└───────────────────────────────────────────────────────┘
```

**Pydantic V1 vs V2**：GrassSea 项目使用的是 **Pydantic V2**（通过 `pydantic_settings` 依赖），V2 速度更快，API 有所变化。本文讲解的内容基于 V2 语法。

---

## 2. 项目代码精讲

> 🔗 **参考文件**：`shared/utils/config.py`、`services/model_gateway/main.py`

### 2.1 Settings 类 -- 管理全局配置

打开 `shared/utils/config.py`，这是项目中使用 Pydantic 最典型的例子：

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """应用全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",          # 从 .env 文件读取配置
        env_file_encoding="utf-8",
        extra="ignore",           # 忽略未定义的额外字段
        case_sensitive=False,     # 环境变量名不区分大小写
    )

    # --- 应用 ---
    APP_NAME: str = "GrassSea"
    APP_VERSION: str = "0.1.0"
    APP_DEBUG: bool = True

    # --- PostgreSQL ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "grasssea"
    POSTGRES_PASSWORD: str = "grasssea"
    POSTGRES_DB: str = "grasssea"
```

**关键点**：
- `BaseSettings` 继承自 `BaseModel`，额外增加了从环境变量/`.env` 文件自动加载值的能力
- `model_config` 是 Pydantic V2 的配置方式（V1 用的是 `class Config`）
- 每个字段的默认值就是它的 fallback 值。如果环境变量中设置了 `POSTGRES_HOST=myhost`，则会覆盖默认值 `"localhost"`

### 2.2 @property -- 计算属性

`Settings` 类中的 `@property` 展示了如何从多个字段派生出新的值：

```python
@property
def POSTGRES_URI(self) -> str:
    return (
        f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
        f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    )

@property
def REDIS_URI(self) -> str:
    if self.REDIS_PASSWORD:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
```

`@property` 将方法伪装为属性，使用时就像访问字段一样 `settings.POSTGRES_URI`，不需要写括号。每次访问都会动态计算，保证值始终基于最新的字段值。

### 2.3 Field -- 字段验证约束

打开 `services/model_gateway/main.py`，看看请求模型中的字段验证：

```python
from pydantic import BaseModel, Field
from typing import Optional

class ChatCompletionRequest(BaseModel):
    model: str = "deepseek-chat"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)   # ≥0.0 且 ≤2.0
    max_tokens: int = Field(default=4096, ge=1, le=128000)      # 1-128000 范围
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)          # 0.0-1.0
    user: Optional[str] = None
```

**Field 常用参数**：

| 参数 | 含义 | 示例 |
|------|------|------|
| `default` | 默认值 | `default=0.7` |
| `ge` | greater or equal (>=) | `ge=0.0` |
| `le` | less or equal (<=) | `le=2.0` |
| `gt` | greater than (>) | `gt=0` |
| `lt` | less than (<) | `lt=100` |
| `min_length` | 字符串最小长度 | `min_length=1` |
| `max_length` | 字符串最大长度 | `max_length=500` |
| `pattern` | 正则匹配 | `pattern=r"^[a-z_]+$"` |
| `description` | 字段描述（会出现在 API 文档中） | `description="模型名称"` |

### 2.4 嵌套模型

同一个文件中，`ChatCompletionRequest` 使用了嵌套的 `ChatMessage` 模型：

```python
class ChatMessage(BaseModel):
    role: str = "user"
    content: str

class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]   # ← messages 中的每个元素都必须符合 ChatMessage 格式
    # ...
```

Pydantic 会自动递归验证嵌套模型。如果传入 `{"messages": [{"role": 123}]}`，会报错说 `role` 必须是字符串，而不是整数。

### 2.5 model_dump() -- 模型转字典

在 `services/model_gateway/main.py` 第196行：

```python
messages=[m.model_dump() for m in request.messages],
```

`model_dump()` 是 Pydantic V2 的方法（V1 叫 `.dict()`），将模型对象转换回普通字典。这在需要将 Pydantic 对象传给其他 API 时非常有用。

---

## 3. 手把手实践

### 3.1 基础模型定义与验证

```python
from pydantic import BaseModel, Field, ValidationError
from typing import Optional

class ShipInfo(BaseModel):
    """船舶基本信息模型"""
    name: str = Field(min_length=1, max_length=100, description="船名")
    ship_type: str = Field(default="散货船", description="船型")
    length_m: float = Field(gt=0, description="船长(米)")
    breadth_m: float = Field(gt=0, description="船宽(米)")
    draft_m: float = Field(gt=0, description="吃水(米)")
    deadweight_t: Optional[float] = None  # 载重吨，可选

# 正确使用
ship = ShipInfo(
    name="海洋之星",
    ship_type="油轮",
    length_m=180.0,
    breadth_m=32.0,
    draft_m=9.5,
)
print(ship.model_dump())  # 转换为字典

# 错误示例 — 自动验证
try:
    bad_ship = ShipInfo(name="", length_m=-5, breadth_m=20, draft_m=0)
except ValidationError as e:
    print(e)  # 会显示所有验证错误
```

### 3.2 与 FastAPI 结合

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

@app.post("/chat")
async def chat(request: ChatRequest):
    # request 已经被自动验证过了！
    return {
        "reply": f"收到消息: {request.message}",
        "temp": request.temperature,
    }
``` 

启动后用 FastAPI 自带的 Swagger 文档（http://localhost:8000/docs）可以看到每个字段的类型、约束和默认值自动生成了文档。

### 3.3 @property 计算属性实践

```python
from pydantic import BaseModel

class VesselDimensions(BaseModel):
    length_m: float
    breadth_m: float
    depth_m: float

    @property
    def volume_approx(self) -> float:
        """估算舱容 (m³)"""
        return self.length_m * self.breadth_m * self.depth_m

    @property
    def length_to_breadth_ratio(self) -> float:
        """长宽比"""
        return self.length_m / self.breadth_m

vessel = VesselDimensions(length_m=200, breadth_m=35, depth_m=15)
print(f"估算舱容: {vessel.volume_approx:.0f} m³")
print(f"长宽比: {vessel.length_to_breadth_ratio:.2f}")
```

---

## 4. 视频学习资源

在 B站搜索以下关键词：

- [B站搜索: Pydantic V2 教程](https://search.bilibili.com/all?keyword=Pydantic+V2+教程) -- 入门与进阶
- [B站搜索: FastAPI Pydantic 数据验证](https://search.bilibili.com/all?keyword=FastAPI+Pydantic+数据验证) -- 结合框架实战
- [B站搜索: Pydantic BaseModel 数据模型](https://search.bilibili.com/all?keyword=Pydantic+BaseModel+数据模型) -- 基础概念

> 💡 **提示**：Pydantic 官方文档（https://docs.pydantic.dev/）非常详细，是学习的最佳参考。

---

## 5. 常见问题与排错

### Q1: `pydantic.errors.PydanticImportError: BaseSettings has been moved...`

Pydantic V2 将 `BaseSettings` 分离到了 `pydantic-settings` 包中。需要单独安装：

```bash
pip install pydantic-settings
```

然后从 `pydantic_settings` 导入：`from pydantic_settings import BaseSettings`

### Q2: `Field` 的 `regex` 参数不生效

Pydantic V2 中 `Field(regex=...)` 改为了 `Field(pattern=...)`。

### Q3: 模型 `.dict()` 方法报错

Pydantic V2 中 `.dict()` 改名为 `.model_dump()`，`.json()` 改名为 `.model_dump_json()`。

### Q4: 可选字段默认值设为 `None` 时的类型问题

```python
# 正确写法（Python 3.10+）
email: str | None = None
# 或
from typing import Optional
email: Optional[str] = None

# 错误写法 — 类型注解与默认值不一致
email: str = None  # ← mypy 会报错
```

---

## 6. 练习任务

### 练习1：定义船舶模型
参考 GrassSea 项目中 `Project` 相关的业务需求，定义一个 `ShipDesignRequest` Pydantic 模型，包含：
- `project_name`：必填，字符串，1-200 字符
- `ship_type`：枚举，可选值为 "散货船"、"油轮"、"集装箱船"、"客船"
- `length_overall`：浮点数，大于 0 且小于 500
- `designer_email`：可选字段，必须是有效的邮箱格式
- `requirements`：字符串列表，每个元素至少 5 个字符

### 练习2：阅读并注释
打开 `services/model_gateway/main.py`，找到所有 Pydantic 模型定义（第61-95行），在每行旁边添加注释解释其作用。

### 练习3：计算属性
为 `ShipDesignRequest` 添加一个 `@property` 方法 `size_category`，根据 `length_overall` 自动判断船舶大小类别：
- `< 100m`：小型
- `100-200m`：中型
- `> 200m`：大型

---

*上一篇：[01-Python异步编程.md](./01-Python异步编程.md)*
*下一篇：[03-SQLAlchemy异步ORM.md](./03-SQLAlchemy异步ORM.md)*
