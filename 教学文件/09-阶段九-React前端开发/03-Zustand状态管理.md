# 03 - Zustand 状态管理

## 学习目标

1. 理解 Zustand 的核心概念：store、state、action
2. 掌握 chatStore（消息列表/流式状态）的完整设计
3. 掌握 uiStore（侧栏展开/主题切换）的轻量用法
4. 理解 Zustand 与 Redux 的差异及选型理由

## 前置知识

- 了解 React Hooks 基础（useState, useEffect）
- 了解 React 组件间数据传递的"状态提升"概念
- 不需要 Redux 经验（Zustand 的设计就是为了不用 Redux）

## 概念讲解

### 为什么需要状态管理？

React 组件中有一个关键限制：**状态默认属于组件，兄弟组件无法直接共享**。

```
组件A (有自己的 state_A)
组件B (有自己的 state_B)   <-- 无法访问 state_A
```

解决方案：**把状态提取到组件树之外**：

```
      +-------------+
      |  Zustand    |  <-- 全局 Store（在组件树之外）
      |  Store      |
      +------+------+
             |
     +-------+-------+
     |               |
+----v----+     +----v----+
| 组件A   |     | 组件B   |
| 读写    |     | 读写    |
+---------+     +---------+
```

Zustand 和 Redux 都是做这件事的。区别在于 Zustand 的 API 极其简洁：

```typescript
// Zustand — 一个函数调用创建一个 store
const useStore = create((set) => ({
  count: 0,
  increment: () => set((s) => ({ count: s.count + 1 })),
}));

// Redux — 需要创建 slice / reducer / configureStore / Provider...
```

### chatStore vs uiStore 的设计分工

```
chatStore.ts   ->  聊天相关状态（业务状态）
  - sessionId: 当前会话 ID
  - messages:  消息列表
  - streaming: 是否正在流式接收
  - actions:   addMessage / appendContent / clearMessages

uiStore.ts     ->  UI 相关状态（界面状态）
  - collapsed: 侧边栏是否收起
  - theme:     主题（亮色/暗色）
  - actions:   toggleCollapsed / setTheme
```

这种拆分遵循"关注点分离"原则：聊天逻辑和 UI 逻辑互不干扰。

## 项目代码精讲

### 1. chatStore — 聊天状态管理

**文件位置**: `frontend/src/stores/chatStore.ts`

```typescript
import { create } from 'zustand';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  sources?: Array<{ chunk_id: string; text: string; source: Record<string, string> }>;
  taskId?: string;
}
```

**逐段解析**：

`interface Message` 定义了消息对象的数据结构：
- `id` — 唯一标识，用于更新和删除
- `role` — 角色：user（用户）、assistant（AI）、system（系统提示）
- `content` — 消息文本（Markdown 格式）
- `timestamp` — Unix 时间戳，用于排序和显示时间
- `sources?` — 可选字段，RAG 返回的引用来源
- `taskId?` — 可选字段，关联的异步任务 ID

`?` 表示可选字段（TypeScript 的 `Optional` 特性）。不是每条消息都有引用来源或任务 ID。

```typescript
interface ChatState {
  sessionId: string | null;
  messages: Message[];
  streaming: boolean;
  addMessage: (msg: Message) => void;
  appendContent: (id: string, chunk: string) => void;
  setSessionId: (id: string) => void;
  setStreaming: (v: boolean) => void;
  clearMessages: () => void;
}
```

**interface 中的 3 个数据字段 + 5 个方法**：

| 字段/方法 | 类型 | 用途 |
|-----------|------|------|
| sessionId | string\|null | 追踪对话会话 |
| messages | Message[] | 所有消息 |
| streaming | boolean | 是否正在接收 AI 回复 |
| addMessage | (msg)=>void | 追加一条新消息 |
| appendContent | (id,chunk)=>void | 追加文本到某条消息（流式） |
| setSessionId | (id)=>void | 设置会话 ID |
| setStreaming | (v)=>void | 设置流式状态 |
| clearMessages | ()=>void | 清空所有消息 |

```typescript
export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  streaming: false,

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
```

