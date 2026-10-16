# 04 - Axios 客户端封装

## 学习目标

1. 理解 Axios 实例创建、拦截器机制和模块化导出模式
2. 掌握请求拦截器（添加 token）和响应拦截器（统一错误处理）的编写
3. 理解 `FormData` 文件上传的 Axios 封装方式
4. 能够将 API 调用封装为独立模块，保持代码整洁

## 前置知识

- 了解 HTTP 请求方法（GET、POST）和请求头（Content-Type）
- 了解 Promise 和 async/await 的基础用法
- 了解 TypeScript 的类型标注

## 概念讲解

### Axios 在项目中的位置

```
  React 组件
     |
     | 调用 API 模块函数
     v
  api/index.ts  (封装层)
     |
     | 使用 Axios 实例
     v
  Axios 实例 (基础配置 + 拦截器)
     |
     | HTTP 请求
     v
  Vite 代理 (/api -> localhost:8001)
     |
     | 转发
     v
  Chat Service (API 网关)
```

Axios 封装层充当了"前端请求管家"——所有 HTTP 请求都必须通过它，它负责：
1. 设置基础 URL（`/api`）
2. 配置超时时间
3. 附加请求头
4. 拦截和处理错误

### 为什么需要封装 Axios？

```
不用封装:           用封装:
组件A: axios.post()  组件A: chatApi()
组件B: axios.post()  组件B: chatApi()   <-- 统一的 API 函数
组件C: axios.get()   组件C: getTaskApi()

问题:                 好处:
- URL 散落各处        - API 函数集中管理
- 配置重复            - 配置只写一次
- 错误处理不一致      - 拦截器统一处理
- 难以迁移            - 换库只改封装层
```

## 项目代码精讲

**文件位置**: `frontend/src/api/index.ts`

### 1. Axios 实例创建

```typescript
import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
});
```

**逐段解析**：

1. `const API_BASE = '/api';` — 基础路径。注意是 `/api` 而不是 `http://localhost:8001`。因为 Vite 开发代理会自动将 `/api/*` 转发到后端。

2. `axios.create({...})` — 创建 Axios 实例，而非使用全局的 `axios`。**实例化是关键**——这样可以为不同的后端服务创建不同的实例（不同的 baseURL、timeout、拦截器）。

3. `timeout: 60000` — 60 秒超时。AI 对话可能因为 LLM 推理需要较长时间，60 秒足够。普通 API 通常会设 10-15 秒。

4. `headers: { 'Content-Type': 'application/json' }` — 默认请求头。大部分 API 都是 JSON 格式，设好默认值避免每个请求重复写。

### 2. 响应拦截器

```typescript
api.interceptors.response.use(
  (res) => res,
  (err) => Promise.reject(err)
);
```

**代码精讲**：

拦截器的签名是 `use(onFulfilled, onRejected)`：

- **onFulfilled** `(res) => res` — 成功响应直接透传。这里不处理是因为 GrassSea 各组件自己处理业务成功逻辑。

- **onRejected** `(err) => Promise.reject(err)` — 错误原样抛出。调用方用 try/catch 处理。

当前实现非常简洁（相当于"无拦截"），但拦截器的结构为后续扩展打好了基础。常见的扩展场景：

```typescript
// 请求拦截器：添加认证 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：统一错误处理
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // 跳转到登录页
      window.location.href = '/login';
    }
    if (err.response?.status === 500) {
      // 显示统一错误提示
      message.error('服务器内部错误，请稍后重试');
    }
    return Promise.reject(err);
  }
);
```

### 3. API 模块化导出

```typescript
// Chat
export const chatApi = (message: string, sessionId?: string) =>
  api.post('/chat', { message, session_id: sessionId });
```

**代码精讲**：

- `message: string` — 必传参数，用户输入的消息内容
- `sessionId?: string` — 可选参数（`?` 表示可选），首次对话时为空
- `{ message, session_id: sessionId }` — JS 对象简写 + 驼峰转下划线。前端用驼峰命名（`sessionId`），后端 Python 期望下划线（`session_id`），在 API 层做转换。

```typescript
// RAG
export const ragQueryApi = (query: string) =>
  api.post('/rag/query', { query });
```

简短的 API 模块。RAG 查询只需要一个 `query` 参数。

```typescript
export const uploadDocumentApi = (file: File, kb: string) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post(`/rag/documents?knowledge_base=${encodeURIComponent(kb)}`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
```

**文件上传的封装要点**：

1. `const fd = new FormData()` — 创建 `FormData` 对象，用于 multipart 文件上传。

2. `fd.append('file', file)` — 将文件对象加入表单。`'file'` 是字段名，必须和后端 FastAPI 的 `File(...)` 参数名一致。

