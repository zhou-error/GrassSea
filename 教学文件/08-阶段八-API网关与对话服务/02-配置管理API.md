# 02 - 配置管理 API

## 学习目标

1. 理解 GrassSea 的动态配置热加载机制（无需重启容器即可修改配置）
2. 掌握敏感配置（API Key）的 Fernet 加密存储方案
3. 理解配置变更如何自动传播到下游微服务
4. 学会设计并实现 RESTful 的配置管理 API

## 前置知识

- 了解环境变量和 `.env` 文件的基本概念
- 了解 HTTP API 的 GET/PUT/POST 请求
- 了解对称加密的基本概念（不需要深究密码学细节）
- 掌握 Python 的 `BackgroundTasks` 基本用法

## 概念讲解

### 为什么需要动态配置管理？

传统做法是修改 `.env` 文件，然后重启容器。但这有几个问题：

1. **重启太慢** — 容器重启需要几十秒到几分钟，影响服务可用性
2. **忘记配置** — 重启后往往忘记改了什么
3. **多服务同步** — 一个 Key 改了，需要逐个重启所有依赖它的服务

GrassSea 的解决方案：

```
  [用户修改 DeepSeek API Key]
              |
              v
  PUT /config/update {"key": "DEEPSEEK_API_KEY", "value": "sk-xxx"}
              |
              v
  +----------------------------+
  |  Chat Service (8001)       |
  |  1. 判断是否敏感 key       |
  |  2. 敏感 -> Fernet 加密存储 |
  |  3. 更新 os.environ        |
  |  4. 后台推送到下游服务      |
  +----------------------------+
        |        |        |
        v        v        v
    Agent    Knowledge  Model
    Service  Service   Gateway
    (8002)   (8003)    (8004)
   /admin/reload 端点接收新配置
```

### Fernet 加密方案

```
首次启动                    后续启动
---------                    --------
生成 .grasssea_key           读取 .grasssea_key
   |                              |
   v                              v
+--------+                  +--------+
| Fernet |  <-- 对称密钥    | Fernet |
+--------+                  +--------+
                               |
                    解密 .grasssea_secrets
                               |
                               v
                    注入 os.environ
```

- `.grasssea_key` — 对称加密密钥（自动生成，永不提交到 Git）
- `.grasssea_secrets` — 加密存储的 API Key 集合（可提交到 Git，因为已加密）

### 配置项分类

GrassSea 的配置分为几大类：

| 分类 | 示例 Key | 存储方式 |
|------|----------|---------|
| LLM | DEEPSEEK_API_KEY, CLAUDE_API_KEY | Fernet 加密 |
| 模型 | EMBEDDING_MODEL, EMBEDDING_DIM | .env 文件 |
| RAG | rag_chunk_size, rag_top_k | .env 文件 |
| 会话 | max_context_turns | .env 文件 |
| 搜索 | BRAVE_SEARCH_API_KEY | Fernet 加密 |

所有配置项定义在 `CONFIG_SCHEMA` 列表中，每个配置项有 key/label/category/type/sensitive 属性。

## 项目代码精讲

**文件位置**: `services/chat_service/config_api.py`

### 1. 启动时加载加密密钥

```python
# ---- 模块加载时：解密并注入敏感配置到环境变量 ----
_secrets = load_secrets()
for _k, _v in _secrets.items():
    os.environ[_k] = _v
    # 同步更新 pydantic Settings 对象
    if hasattr(settings, _k):
        setattr(settings, _k, _v)
if _secrets:
    logger.info("Encrypted secrets loaded into environment", keys=list(_secrets.keys()))
```

**逐段解析**：

这段代码在 `config_api.py` 被 `import` 时自动执行（模块级别的代码）。

1. `load_secrets()` — 调用 `shared/utils/secrets.py` 中的解密函数，读取 `.grasssea_key` 和 `.grasssea_secrets`，解密得到所有 Key。

