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

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  streaming: false,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendContent: (id, chunk) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + chunk } : m
      ),
    })),
  setToolTrace: (id, trace) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, toolTrace: trace } : m)),
    })),
  setSessionId: (id) => set({ sessionId: id }),
  setStreaming: (v) => set({ streaming: v }),
  clearMessages: () => set({ messages: [], sessionId: null }),
}));
