"use client";

import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, BookOpen, CheckCircle2, Circle, Database, FileText, Loader2, Search, Trash2, Upload, X, XCircle } from "lucide-react";
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
  version: string;
  processing_status?: "uploaded" | "parsing" | "chunking" | "embedding" | "indexing" | "ready" | "failed";
  processing_checkpoint?: "uploaded" | "parsed" | "chunked" | "embedded" | "ready";
  processing_progress?: number;
  error_message?: string | null;
  source_url?: string | null;
  storage_key?: string | null;
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

interface DuplicateChunkLocation {
  chunk_index: number;
  section_title: string;
  page_start: number | null;
  page_end: number | null;
}

interface DuplicateChunk {
  content_hash: string;
  content: string;
  incoming: DuplicateChunkLocation;
  existing: DuplicateChunkLocation & {
    chunk_id: string;
    created_at: string | null;
  };
}

interface DuplicateConflict {
  code: "DUPLICATE_CHUNKS";
  message: string;
  document_id: string;
  document_name: string;
  version: string;
  duplicate_count: number;
  incoming_chunk_count: number;
  duplicates: DuplicateChunk[];
  actions: Array<"replace" | "keep_old">;
}

type PipelineStage = "selected" | "uploading" | "parsing" | "chunking" | "embedding" | "indexing" | "ready";

interface UploadPipeline {
  fileName: string;
  fileSize: number | null;
  stage: PipelineStage;
  uploadPercent: number;
  stageProgress: number;
  chunkCount?: number;
  failed?: boolean;
  needsAttention?: boolean;
  error?: string;
}

interface ProcessingStatusResponse {
  processing_status: "uploaded" | "parsing" | "chunking" | "embedding" | "indexing" | "ready" | "failed";
  processing_progress: number;
  chunk_count: number;
  error_message: string | null;
}

const PIPELINE_STAGES: Array<{
  key: Exclude<PipelineStage, "selected">;
  label: string;
  description: string;
}> = [
  { key: "uploading", label: "Tải tài liệu lên", description: "Truyền file an toàn tới máy chủ" },
  { key: "parsing", label: "Đọc nội dung", description: "Trích xuất và kiểm tra văn bản" },
  { key: "chunking", label: "Chia đoạn", description: "Tách tài liệu theo cấu trúc ngữ nghĩa" },
  { key: "embedding", label: "Tạo embedding", description: "Chuyển các đoạn thành vector tìm kiếm" },
  { key: "indexing", label: "Lập chỉ mục", description: "Lưu dữ liệu vào kho tri thức" },
  { key: "ready", label: "Hoàn tất", description: "Tài liệu đã sẵn sàng cho RAG" },
];

const PIPELINE_RANK: Record<PipelineStage, number> = {
  selected: -1,
  uploading: 0,
  parsing: 1,
  chunking: 2,
  embedding: 3,
  indexing: 4,
  ready: 5,
};

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function pipelineStageFromDocument(item: DocumentItem): PipelineStage {
  if (item.processing_status === "ready") return "ready";
  if (item.processing_status && item.processing_status !== "failed") {
    return item.processing_status === "uploaded" ? "parsing" : item.processing_status;
  }
  switch (item.processing_checkpoint) {
    case "parsed": return "chunking";
    case "chunked": return "embedding";
    case "embedded": return "indexing";
    case "ready": return "ready";
    default: return "parsing";
  }
}

function duplicateConflictFrom(error: unknown): DuplicateConflict | null {
  if (!axios.isAxiosError(error) || error.response?.status !== 409) return null;
  const payload = error.response.data as { detail?: unknown } | undefined;
  const detail = payload?.detail as Partial<DuplicateConflict> | undefined;
  if (detail?.code !== "DUPLICATE_CHUNKS" || !Array.isArray(detail.duplicates)) return null;
  return detail as DuplicateConflict;
}