2. `os.environ[_k] = _v` — 将解密后的 Key 注入环境变量，这样 `os.getenv("DEEPSEEK_API_KEY")` 就能获取到真实值。

3. `setattr(settings, _k, _v)` — 同步更新 Pydantic Settings 对象。Pydantic Settings 会在启动时读取环境变量并缓存，所以需要手动更新。

**为什么需要同步 settings 对象？** 因为 `settings.DEEPSEEK_API_KEY` 不会自动从 `os.environ` 重新读取。`setattr` 确保两种访问方式都能获得最新值。

### 2. 配置项 Schema 定义

```python
CONFIG_SCHEMA: list[dict] = [
    {"key": "DEEPSEEK_API_KEY",  "label": "DeepSeek API Key",
     "category": "LLM", "type": "password", "sensitive": True},
    {"key": "DEEPSEEK_BASE_URL", "label": "DeepSeek 接口地址",
     "category": "LLM", "type": "text"},
    {"key": "EMBEDDING_MODEL",   "label": "Embedding 模型",
     "category": "模型", "type": "select",
     "options": ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"]},
    {"key": "rag_chunk_size",    "label": "文档分块大小 (tokens)",
     "category": "RAG", "type": "number", "default": "512"},
    ...
]
```

**代码精讲**：

每个配置项有 6 个属性：

- `key` — 环境变量名
- `label` — 前端显示的中文名
- `category` — 分类（用于前端分组展示）
- `type` — 控件类型（"password" = 密码框, "text" = 文本框, "select" = 下拉选择, "number" = 数字输入）
- `sensitive` — 是否敏感（true 则加密存储、前端脱敏显示）
- `options` / `default` — 可选值和默认值

这种"配置描述"的设计让前端可以**自动生成**设置页面，无需为每个配置项单独写表单。新增配置项只需要在 `CONFIG_SCHEMA` 中加一条记录。

### 3. 读取配置（脱敏展示）

```python
@router.get("/schema", response_model=list[ConfigItemResponse])
async def get_config_schema():
    """获取所有可配置项（含当前值）"""
    envs = _read_env()
    result = []
    for item in CONFIG_SCHEMA:
        value = envs.get(item["key"], item.get("default", ""))
        # 敏感字段脱敏
        if item.get("sensitive") and value:
            masked = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
            value = masked
        result.append(...)
    return result
```

**脱敏逻辑详解**：

```python
masked = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
```

例如 `sk-1234567890abcdefgh` 会被脱敏为 `sk-1****efgh`。前端显示脱敏后的值，但也有足够的信息让用户确认"这是我配置的那个 Key"。

### 4. 更新配置（核心逻辑）

```python
@router.put("/update")
async def update_config(request: ConfigUpdateRequest, background_tasks: BackgroundTasks):
    """更新单个配置项 — 敏感 Key 加密存储，自动推送到下游"""

    # --- 安全检查：防止提交脱敏值 ---
    if item.get("sensitive") and request.value.count("*") > 4:
        raise HTTPException(status_code=400, detail="请勿提交脱敏后的值")

    # --- 敏感 Key 处理 ---
    if is_sensitive_key(request.key):
        update_secret(request.key, request.value)      # Fernet 加密存储
        os.environ[request.key] = request.value         # 内存注入
        background_tasks.add_task(_propagate_to_services, request.key, request.value)
        return {"status": "ok", "encrypted": True}

    # --- 普通配置处理 ---
    envs = _read_env()
    envs[request.key] = request.value
    _write_env(envs)
    os.environ[request.key] = request.value

    if request.key in PROPAGATABLE_KEYS:
        background_tasks.add_task(_propagate_to_services, request.key, request.value)

    return {"status": "ok"}
```

**逐步拆解这个核心方法**：

**步骤 1: 安全校验**

```python
if item.get("sensitive") and request.value.count("*") > 4:
    raise HTTPException(status_code=400, detail="请勿提交脱敏后的值")
```

