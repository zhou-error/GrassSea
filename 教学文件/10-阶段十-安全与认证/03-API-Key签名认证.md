# 03 - API Key 签名认证

## 学习目标

1. 理解 HMAC-SHA256 签名认证的原理
2. 掌握 API Key + Secret 的配对使用方式
3. 理解时间戳在防重放攻击中的作用
4. 了解 API Key 的加密存储方案

## 前置知识

- 基础 Python（字符串、bytes、hashlib 模块）
- 理解 JWT 认证的基本概念（阶段十第1章）
- 了解哈希函数的基本概念（如 MD5、SHA256 能把任意数据变成固定长度的"指纹"）

## 概念讲解

### 为什么需要 API Key 签名？

JWT 适合人类用户通过浏览器登录的场景，但对于机器间的 API 调用（如外部系统调用 GrassSea 的内部接口），需要有更适合机器的方法。

```
JWT 认证 vs API Key 签名的适用场景：

JWT (人类用户):
┌──────────────────────────────────────────────┐
│ 浏览器 → 登录页 → 输入密码 → 获得 JWT       │
│ 场景：Web 前端调用后端 API                    │
│ 特点：有过期时间、需要刷新、绑定用户身份      │
└──────────────────────────────────────────────┘

API Key 签名 (机器/外部系统):
┌──────────────────────────────────────────────┐
│ 第三方系统 → 带签名的请求 → GrassSea API     │
│ 场景：自动化的数据同步、Webhook 回调等        │
│ 特点：长期有效、不需要登录、重在防篡改        │
└──────────────────────────────────────────────┘
```

### HMAC-SHA256 签名工作原理

HMAC = Hash-based Message Authentication Code（基于哈希的消息认证码）。核心思路：用密钥 + 消息内容生成一个"签名"，接收方用同样的密钥验证签名。

```
发送方（客户端）:
┌─────────────────────────────────────────────────┐
│                                                  │
│  api_key = "gs_abc123..."     ← 公开的 Key        │
│  secret   = "f7e3d2..."      ← 私有的 Secret     │
│                                                  │
│  请求体 payload = {"query": "计算稳性"}          │
│       │                                          │
│       ▼                                          │
│  HMAC-SHA256(payload, secret)                    │
│       │                                          │
│       ▼                                          │
│  signature = "a1b2c3d4..."   ← 消息认证码         │
│                                                  │
│  发送: Headers {                                 │
│    "X-API-Key": "gs_abc123...",                 │
│    "X-Signature": "a1b2c3d4..."                 │
│  } + 请求体                                      │
└─────────────────────────────────────────────────┘

接收方（服务器）:
┌─────────────────────────────────────────────────┐
│                                                  │
│  1. 从 Header 中取出 X-API-Key                   │
│  2. 用 X-API-Key 查到对应的 secret               │
│  3. 对收到的 payload 执行同样的 HMAC-SHA256      │
│  4. 比较计算结果与 X-Signature 是否一致           │
│                                                  │
│  一致 → 签名有效，请求未被篡改 ✓                  │
│  不一致 → 签名无效，请求被篡改或伪造 ✗           │
│                                                  │
│  关键点: 攻击者知道 api_key，但不知道 secret，    │
│  所以无法伪造签名。                              │
└─────────────────────────────────────────────────┘
```

### 签名认证的三层防护

```
第一层：认证（谁在调用？）
┌──────────────────────────────────────┐
│ 通过 X-API-Key 识别调用方身份        │
└──────────────────────────────────────┘

第二层：完整性（消息被改过吗？）
┌──────────────────────────────────────┐
│ 通过 HMAC 签名验证消息内容未被篡改   │
│ 哪怕改了一个字符，签名就对不上了     │
└──────────────────────────────────────┘

第三层：防重放（是旧的请求吗？）
┌──────────────────────────────────────┐
│ 通过请求中的时间戳，拒绝过期的请求   │
│ 攻击者截获了请求也无法重复使用       │
└──────────────────────────────────────┘
```

### API Key 的生成

