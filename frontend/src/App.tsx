import { useEffect } from "react";
import { useAppStore } from "./stores/appStore";
import { checkHealth } from "./utils/api";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import "./styles/global.css";

export default function App() {
  const { createSession, activeSessionId, setConnected, sidebarOpen } = useAppStore();

  // Create initial session
  useEffect(() => {
    if (!activeSessionId) createSession();
  }, []);

  // Poll health
  useEffect(() => {
    const poll = async () => {
      const ok = await checkHealth();
      setConnected(ok);
    };
    poll();
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="app-shell">
      <Sidebar />
      <main className={`chat-main ${sidebarOpen ? "sidebar-open" : ""}`}>
        <ChatPanel />
      </main>
    </div>
  );
}
