# 01 - pytest 单元测试

## 学习目标

1. 理解 pytest 测试框架的基本用法和命名约定
2. 掌握 `@pytest.fixture` 夹具的使用——管理测试中的共享资源
3. 理解异步测试（`@pytest.mark.asyncio`）的写法
4. 学会用 Mock 隔离外部依赖，让测试快速且可靠

## 前置知识

- 基础 Python（函数、类、import）
- 了解什么是"测试"——用代码验证代码的正确性
- 了解 pip 安装第三方库的基本操作

## 概念讲解

### 为什么需要单元测试？

你写完一段代码，怎么确认它是对的？手动运行一次？那如果改了别的代码后，怎么知道这个函数还能正常工作？单元测试就是为这个问题而生——**用自动化的方式验证代码的正确性**。

```
没有单元测试的开发流程:
  写代码 → 手动试一下 → 好像没问题 → 上线 → 出 Bug → 修复 → ...
  问题: 每次修改都可能破坏旧功能，但自己不知道

有单元测试的开发流程:
  写测试 → 写代码 → 运行测试 → 所有测试通过 ✓ → 放心上线
  优势: 每次修改后运行全部测试，立即知道是否破坏了旧功能
```

### pytest 基本约定

pytest 通过"约定大于配置"的方式发现和运行测试：

```
测试文件: test_*.py 或 *_test.py
        例如: test_config.py, test_logging.py, model_test.py

测试类:   Test* 开头
        例如: TestSettings, TestLogging, TestModelRouter

测试函数: test_* 开头
        例如: test_default_settings, test_postgres_uri

运行方式:
  pytest                          # 运行所有测试
  pytest tests/unit/             # 运行指定目录
  pytest tests/unit/test_config.py  # 运行指定文件
  pytest -v                      # 详细输出 (verbose)
  pytest -x                      # 遇错即停
  pytest -k "test_config"        # 只运行匹配关键字的测试
```

### Fixture（夹具）— 共享测试资源

Fixture 是 pytest 最重要的概念之一。它让你在测试前准备资源（如数据库连接、配置对象），在测试后清理资源。

```
Fixture 的生命周期:

  def my_fixture():        ← 准备资源
      resource = setup()   ← 创建资源
      yield resource       ← 把资源交给测试使用
      resource.cleanup()   ← 测试结束，清理资源

  测试函数可以声明需要的 Fixture:

  def test_something(my_fixture):   ← 参数名 = Fixture 名
      result = my_fixture.do_work()
      assert result == expected

  pytest 自动匹配参数名和 Fixture 名，注入资源
```

### 异步测试

FastAPI 的代码大量使用 `async/await`，测试这些代码也需要异步测试。

```python
# 同步测试（普通）
def test_add():
    assert 1 + 2 == 3

# 异步测试（测试 async 函数）
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected
```

`@pytest.mark.asyncio` 标记告诉 pytest："这个测试函数是异步的，请在事件循环中运行它"。

## 项目代码精讲

GrassSea 的单元测试在 `tests/unit/` 目录下。我们选取两个代表性文件精读。

### 测试配置模块 — test_config.py

```python
# tests/unit/test_config.py 第7-8行
from shared.utils.config import Settings, get_settings

class TestSettings:
    def test_default_settings(self) -> None:
        """测试默认配置值"""
        settings = Settings()
        assert settings.APP_NAME == "GrassSea"
        assert settings.APP_VERSION == "0.1.0"
        assert settings.APP_ENV == "development"
```

**逐段解析**：

1. `from shared.utils.config import Settings, get_settings` — 导入被测试的类。被测试的代码在 `shared/utils/config.py`，测试文件在 `tests/unit/test_config.py`。

2. `class TestSettings:` — 测试类，以 `Test` 开头。这个名字清楚地告诉别人"这个类是测试 Settings 的"。

3. `def test_default_settings(self) -> None:` — 测试方法，以 `test_` 开头。方法名描述了测试内容："测试默认配置值"。

4. `settings = Settings()` — 创建一个 Settings 实例。注意：没有传任何参数，使用 Settings 类的默认值。

5. `assert settings.APP_NAME == "GrassSea"` — 断言。`assert` 是 Python 关键字，如果后面的表达式为 `False`，测试失败。这里验证默认的 APP_NAME 确实是 "GrassSea"。

6. 三个 assert 分别验证三个默认值。如果任何一个不匹配，pytest 会精确地告诉你哪个断言失败了，以及期望值和实际值是什么。

```python
    def test_get_settings_singleton(self) -> None:
        """测试配置单例"""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
```

**关键知识点 — 单例测试**：`get_settings()` 使用了 `@lru_cache` 装饰器，确保第二次调用返回同一个对象（单例模式）。`assert s1 is s2` 使用 `is`（身份比较，比较内存地址）而不是 `==`（值比较），验证两个调用返回的是同一个对象实例。

### 测试模型网关路由 — test_model_gateway.py

```python
# tests/unit/test_model_gateway.py
class TestModelRouter:
    @pytest.fixture
    def settings(self):
        return Settings(
            DEEPSEEK_API_KEY="test-key",
            CLAUDE_API_KEY="test-key",
        )

    @pytest.fixture
    async def router(self, settings):
        r = ModelRouter(settings)
        await r.initialize()
        yield r          # 测试运行期间使用这个 router
        await r.close()  # 测试结束后关闭

    @pytest.mark.asyncio
    async def test_route_simple_chat(self, router):
        """测试简单对话路由"""
        request = ModelRouteRequest(
            model="deepseek-chat",
            task_type="simple_chat",
        )
        result = await router.route(request)
        assert result.model == "deepseek-chat"
        assert result.provider == "deepseek"
```