function messageFrom(error: unknown) {
  if (!axios.isAxiosError(error)) return "Không thể xử lý yêu cầu.";
  const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return error.message;
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
  const [uploadBusy, setUploadBusy] = useState(false);
  const [importBusy, setImportBusy] = useState(false);
  const [searchBusy, setSearchBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<DuplicateConflict | null>(null);
  const [pipeline, setPipeline] = useState<UploadPipeline | null>(null);
  const pollingGeneration = useRef(0);
  const observedBackendProgress = useRef(false);
  const resumeRequests = useRef(new Set<string>());
  const resumeCooldowns = useRef(new Map<string, number>());
  const pipelineDocumentKey = useRef<string | null>(null);

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

  const hasActiveDocuments = documents.some((item) =>
    item.processing_status != null
    && !["ready", "failed"].includes(item.processing_status)
  );

  useEffect(() => {
    if (file) return;
    const tracked = pipelineDocumentKey.current
      ? documents.find((item) => `${item.document_id}:${item.version}` === pipelineDocumentKey.current)
      : documents.find((item) => Boolean(item.storage_key) && !item.source_url && item.processing_status != null);
    if (!tracked) return;

    pipelineDocumentKey.current = `${tracked.document_id}:${tracked.version}`;
    const stage = pipelineStageFromDocument(tracked);
    setPipeline({
      fileName: tracked.document_name,
      fileSize: null,
      stage,
      uploadPercent: 100,
      stageProgress: stage === "ready" ? 100 : Math.max(0, Math.min(100, tracked.processing_progress ?? 0)),
      chunkCount: tracked.chunk_count,
      failed: tracked.processing_status === "failed",
      error: tracked.processing_status === "failed" ? tracked.error_message || "Không thể xử lý tài liệu." : undefined,
    });
  }, [documents, file]);

  useEffect(() => {
    if (!isAuthenticated || !hasActiveDocuments) return;
    const timer = window.setInterval(async () => {
      try {
        const { data } = await api.get<DocumentItem[]>("/api/v1/documents");
        setDocuments(data);
      } catch {
        // Keep the current list visible; the next poll can recover after a restart.
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [hasActiveDocuments, isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || !["Owner", "Admin", "CEO", "Manager"].includes(user?.role || "")) return;
    const activeDocuments = documents.filter((item) =>
      item.processing_status != null
      && Boolean(item.storage_key)
      && !item.source_url
      && !["ready", "failed"].includes(item.processing_status)
    );
    for (const item of activeDocuments) {
      const key = `${item.document_id}:${item.version}`;
      if (resumeRequests.current.has(key)) continue;
      if ((resumeCooldowns.current.get(key) || 0) > Date.now()) continue;
      resumeRequests.current.add(key);
      void api.post(`/api/v1/documents/${encodeURIComponent(item.document_id)}/retry`, null, {
        params: { version: item.version },
      }).then(async () => {
        const { data } = await api.get<DocumentItem[]>("/api/v1/documents");
        setDocuments(data);
      }).catch((reason) => {
        if (!axios.isAxiosError(reason) || reason.response?.status !== 409) {
          // A later list poll retries after the backend or network recovers.
        }
      }).finally(() => {
        resumeRequests.current.delete(key);
        resumeCooldowns.current.set(key, Date.now() + 5000);
      });
    }
  }, [documents, isAuthenticated, user?.role]);

  useEffect(() => () => {
    pollingGeneration.current += 1;
  }, []);

  const selectFile = (nextFile: File | null) => {
    pollingGeneration.current += 1;
    pipelineDocumentKey.current = null;
    setDuplicateWarning(null);
    setMessage(null);
    setError(null);
    if (!nextFile) {
      setFile(null);
      setPipeline(null);
      return;
    }

    const extension = nextFile.name.split(".").pop()?.toLowerCase();
    if (!extension || !["pdf", "docx", "txt", "md", "csv"].includes(extension)) {
      setFile(null);
      setPipeline(null);
      setError("Định dạng chưa được hỗ trợ. Vui lòng chọn PDF, DOCX, TXT, MD hoặc CSV.");
      return;
    }
    if (nextFile.size > 10 * 1024 * 1024) {
      setFile(null);
      setPipeline(null);
      setError("Tài liệu vượt quá giới hạn 10 MB.");
      return;
    }

    setFile(nextFile);
    setPipeline({
      fileName: nextFile.name,
      fileSize: nextFile.size,
      stage: "selected",
      uploadPercent: 0,
      stageProgress: 0,
    });
  };

  const pollProcessingStatus = async (
    documentId: string,
    generation: number,
    version = "1.0"
  ) => {
    while (pollingGeneration.current === generation) {
      try {
        const { data } = await api.get<ProcessingStatusResponse>(
          `/api/v1/documents/processing-status/${encodeURIComponent(documentId)}`,
          { params: { version }, timeout: 5000 }
        );
        if (pollingGeneration.current !== generation) return;

        const backendStage = data.processing_status === "uploaded"
          ? "parsing"
          : data.processing_status;
        const isActiveBackendStage = backendStage !== "ready" && backendStage !== "failed";
        if (isActiveBackendStage) observedBackendProgress.current = true;

        if (backendStage === "failed" && observedBackendProgress.current) {
          setPipeline((current) => current ? {
            ...current,
            failed: true,
            error: data.error_message || "Không thể xử lý tài liệu.",
          } : current);
          await fetchData();
          return;
        }
        if (backendStage === "ready" && observedBackendProgress.current) {
          setPipeline((current) => current ? {
            ...current,
            stage: "ready",
            uploadPercent: 100,
            stageProgress: 100,
            chunkCount: data.chunk_count,
          } : current);
          setMessage("Đã lập chỉ mục tài liệu thành công.");
          await fetchData();
          return;
        }
        if (isActiveBackendStage) {
          setPipeline((current) => {
            if (!current || PIPELINE_RANK[backendStage] < PIPELINE_RANK[current.stage]) return current;
            return {
              ...current,
              stage: backendStage,
              uploadPercent: 100,
              stageProgress: Math.max(0, Math.min(100, data.processing_progress)),
            };
          });
        }
      } catch (reason) {
        if (!axios.isAxiosError(reason) || reason.response?.status !== 404) {
          // Progress polling is best-effort; the upload request remains authoritative.
        }
      }
      await new Promise((resolve) => window.setTimeout(resolve, 650));
    }
  };

  const submitFile = async (duplicateStrategy: "prompt" | "replace" | "keep_old") => {
    if (!file) return;
    setUploadBusy(true);
    setError(null);
    setMessage(null);
    observedBackendProgress.current = false;
    const generation = ++pollingGeneration.current;
    setPipeline((current) => ({
      fileName: file.name,
      fileSize: file.size,
      stage: "uploading",
      uploadPercent: 0,
      stageProgress: 0,
      ...(current?.chunkCount ? { chunkCount: current.chunkCount } : {}),
    }));
    void pollProcessingStatus(file.name, generation);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("collection_name", collection);
      body.append("department_access", department);
      body.append("duplicate_strategy", duplicateStrategy);
      const { data } = await api.post<{
        status: string;
        document_id: string;
        chunks_created?: number;
      }>("/api/v1/documents/upload", body, {
        onUploadProgress: (progressEvent) => {
          const total = progressEvent.total || file.size;
          const percent = Math.min(100, Math.round((progressEvent.loaded / total) * 100));
          setPipeline((current) => {
            if (!current || PIPELINE_RANK[current.stage] > PIPELINE_RANK.uploading) return current;
            return {
              ...current,
              stage: percent === 100 ? "parsing" : "uploading",
              uploadPercent: percent,
              stageProgress: 0,
            };
          });
        },
      });
      setDuplicateWarning(null);
      setPipeline((current) => current ? {
        ...current,
        stage: "ready",
        uploadPercent: 100,
        stageProgress: 100,
        chunkCount: data.chunks_created ?? current.chunkCount,
        failed: false,
        needsAttention: false,
        error: undefined,
      } : current);
      setFile(null);
      const input = document.getElementById("knowledge-file") as HTMLInputElement | null;
      if (input) input.value = "";
      setMessage(
        data.status === "KEPT_EXISTING"
          ? "Đã giữ tài liệu cũ. Không có chunk nào bị thay đổi."
          : "Đã lập chỉ mục tài liệu thành công."
      );
      await fetchData();
    } catch (reason) {
      const conflict = duplicateConflictFrom(reason);
      if (conflict) {
        setDuplicateWarning(conflict);
        setPipeline((current) => current ? {
          ...current,
          needsAttention: true,
          error: `Phát hiện ${conflict.duplicate_count} đoạn trùng. Cần bạn chọn cách xử lý.`,
        } : current);
      } else {
        const failureMessage = messageFrom(reason);
        setError(failureMessage);
        setPipeline((current) => current ? {
          ...current,
          failed: true,
          error: failureMessage,
        } : current);
      }
    } finally {
      if (pollingGeneration.current === generation) pollingGeneration.current += 1;
      setUploadBusy(false);
    }
  };

  const uploadFile = (event: React.FormEvent) => {
    event.preventDefault();
    void submitFile("prompt");
  };

  const searchKnowledge = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!search.trim()) return;
    setSearchBusy(true);
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
      setSearchBusy(false);
    }
  };

  const importWebsite = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!websiteUrl.trim()) return;
    setImportBusy(true);
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
      setImportBusy(false);
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

  const retryDocument = async (documentId: string, version: string) => {
    const item = documents.find((document) =>
      document.document_id === documentId && document.version === version
    );
    const stage = item ? pipelineStageFromDocument(item) : "embedding";
    const resumedStatus: DocumentItem["processing_status"] =
      stage === "selected" || stage === "uploading" ? "parsing" : stage;
    pipelineDocumentKey.current = `${documentId}:${version}`;
    setFile(null);
    setError(null);
    setPipeline({
      fileName: item?.document_name || documentId,
      fileSize: null,
      stage,
      uploadPercent: 100,
      stageProgress: 0,
      chunkCount: item?.chunk_count,
      failed: false,
      error: undefined,
    });
    setDocuments((current) => current.map((document) =>
      document.document_id === documentId && document.version === version
        ? {
            ...document,
            processing_status: resumedStatus,
            processing_progress: 0,
            error_message: null,
            status: stage.toUpperCase(),
          }
        : document
    ));
    observedBackendProgress.current = false;
    const generation = ++pollingGeneration.current;
    void pollProcessingStatus(documentId, generation, version);
    try {
      setMessage("Đang tiếp tục từ bước đã lưu gần nhất...");
      await api.post(`/api/v1/documents/${encodeURIComponent(documentId)}/retry`, null, {
        params: { version },
      });
      setMessage("Đã hoàn tất xử lý tài liệu.");
      await fetchData();
    } catch (reason) {
      const failureMessage = messageFrom(reason);
      setError(failureMessage);
      setPipeline((current) => current ? {
        ...current,
        failed: true,
        error: failureMessage,
      } : current);
    } finally {
      if (pollingGeneration.current === generation) pollingGeneration.current += 1;
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
          {message && <div className="ta-card" style={{ padding: 13, color: "#047857", background: "#ECFDF5", marginBottom: 14 }}>{message}</div>}
          {error && <div className="ta-card" style={{ padding: 13, color: "#B91C1C", marginBottom: 14 }}>{error}</div>}

          <div style={{ display: "grid", gridTemplateColumns: "minmax(380px, 1fr) minmax(420px, 1fr)", gap: 20 }}>
            <section className="ta-card" style={{ padding: 20 }}>
              <h2 style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 750, marginBottom: 14 }}><Database size={18} /> Tài liệu ({documents.length})</h2>
              {loading ? <p>Đang tải...</p> : documents.map((item) => (
                <div key={`${item.document_id}-${item.collection_name}`} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "12px 0", borderTop: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", gap: 10 }}><FileText size={19} /><div><strong>{item.document_name}</strong><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.collection_name} · {item.department_access} · {item.chunk_count} chunks{item.processing_status && !["ready", "failed"].includes(item.processing_status) ? ` · ${item.processing_progress ?? 0}%` : ""}</div>{item.error_message && item.processing_status === "failed" && <div style={{ marginTop: 3, maxWidth: 420, color: "var(--danger)", fontSize: 11 }}>{item.error_message}</div>}</div></div>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>{item.processing_status && !["ready", "failed"].includes(item.processing_status) && <Loader2 size={14} className="animate-spin" color="var(--primary)" />}<span className={`ta-badge ${item.processing_status === "failed" ? "ta-badge-danger" : item.processing_status === "ready" ? "ta-badge-success" : "ta-badge-info"}`}>{item.status}</span>{canManage && item.processing_status === "failed" && <button className="ta-btn ta-btn-ghost" onClick={() => void retryDocument(item.document_id, item.version)}>Thử lại</button>}{canManage && <button className="ta-btn ta-btn-ghost" aria-label="Xóa tài liệu" onClick={() => void deleteDocument(item.document_id)}><Trash2 size={14} /></button>}</div>
                </div>
              ))}
              {!loading && documents.length === 0 && <p style={{ color: "var(--text-muted)" }}>Chưa có tài liệu bạn được phép xem.</p>}
            </section>

            <section style={{ display: "grid", gap: 16 }}>
              {canManage && <form className="ta-card" onSubmit={uploadFile} style={{ padding: 20, display: "grid", gap: 11 }}>
                <h2 style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 750 }}><Upload size={18} /> Tải tài liệu</h2>
                <label
                  htmlFor="knowledge-file"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (!uploadBusy) selectFile(event.dataTransfer.files?.[0] || null);
                  }}
                  style={{
                    display: "grid",
                    placeItems: "center",
                    gap: 7,
                    minHeight: 116,
                    padding: 18,
                    border: `1.5px dashed ${file ? "var(--primary)" : "var(--border-mid)"}`,
                    borderRadius: 12,
                    background: file ? "var(--primary-light)" : "#F8FAFC",
                    cursor: uploadBusy ? "not-allowed" : "pointer",
                    textAlign: "center",
                  }}
                >
                  <input
                    id="knowledge-file"
                    type="file"
                    accept=".pdf,.docx,.txt,.md,.csv"
                    onChange={(event) => selectFile(event.target.files?.[0] || null)}
                    disabled={uploadBusy}
                    style={{ position: "absolute", width: 1, height: 1, opacity: 0, pointerEvents: "none" }}
                  />
                  <span style={{ width: 38, height: 38, display: "grid", placeItems: "center", borderRadius: 10, color: "var(--primary)", background: "#fff", boxShadow: "var(--shadow-sm)" }}><Upload size={19} /></span>
                  <span style={{ fontSize: 13, fontWeight: 700 }}>{file ? file.name : "Kéo thả tài liệu vào đây"}</span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{file ? formatFileSize(file.size) : "hoặc bấm để chọn · PDF, DOCX, TXT, MD, CSV · tối đa 10 MB"}</span>
                </label>
                <input className="ta-input" value={collection} onChange={(event) => setCollection(event.target.value)} placeholder="Collection" required />
                <select className="ta-input" value={department} onChange={(event) => setDepartment(event.target.value)}>
                  <option value="ALL">Toàn công ty</option>
                  {departments.map((item) => <option key={item.id} value={item.code}>{item.name} ({item.code})</option>)}
                </select>
                {pipeline && <DocumentProcessingPipeline pipeline={pipeline} />}
                <button className="ta-btn ta-btn-primary" disabled={uploadBusy || !file}><Upload size={15} /> {uploadBusy ? "Đang xử lý..." : "Upload & index"}</button>
              </form>}
              {canManage && <form className="ta-card" onSubmit={importWebsite} style={{ padding: 20 }}>
                <h2 style={{ fontWeight: 750, marginBottom: 10 }}>Import website công khai</h2>
                <div style={{ display: "flex", gap: 8 }}>
                  <input className="ta-input" type="url" value={websiteUrl} onChange={(event) => setWebsiteUrl(event.target.value)} placeholder="https://company.example/policies" disabled={importBusy} required />
                  <button className="ta-btn ta-btn-primary" disabled={importBusy}>{importBusy ? "Đang import..." : "Import"}</button>
                </div>
              </form>}
              <form className="ta-card" onSubmit={searchKnowledge} style={{ padding: 20 }}>
                <h2 style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 750, marginBottom: 11 }}><Search size={18} /> Kiểm thử RAG</h2>
                <div style={{ display: "flex", gap: 8 }}><input className="ta-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nhập câu hỏi..." disabled={searchBusy} /><button className="ta-btn ta-btn-primary" disabled={searchBusy}>{searchBusy ? "Đang tìm..." : "Tìm"}</button></div>
                <div style={{ marginTop: 12 }}>
                  {results.map((item) => <div key={item.id} style={{ borderTop: "1px solid var(--border)", padding: "11px 0" }}><div style={{ display: "flex", justifyContent: "space-between" }}><strong>{item.document_name} — {item.section_title}</strong><span className="ta-badge ta-badge-info">{item.score}</span></div><p style={{ fontSize: 13, margin: "5px 0" }}>{item.content}</p><small style={{ color: "var(--primary)" }}>{item.citation_tag}</small></div>)}
                </div>
              </form>
            </section>
          </div>
        </main>
      </div>
      {duplicateWarning && (
        <DuplicateChunkDialog
          conflict={duplicateWarning}
          busy={uploadBusy}
          onClose={() => setDuplicateWarning(null)}
          onKeepOld={() => void submitFile("keep_old")}
          onReplace={() => void submitFile("replace")}
        />
      )}
    </div>
  );
}

