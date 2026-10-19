import { create } from 'zustand';
import type { ToolCallTrace } from '../api';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  sources?: Array<{ chunk_id: string; text: string; source: Record<string, string> }>;
  taskId?: string;
  /** 模型自主调用工具的轨迹（仅工具调用路径会产生） */
  toolTrace?: ToolCallTrace[];
}

interface ChatState {
  sessionId: string | null;
  messages: Message[];
  streaming: boolean;
  addMessage: (msg: Message) => void;
  appendContent: (id: string, chunk: string) => void;
  setToolTrace: (id: string, trace: ToolCallTrace[]) => void;
  setSessionId: (id: string) => void;
  setStreaming: (v: boolean) => void;
  clearMessages: () => void;
}

/**
 * 会话持久化（localStorage）
 *
 * 为什么需要：此前 sessionId 与消息只存在内存，刷新页面或重启 GrassSea 后
 * 前端会开新会话、后端历史也归零。用户接着说「继续」时，模型只收到两个字，
 * 没有任务上下文，只能凭空发挥（实测出现过突然讲起 LangChain 的情况）。
 * 现在把 sessionId 与最近消息落到 localStorage，至少刷新后能接上；
 * 后端另有一份 <DATA_DIR>/sessions/*.json 作为兜底。
 */
const STORAGE_KEY = 'grasssea.chat.v1';
const MAX_PERSISTED = 40;

interface Persisted {
  sessionId: string | null;
  messages: Message[];
}

function loadPersisted(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { sessionId: null, messages: [] };
    const parsed = JSON.parse(raw) as Persisted;
    return {
      sessionId: typeof parsed?.sessionId === 'string' ? parsed.sessionId : null,
      messages: Array.isArray(parsed?.messages) ? parsed.messages.slice(-MAX_PERSISTED) : [],
    };
  } catch {
    return { sessionId: null, messages: [] };
  }
}

function savePersisted(sessionId: string | null, messages: Message[]): void {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ sessionId, messages: messages.slice(-MAX_PERSISTED) })
    );
  } catch {
    // 配额满或隐私模式下静默失败，不影响对话
  }
}

const initial = loadPersisted();

export const useChatStore = create<ChatState>((set, get) => {
  /** 任何一次状态变更后落盘 */
  const persist = () => savePersisted(get().sessionId, get().messages);

  return {
    sessionId: initial.sessionId,
    messages: initial.messages,
    streaming: false,
    addMessage: (msg) => {
      set((s) => ({ messages: [...s.messages, msg] }));
      persist();
    },
    appendContent: (id, chunk) => {
      set((s) => ({
        messages: s.messages.map((m) =>
          m.id === id ? { ...m, content: m.content + chunk } : m
        ),
      }));
    },
    setToolTrace: (id, trace) => {
      set((s) => ({
        messages: s.messages.map((m) => (m.id === id ? { ...m, toolTrace: trace } : m)),
      }));
      persist();
    },
    setSessionId: (id) => {
      set({ sessionId: id });
      persist();
    },
    setStreaming: (v) => set({ streaming: v }),
    clearMessages: () => {
      set({ messages: [], sessionId: null });
      persist();
    },
  };
});