这是一个聪明的防护。前端显示的 Key 是脱敏的（`sk-1****efgh`），如果用户不修改就直接点"保存"，提交的值会包含 `****`。这段代码检测到超过 4 个 `*` 就拒绝请求，提示用户重新输入完整 Key。

**步骤 2: 敏感 Key 处理**

```python
if is_sensitive_key(request.key):
    update_secret(request.key, request.value)   # Fernet 加密写入文件
    os.environ[request.key] = request.value      # 注入环境变量
    background_tasks.add_task(_propagate_to_services, ...)
```

- `update_secret()` — 用 Fernet 加密 Key，写入 `.grasssea_secrets` 文件
- `os.environ[...] = ...` — 同时注入当前进程的环境变量（不必等重启）
- `background_tasks.add_task()` — 启动后台任务推送到下游。这里不等待推送结果，API 先返回给前端，推送在后台进行。

**步骤 3: 普通配置处理**

```python
envs = _read_env()        # 读取当前 .env
envs[request.key] = request.value
_write_env(envs)           # 写回 .env（保留注释和空行）
os.environ[request.key] = request.value
```

`_write_env()` 保留原有的注释和空行，而不是整个重写文件。这使得手动编辑 `.env` 和通过 API 修改可以共存。

### 5. 配置推送（传播机制）

```python
async def _propagate_to_service_urls(payload: dict[str, str]) -> dict[str, str]:
    """推送配置到所有下游服务"""
    service_urls = [
        settings.MODEL_GATEWAY_URL,
        settings.AGENT_SERVICE_URL,
        settings.KNOWLEDGE_SERVICE_URL,
    ]

    results = {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
        for url in service_urls:
            try:
                resp = await client.post(f"{url}/admin/reload", json=payload)
                results[url] = "ok" if resp.status_code == 200 else f"HTTP {resp.status_code}"
            except httpx.ConnectError:
                results[url] = "unreachable"
            except Exception as e:
                results[url] = str(e)

    return results
```

**精讲传播策略**：

1. **短超时** — `timeout=5.0, connect=3.0`。推送不需要长时间等待——下游服务的 `/admin/reload` 是轻量操作（只是更新内存中的环境变量）。

2. **容错** — 某个服务不可达（`ConnectError`），不会中断其他服务的推送。结果字典记录了每个服务的推送状态。

3. **重试机制** — 在启动传播 `_propagate_all_secrets` 中，有最多 5 次重试，间隔 3 秒。处理"下游服务还没启动完"的场景。

### 6. 启动时传播（带重试）

```python
async def _propagate_all_secrets(max_retries: int = 5, retry_delay: float = 3.0) -> None:
    secrets = load_secrets()
    if not secrets:
        return

    payload = {k: v for k, v in secrets.items() if is_sensitive_key(k)}

    for attempt in range(1, max_retries + 1):
        results = await _propagate_to_service_urls(payload)
        failures = [url for url, status in results.items() if status != "ok"]

        if not failures:
            logger.info("Startup secrets propagated", keys=list(payload.keys()))
            return

        logger.warning("Startup propagation retry", attempt=attempt, failures=failures)
        if attempt < max_retries:
            await asyncio.sleep(retry_delay)

    logger.error("Startup propagation failed after retries", failures=failures)
```

这段代码展示了"优雅重试"的设计模式：
1. 有最大重试次数（5次）
2. 每次重试之间有延迟（3秒）
3. 单次成功就立即退出
4. 全部失败后记录错误日志

### 7. LLM 连接测试

```python
@router.post("/test-llm")
async def test_llm_connection():
    envs = _read_env()
    api_key = envs.get("DEEPSEEK_API_KEY", "")
    base_url = envs.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key or api_key.startswith("your-"):
        return {"status": "error", "message": "请先配置 DeepSeek API Key"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10},
        )
```

`api_key.startswith("your-")` 检查 Key 是否是默认占位符（如 `your-deepseek-api-key`），这是 `.env.example` 中的占位值风格。

