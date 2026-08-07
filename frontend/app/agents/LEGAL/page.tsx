"use client";

import axios from "axios";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Bot,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleGauge,
  Code2,
  FileDiff,
  FileKey2,
  FilePlus2,
  FileSearch,
  FileText,
  Fingerprint,
  GitCompareArrows,
  Loader2,
  LockKeyhole,
  MessageSquareText,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Upload,
  UsersRound,
  WandSparkles,
  X,
  Download,
  ExternalLink,
  Eye,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import Sidebar from "@/components/Sidebar";
import ChatMessageContent from "@/components/chat/ChatMessageContent";
import LegalDocumentGeneratorModal from "@/components/legal/LegalDocumentGeneratorModal";
import api from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";
import styles from "./legal.module.css";

type View = "overview" | "review" | "knowledge" | "compliance";
type ReviewMode = "contract" | "compare" | "privacy" | "license";
type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
type RepresentedParty = "" | "PARTY_A" | "PARTY_B" | "NEUTRAL";

interface Agent { name: string; description?: string; is_active: boolean; }
interface DocumentItem {
  document_id: string;
  document_name: string;
  document_title?: string;
  collection_name: string;
  department_access: string;
  confidentiality?: string;
  status: string;
  processing_status?: string;
  expiration_date?: string | null;
  chunk_count: number;
}
interface ApprovalItem { id: string; action_type: string; risk_level: Severity | "CRITICAL"; workflow_title: string; }
interface Citation { document_name?: string; section_title?: string; citation_tag?: string; }
interface ChatResult { reply: string; citations: Citation[]; conversation_id: string; }
interface RiskFinding {
  id: string;
  clause: string;
  clause_title: string;
  severity: Severity;
  category: string;
  finding_type: "LEGAL_ISSUE" | "COMMERCIAL_RISK" | "POLICY_VIOLATION" | "MISSING_CLAUSE" | "AMBIGUOUS_CLAUSE" | "INTERNAL_CONFLICT";
  issue: string;
  reason: string;
  recommendation: string;
  evidence: string;
  original_text: string;
  suggested_revision: string;
  perspective: string;
  impact: "ADVERSE" | "BENEFICIAL" | "BALANCED" | "SHARED";
  sources: Array<{ id: string; title: string; type: string; url?: string; note?: string }>;
}
interface ContractReview {
  review_version: string;
  document_name: string;
  risk_score: number;
  risk_level: Severity;
  total_risks_found: number;
  risks: RiskFinding[];
  findings: RiskFinding[];
  represented_party: Exclude<RepresentedParty, "">;
  represented_party_label: string;
  contract_type: string;
  contract_type_label: string;
  contract_type_confidence: number;
  metadata: {
    contract_title: string; party_a: string; party_b: string;
    party_a_label: string; party_b_label: string; party_a_role: "COMPANY"; party_b_role: "CUSTOMER";
    party_a_source: "DOCUMENT" | "SYSTEM_DEFAULT"; party_b_source: "DOCUMENT" | "SYSTEM_DEFAULT";
    party_mapping_source: "DOCUMENT" | "DOCUMENT_AND_SYSTEM_DEFAULT" | "SYSTEM_DEFAULT";
    party_mapping_warnings: string[];
    contract_value?: string | null; dates: string[]; start_date?: string | null;
    end_date?: string | null; payment_terms: string[]; term?: string | null; clause_count: number;
  };
  checklist: Array<{ category: string; label: string; status: "PRESENT" | "MISSING"; severity_if_missing: Severity }>;
  severity_counts: Record<Severity, number>;
  missing_clauses_count: number;
  internal_conflicts_count: number;
  policy_violations_count: number;
  category_summary: Array<{ category: string; severity: Severity }>;
  reference_sources: Array<{ id: string; title: string; type: string; url?: string; reader_url?: string; note?: string; citation_tag?: string; section_title?: string }>;
  review_disclaimer: string;
  approval_created: boolean;
  workflow_id?: string | null;
}
interface PrivacyResult {
  document_name: string;
  contains_sensitive_data: boolean;
  requires_legal_approval: boolean;
  risk_level: Severity;
  findings: Array<{ type: string; count: number | null; severity: Severity }>;
  frameworks: string[];
  suggested_action: string;
  approval_created?: boolean;
}
interface CompareResult {
  old_document: string;
  new_document: string;
  similarity_percent: number;
  total_changes: number;
  changes: Array<{ type: string; old: string[]; new: string[]; old_location?: number | null; new_location?: number | null }>;
}
interface LicenseResult {
  manifest: string;
  dependencies_scanned: number;
  risk_level: Severity;
  commercial_use_requires_review: boolean;
  unresolved_dependencies: number;
  findings: Array<{ package: string; license: string; severity: Severity; action: string }>;
  approval_created?: boolean;
}
interface SearchResult { id: string; document_name: string; section_title: string; content: string; citation_tag: string; score: number; }
interface DocumentReader {
  document_id?: string;
  document_name: string;
  document_title: string;
  document_type?: string;
  version?: string;
  content: string;
  character_count?: number;
  chunk_count?: number;
  source_url?: string | null;
  download_url?: string | null;
}