**最关键的代码**：

`create<ChatState>` — Zustand 的核心函数，泛型参数 `ChatState` 让 TypeScript 知道 store 里的所有字段类型。

`(set) => ({...})` — 工厂函数，接收 `set` 方法，返回初始状态对象。`set` 用于更新状态。

**addMessage 方法解析**：

```typescript
addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
```

- `set((s) => ({...}))` — `s` 是当前状态，返回新状态（部分更新，自动合并）
- `[...s.messages, msg]` — 展开旧消息数组，在末尾追加新消息

注意这里使用了"不可变更新"——创建新数组而非修改原数组（`s.messages.push(msg)` 是不对的）。

```typescript
  appendContent: (id, chunk) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + chunk } : m
      ),
    })),
```

**appendContent — 流式追加内容的核心**：

这是实现"打字效果"的关键方法。AI 回复是逐字返回的（流式输出），每收到一个字符就调用一次 `appendContent`。

```typescript
s.messages.map((m) =>
  m.id === id ? { ...m, content: m.content + chunk } : m
)
```

1. 用 `map` 遍历所有消息
2. 找到 ID 匹配的那条消息
3. 用 `{ ...m, content: m.content + chunk }` 创建一个新对象，内容追加 `chunk`
4. 其他消息原样返回

**性能考虑**：每条消息到达时 `map` 遍历整个数组。对于几百条消息的对话，这个 O(n) 操作完全可以接受。如果消息量巨大（几千条），需要优化（使用 `findIndex` + 直接替换）。

```typescript
  setSessionId: (id) => set({ sessionId: id }),
  setStreaming: (v) => set({ streaming: v }),
  clearMessages: () => set({ messages: [], sessionId: null }),
}));
```

- 简单方法直接用 `set({ key: value })` 不需要函数形式
- `clearMessages` 同时清空消息和会话 ID——开始新对话

### 2. uiStore — UI 状态管理

**文件位置**: `frontend/src/stores/uiStore.ts`

```typescript
import { create } from 'zustand';

interface UIState {
  collapsed: boolean;
  theme: 'light' | 'dark';
  toggleCollapsed: () => void;
  setTheme: (t: 'light' | 'dark') => void;
}

export const useUIStore = create<UIState>((set) => ({
  collapsed: false,
  theme: 'light',
  toggleCollapsed: () => set((s) => ({ collapsed: !s.collapsed })),
  setTheme: (t) => set({ theme: t }),
}));
```

**代码极其简短，但设计很精巧**：

1. `theme` 的类型是联合类型 `'light' | 'dark'`，TypeScript 会阻止赋值为其他字符串。
2. `toggleCollapsed` 使用函数形式的 `set`，因为需要读取旧值来取反。
3. uiStore 只有 2 个字段 + 2 个方法，不为"未来可能需要"的东西提前设计。

**在组件中使用 uiStore**：

```typescript
// 在 Sidebar 组件中：
import { useUIStore } from '@/stores/uiStore';

function Sidebar() {
  const collapsed = useUIStore((s) => s.collapsed);
  const toggleCollapsed = useUIStore((s) => s.toggleCollapsed);
  // ...
}
```

注意这里没有 Provider 包裹！Zustand 的 Store 是跨组件的全局单例，直接 `useXxxStore()` 即可。不需要像 Redux 那样在根组件包一层 `<Provider>`。

### 3. Zustand 状态更新机制图解

```
用户点击发送按钮
       |
       v
调用 addMessage(userMsg)  -->  set() 触发
       |
       +--> setStreaming(true)
       |
       +--> addMessage(assistantMsg)    空内容占位
       |
       v
收到第一个字符 "排"
       |
       v
调用 appendContent(id, "排")  -->  set() 触发
       |
       v
收到第二个字符 "水"
       |
       v
调用 appendContent(id, "水")  -->  set() 触发
       |
       ...
       |
       v
收到最后字符，流结束
       |
       v
setStreaming(false)
```

每次 `set()` 调用都会触发所有使用该 store 的组件重新渲染。Zustand 有选择器（selector）机制避免不必要的渲染：