3. `encodeURIComponent(kb)` — 对知识库名称进行 URL 编码。如果知识库名包含中文或特殊字符（如 `"项目知识库"`），必须编码才能在 URL 中安全传递。

4. `headers: { 'Content-Type': 'multipart/form-data' }` — 覆盖默认的 `application/json`。multipart 格式用于文件上传。

```typescript
// Task
export const getTaskStatusApi = (taskId: string) =>
  api.get(`/task/${taskId}/status`);
```

注意这里用 `api.get()` 而非 `api.post()`。查询操作应该用 GET 方法。

### 4. API 调用全景图

```
                     API 封装层 (api/index.ts)
                     ========================

  chatApi(msg, sid)  --->  POST /chat
                             {
                               message: "...",
                               session_id: "..."
                             }

  ragQueryApi(q)     --->  POST /rag/query
                             { query: "..." }

  uploadDocumentApi  --->  POST /rag/documents?knowledge_base=xxx
  (file, kb)                 FormData { file: <binary> }

  getTaskStatusApi   --->  GET /task/{taskId}/status
  (taskId)
```

## 手把手实践

### 实践1: 在组件中调用 API

```typescript
// 在 Chat.tsx 中
import { chatApi } from '../api';

const sendMessage = async () => {
  try {
    const res = await chatApi(currentInput, sessionId || undefined);
    const { session_id, answer, task_id } = res.data;
    // 处理响应...
  } catch (err) {
    console.error('请求失败:', err);
  }
};
```

### 实践2: 添加请求拦截器

在 `api/index.ts` 中添加请求拦截器：

```typescript
// 请求拦截器：打印所有请求
api.interceptors.request.use((config) => {
  console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  return config;
});
```

发送一条聊天消息，观察浏览器控制台输出的请求日志。

### 实践3: 添加响应拦截器统一错误处理

```typescript
import { message } from 'antd';

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.code === 'ECONNABORTED') {
      message.error('请求超时，请稍后重试');
    } else if (!err.response) {
      message.error('网络连接失败，请检查网络');
    } else {
      message.error(`请求失败: ${err.response.status}`);
    }
    return Promise.reject(err);
  }
);
```

## 视频学习资源

1. **Axios 从入门到实战** — 拦截器、实例封装完整教程
   - 搜索关键词: `Axios 拦截器 React 封装`
   - 推荐在 B 站搜索 "Axios 教程" 观看

2. **FormData 文件上传** — multipart/form-data 详解
   - 搜索关键词: `FormData 文件上传 Axios`
   - 推荐在 B 站搜索 "FormData 文件上传" 观看

3. **HTTP 状态码详解** — 2xx/4xx/5xx 的含义
   - 搜索关键词: `HTTP 状态码 详解`
   - 推荐在 B 站搜索 "HTTP 状态码" 观看

## 常见问题与排错

### Q1: 请求发送后报 CORS 错误

**错误信息**: `Access to XMLHttpRequest at '...' has been blocked by CORS policy`
**原因**: Vite 代理未生效或配置错误。
**解决**: 确认请求 URL 以 `/api` 开头，Vite 才会代理转发。

### Q2: 文件上传失败，后端收不到文件

**常见原因**:
1. `FormData` 的字段名与后端不匹配（前端 `fd.append('file', ...)` 但后端参数名是 `upload_file`）
2. Content-Type 头设置错误（multipart 必须用 `multipart/form-data`）
3. 文件大小超过限制（fastapi/nginx 默认有限制）

### Q3: GET 请求参数在 URL 中乱码

**原因**: 查询参数包含中文但未编码。
**解决**: 使用 `encodeURIComponent()` 对中文参数编码：
```typescript
api.get(`/search?query=${encodeURIComponent('稳性规范')}`);
```

### Q4: 请求超时但没有触发 catch

**原因**: Axios 的超时错误 `error.code === 'ECONNABORTED'`，捕获方式与网络错误不同。确保在拦截器中检查 `error.code`。

## 练习任务

1. **基础练习**: 在 `api/index.ts` 中添加一个 `getDocumentListApi(kb: string)` 函数，发送 GET 请求获取指定知识库的文档列表。

2. **进阶练习**: 在请求拦截器中实现"token 过期自动刷新"逻辑——当响应返回 401 时，尝试用 refresh token 获取新 token，成功后重试原请求。

3. **挑战练习**: 实现一个 `createCancellableRequest` 工具函数，支持取消正在进行的请求（使用 Axios 的 CancelToken）。在对话场景中，用户发送新消息时自动取消上一轮正在进行的请求。