const REVIEW_MODES: Array<{ id: ReviewMode; label: string; icon: typeof FileSearch; accept: string }> = [
  { id: "contract", label: "Rà soát hợp đồng", icon: FileSearch, accept: ".pdf,.docx,.txt,.md,.csv" },
  { id: "compare", label: "So sánh phiên bản", icon: FileDiff, accept: ".pdf,.docx,.txt,.md" },
  { id: "privacy", label: "Kiểm tra dữ liệu", icon: Fingerprint, accept: ".xlsx,.csv,.json,.txt,.pdf,.docx" },
  { id: "license", label: "License phần mềm", icon: Code2, accept: ".json,.txt" },
];

function messageFrom(error: unknown) {
  if (!axios.isAxiosError(error)) return "Không thể xử lý yêu cầu.";
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : error.message;
}

function riskClass(level: string) {
  if (level === "HIGH" || level === "CRITICAL") return styles.high;
  if (level === "MEDIUM") return styles.medium;
  return styles.low;
}

export default function LegalAgentPage() {
  const router = useRouter();
  const { isAuthenticated, hasHydrated, user } = useAuthStore();
  const [view, setView] = useState<View>("overview");
  const [agent, setAgent] = useState<Agent | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [chatResult, setChatResult] = useState<ChatResult | null>(null);
  const [reviewMode, setReviewMode] = useState<ReviewMode>("contract");
  const [primaryFile, setPrimaryFile] = useState<File | null>(null);
  const [secondaryFile, setSecondaryFile] = useState<File | null>(null);
  const [representedParty, setRepresentedParty] = useState<RepresentedParty>("");
  const [reviewResult, setReviewResult] = useState<ContractReview | PrivacyResult | CompareResult | LicenseResult | null>(null);
  const [knowledgeQuery, setKnowledgeQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showGenerator, setShowGenerator] = useState(false);
  const questionRef = useRef<HTMLInputElement | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [agentResponse, documentsResponse, approvalsResponse] = await Promise.all([
        api.get<Agent>("/api/v1/agents/LEGAL"),
        api.get<DocumentItem[]>("/api/v1/documents"),
        api.get<ApprovalItem[]>("/api/v1/approvals/pending"),
      ]);
      setAgent(agentResponse.data);
      setDocuments(documentsResponse.data);
      setApprovals(approvalsResponse.data.filter((item) => item.action_type.includes("LEGAL")));
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
    const timer = window.setTimeout(() => void loadData(), 0);
    return () => window.clearTimeout(timer);
  }, [hasHydrated, isAuthenticated, loadData, router]);

  const legalDocuments = useMemo(
    () => documents.filter((item) => ["LEGAL", "ALL"].includes(item.department_access)),
    [documents],
  );
  const readyDocuments = legalDocuments.filter((item) => item.processing_status === "ready" || item.status === "active");
  const deadlines = legalDocuments
    .filter((item) => item.expiration_date)
    .sort((a, b) => String(a.expiration_date).localeCompare(String(b.expiration_date)))
    .slice(0, 4);

  const askLegal = async (event?: FormEvent) => {
    event?.preventDefault();
    const content = question.trim();
    if (!content || busy) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post<ChatResult>("/api/v1/agent/chat", { agent_role: "LEGAL", message: content });
      setChatResult(data);
      setQuestion("");
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const openTool = (mode: ReviewMode) => {
    setReviewMode(mode);
    setReviewResult(null);
    setPrimaryFile(null);
    setSecondaryFile(null);
    setRepresentedParty("");
    setView(mode === "privacy" || mode === "license" ? "compliance" : "review");
  };

  const analyzeFiles = async () => {
    if (!primaryFile || (reviewMode === "compare" && !secondaryFile) || (reviewMode === "contract" && !representedParty)) return;
    setBusy(true);
    setError(null);
    setReviewResult(null);
    try {
      const form = new FormData();
      let endpoint = "/api/v1/legal/review-document";
      if (reviewMode === "compare") {
        form.append("old_file", primaryFile);
        form.append("new_file", secondaryFile!);
        endpoint = "/api/v1/legal/compare-documents";
      } else {
        form.append("file", primaryFile);
        if (reviewMode === "contract") form.append("represented_party", representedParty);
        if (reviewMode === "privacy") endpoint = "/api/v1/legal/privacy-check";
        if (reviewMode === "license") endpoint = "/api/v1/legal/license-check";
      }
      const { data } = await api.post(endpoint, form);
      setReviewResult(data);
      if ((data as ContractReview).approval_created) await loadData();
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const searchKnowledge = async (event: FormEvent) => {
    event.preventDefault();
    if (!knowledgeQuery.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post<SearchResult[]>("/api/v1/documents/search", { query: knowledgeQuery, top_k: 8 });
      setSearchResults(data);
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  if (!hasHydrated || !isAuthenticated) return null;

  return (
    <div className={styles.page}>
      <Sidebar agentStatuses={{ LEGAL: agent?.is_active !== false }} />
      <div className={styles.shell}>
        <header className={styles.topbar}>
          <div className={styles.breadcrumb}><span>AI Employees</span><ChevronRight size={14} /><strong>Legal Agent</strong></div>
          <div className={styles.topActions}>
            <button type="button" className={styles.iconButton} title="Trung tâm phê duyệt" onClick={() => router.push("/approvals")}><ShieldCheck size={17} /></button>
            <span className={styles.status}><span />{agent?.is_active === false ? "Tạm dừng" : "Đang hoạt động"}</span>
          </div>
        </header>

        <div className={styles.workspace}>
          <aside className={styles.rail}>
            <div className={styles.agentIdentity}>
              <div className={styles.agentMark}><ShieldCheck size={23} /></div>
              <div><strong>Legal Counsel AI</strong><span>Pháp chế doanh nghiệp</span></div>
            </div>
            <nav className={styles.nav} aria-label="Legal workspace">
              <button className={view === "overview" ? styles.active : ""} onClick={() => setView("overview")}><CircleGauge size={17} />Tổng quan</button>
              <button className={view === "review" ? styles.active : ""} onClick={() => { setReviewMode("contract"); setReviewResult(null); setView("review"); }}><FileSearch size={17} />Tài liệu & hợp đồng</button>
              <button className={view === "knowledge" ? styles.active : ""} onClick={() => setView("knowledge")}><BookOpen size={17} />Kho pháp lý</button>
              <button className={view === "compliance" ? styles.active : ""} onClick={() => { setReviewMode("privacy"); setReviewResult(null); setView("compliance"); }}><ShieldAlert size={17} />Compliance & IP</button>
            </nav>
            <div className={styles.accessScope}>
              <div><LockKeyhole size={15} /><strong>Phạm vi truy cập</strong></div>
              <span>{user?.department || "ALL"} · {user?.role || "Employee"}</span>
              <small>ACL được áp dụng trước truy xuất</small>
            </div>
            <div className={styles.railFooter}>
              <span><span className={styles.liveDot} />RAG services online</span>
              <small>Hybrid search · Reranker</small>
            </div>
          </aside>

          <main className={styles.main}>
            <section className={styles.commandBar}>
              <div className={styles.commandIntro}>
                <span className={styles.commandIcon}><MessageSquareText size={18} /></span>
                <div><strong>Hỏi Legal Agent</strong><span>Câu trả lời theo tài liệu bạn được phép truy cập</span></div>
              </div>
              <form onSubmit={askLegal}>
                <input ref={questionRef} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ví dụ: Tôi được nghỉ phép bao nhiêu ngày?" />
                <button type="submit" disabled={busy || !question.trim()} title="Gửi câu hỏi">{busy ? <Loader2 className={styles.spin} size={17} /> : <Send size={17} />}</button>
              </form>
            </section>

            {error && <div className={styles.error}><AlertTriangle size={17} /><span>{error}</span><button onClick={() => setError(null)} title="Đóng"><X size={15} /></button></div>}
            {chatResult && (
              <section className={styles.answerPanel}>
                <header><span><Bot size={16} /></span><div><strong>Legal Counsel AI</strong><small>Trả lời có kiểm soát nguồn</small></div><button onClick={() => setChatResult(null)} title="Đóng"><X size={15} /></button></header>
                <div className={styles.answerBody}><ChatMessageContent content={chatResult.reply} /></div>
                {chatResult.citations.length > 0 && <footer>{chatResult.citations.map((citation, index) => <span key={index}><FileText size={12} />{citation.citation_tag || citation.document_name}{citation.section_title ? ` · ${citation.section_title}` : ""}</span>)}</footer>}
              </section>
            )}

            {view === "overview" && (
              <>
                <div className={styles.headingRow}><div><span className={styles.eyebrow}>LEGAL OPERATIONS</span><h1>Trung tâm pháp chế</h1></div><button className={styles.primaryButton} onClick={() => setShowGenerator(true)}><FilePlus2 size={16} />Tạo văn bản</button></div>
                <section className={styles.stats}>
                  <article><span className={styles.statIcon}><FileText size={18} /></span><div><strong>{loading ? "—" : legalDocuments.length}</strong><small>Tài liệu được phép xem</small></div><span className={styles.trend}>ACL</span></article>
                  <article><span className={`${styles.statIcon} ${styles.amber}`}><ShieldAlert size={18} /></span><div><strong>{approvals.length}</strong><small>Chờ phê duyệt Legal</small></div><button onClick={() => router.push("/approvals")} title="Mở phê duyệt"><ArrowRight size={15} /></button></article>
                  <article><span className={`${styles.statIcon} ${styles.green}`}><BadgeCheck size={18} /></span><div><strong>{readyDocuments.length}</strong><small>Đã lập chỉ mục RAG</small></div><span className={styles.trend}>Ready</span></article>
                  <article><span className={`${styles.statIcon} ${styles.red}`}><CalendarClock size={18} /></span><div><strong>{deadlines.length}</strong><small>Mốc hết hạn sắp tới</small></div><button onClick={() => router.push("/calendar")} title="Mở lịch"><ArrowRight size={15} /></button></article>
                </section>

                <div className={styles.dashboardGrid}>
                  <section className={styles.sectionBlock}>
                    <div className={styles.sectionHeader}><div><h2>Công cụ pháp lý</h2><p>Chọn nghiệp vụ cần xử lý</p></div></div>
                    <div className={styles.toolGrid}>
                      <Tool icon={FileSearch} title="Contract Review" meta="Risk · Summary · Clauses" tone="blue" onClick={() => openTool("contract")} />
                      <Tool icon={FileKey2} title="NDA Checker" meta="Sharing · Duration · Scope" tone="violet" onClick={() => openTool("contract")} />
                      <Tool icon={GitCompareArrows} title="Clause Comparison" meta="V1 / V2 · Changed terms" tone="cyan" onClick={() => openTool("compare")} />
                      <Tool icon={Fingerprint} title="Privacy Checker" meta="PII · PDPL · Approval" tone="rose" onClick={() => openTool("privacy")} />
                      <Tool icon={Code2} title="OSS & License" meta="GPL · AGPL · MIT · Apache" tone="green" onClick={() => openTool("license")} />
                      <Tool icon={WandSparkles} title="Contract Generator" meta="DOCX · PDF · 7 templates" tone="amber" onClick={() => setShowGenerator(true)} />
                      <Tool icon={BookOpen} title="Policy QA" meta="Nội quy · OT · Remote · Leave" tone="blue" onClick={() => { setQuestion("Theo chính sách công ty, "); questionRef.current?.focus(); }} />
                      <Tool icon={Search} title="Legal Document Search" meta="Contract · NDA · SOW · MSA" tone="cyan" onClick={() => setView("knowledge")} />
                    </div>
                  </section>

                  <aside className={styles.deadlinePanel}>
                    <div className={styles.sectionHeader}><div><h2>Deadline pháp lý</h2><p>Hết hạn hợp đồng, NDA và license</p></div><button onClick={() => router.push("/calendar")}><CalendarClock size={15} /></button></div>
                    <div className={styles.deadlineList}>
                      {deadlines.length === 0 && <div className={styles.emptyCompact}><CheckCircle2 size={20} /><span>Chưa có deadline trong tài liệu được phép xem</span></div>}
                      {deadlines.map((item) => <div key={item.document_id}><span className={styles.dateBox}>{new Date(item.expiration_date!).getDate()}<small>{new Date(item.expiration_date!).toLocaleString("vi-VN", { month: "short" })}</small></span><div><strong>{item.document_title || item.document_name}</strong><small>{item.collection_name}</small></div><ChevronRight size={15} /></div>)}
                    </div>
                  </aside>
                </div>

                <section className={styles.pipeline}>
                  <div className={styles.sectionHeader}><div><h2>Legal RAG pipeline</h2><p>Authorization được thực thi trước mọi truy vấn dữ liệu</p></div><span className={styles.secureBadge}><ShieldCheck size={13} />Tenant isolated</span></div>
                  <div className={styles.pipelineSteps}>
                    {[ [LockKeyhole, "ACL Filter", "Role · Department · Owner"], [Search, "Hybrid Search", "pgvector + BM25"], [Sparkles, "Reranker", "BGE / Qwen"], [Bot, "Legal LLM", "Analysis · Citation"], [UsersRound, "Human Gate", "High-risk approval"] ].map(([Icon, title, sub], index) => <div key={String(title)}><span><Icon size={17} /></span><strong>{String(title)}</strong><small>{String(sub)}</small>{index < 4 && <ChevronRight className={styles.pipelineArrow} size={15} />}</div>)}
                  </div>
                </section>
              </>
            )}

            {(view === "review" || view === "compliance") && (
              <ReviewWorkspace
                mode={reviewMode}
                setMode={(nextMode) => { setReviewMode(nextMode); setReviewResult(null); setPrimaryFile(null); setSecondaryFile(null); setRepresentedParty(""); }}
                primaryFile={primaryFile}
                secondaryFile={secondaryFile}
                setPrimaryFile={setPrimaryFile}
                setSecondaryFile={setSecondaryFile}
                representedParty={representedParty}
                setRepresentedParty={setRepresentedParty}
                result={reviewResult}
                busy={busy}
                analyze={analyzeFiles}
              />
            )}

            {view === "knowledge" && (
              <KnowledgeWorkspace
                documents={legalDocuments}
                query={knowledgeQuery}
                setQuery={setKnowledgeQuery}
                search={searchKnowledge}
                results={searchResults}
                busy={busy}
                userRole={`${user?.department || "ALL"} · ${user?.role || "Employee"}`}
              />
            )}
          </main>
        </div>
      </div>

      {showGenerator && <LegalDocumentGeneratorModal onClose={() => setShowGenerator(false)} />}
    </div>
  );
}

function Tool({ icon: Icon, title, meta, tone, onClick }: { icon: typeof FileSearch; title: string; meta: string; tone: string; onClick: () => void }) {
  return <button className={styles.tool} onClick={onClick}><span className={`${styles.toolIcon} ${styles[tone]}`}><Icon size={20} /></span><span><strong>{title}</strong><small>{meta}</small></span><ChevronRight size={16} /></button>;
}

function ReviewWorkspace({ mode, setMode, primaryFile, secondaryFile, setPrimaryFile, setSecondaryFile, representedParty, setRepresentedParty, result, busy, analyze }: {
  mode: ReviewMode; setMode: (mode: ReviewMode) => void; primaryFile: File | null; secondaryFile: File | null;
  setPrimaryFile: (file: File | null) => void; setSecondaryFile: (file: File | null) => void;
  representedParty: RepresentedParty; setRepresentedParty: (party: RepresentedParty) => void;
  result: ContractReview | PrivacyResult | CompareResult | LicenseResult | null; busy: boolean; analyze: () => void;
}) {
  const config = REVIEW_MODES.find((item) => item.id === mode)!;
  return <>
    <div className={styles.headingRow}><div><span className={styles.eyebrow}>DOCUMENT INTELLIGENCE</span><h1>Tài liệu & tuân thủ</h1></div></div>
    <div className={styles.segmented}>{REVIEW_MODES.map((item) => <button key={item.id} className={mode === item.id ? styles.selected : ""} onClick={() => { setMode(item.id); setPrimaryFile(null); setSecondaryFile(null); }}><item.icon size={15} />{item.label}</button>)}</div>
    <div className={styles.reviewGrid}>
      <section className={styles.uploadPanel}>
        <div className={styles.sectionHeader}><div><h2>{config.label}</h2><p>{mode === "compare" ? "Chọn bản cũ và bản mới" : "PDF, DOCX, TXT, CSV, XLSX hoặc JSON · tối đa 10 MB"}</p></div></div>
        {mode === "contract" && <div className={styles.partySelector}>
          <strong>Bạn đang đại diện cho bên nào?</strong>
          <small>Góc nhìn này ảnh hưởng trực tiếp đến mức rủi ro của từng điều khoản.</small>
          <div>
            {([ ["PARTY_A", "Bên A · Công ty"], ["PARTY_B", "Bên B · Khách hàng"], ["NEUTRAL", "Neutral review"] ] as const).map(([value, label]) =>
              <button key={value} type="button" className={representedParty === value ? styles.partySelected : ""} onClick={() => setRepresentedParty(value)}>{label}</button>
            )}
          </div>
        </div>}
        <FilePicker label={mode === "compare" ? "Hợp đồng V1" : "Tài liệu cần kiểm tra"} file={primaryFile} setFile={setPrimaryFile} accept={config.accept} />
        {mode === "compare" && <FilePicker label="Hợp đồng V2" file={secondaryFile} setFile={setSecondaryFile} accept={config.accept} />}
        <button className={styles.analyzeButton} disabled={busy || !primaryFile || (mode === "compare" && !secondaryFile) || (mode === "contract" && !representedParty)} onClick={analyze}>{busy ? <Loader2 className={styles.spin} size={17} /> : <Sparkles size={17} />}{busy ? "Đang phân tích…" : "Phân tích tài liệu"}</button>
        <div className={styles.securityNote}><LockKeyhole size={15} /><span><strong>Xử lý trong tenant của doanh nghiệp</strong><small>Không gửi nội dung sang dịch vụ ngoài workflow được phê duyệt.</small></span></div>
      </section>
      <section className={styles.resultPanel}>
        {!result && <div className={styles.resultEmpty}><FileSearch size={35} /><h3>Chưa có kết quả phân tích</h3><p>Kết quả, evidence, mức rủi ro và hành động đề xuất sẽ xuất hiện tại đây.</p></div>}
        {result && <ResultView result={result} />}
      </section>
    </div>
  </>;
}

function FilePicker({ label, file, setFile, accept }: { label: string; file: File | null; setFile: (file: File | null) => void; accept: string }) {
  const ref = useRef<HTMLInputElement | null>(null);
  return <div className={`${styles.filePicker} ${file ? styles.hasFile : ""}`} onClick={() => ref.current?.click()}>
    <input ref={ref} type="file" accept={accept} onChange={(event) => setFile(event.target.files?.[0] || null)} />
    <span>{file ? <FileText size={21} /> : <Upload size={21} />}</span>
    <div><strong>{file?.name || label}</strong><small>{file ? `${(file.size / 1024).toFixed(0)} KB · Sẵn sàng` : "Bấm để chọn file"}</small></div>
    {file ? <Check size={17} /> : <ChevronRight size={17} />}
  </div>;
}

function ResultView({ result }: { result: ContractReview | PrivacyResult | CompareResult | LicenseResult }) {
  if ("risk_score" in result) return <ContractReviewResult review={result} />;
  if ("similarity_percent" in result) return <div className={styles.compareResult}><header><span><FileDiff size={20} /></span><div><h2>{result.total_changes} thay đổi</h2><p>Tương đồng {result.similarity_percent}% · {result.old_document} → {result.new_document}</p></div></header><div className={styles.changes}>{result.changes.map((change, index) => <article key={index}><span className={styles.changeType}>{change.type}</span>{change.old.map((line, i) => <p className={styles.oldLine} key={`old-${i}`}>− {line}</p>)}{change.new.map((line, i) => <p className={styles.newLine} key={`new-${i}`}>+ {line}</p>)}</article>)}</div></div>;
  if ("contains_sensitive_data" in result) return <div className={styles.privacyResult}><header><span className={result.requires_legal_approval ? styles.dangerMark : styles.safeMark}>{result.requires_legal_approval ? <ShieldAlert size={22} /> : <ShieldCheck size={22} />}</span><div><span className={`${styles.riskBadge} ${riskClass(result.risk_level)}`}>{result.risk_level}</span><h2>{result.requires_legal_approval ? "Cần Legal phê duyệt" : "Không phát hiện dữ liệu nhạy cảm"}</h2><p>{result.document_name}</p></div></header>{result.approval_created && <div className={styles.workflowAlert}><ShieldAlert size={17} /><span><strong>Đã tạo approval workflow</strong><small>Employee → Manager → Legal Team</small></span></div>}<div className={styles.piiGrid}>{result.findings.map((item) => <div key={item.type}><Fingerprint size={15} /><span><strong>{item.type}</strong><small>{item.count == null ? "Phát hiện theo cột" : `${item.count} giá trị`}</small></span></div>)}</div><div className={styles.actionNote}><strong>Hành động đề xuất</strong><p>{result.suggested_action}</p></div></div>;
  return <div className={styles.licenseResult}><header><span><Code2 size={21} /></span><div><span className={`${styles.riskBadge} ${riskClass(result.risk_level)}`}>{result.risk_level}</span><h2>{result.dependencies_scanned} dependency đã quét</h2><p>{result.manifest}</p></div></header>{result.commercial_use_requires_review && <div className={styles.workflowAlert}><AlertTriangle size={17} /><span><strong>{result.approval_created ? "Đã tạo approval workflow" : "Cần kiểm tra license thương mại"}</strong><small>Không phát hành trước khi Legal xác nhận.</small></span></div>}<div className={styles.licenseList}>{result.findings.map((item) => <article key={`${item.package}-${item.license}`}><span className={`${styles.licenseTag} ${riskClass(item.severity)}`}>{item.license}</span><div><strong>{item.package}</strong><small>{item.action}</small></div></article>)}</div></div>;
}

function ContractReviewResult({ review }: { review: ContractReview }) {
  const [decisions, setDecisions] = useState<Record<string, "ACCEPTED" | "REJECTED" | "EDITED">>({});
  const [editingId, setEditingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [reader, setReader] = useState<DocumentReader | null>(null);
  const [readerLoading, setReaderLoading] = useState(false);
  const [readerError, setReaderError] = useState<string | null>(null);
  const metadata = review.metadata;
  const findingTypeLabels: Record<RiskFinding["finding_type"], string> = {
    LEGAL_ISSUE: "Vấn đề pháp lý", COMMERCIAL_RISK: "Rủi ro thương mại",
    POLICY_VIOLATION: "Vi phạm policy", MISSING_CLAUSE: "Điều khoản thiếu",
    AMBIGUOUS_CLAUSE: "Điều khoản mơ hồ", INTERNAL_CONFLICT: "Mâu thuẫn nội bộ",
  };

  const setDecision = (id: string, decision: "ACCEPTED" | "REJECTED") => {
    setDecisions((current) => ({ ...current, [id]: decision }));
    setEditingId(null);
  };

  const openReference = async (source: ContractReview["reference_sources"][number]) => {
    if (source.url) {
      window.open(source.url, "_blank", "noopener,noreferrer");
      return;
    }
    setReaderError(null);
    if (!source.reader_url) {
      setReader({
        document_name: source.title,
        document_title: source.title,
        document_type: source.type,
        content: source.note || "Nguồn này là rule pack hệ thống và chưa có file gốc trong Knowledge Base.",
      });
      return;
    }
    setReaderLoading(true);
    try {
      const { data } = await api.get<DocumentReader>(source.reader_url);
      setReader(data);
    } catch (reason) {
      setReaderError(messageFrom(reason));
    } finally {
      setReaderLoading(false);
    }
  };

  const downloadOriginal = async () => {
    if (!reader?.download_url) return;
    setReaderError(null);
    try {
      const response = await api.get<Blob>(reader.download_url, { responseType: "blob" });
      const objectUrl = URL.createObjectURL(response.data);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = reader.document_name;
      link.click();
      URL.revokeObjectURL(objectUrl);
    } catch (reason) {
      setReaderError(messageFrom(reason));
    }
  };

  return <div className={styles.contractResult}>
    <header><div className={`${styles.scoreRing} ${riskClass(review.risk_level)}`}><strong>{review.risk_score}</strong><small>/100</small></div><div><span className={`${styles.riskBadge} ${riskClass(review.risk_level)}`}>{review.risk_level} RISK</span><h2>{review.document_name}</h2><p>{review.contract_type_label} · {review.represented_party_label} · {review.total_risks_found} phát hiện</p></div></header>
    <div className={styles.contractScroll}>
      {review.approval_created && <div className={styles.workflowAlert}><ShieldAlert size={17} /><span><strong>Đã tạo approval workflow</strong><small>Employee → Manager → Legal Team</small></span></div>}

      <section className={styles.reviewSection}>
        <div className={styles.reviewSectionTitle}><div><strong>Tóm tắt hợp đồng</strong><small>Loại hợp đồng được nhận diện với độ tin cậy {Math.round(review.contract_type_confidence * 100)}%</small></div></div>
        <div className={styles.metadataGrid}>
          <div><small>Tên hợp đồng</small><strong>{metadata.contract_title}</strong></div>
          <div><small>{metadata.party_a_label}</small><strong>{metadata.party_a}</strong><em>{metadata.party_a_source === "DOCUMENT" ? "Theo tài liệu" : "Hệ thống tự định nghĩa"}</em></div>
          <div><small>{metadata.party_b_label}</small><strong>{metadata.party_b}</strong><em>{metadata.party_b_source === "DOCUMENT" ? "Theo tài liệu" : "Hệ thống tự định nghĩa"}</em></div>
          <div><small>Giá trị</small><strong>{metadata.contract_value || "Chưa trích xuất"}</strong></div>
          <div><small>Thời hạn</small><strong>{metadata.start_date || "—"} → {metadata.end_date || "—"}</strong></div>
          <div><small>Cấu trúc</small><strong>{metadata.clause_count} điều khoản</strong></div>
        </div>
        {metadata.party_mapping_warnings.length > 0 && <div className={styles.partyWarning}><AlertTriangle size={14} /><div><strong>Cần xác nhận vai trò các bên</strong>{metadata.party_mapping_warnings.map((warning) => <p key={warning}>{warning}</p>)}</div></div>}
        {metadata.payment_terms.length > 0 && <div className={styles.paymentSummary}><small>Điều kiện thanh toán</small><p>{metadata.payment_terms[0]}</p></div>}
      </section>

      <section className={styles.reviewSection}>
        <div className={styles.reviewSectionTitle}><div><strong>Tổng quan rủi ro</strong><small>Điểm được tính từ mức độ và có floor theo finding nghiêm trọng nhất</small></div></div>
        <div className={styles.riskMetrics}>
          {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as Severity[]).map((level) => <div key={level}><strong className={riskClass(level)}>{review.severity_counts[level] || 0}</strong><small>{level}</small></div>)}
          <div><strong>{review.missing_clauses_count}</strong><small>Thiếu điều khoản</small></div>
          <div><strong>{review.internal_conflicts_count}</strong><small>Mâu thuẫn</small></div>
          <div><strong>{review.policy_violations_count}</strong><small>Vi phạm policy</small></div>
        </div>
        <p className={styles.scoringNote}>Cách tính: CRITICAL +35 · HIGH +22 · MEDIUM +10 · LOW +4. Nếu có một finding HIGH, điểm tổng tối thiểu là 70; chỉ finding CRITICAL mới làm báo cáo mang nhãn CRITICAL.</p>
        <div className={styles.categorySummary}>{review.category_summary.map((item) => <span key={item.category}>{item.category}<b className={riskClass(item.severity)}>{item.severity}</b></span>)}</div>
      </section>

      <section className={styles.reviewSection}>
        <div className={styles.reviewSectionTitle}><div><strong>Checklist theo loại hợp đồng</strong><small>{review.checklist.filter((item) => item.status === "PRESENT").length}/{review.checklist.length} nhóm điều khoản hiện diện</small></div></div>
        <div className={styles.checklist}>{review.checklist.map((item) => <div key={item.category} className={item.status === "MISSING" ? styles.missingItem : ""}>{item.status === "PRESENT" ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}<span>{item.label}</span><small>{item.status === "PRESENT" ? "Có" : `Thiếu · ${item.severity_if_missing}`}</small></div>)}</div>
      </section>

      <section className={`${styles.reviewSection} ${styles.findingSection}`}>
        <div className={styles.reviewSectionTitle}><div><strong>Phát hiện & đề xuất sửa</strong><small>AI không thay đổi file gốc; mỗi đề xuất cần được xác nhận</small></div></div>
        <div className={styles.findings}>{review.findings.map((item) => {
          const decision = decisions[item.id];
          const draft = drafts[item.id] ?? item.suggested_revision;
          return <article key={item.id}>
            <div className={styles.findingHeader}><span className={`${styles.severityDot} ${riskClass(item.severity)}`} /><strong>{item.clause === "MISSING" ? item.issue : `Điều ${item.clause} · ${item.issue}`}</strong><span className={`${styles.impactBadge} ${styles[item.impact.toLowerCase()]}`}>{item.impact === "ADVERSE" ? "Bất lợi" : item.impact === "BENEFICIAL" ? "Có lợi" : item.impact === "BALANCED" ? "Cân bằng" : "Chung"}</span><span className={styles.findingType}>{findingTypeLabels[item.finding_type]}</span><span className={`${styles.riskBadge} ${riskClass(item.severity)}`}>{item.severity}</span></div>
            <div className={styles.findingExplanation}><p><b>Lý do:</b> {item.reason}</p><p><b>Khuyến nghị:</b> {item.recommendation}</p></div>
            <div className={styles.redlineGrid}>
              <div><small>ORIGINAL</small><blockquote>{item.original_text}</blockquote></div>
              <div><small>AI RECOMMENDATION</small>{editingId === item.id ? <textarea value={draft} onChange={(event) => setDrafts((current) => ({ ...current, [item.id]: event.target.value }))} /> : <blockquote>{draft}</blockquote>}</div>
            </div>
            {item.sources.length > 0 && <div className={styles.findingSources}>{item.sources.map((source) => source.url ? <a key={source.id} href={source.url} target="_blank" rel="noreferrer">{source.title}</a> : <span key={source.id}>{source.title}</span>)}</div>}
            <div className={styles.findingActions}>
              <button className={decision === "ACCEPTED" ? styles.accepted : ""} onClick={() => setDecision(item.id, "ACCEPTED")}><Check size={13} />Accept</button>
              <button className={decision === "REJECTED" ? styles.rejected : ""} onClick={() => setDecision(item.id, "REJECTED")}><X size={13} />Reject</button>
              <button className={decision === "EDITED" ? styles.edited : ""} onClick={() => {
                if (editingId === item.id) { setDecisions((current) => ({ ...current, [item.id]: "EDITED" })); setEditingId(null); }
                else { setDrafts((current) => ({ ...current, [item.id]: draft })); setEditingId(item.id); }
              }}>{editingId === item.id ? <><Check size={13} />Lưu bản sửa</> : "Edit"}</button>
              {decision && <small>{decision === "ACCEPTED" ? "Đã chấp nhận đề xuất" : decision === "REJECTED" ? "Đã từ chối" : "Đã lưu bản chỉnh sửa"}</small>}
            </div>
          </article>;
        })}</div>
      </section>

      {review.reference_sources.length > 0 && <section className={styles.reviewSection}><div className={styles.reviewSectionTitle}><div><strong>Nguồn tham chiếu</strong><small>Click vào tên nguồn để mở và đọc nội dung</small></div></div><div className={styles.referenceList}>{review.reference_sources.map((source) => <div key={`${source.id}-${source.type}`}><span>{source.type}</span><button type="button" onClick={() => void openReference(source)} disabled={readerLoading}><span>{source.title}</span>{source.url ? <ExternalLink size={12} /> : <Eye size={12} />}</button><small>{source.note}</small></div>)}</div></section>}
      <p className={styles.reviewDisclaimer}>{review.review_disclaimer}</p>
    </div>
    {(reader || readerLoading || readerError) && <div className={styles.readerBackdrop} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) { setReader(null); setReaderError(null); } }}>
      <section className={styles.readerModal} role="dialog" aria-modal="true" aria-label="Trình đọc tài liệu tham chiếu">
        <header><div><span><FileText size={19} /></span><div><strong>{reader?.document_title || "Đang mở tài liệu…"}</strong><small>{reader ? `${reader.document_name}${reader.version ? ` · v${reader.version}` : ""}` : "Đang tải nội dung theo quyền truy cập"}</small></div></div><button type="button" onClick={() => { setReader(null); setReaderError(null); }} aria-label="Đóng trình đọc"><X size={17} /></button></header>
        {readerLoading ? <div className={styles.readerState}><Loader2 className={styles.spin} size={20} />Đang đọc tài liệu…</div> : readerError ? <div className={`${styles.readerState} ${styles.readerError}`}><AlertTriangle size={18} />{readerError}</div> : reader && <>
          <div className={styles.readerMeta}><span>{reader.document_type || "DOCUMENT"}</span>{reader.chunk_count != null && <span>{reader.chunk_count} chunks</span>}{reader.character_count != null && <span>{reader.character_count.toLocaleString("vi-VN")} ký tự</span>}</div>
          <pre className={styles.readerContent}>{reader.content}</pre>
          <footer>{reader.source_url && <a href={reader.source_url} target="_blank" rel="noreferrer"><ExternalLink size={13} />Mở trang gốc</a>}{reader.download_url && <button type="button" onClick={() => void downloadOriginal()}><Download size={13} />Tải file gốc</button>}<button type="button" onClick={() => { setReader(null); setReaderError(null); }}>Đóng</button></footer>
        </>}
      </section>
    </div>}
  </div>;
}

function KnowledgeWorkspace({ documents, query, setQuery, search, results, busy, userRole }: { documents: DocumentItem[]; query: string; setQuery: (value: string) => void; search: (event: FormEvent) => void; results: SearchResult[]; busy: boolean; userRole: string }) {
  return <>
    <div className={styles.headingRow}><div><span className={styles.eyebrow}>GOVERNED KNOWLEDGE</span><h1>Kho tri thức pháp lý</h1></div></div>
    <form className={styles.knowledgeSearch} onSubmit={search}><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm điều khoản, hợp đồng, NDA hoặc chính sách…" /><button disabled={busy || !query.trim()}>{busy ? <Loader2 className={styles.spin} size={16} /> : "Tìm kiếm"}</button></form>
    <div className={styles.knowledgeGrid}>
      <section className={styles.documentList}><div className={styles.sectionHeader}><div><h2>Tài liệu có quyền truy cập</h2><p>{documents.length} tài liệu · {userRole}</p></div><span className={styles.secureBadge}><LockKeyhole size={12} />ACL filtered</span></div>{documents.length === 0 ? <div className={styles.resultEmpty}><BookOpen size={30} /><h3>Chưa có tài liệu phù hợp ACL</h3></div> : documents.map((item) => <article key={item.document_id}><span className={styles.docIcon}><FileText size={17} /></span><div><strong>{item.document_title || item.document_name}</strong><small>{item.collection_name} · {item.chunk_count} chunks</small></div><span className={styles.confidentiality}>{item.confidentiality || "internal"}</span></article>)}</section>
      <section className={styles.searchResultList}><div className={styles.sectionHeader}><div><h2>Kết quả hybrid search</h2><p>Vector + BM25 · reranked</p></div></div>{results.length === 0 ? <div className={styles.resultEmpty}><Search size={30} /><h3>Nhập truy vấn để tìm tài liệu</h3></div> : results.map((item) => <article key={item.id}><div><span>{Math.round(item.score * 100)}%</span><strong>{item.document_name}</strong></div><h3>{item.section_title}</h3><p>{item.content}</p><small><FileText size={11} />{item.citation_tag}</small></article>)}</section>
    </div>
  </>;
}