## 手把手实践

### 实践1: 通过 API 查看和修改配置

```bash
# 1. 查看所有配置项 schema
curl http://localhost:8001/config/schema | python -m json.tool

# 2. 修改 RAG chunk_size
curl -X PUT http://localhost:8001/config/update \
  -H "Content-Type: application/json" \
  -d '{"key": "rag_chunk_size", "value": "1024"}'

# 3. 测试 LLM 连接
curl -X POST http://localhost:8001/config/test-llm
```

### 实践2: 添加一个新配置项

在 `CONFIG_SCHEMA` 中添加：

```python
{"key": "MAX_FILE_SIZE_MB", "label": "最大文件上传 (MB)",
 "category": "RAG", "type": "number", "default": "50"},
```

然后重启服务，访问 `/config/schema` 查看新配置项是否出现。

### 实践3: 模拟敏感配置脱敏

在 Python 中测试脱敏逻辑：

```python
def mask_sensitive(value):
    if len(value) > 8:
        return value[:4] + "****" + value[-4:]
    return "****"

# 测试
print(mask_sensitive("sk-1234567890abcdefghijklmn"))  # sk-1****klmn
print(mask_sensitive("short"))                          # ****
print(mask_sensitive(""))                               # 空字符串不脱敏
```

观察不同长度的字符串脱敏效果，理解为什么用 `> 8` 作为分界。

## 视频学习资源

1. **Python Fernet 加密实战** — cryptography 库的对称加密用法
   - 搜索关键词: `Python Fernet 加密 cryptography`
   - 推荐在 B 站搜索 "Python cryptography Fernet" 观看

2. **FastAPI BackgroundTasks 异步任务** — 后台任务处理
   - 搜索关键词: `FastAPI BackgroundTasks 后台任务`
   - 推荐在 B 站搜索 "FastAPI BackgroundTasks" 观看

3. **Pydantic Settings 配置管理** — 类型安全的配置方案
   - 搜索关键词: `Pydantic Settings 配置`
   - 推荐在 B 站搜索 "Pydantic" 或 "pydantic-settings" 观看

## 常见问题与排错

### Q1: 加密的 Key 重启后丢失

**原因**: `.grasssea_secrets` 文件被删除或损坏。
**排查**: 检查项目根目录是否有 `.grasssea_secrets` 和 `.grasssea_key` 文件。如果 `.grasssea_key` 丢失，加密数据无法解密。

### Q2: 前端显示 API Key 被脱敏，但用户想看到完整 Key

**设计意图**: 故意不提供"查看完整 Key"功能。这是安全最佳实践——配置后不应再明文展示。如果用户需要修改，直接输入新值覆盖即可。

### Q3: 修改配置后下游服务没生效

**排查步骤**:
1. 检查推送日志，看 `/admin/reload` 返回什么
2. 手动 curl 下游服务的 `/admin/reload` 端点确认可达
3. 检查下游服务的 `ADMIN_TOKEN`（如果有）是否匹配

### Q4: 为什么不用 Redis 做配置中心？

更复杂的系统会使用配置中心（如 Consul / Nacos / Apollo），但对于 GrassSea 当前规模，`.env + Fernet + 推送` 的组合已经足够，复杂度和可靠性达到了平衡。不使用 Radis 的额外原因是：减少外部依赖，降低部署复杂度。

## 练习任务

1. **基础练习**: 在 `CONFIG_SCHEMA` 中添加一个"默认模型选择"配置项，type 为 `"select"`，options 包含 `["deepseek-chat", "claude-sonnet-4-20250514"]`。

2. **进阶练习**: 阅读 `shared/utils/secrets.py` 文件，画出 Fernet 加密/解密/存储的完整流程图，标注每个函数的作用。

3. **挑战练习**: 在 config_api.py 中实现一个 `/config/batch-update` 端点，一次接受多个配置项的批量更新，并为每个配置项返回独立的更新结果。
