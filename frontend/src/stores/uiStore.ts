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