API Key 不是随便生成的一串字符，它需要满足几个要求：
- **唯一性**：每个用户的 Key 不同
- **不可猜测**：不能被枚举或暴力破解
- **可关联**：能追溯到具体的用户

GrassSea 的生成方式（`shared/middleware/security.py` 第40-45行）：

```
生成过程:
  user_id + 当前时间戳
       │
       ▼ SHA256 哈希
  64位十六进制字符串  →  取前32位
       │
       ▼ 加上前缀
  "gs_abc123def456..."  ← api_key（类似用户名）

  secret 也类似生成:
  api_key + 时间戳 → SHA256 → 64位 → secret
```

## 项目代码精讲

### API Key 生成代码

```python
# shared/middleware/security.py 第40-45行
def generate_api_key(user_id: str) -> tuple[str, str]:
    """生成 API Key 和 Secret"""
    api_key = f"gs_{hashlib.sha256(f'{user_id}:{time.time()}'.encode()).hexdigest()[:32]}"
    secret = hashlib.sha256(f"secret_{api_key}_{time.time()}".encode()).hexdigest()
    API_KEYS[api_key] = {"user_id": user_id, "secret": secret,
                         "created": datetime.utcnow()}
    return api_key, secret
```

**逐段解析**：

1. `hashlib.sha256(...).encode()` — 将字符串编码为 bytes（Python 的 SHA256 需要 bytes 输入，不能直接接受 str）

2. `.hexdigest()[:32]` — 将哈希结果转为 64 位十六进制字符串，取前 32 位作为 api_key。对于 API Key 来说 32 位足够唯一（256 位熵），截断是为了缩短长度便于传输。

3. `f"gs_{...}"` — 给 api_key 加上 `gs_` 前缀。这是一个工程习惯：通过前缀快速识别 Key 的来源系统。

4. `secret = hashlib.sha256(...).hexdigest()` — Secret 使用完整的 64 位，因为它不暴露在 URL 中，长度不影响使用。

5. `API_KEYS[api_key] = {...}` — 将生成的 Key 信息存入内存字典。注意文档注释写着"生产环境存数据库"——内存存储在服务重启后会丢失。

6. 返回值是 `(api_key, secret)` 元组——api_key 给调用方作为"用户名"，secret 给调用方用于签名。调用方必须妥善保管 secret，不要泄露。

### 签名验证代码

```python
# shared/middleware/security.py 第48-51行
def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """验证 HMAC-SHA256 签名"""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**逐段解析**：

1. `payload: bytes` — 注意参数类型是 `bytes`，不是 `str`。Python 中 `"hello".encode()` 将 str 转为 bytes。调用前需要确保 payload 已经编码。

2. `hmac.new(secret.encode(), payload, hashlib.sha256)` — 使用 HMAC 算法计算签名。三个参数依次是：密钥（bytes）、消息内容（bytes）、哈希算法（SHA256）。这个计算是单向的——知道输入可以算出输出，但从输出反推不出输入。

3. `.hexdigest()` — 将二进制签名转为十六进制字符串，便于在 HTTP Header 中传输。

4. `hmac.compare_digest(expected, signature)` — **关键的安全细节**：使用 `compare_digest` 而不是 `==`。因为普通的 `==` 比较在字符串不相同时会提前返回（用时不同），这会让攻击者通过测量响应时间逐步猜出正确的签名（时序攻击）。`compare_digest` 每次比较都花费相同的时间，消除了这个隐患。

### API Key 的加密存储

GrassSea 使用 Fernet（AES-128-CBC + HMAC）加密存储敏感配置，包括 API Key：

```
存储架构（shared/utils/secrets.py）:

  明文 API Key           加密存储              运行时解密
  ┌──────────┐    ┌──────────────────┐    ┌──────────┐
  │ sk-xxxx  │───▶│ .grasssea_secrets│───▶│ sk-xxxx  │
  │ (永不落盘)│    │ (密文, 可提交Git) │    │ (只在内存)│
  └──────────┘    └──────────────────┘    └──────────┘
       │                   │                    │
       │            .grasssea_key               │
       │           (密钥文件，不可提交Git)        │
       └───────────────────┴────────────────────┘

