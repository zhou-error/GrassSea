# 01 - JWT 认证机制

## 学习目标

1. 理解 JWT（JSON Web Token）的结构和工作原理
2. 掌握 Access Token 与 Refresh Token 的区别和双 Token 刷新策略
3. 理解 HMAC 签名在 JWT 中的作用——为什么不能伪造 Token
4. 能够在 FastAPI 中集成 JWT 认证

## 前置知识

- 基础 Python（函数、字典、base64 编码）
- 了解 HTTP 请求头（Header）的概念
- 知道什么是 JSON 格式

## 概念讲解

### 为什么需要 Token 认证？

Web 应用面临一个基本问题：HTTP 是无状态的，服务器怎么知道"你是谁"？

```
传统方案（Session）：
┌──────────┐     ┌──────────┐     ┌──────────┐
│ 用户登录   │────▶│ 服务器    │────▶│ 返回      │
│ 提交密码   │     │ 创建会话  │     │ Cookie   │
└──────────┘     └──────────┘     └──────────┘
                                       │
         ┌─────────────────────────────┘
         ▼
┌──────────────────────────────────┐
│ 问题：服务器需要存储每个用户      │
│ 的 Session，内存开销大，          │
│ 不适合微服务（多台服务器）       │
└──────────────────────────────────┘

JWT 方案（无状态）：
┌──────────┐     ┌──────────┐     ┌──────────────────────────────┐
│ 用户登录   │────▶│ 服务器    │────▶│ 返回 JWT Token（一串字符串）  │
│ 提交密码   │     │ 签发 JWT  │     │ 包含用户信息 + 签名          │
└──────────┘     └──────────┘     └──────────────────────────────┘
                                       │
         ┌─────────────────────────────┘
         ▼
┌──────────────────────────────────┐
│ 优势：Token 本身包含用户信息，    │
│ 服务器不用存，任何微服务都能验证  │
└──────────────────────────────────┘
```

### JWT 的三段式结构

JWT 看起来像一串随机字符，但其实由三部分组成，用 `.` 分隔：

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.4K4bS4FfX6...

    Header           Payload         Signature
   (头部)           (载荷)            (签名)
```

用 ASCII 图解三部分的关系：

```
Header (头部)
┌────────────────────────────┐
│ {"alg": "HS256",           │  ← 签名算法（HMAC-SHA256）
│  "typ": "JWT"}             │  ← Token 类型
└────────────────────────────┘
         │
         ▼  Base64 编码
   eyJhbGciOiJIUzI1NiJ9

Payload (载荷)
┌────────────────────────────┐
│ {"sub": "user123",         │  ← 用户ID（subject）
│  "role": "engineer",       │  ← 用户角色
│  "exp": 1719123456,        │  ← 过期时间（Unix 时间戳）
│  "iat": 1719037056}        │  ← 签发时间
└────────────────────────────┘
         │
         ▼  Base64 编码
   eyJzdWIiOiJ1c2VyMTIzIn0

Signature (签名)
┌──────────────────────────────────────┐
│ HMAC-SHA256(                         │
│   Header + "." + Payload,            │  ← 前两段拼接
│   Secret_Key                         │  ← 服务器私钥
│ )                                     │
└──────────────────────────────────────┘
         │
         ▼  Base64 编码
   4K4bS4FfX6...

最终 Token:
Header.Payload.Signature
```

**为什么不能伪造**：如果你修改了 Payload（比如把角色改成 admin），签名就对不上了。因为签名是用服务器的 `Secret_Key` 计算的，你不知道这个密钥，算不出正确的签名。

### Access Token vs Refresh Token（双 Token 策略）

```
为什么需要两个 Token？

Access Token（访问令牌）:
┌─────────────────────────────────────┐
│ - 有效期短（15分钟-1小时）            │
│ - 放在请求头 Authorization 中         │
│ - 过期后需要刷新                      │
│ - 即使被盗，影响也有限                │
└─────────────────────────────────────┘

Refresh Token（刷新令牌）:
┌─────────────────────────────────────┐
│ - 有效期长（7天-30天）               │
│ - 只用于获取新的 Access Token        │
│ - 不参与业务请求                      │
│ - 被盗后可以吊销                      │
└─────────────────────────────────────┘

工作原理:

  用户请求 API（带着过期的 Access Token）
       │
       ▼
  ┌──────────┐   Token 过期   ┌──────────┐
  │ 业务服务   │──────────────▶│ 返回 401  │
  └──────────┘               └──────────┘
                                     │
                          前端自动用 Refresh Token
                          请求 /auth/refresh 获取新的
                          Access Token，然后重试请求
```

## 项目代码精讲

GrassSea 的认证与安全代码集中在 `shared/middleware/security.py`。JWT 认证虽然未在这个文件中直接实现，但其 RBAC 权限检查与 JWT 载荷紧密配合。

### 权限检查的核心函数

```python
# shared/middleware/security.py 第 20-27 行
ROLE_PERMISSIONS = {
    "admin": ["*"],
    "project_lead": ["project:read", "project:write",
                     "knowledge:read", "knowledge:write",
                     "member:manage", "task:assign"],
    "engineer": ["project:read", "project:write",
                 "knowledge:read", "tool:use", "report:generate"],
    "guest": ["project:read", "knowledge:read"],
    "api_user": ["api:access"],
}
```

这个字典定义了 GrassSea 的 5 种角色及其权限。当 JWT Token 签发时，`role` 会写入 Payload。后续请求验证 Token 后，系统从 Payload 中取出 `role`，用这个字典判断用户是否能执行某个操作。

```python
# 第 32-35 行
def check_permission(role: str, required: str) -> bool:
    """检查角色权限"""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or required in perms
