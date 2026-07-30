"use client";

import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Bot, Copy, Download, History, MessageSquare, RefreshCw, Save, Send, Settings, ThumbsDown, ThumbsUp } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import api from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

interface Agent {
  id: string;
  name: string;
  role_code: string;
  system_prompt: string;
  model_name: string;
  is_active: boolean;
  tools_access: string[];
  allowed_actions: string[];
  disallowed_actions: string[];
  knowledge_access: string[];
  avatar_emoji?: string;
  description?: string;
}

interface Citation {
  document_name?: string;
  section_title?: string;
  citation_tag?: string;
}

interface ChatResponse {
  conversation_id: string;
  message_id: string;
  reply: string;
  citations: Citation[];
}

interface Conversation {
  id: string;
  title: string;
  agent_role: string;
  message_count: number;
  updated_at?: string;
}

interface AgentStats {
  executions: number;
  success_rate: number;
  cost_usd: number;
}

function messageFrom(error: unknown) {
  return axios.isAxiosError(error)
    ? String(error.response?.data?.detail || error.message)
    : "Không thể xử lý yêu cầu.";
}

export default function AgentPage() {
  const params = useParams<{ role: string }>();
  const role = String(params.role || "").toUpperCase();
  const router = useRouter();
  const { isAuthenticated, hasHydrated, user } = useAuthStore();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [stats, setStats] = useState<AgentStats | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [prompt, setPrompt] = useState("");
  const [tools, setTools] = useState("");
  const [allowed, setAllowed] = useState("");
  const [denied, setDenied] = useState("");
  const [collections, setCollections] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAgent = useCallback(async () => {
    setError(null);
    try {
      const [agentResponse, statsResponse, conversationsResponse] = await Promise.all([
        api.get<Agent>(`/api/v1/agents/${role}`),
        api.get<AgentStats>(`/api/v1/agents/${role}/stats`),
        api.get<Conversation[]>("/api/v1/agent/conversations"),
      ]);
      const value = agentResponse.data;
      setAgent(value);
      setStats(statsResponse.data);
      setConversations(conversationsResponse.data.filter((item) => item.agent_role === role));
      setPrompt(value.system_prompt);
      setTools(value.tools_access.join(", "));
      setAllowed(value.allowed_actions.join(", "));
      setDenied(value.disallowed_actions.join(", "));
      setCollections(value.knowledge_access.join(", "));
    } catch (reason) {
      setError(messageFrom(reason));
    }
  }, [role]);

  useEffect(() => {
    if (!hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    const timer = window.setTimeout(() => void fetchAgent(), 0);
    return () => window.clearTimeout(timer);
  }, [fetchAgent, hasHydrated, isAuthenticated, router]);

  const sendMessage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!message.trim() || !agent) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post<ChatResponse>("/api/v1/agent/chat", {
        agent_role: agent.role_code,
        message,
        conversation_id: conversationId,
      });
      setResponse(data);
      setConversationId(data.conversation_id);
      setMessage("");
      await fetchAgent();
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    if (!conversationId) return;
    setBusy(true);
    try {
      const { data } = await api.post<ChatResponse>(`/api/v1/agent/conversations/${conversationId}/regenerate`);
      setResponse(data);
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const rate = async (rating: -1 | 1) => {
    if (!response) return;
    try {
      await api.post(`/api/v1/agent/messages/${response.message_id}/feedback`, { rating });
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  const createTask = async () => {
    if (!conversationId) return;
    try {
      await api.post(`/api/v1/agent/conversations/${conversationId}/task`, {
        title: `Theo dõi hội thoại với ${agent?.name || role}`,
      });
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  const exportConversation = async () => {
    if (!conversationId) return;
    try {
      const { data } = await api.get<string>(
        `/api/v1/agent/conversations/${conversationId}/export`,
        { responseType: "text" },
      );
      const url = URL.createObjectURL(new Blob([data], { type: "text/markdown" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `conversation-${conversationId}.md`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  const saveConfiguration = async () => {
    if (!agent) return;
    setBusy(true);
    setError(null);
    try {
      const split = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);
      const { data } = await api.patch<Agent>(`/api/v1/agents/${role}`, {
        system_prompt: prompt,
        tools_access: split(tools),
        allowed_actions: split(allowed),
        disallowed_actions: split(denied),
        knowledge_access: split(collections),
      });
      setAgent(data);
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  if (!hasHydrated || !isAuthenticated) return null;
  const canConfigure = ["Owner", "Admin", "CEO"].includes(user?.role || "");

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--body-bg)" }}>
      <Sidebar agentStatuses={agent ? { [role]: agent.is_active } : {}} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <header className="ta-topbar">
          <div className="breadcrumb"><span>AI Employees</span><span className="breadcrumb-sep">›</span><span className="breadcrumb-current">{agent?.name || role}</span></div>
          <span className={`ta-badge ${agent?.is_active ? "ta-badge-success" : "ta-badge-danger"}`}>{agent?.is_active ? "Hoạt động" : "Đã tắt"}</span>
        </header>
        <main style={{ padding: "24px 32px" }}>
          {error && <div className="ta-card" style={{ padding: 13, color: "#B91C1C", marginBottom: 14 }}>{error}</div>}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
            <div style={{ fontSize: 34 }}>{agent?.avatar_emoji || "🤖"}</div>
            <div><h1 style={{ fontSize: "1.5rem", fontWeight: 800 }}>{agent?.name}</h1><p style={{ color: "var(--text-muted)" }}>{agent?.description}</p></div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(140px, 1fr))", gap: 10, marginBottom: 18 }}>
            <div className="ta-card" style={{ padding: 14 }}><small>Lượt thực thi</small><div style={{ fontSize: 22, fontWeight: 800 }}>{stats?.executions || 0}</div></div>
            <div className="ta-card" style={{ padding: 14 }}><small>Tỷ lệ thành công</small><div style={{ fontSize: 22, fontWeight: 800 }}>{stats?.success_rate || 0}%</div></div>
            <div className="ta-card" style={{ padding: 14 }}><small>Chi phí ghi nhận</small><div style={{ fontSize: 22, fontWeight: 800 }}>${(stats?.cost_usd || 0).toFixed(4)}</div></div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, .7fr) minmax(500px, 1.5fr)", gap: 18 }}>
            <section className="ta-card" style={{ padding: 18 }}>
              <h2 style={{ display: "flex", gap: 7, alignItems: "center", fontWeight: 750, marginBottom: 12 }}><History size={17} /> Hội thoại</h2>
              <button className="ta-btn ta-btn-primary" style={{ width: "100%", marginBottom: 10 }} onClick={() => { setConversationId(null); setResponse(null); }}><MessageSquare size={15} /> Hội thoại mới</button>
              {conversations.map((item) => <button key={item.id} className="ta-card" onClick={() => { setConversationId(item.id); setResponse(null); }} style={{ width: "100%", textAlign: "left", padding: 11, marginBottom: 8, borderLeft: conversationId === item.id ? "3px solid var(--primary)" : undefined }}><strong>{item.title}</strong><div style={{ fontSize: 11, color: "var(--text-muted)" }}>{item.message_count} tin nhắn</div></button>)}
            </section>

            <section className="ta-card" style={{ padding: 20 }}>
              <h2 style={{ display: "flex", gap: 7, alignItems: "center", fontWeight: 750 }}><Bot size={18} /> Chat với {agent?.name}</h2>
              {response && <div style={{ margin: "16px 0", padding: 16, background: "#F8FAFC", borderRadius: 9 }}>
                <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.55 }}>{response.reply}</div>
                {response.citations.length > 0 && <div style={{ marginTop: 10, color: "var(--primary)", fontSize: 12 }}>Nguồn: {response.citations.map((item) => item.citation_tag || item.document_name).join(" · ")}</div>}
                <div style={{ display: "flex", gap: 7, marginTop: 12 }}>
                  <button className="ta-btn ta-btn-ghost" onClick={() => void navigator.clipboard.writeText(response.reply)}><Copy size={14} /> Copy</button>
                  <button className="ta-btn ta-btn-ghost" onClick={() => void rate(1)}><ThumbsUp size={14} /></button>
                  <button className="ta-btn ta-btn-ghost" onClick={() => void rate(-1)}><ThumbsDown size={14} /></button>
                  <button className="ta-btn ta-btn-ghost" onClick={() => void regenerate()}><RefreshCw size={14} /> Regenerate</button>
                  <button className="ta-btn ta-btn-ghost" onClick={() => void createTask()}>Tạo task</button>
                  {conversationId && <button className="ta-btn ta-btn-ghost" onClick={() => void exportConversation()}><Download size={14} /> Export</button>}
                </div>
              </div>}
              <form onSubmit={sendMessage} style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <textarea className="ta-input" rows={3} value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Nhập yêu cầu..." />
                <button className="ta-btn ta-btn-primary" disabled={busy || !agent?.is_active}><Send size={16} /> Gửi</button>
              </form>
            </section>
          </div>

          {canConfigure && agent && <section className="ta-card" style={{ padding: 20, marginTop: 18 }}>
            <h2 style={{ display: "flex", gap: 7, alignItems: "center", fontWeight: 750, marginBottom: 12 }}><Settings size={18} /> Cấu hình quyền AI Employee</h2>
            <label>System prompt</label><textarea className="ta-input" rows={5} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
              <div><label>Tools được phép (phân tách dấu phẩy)</label><input className="ta-input" value={tools} onChange={(event) => setTools(event.target.value)} /></div>
              <div><label>Knowledge collections</label><input className="ta-input" value={collections} onChange={(event) => setCollections(event.target.value)} /></div>
              <div><label>Hành động được phép</label><input className="ta-input" value={allowed} onChange={(event) => setAllowed(event.target.value)} /></div>
              <div><label>Hành động cấm</label><input className="ta-input" value={denied} onChange={(event) => setDenied(event.target.value)} /></div>
            </div>
            <button className="ta-btn ta-btn-primary" style={{ marginTop: 12 }} disabled={busy} onClick={() => void saveConfiguration()}><Save size={15} /> Lưu cấu hình</button>
          </section>}
        </main>
      </div>
    </div>
  );
}
