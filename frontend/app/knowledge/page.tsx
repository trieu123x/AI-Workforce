"use client";

import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, Database, FileText, Search, Trash2, Upload } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import api from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

interface DocumentItem {
  document_id: string;
  document_name: string;
  collection_name: string;
  department_access: string;
  chunk_count: number;
  status: string;
  created_at?: string;
}

interface SearchResult {
  id: string;
  document_name: string;
  section_title: string;
  content: string;
  score: number;
  citation_tag: string;
}

interface Department {
  id: string;
  code: string;
  name: string;
}

function messageFrom(error: unknown) {
  return axios.isAxiosError(error)
    ? String(error.response?.data?.detail || error.message)
    : "Không thể xử lý yêu cầu.";
}

export default function KnowledgeBasePage() {
  const router = useRouter();
  const { isAuthenticated, hasHydrated, user } = useAuthStore();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [search, setSearch] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [collection, setCollection] = useState("General Knowledge");
  const [department, setDepartment] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [documentsResponse, departmentsResponse] = await Promise.all([
        api.get<DocumentItem[]>("/api/v1/documents"),
        api.get<Department[]>("/api/v1/workspace/departments"),
      ]);
      setDocuments(documentsResponse.data);
      setDepartments(departmentsResponse.data);
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    const timer = window.setTimeout(() => void fetchData(), 0);
    return () => window.clearTimeout(timer);
  }, [fetchData, hasHydrated, isAuthenticated, router]);

  const uploadFile = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("collection_name", collection);
      body.append("department_access", department);
      await api.post("/api/v1/documents/upload", body);
      setFile(null);
      const input = document.getElementById("knowledge-file") as HTMLInputElement | null;
      if (input) input.value = "";
      await fetchData();
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const searchKnowledge = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!search.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post<SearchResult[]>("/api/v1/documents/search", {
        query: search,
        top_k: 5,
      });
      setResults(data);
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const importWebsite = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!websiteUrl.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/documents/import-website", {
        url: websiteUrl,
        collection_name: collection,
        department_access: department,
      });
      setWebsiteUrl("");
      await fetchData();
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const deleteDocument = async (documentId: string) => {
    if (!window.confirm("Xóa tài liệu và toàn bộ chunk liên quan?")) return;
    try {
      await api.delete(`/api/v1/documents/${encodeURIComponent(documentId)}`);
      await fetchData();
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  if (!hasHydrated || !isAuthenticated) return null;
  const canManage = ["Owner", "Admin", "CEO", "Manager"].includes(user?.role || "");

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--body-bg)" }}>
      <Sidebar />
      <div style={{ flex: 1, minWidth: 0 }}>
        <header className="ta-topbar">
          <div className="breadcrumb"><span>Home</span><span className="breadcrumb-sep">›</span><span className="breadcrumb-current">Knowledge Base</span></div>
          <span className="ta-badge ta-badge-success">RAG index active</span>
        </header>
        <main style={{ padding: "24px 32px" }}>
          <h1 style={{ display: "flex", alignItems: "center", gap: 9, fontSize: "1.5rem", fontWeight: 800 }}><BookOpen size={24} color="var(--primary)" /> Knowledge Base & RAG</h1>
          <p style={{ color: "var(--text-muted)", margin: "6px 0 20px" }}>PDF, DOCX, TXT, CSV được phân collection, ACL phòng ban, chunk, embedding và trả lời kèm nguồn.</p>
          {error && <div className="ta-card" style={{ padding: 13, color: "#B91C1C", marginBottom: 14 }}>{error}</div>}

          <div style={{ display: "grid", gridTemplateColumns: "minmax(380px, 1fr) minmax(420px, 1fr)", gap: 20 }}>
            <section className="ta-card" style={{ padding: 20 }}>
              <h2 style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 750, marginBottom: 14 }}><Database size={18} /> Tài liệu ({documents.length})</h2>
              {loading ? <p>Đang tải...</p> : documents.map((item) => (
                <div key={`${item.document_id}-${item.collection_name}`} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "12px 0", borderTop: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", gap: 10 }}><FileText size={19} /><div><strong>{item.document_name}</strong><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.collection_name} · {item.department_access} · {item.chunk_count} chunks</div></div></div>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}><span className="ta-badge ta-badge-success">{item.status}</span>{canManage && <button className="ta-btn ta-btn-ghost" aria-label="Xóa tài liệu" onClick={() => void deleteDocument(item.document_id)}><Trash2 size={14} /></button>}</div>
                </div>
              ))}
              {!loading && documents.length === 0 && <p style={{ color: "var(--text-muted)" }}>Chưa có tài liệu bạn được phép xem.</p>}
            </section>

            <section style={{ display: "grid", gap: 16 }}>
              {canManage && <form className="ta-card" onSubmit={uploadFile} style={{ padding: 20, display: "grid", gap: 11 }}>
                <h2 style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 750 }}><Upload size={18} /> Tải tài liệu</h2>
                <input id="knowledge-file" className="ta-input" type="file" accept=".pdf,.docx,.txt,.md,.csv" onChange={(event) => setFile(event.target.files?.[0] || null)} required />
                <input className="ta-input" value={collection} onChange={(event) => setCollection(event.target.value)} placeholder="Collection" required />
                <select className="ta-input" value={department} onChange={(event) => setDepartment(event.target.value)}>
                  <option value="ALL">Toàn công ty</option>
                  {departments.map((item) => <option key={item.id} value={item.code}>{item.name} ({item.code})</option>)}
                </select>
                <button className="ta-btn ta-btn-primary" disabled={busy || !file}><Upload size={15} /> {busy ? "Đang xử lý..." : "Upload & index"}</button>
              </form>}
              {canManage && <form className="ta-card" onSubmit={importWebsite} style={{ padding: 20 }}>
                <h2 style={{ fontWeight: 750, marginBottom: 10 }}>Import website công khai</h2>
                <div style={{ display: "flex", gap: 8 }}>
                  <input className="ta-input" type="url" value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} placeholder="https://company.example/policies" required />
                  <button className="ta-btn ta-btn-primary" disabled={busy}>Import</button>
                </div>
              </form>}
              <form className="ta-card" onSubmit={searchKnowledge} style={{ padding: 20 }}>
                <h2 style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 750, marginBottom: 11 }}><Search size={18} /> Kiểm thử RAG</h2>
                <div style={{ display: "flex", gap: 8 }}><input className="ta-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nhập câu hỏi..." /><button className="ta-btn ta-btn-primary" disabled={busy}>Tìm</button></div>
                <div style={{ marginTop: 12 }}>
                  {results.map((item) => <div key={item.id} style={{ borderTop: "1px solid var(--border)", padding: "11px 0" }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{item.document_name} — {item.section_title}</strong><span className="ta-badge ta-badge-info">{item.score}</span></div><p style={{ fontSize: 13, margin: "5px 0" }}>{item.content}</p><small style={{ color: "var(--primary)" }}>{item.citation_tag}</small></div>)}
                </div>
              </form>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