**逐段解析**：

1. `@pytest.fixture` — 声明 `settings` 是一个 Fixture。测试类中的 Fixture 方法需要 `self` 参数。

2. `Settings(DEEPSEEK_API_KEY="test-key", ...)` — 创建一个测试用的 Settings，使用假的 API Key。**不连接真实的 DeepSeek API**。

3. `async def router(self, settings):` — 第二个 Fixture。注意它的参数 `settings` 引用了第一个 Fixture。pytest 的依赖注入会自动先调用 `settings()`，再把结果传给 `router()`。

4. `await r.initialize()` — 初始化路由（这可能包括加载模型列表等准备工作）。

5. `yield r` — 把 router 实例交给测试函数使用。`yield` 之前的代码是"准备"阶段，`yield` 之后的 `await r.close()` 是"清理"阶段。

6. `@pytest.mark.asyncio` — 标记为异步测试。

7. `async def test_route_simple_chat(self, router):` — 测试函数声明参数 `router`，pytest 会自动注入 `router` Fixture 的返回值。

8. `ModelRouteRequest(model="deepseek-chat", task_type="simple_chat")` — 构造测试请求数据。

9. `result = await router.route(request)` — 调用被测试的方法。

10. `assert result.model == "deepseek-chat"` — 验证模型名称正确。
11. `assert result.provider == "deepseek"` — 验证提供商识别正确。

### 测试未知模型降级

```python
    @pytest.mark.asyncio
    async def test_route_unknown_model_fallback(self, router):
        """测试未知模型降级"""
        request = ModelRouteRequest(
            model="unknown-model",
            task_type="simple_chat",
        )
        result = await router.route(request)
        assert result.model == "deepseek-chat"
```

这个测试验证了一个重要的容错行为：当请求的模型不存在时，系统应该降级（fallback）到默认模型 `deepseek-chat`，而不是直接报错。测试"异常路径"和测试"正常路径"同样重要。

## 手把手实践

### 实验一：运行现有测试

1. 在项目根目录打开终端
2. 运行：`pytest tests/unit/test_config.py -v`
3. 观察输出：每个测试的名字、PASSED/FAILED 状态
4. 故意修改 `Settings` 的一个默认值（如把 APP_NAME 改为别的），重新运行测试，观察失败信息

### 实验二：编写你的第一个测试

创建一个简单的测试文件 `tests/unit/test_my_first.py`：

```python
import pytest

def add(a: int, b: int) -> int:
    return a + b

def test_add_positive():
    assert add(2, 3) == 5

def test_add_negative():
    assert add(-1, -1) == -2

def test_add_zero():
    assert add(0, 5) == 5

@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
    (100, 200, 300),
])
def test_add_parametrized(a, b, expected):
    assert add(a, b) == expected
```

运行 `pytest tests/unit/test_my_first.py -v`，观察 `parametrize` 如何把一组测试数据变成四个独立的测试用例。

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "pytest 入门教程 fixture" -- 从零开始学 pytest
- "pytest.mark.parametrize 参数化测试" -- 学习高效的参数化测试
- "Python 单元测试 Mock 模拟" -- 学习如何模拟外部依赖
- "测试驱动开发 TDD pytest" -- 了解先写测试再写代码的开发方式

## 常见问题与排错

**Q1：`assert s1 is s2` 和 `assert s1 == s2` 有什么区别？**

A：`is` 比较身份（两个变量是否指向同一个内存对象），`==` 比较值（两个对象的内容是否相等）。测试单例时用 `is`，测试数据内容时用 `==`。

**Q2：Fixture 中的 `yield` 和 `return` 有什么区别？**

A：`return` 把值交给测试后，Fixture 函数就结束了，无法执行清理代码。`yield` 把值交给测试后"暂停"，等测试完成后再继续执行 `yield` 之后的清理代码。

**Q3：异步测试报错 "no running event loop"？**

A：确保安装了 `pytest-asyncio` 包，并且在测试函数上添加了 `@pytest.mark.asyncio` 装饰器。

**Q4：测试应该覆盖 100% 的代码吗？**

A：不必要，也不划算。追求 100% 覆盖率往往导致大量低质量的测试（比如只测试 getter/setter）。建议聚焦：1) 核心业务逻辑；2) 容易出现 Bug 的边界条件；3) 之前出过 Bug 的地方。GrassSea 的目标是 80% 以上的覆盖率。

## 练习任务

1. **概念题**：pytest 如何发现测试文件和测试函数？（提示：回想"约定大于配置"的命名规则）
2. **实践题**：为 `check_permission` 函数（`shared/middleware/security.py` 第32行）编写单元测试，至少包含以下场景：
   - admin 角色访问任何权限都应通过
   - engineer 角色访问 `tool:use` 应通过
   - guest 角色访问 `project:write` 应被拒绝
   - 不存在的角色访问任何权限应被拒绝
3. **进阶题**：在 `test_config.py` 中添加一个测试，验证 `POSTGRES_URI` 属性在端口为 5432、用户为 "test" 时的完整 URI 格式是否正确。
4. **思考题**：为什么 `test_model_gateway.py` 中使用 `"test-key"` 作为 API Key 而不是真实的 Key？Mock 在测试中扮演什么角色？