```typescript
// 只在 messages 变化时重渲染
const messages = useChatStore((s) => s.messages);

// 只在 streaming 变化时重渲染
const streaming = useChatStore((s) => s.streaming);
```

## 手把手实践

### 实践1: 创建自己的 Store

创建一个新的 `counterStore.ts`：

```typescript
import { create } from 'zustand';

interface CounterState {
  count: number;
  increment: () => void;
  decrement: () => void;
  reset: () => void;
}

export const useCounterStore = create<CounterState>((set) => ({
  count: 0,
  increment: () => set((s) => ({ count: s.count + 1 })),
  decrement: () => set((s) => ({ count: s.count - 1 })),
  reset: () => set({ count: 0 }),
}));
```

在任意组件中使用：

```typescript
import { useCounterStore } from '@/stores/counterStore';

function Counter() {
  const { count, increment, decrement, reset } = useCounterStore();
  return (
    <div>
      <p>计数: {count}</p>
      <button onClick={increment}>+1</button>
      <button onClick={decrement}>-1</button>
      <button onClick={reset}>重置</button>
    </div>
  );
}
```

### 实践2: 理解不可变更新

在浏览器控制台中测试：

```javascript
// 正确：创建新对象
const newMessages = [...oldMessages, newMsg];

// 错误：直接修改——Zustand 检测不到变化！
oldMessages.push(newMsg);
```

Zustand 使用浅比较（shallow comparison）来判断状态是否变化。直接修改原对象不会触发重渲染。

### 实践3: 观察流式内容追加

在 Chat 页面，打开开发者工具 React DevTools，找到 `ChatPage` 组件，观察 `messages` 数组的最后一条 assistant 消息的 `content` 字段——你会看到它在实时增长。

## 视频学习资源

1. **Zustand 状态管理入门** — 轻量级全局状态方案
   - 搜索关键词: `Zustand React 状态管理`
   - 推荐在 B 站搜索 "Zustand 教程" 观看

2. **React 状态管理选型** — Redux vs Zustand vs Context
   - 搜索关键词: `React 状态管理对比 Redux Zustand`
   - 推荐在 B 站搜索 "Zustand vs Redux" 观看

3. **TypeScript 泛型与接口** — interface 定义详解
   - 搜索关键词: `TypeScript interface 泛型`
   - 推荐在 B 站搜索 "TypeScript 泛型" 观看

## 常见问题与排错

### Q1: 修改了状态但组件没有重渲染

**常见原因**:
1. 直接修改了状态对象（`state.messages.push()` 而不是 `set()`）
2. 选择器写成了全量引用（变化的是其他字段）
3. 组件没有正确订阅到对应的 Store

### Q2: `appendContent` 追加到了错误的消息

**原因**: 传入的 `id` 与目标消息的 `id` 不匹配。检查消息创建时生成的 `id` 和追加时使用的 `id` 是否一致。

### Q3: Store 中的数据在刷新页面后丢失

**原因**: Zustand 默认只在内存中保持状态，刷新页面会丢失。
**解决方案**: 使用 Zustand 的 `persist` 中间件将状态保存在 localStorage：

```typescript
import { persist } from 'zustand/middleware';

export const useChatStore = create(
  persist(
    (set) => ({ ... }),
    { name: 'chat-storage' }
  )
);
```

### Q4: 类型错误 "Property does not exist on type..."

**原因**: TypeScript 不知道 Store 的类型。
**检查**: `create<ChatState>` 的泛型是否与返回值类型匹配。

## 练习任务

1. **基础练习**: 为 `uiStore` 添加一个新状态 `sidebarWidth`，默认值 240，方法 `setSidebarWidth`。在 Sidebar 组件中使用它。

2. **进阶练习**: 在 `chatStore` 中实现 `deleteMessage(id)` 方法，通过 `filter` 删除指定 ID 的消息。

3. **挑战练习**: 研究 Zustand 的 `subscribe` API，实现一个功能：当消息数量超过 50 条时，自动调用 `clearMessages` 清理旧消息（提示：使用 `useChatStore.subscribe()`）。