安全特性:
- 明文 Key 永不写入磁盘
- 密钥和数据分离存储（两个文件）
- 密文离开本机无法解密（需同时持有 key 文件）
- .gitignore 保护密钥文件，不会误提交
```

## 手把手实践

### 实验一：手动验证 HMAC 签名

打开 Python 交互环境（`python` 或 `python3`）：

```python
import hmac
import hashlib

# 模拟服务器端的密钥
secret = "my-secret-key"

# 模拟收到的请求
payload = b'{"query": "test"}'
signature_from_client = "abc123..."  # 客户端发来的签名

# 服务器端计算期望的签名
expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
print("期望签名:", expected)
print("客户端签名:", signature_from_client)
print("验证结果:", hmac.compare_digest(expected, signature_from_client))

# 尝试篡改 payload 再验证
tampered_payload = b'{"query": "hacked"}'
tampered_expected = hmac.new(secret.encode(), tampered_payload, hashlib.sha256).hexdigest()
print("篡改后签名:", tampered_expected)
print("篡改验证:", hmac.compare_digest(expected, tampered_expected))
# 输出: False — 签字对不上
```

### 实验二：追踪 API Key 的生成

1. 打开 `shared/middleware/security.py`
2. 找到 `generate_api_key` 函数（第40行）
3. 逐行理解：user_id 被如何编码？api_key 的前缀是什么？secret 的长度是多少？
4. 找到 `verify_hmac_signature` 函数（第48行），理解为什么用 `compare_digest` 而不是 `==`

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "HMAC 消息认证码 原理" -- 理解 HMAC 的数学原理
- "API Key 签名认证 实现" -- 学习如何实现 API 签名
- "Web API 安全 防篡改" -- 了解 API 安全的整体方案
- "时序攻击 原理与防范" -- 理解为什么需要 `compare_digest`

## 常见问题与排错

**Q1：API Key 和 Secret 有什么区别？**

A：API Key 是"公钥"，可以放在 URL 或 Header 中用于识别身份。Secret 是"私钥"，只在签名计算时使用，绝不对外传输。可以类比为"用户名"和"密码"的关系——只不过这里密码通过 HMAC 间接使用，不直接发送。

**Q2：为什么 `compare_digest` 比 `==` 更安全？**

A：`==` 按字符逐个比较，遇到第一个不同的字符就返回 `False`。攻击者可以通过测量服务器响应时间，逐位猜出正确的签名（这就是"时序攻击"）。`compare_digest` 每次比较耗时相同，消除了这个信息泄露。

**Q3：API Key 存在内存字典中有什么问题？**

A：服务重启后所有 Key 丢失。生产环境应存储到数据库中（如 PostgreSQL），并启用定期轮换（rotation）机制。GrassSea 代码中已标注了 `# 生产环境存数据库` 的提醒。

**Q4：签名能防止重放攻击吗？**

A：单靠 HMAC 签名不能——攻击者截获一个完整请求后可以直接重放（因为签名也是有效的）。需要在签名中纳入时间戳或随机数（nonce），服务端检查时间戳是否在允许的窗口内。GrassSea 的预签名 URL 就使用了 `expires` 参数来实现时效控制。

## 练习任务

1. **概念题**：用自己的话解释 HMAC 签名验证三步走：发送方签名 -> 传输 -> 接收方验证。
2. **代码题**：在 Python 中写一个函数，接收 `api_key`、`secret`、`payload` 三个参数，计算签名并返回完整的 HTTP 请求头（包含 `X-API-Key` 和 `X-Signature`）。
3. **安全题**：如果攻击者截获了一个包含 `X-Signature` 的请求，但修改了请求体中的 `query` 字段，他能伪造出新的有效签名吗？为什么？
4. **扩展题**：阅读 `shared/utils/secrets.py`，理解 Fernet 加密的三个核心步骤：生成密钥、加密存储、解密读取。
