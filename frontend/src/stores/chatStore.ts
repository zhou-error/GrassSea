import { create } from 'zustand';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  sources?: Array<{ chunk_id: string; text: string; source: Record<string, string> }>;
  taskId?: string;
}

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
  setSessionId: (id) => set({ sessionId: id }),
  setStreaming: (v) => set({ streaming: v }),
  clearMessages: () => set({ messages: [], sessionId: null }),
}));