```

**逐段解析**：

1. `ROLE_PERMISSIONS.get(role, [])` — 从字典中取出该角色对应的权限列表。如果角色不存在，返回空列表 `[]`（即没有任何权限）。

2. `"*" in perms` — 如果角色有通配符权限 `*`（如 admin），直接放行。这是一个性能优化——不必逐个比对权限。

3. `required in perms` — 检查具体的权限字符串是否在列表中。例如，engineer 角色有 `"project:read"` 权限，如果请求要求 `"project:read"`，则通过。

### 安全中间件的配置

```python
# 第 101-113 行
def setup_security(app: FastAPI) -> None:
    """配置安全中间件"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        max_age=3600,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuditMiddleware)
```

这个函数在服务启动时被调用，一次性注册所有安全中间件。中间件就像一道道的"安检闸门"，请求依次通过它们。具体顺序是：

```
请求 → CORS检查 → 安全Header注入 → JWT验证(外部) → RBAC权限检查 → 审计日志 → 业务逻辑
```

### 预签名 URL（补充知识点）

```python
# 第 56-63 行
def generate_presigned_url(
    bucket: str, object_path: str, expires_minutes: int = 15
) -> str:
    """生成 MinIO 预签名下载 URL"""
    expiry = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = f"{bucket}/{object_path}/{int(expiry.timestamp())}"
    signature = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"http://minio:9000/{bucket}/{object_path}?expires={int(expiry.timestamp())}&sig={signature}"
```

预签名 URL 的思路和 JWT 类似：将有效期限和签名嵌入 URL 中，文件服务器验证签名和过期时间后决定是否放行。这样即使 URL 泄露，也只能在限定时间内使用。

## 手把手实践

### 实验一：手动解码 JWT Token

1. 打开浏览器开发者工具（F12），进入 Application -> Local Storage
2. 找到存储的 JWT Token（格式为三段字符串）
3. 复制中间那段（Payload），去 https://jwt.io 粘贴
4. 观察解码后的内容（注意：JWT 不加密，Payload 只是 Base64 编码，任何人都能看到。所以绝不能在 JWT 中存放密码！）

### 实验二：追踪 GrassSea 的权限检查流程

1. 打开 `shared/middleware/security.py`
2. 找到 `ROLE_PERMISSIONS` 字典（第20行）
3. 找到 `check_permission` 函数（第32行）
4. 在脑海中模拟以下场景：
   - 用户角色是 `engineer`，请求操作是 `"tool:use"`，访问被允许吗？
   - 用户角色是 `guest`，请求操作是 `"project:write"`，访问被允许吗？

## 视频学习资源

请在 B站（bilibili.com）搜索以下关键词：

- "JWT 认证原理 通俗" -- 了解 JWT 的三段结构和签名机制
- "Access Token Refresh Token 双Token" -- 理解为什么需要两个 Token
- "FastAPI JWT 认证 实战" -- 在 FastAPI 中实现 JWT
- "OAuth 2.0 授权流程" -- 了解更完善的认证授权协议

## 常见问题与排错

**Q1：JWT 的 Payload 是加密的吗？**

A：不是加密，只是 Base64 编码（相当于明文）。任何人都能解码看到内容。JWT 的安全性在于**签名**——你可以看到内容，但不能伪造。千万不要在 JWT 中放密码之类的敏感信息。

**Q2：Token 过期了怎么办？**

A：前端应拦截 401 响应，自动用 Refresh Token 调用刷新接口。GrassSea 使用 `exp` 字段标记过期时间，服务端验证 Token 时检查该字段。

**Q3：为什么不在每次请求时都验证密码？**

A：每次验证密码需要查询数据库，性能开销大。JWT 的签名验证是纯数学计算（HMAC），速度极快，不需要查库。

**Q4：Refresh Token 被偷了怎么办？**

A：这是防御重点。Refresh Token 应只通过 HttpOnly Cookie 传输（JavaScript 无法读取），使用一次即失效（Refresh Token Rotation），并绑定设备指纹。

## 练习任务

1. **概念题**：JWT 由哪三部分组成？每一部分的作用是什么？
2. **代码题**：在 `shared/middleware/security.py` 中找到 `check_permission` 函数，写出它的执行逻辑（用自然语言描述，不需要代码）。
3. **实践题**：找一个在线 JWT 调试工具（jwt.io），手动输入 Header、Payload、Secret，观察生成的 Token。然后修改 Payload 中的 role，用同一个 Secret 重新签名，观察 Token 的变化。
4. **思考题**：如果 Access Token 的有效期设为 24 小时而不是 15 分钟，会带来什么安全隐患？提示：想想如果 Token 被盗了会怎样。
