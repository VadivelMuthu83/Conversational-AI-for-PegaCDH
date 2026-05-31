import { create } from "zustand";
import { v4 as uuidv4 } from "uuid";
import type { ChatSession, ChatMessage, LLMProvider } from "../types";

interface AppState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  llmProvider: LLMProvider;
  isConnected: boolean;
  sidebarOpen: boolean;

  // Actions
  createSession: () => string;
  setActiveSession: (id: string) => void;
  deleteSession: (id: string) => void;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => void;
  appendToMessage: (sessionId: string, messageId: string, text: string) => void;
  setLLMProvider: (provider: LLMProvider) => void;
  setConnected: (v: boolean) => void;
  toggleSidebar: () => void;
  getActiveSession: () => ChatSession | null;
}

function generateTitle(firstMessage: string): string {
  const trimmed = firstMessage.trim().slice(0, 50);
  return trimmed.length < firstMessage.trim().length ? trimmed + "…" : trimmed;
}

export const useAppStore = create<AppState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  llmProvider: (import.meta.env.VITE_DEFAULT_LLM as LLMProvider) || "anthropic",
  isConnected: false,
  sidebarOpen: true,

  createSession: () => {
    const id = uuidv4();
    const session: ChatSession = {
      id,
      title: "New Chat",
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSessionId: id,
    }));
    return id;
  },

  setActiveSession: (id) => set({ activeSessionId: id }),

  deleteSession: (id) =>
    set((state) => {
      const remaining = state.sessions.filter((s) => s.id !== id);
      return {
        sessions: remaining,
        activeSessionId:
          state.activeSessionId === id
            ? (remaining[0]?.id ?? null)
            : state.activeSessionId,
      };
    }),

  addMessage: (sessionId, message) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        const messages = [...s.messages, message];
        const title =
          s.title === "New Chat" && message.role === "user"
            ? generateTitle(message.content)
            : s.title;
        return { ...s, messages, title, updatedAt: new Date() };
      }),
    })),

  updateMessage: (sessionId, messageId, updates) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) =>
            m.id === messageId ? { ...m, ...updates } : m
          ),
        };
      }),
    })),

  appendToMessage: (sessionId, messageId, text) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) =>
            m.id === messageId ? { ...m, content: m.content + text } : m
          ),
        };
      }),
    })),

  setLLMProvider: (provider) => set({ llmProvider: provider }),
  setConnected: (v) => set({ isConnected: v }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  getActiveSession: () => {
    const { sessions, activeSessionId } = get();
    return sessions.find((s) => s.id === activeSessionId) ?? null;
  },
}));