function DocumentProcessingPipeline({ pipeline }: { pipeline: UploadPipeline }) {
  const currentIndex = PIPELINE_RANK[pipeline.stage];
  const isReady = pipeline.stage === "ready" && !pipeline.failed && !pipeline.needsAttention;
  const heading = pipeline.failed
    ? "Xử lý tài liệu thất bại"
    : pipeline.needsAttention
      ? "Cần bạn xác nhận"
      : isReady
        ? "Tài liệu đã sẵn sàng"
        : pipeline.stage === "selected"
          ? "Sẵn sàng xử lý"
          : "Đang xử lý tài liệu";

  return (
    <section
      aria-live="polite"
      aria-label="Tiến độ xử lý tài liệu"
      style={{ border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", background: "#fff" }}
    >
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "12px 13px", background: "#F8FAFC", borderBottom: "1px solid var(--border)" }}>
        <div style={{ minWidth: 0 }}>
          <strong style={{ display: "block", fontSize: 13 }}>{heading}</strong>
          <span style={{ display: "block", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 2, color: "var(--text-muted)", fontSize: 11 }}>{pipeline.fileName}{pipeline.fileSize != null ? ` · ${formatFileSize(pipeline.fileSize)}` : ""}</span>
        </div>
        {isReady && pipeline.chunkCount != null && <span className="ta-badge ta-badge-success" style={{ flex: "0 0 auto" }}>{pipeline.chunkCount} chunks</span>}
      </header>

      <div style={{ padding: "13px 14px 14px" }}>
        {PIPELINE_STAGES.map((step, index) => {
          const complete = isReady || index < currentIndex;
          const current = !isReady && index === currentIndex;
          const failed = current && pipeline.failed;
          const needsAttention = current && pipeline.needsAttention;
          const active = current && !failed && !needsAttention;
          const iconColor = failed
            ? "var(--danger)"
            : needsAttention
              ? "#D97706"
              : complete
                ? "var(--success)"
                : active
                  ? "var(--primary)"
                  : "#CBD5E1";
          const stepPercent = complete
            ? 100
            : current
              ? step.key === "uploading" ? pipeline.uploadPercent : pipeline.stageProgress
              : 0;
          const description = step.key === "uploading" && current
            ? "Đang truyền file"
            : step.description;

          return (
            <div key={step.key} style={{ display: "grid", gridTemplateColumns: "24px 1fr", gap: 10, minHeight: index === PIPELINE_STAGES.length - 1 ? 36 : 54 }}>
              <div style={{ position: "relative", display: "flex", justifyContent: "center" }}>
                {complete ? <CheckCircle2 size={20} color={iconColor} />
                  : failed ? <XCircle size={20} color={iconColor} />
                    : needsAttention ? <AlertTriangle size={20} color={iconColor} />
                      : active ? <Loader2 size={20} color={iconColor} className="animate-spin" />
                        : <Circle size={20} color={iconColor} />}
                {index < PIPELINE_STAGES.length - 1 && <span style={{ position: "absolute", top: 23, bottom: 2, width: 2, borderRadius: 2, background: complete ? "#A7F3D0" : "#E2E8F0" }} />}
              </div>
              <div style={{ paddingBottom: index === PIPELINE_STAGES.length - 1 ? 0 : 9 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <strong style={{ display: "block", color: failed ? "var(--danger)" : needsAttention ? "#B45309" : active ? "var(--primary)" : complete ? "var(--text-dark)" : "var(--text-muted)", fontSize: 12.5 }}>{step.label}</strong>
                  <span style={{ color: failed ? "var(--danger)" : active ? "var(--primary)" : complete ? "var(--success-text)" : "var(--text-muted)", fontSize: 11, fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>{stepPercent}%</span>
                </div>
                <span style={{ display: "block", marginTop: 1, color: "var(--text-muted)", fontSize: 10.5 }}>{description}</span>
                <div style={{ height: 3, marginTop: 5, overflow: "hidden", borderRadius: 99, background: "#E2E8F0" }}>
                  <span style={{ display: "block", width: `${stepPercent}%`, height: "100%", borderRadius: 99, background: failed ? "var(--danger)" : complete ? "var(--success)" : needsAttention ? "#D97706" : "var(--primary)", transition: "width .3s ease" }} />
                </div>
              </div>
            </div>
          );
        })}
        {pipeline.error && (
          <p style={{ marginTop: 7, padding: "9px 10px", borderRadius: 8, color: pipeline.failed ? "var(--danger-text)" : "#92400E", background: pipeline.failed ? "var(--danger-bg)" : "var(--warning-bg)", fontSize: 11.5, lineHeight: 1.5 }}>
            {pipeline.error}
          </p>
        )}
      </div>
    </section>
  );
}

function pageLabel(start: number | null, end: number | null) {
  if (start == null) return "Không có thông tin trang";
  return end != null && end !== start ? `Trang ${start}–${end}` : `Trang ${start}`;
}

function DuplicateChunkDialog({
  conflict,
  busy,
  onClose,
  onKeepOld,
  onReplace,
}: {
  conflict: DuplicateConflict;
  busy: boolean;
  onClose: () => void;
  onKeepOld: () => void;
  onReplace: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="duplicate-chunks-title"
      style={{ position: "fixed", inset: 0, zIndex: 320, display: "grid", placeItems: "center", padding: 20, background: "rgba(15,23,42,.68)", backdropFilter: "blur(4px)" }}
    >
      <section className="ta-card" style={{ width: "min(920px, 100%)", maxHeight: "calc(100vh - 40px)", display: "flex", flexDirection: "column", overflow: "hidden", padding: 0 }}>
        <header style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, padding: "19px 22px", borderBottom: "1px solid var(--border)", background: "#FFFBEB" }}>
          <div style={{ display: "flex", gap: 11 }}>
            <span style={{ width: 38, height: 38, flex: "0 0 auto", display: "grid", placeItems: "center", borderRadius: 10, background: "#FEF3C7", color: "#B45309" }}><AlertTriangle size={21}/></span>
            <div>
              <h2 id="duplicate-chunks-title" style={{ fontSize: 17, fontWeight: 800, color: "#78350F" }}>Phát hiện {conflict.duplicate_count} chunk trùng</h2>
              <p style={{ marginTop: 4, color: "#92400E", fontSize: 12, lineHeight: 1.5 }}>
                {conflict.document_name} · phiên bản {conflict.version} · {conflict.incoming_chunk_count} chunks trong file mới
              </p>
            </div>
          </div>
          <button type="button" aria-label="Đóng cảnh báo" onClick={onClose} disabled={busy} style={{ width: 34, height: 34, display: "grid", placeItems: "center", border: 0, borderRadius: 9, background: "rgba(255,255,255,.75)", color: "#92400E", cursor: busy ? "not-allowed" : "pointer" }}><X size={18}/></button>
        </header>

        <div style={{ minHeight: 0, overflowY: "auto", padding: 22 }}>
          <p style={{ marginBottom: 15, color: "#475569", fontSize: 13, lineHeight: 1.6 }}>
            Hệ thống chưa thay đổi dữ liệu. Kiểm tra các mục bên dưới rồi chọn giữ nguyên tài liệu đang có hoặc thay toàn bộ batch chunk của phiên bản này bằng file mới.
          </p>
          <div style={{ display: "grid", gap: 11 }}>
            {conflict.duplicates.map((item, index) => (
              <article key={`${item.content_hash}-${item.incoming.chunk_index}`} style={{ border: "1px solid #FDE68A", borderRadius: 12, overflow: "hidden", background: "#fff" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "11px 13px", background: "#FFFBEB", borderBottom: "1px solid #FEF3C7" }}>
                  <strong style={{ color: "#78350F", fontSize: 13 }}>#{index + 1} · {item.incoming.section_title}</strong>
                  <span style={{ flex: "0 0 auto", color: "#A16207", fontSize: 11 }}>{pageLabel(item.incoming.page_start, item.incoming.page_end)}</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "#E2E8F0" }}>
                  <div style={{ padding: 11, background: "#F8FAFC", fontSize: 11 }}><span style={{ color: "#64748B" }}>Chunk cũ</span><strong style={{ display: "block", marginTop: 3 }}>#{item.existing.chunk_index} · {item.existing.section_title}</strong></div>
                  <div style={{ padding: 11, background: "#F8FAFC", fontSize: 11 }}><span style={{ color: "#64748B" }}>Chunk trong file mới</span><strong style={{ display: "block", marginTop: 3 }}>#{item.incoming.chunk_index} · {item.incoming.section_title}</strong></div>
                </div>
                <pre style={{ maxHeight: 180, overflow: "auto", margin: 0, padding: 13, background: "#fff", color: "#334155", font: "400 12px/1.6 Inter, sans-serif", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{item.content}</pre>
              </article>
            ))}
          </div>
        </div>

        <footer style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "15px 22px", borderTop: "1px solid var(--border)", background: "#F8FAFC" }}>
          <button type="button" className="ta-btn" onClick={onClose} disabled={busy}>Hủy</button>
          <div style={{ display: "flex", gap: 9 }}>
            <button type="button" className="ta-btn" onClick={onKeepOld} disabled={busy}>Giữ tài liệu cũ</button>
            <button type="button" className="ta-btn ta-btn-primary" onClick={onReplace} disabled={busy}><Upload size={15}/> {busy ? "Đang xử lý..." : "Thay thế bằng file mới"}</button>
          </div>
        </footer>
      </section>
    </div>
  );
}
