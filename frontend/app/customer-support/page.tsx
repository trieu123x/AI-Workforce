"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, Send } from "lucide-react";

import AdminShell from "@/components/admin/AdminShell";
import { api } from "@/lib/api";

type Step = {
  key: string;
  type: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  error: string | null;
};

type SupportCase = {
  id: string;
  subject: string;
  customer_email: string;
  classification: string | null;
  confidence: number | null;
  status: string;
  last_error: string | null;
  steps: Step[];
  delivery: { status: string; mode: string; attempt_count: number } | null;
};

type Operations = {
  cases: {
    total: number;
    completed: number;
    failed_or_rejected: number;
    waiting_approval: number;
    overdue: number;
    success_rate: number | null;
    average_completion_seconds: number | null;
    retried_steps: number;
  };
  queue: {
    available: boolean;
    queued: number | null;
    processing: number | null;
    dead_letter: number | null;
    worker_online: boolean;
    worker_last_seen: string | null;
  };
};

export default function CustomerSupportPage() {
  const [cases, setCases] = useState<SupportCase[]>([]);
  const [operations, setOperations] = useState<Operations | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    customer_email: "",
    customer_name: "",
    subject: "",
    body: "",
    priority: "MEDIUM",
  });

  const load = useCallback(async () => {
    try {
      const [caseResponse, operationsResponse] = await Promise.all([
        api.get<SupportCase[]>("/api/v1/customer-support/cases"),
        api.get<Operations>("/api/v1/customer-support/operations"),
      ]);
      setCases(caseResponse.data);
      setOperations(operationsResponse.data);
      setError("");
    } catch {
      setError("Không thể tải hàng đợi Customer Support.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(load, 0);
    const poll = window.setInterval(() => void load(), 4000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(poll);
    };
  }, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.post(
        "/api/v1/customer-support/cases",
        { ...form, customer_name: form.customer_name || null },
        { headers: { "Idempotency-Key": crypto.randomUUID() } },
      );
      setForm({ customer_email: "", customer_name: "", subject: "", body: "", priority: "MEDIUM" });
      await load();
    } catch {
      setError("Không thể đưa case vào queue. Case vẫn có thể đã được lưu; hãy refresh trước khi thử lại.");
    } finally {
      setSubmitting(false);
    }
  }

  async function retry(id: string) {
    await api.post(`/api/v1/customer-support/cases/${id}/retry`);
    await load();
  }

  return (
    <AdminShell
      title="Customer Support Operations"
      description="Email → Task → phân loại → RAG → draft → phê duyệt → gửi → audit."
      action={<button className="ops-button secondary" onClick={() => void load()}><RefreshCw size={16}/>Làm mới</button>}
    >
      {error && <div className="ops-alert error"><AlertTriangle size={18}/>{error}</div>}
      {operations && (
        <div className="ops-grid ops-grid-kpi">
          <article className="ops-card">
            <span className="ops-kpi-label">Worker</span>
            <div className="ops-kpi-value">{operations.queue.worker_online ? "Online" : "Offline"}</div>
            <div className="ops-kpi-note">
              Queue {operations.queue.queued ?? "—"} · đang chạy {operations.queue.processing ?? "—"} · dead letter {operations.queue.dead_letter ?? "—"}
            </div>
          </article>
          <article className="ops-card">
            <span className="ops-kpi-label">Tỷ lệ thành công</span>
            <div className="ops-kpi-value">
              {operations.cases.success_rate === null ? "—" : `${Math.round(operations.cases.success_rate * 100)}%`}
            </div>
            <div className="ops-kpi-note">{operations.cases.completed}/{operations.cases.total} case hoàn thành</div>
          </article>
          <article className="ops-card">
            <span className="ops-kpi-label">Cần chú ý</span>
            <div className="ops-kpi-value">{operations.cases.failed_or_rejected + operations.cases.overdue}</div>
            <div className="ops-kpi-note">
              {operations.cases.waiting_approval} chờ duyệt · {operations.cases.retried_steps} step đã retry
            </div>
          </article>
          <article className="ops-card">
            <span className="ops-kpi-label">Thời gian hoàn thành TB</span>
            <div className="ops-kpi-value">
              {operations.cases.average_completion_seconds === null ? "—" : `${operations.cases.average_completion_seconds.toFixed(1)}s`}
            </div>
            <div className="ops-kpi-note">Từ lúc nhận email đến khi hoàn tất</div>
          </article>
        </div>
      )}
      <div className="ops-two-column">
        <form className="ops-panel" onSubmit={submit}>
          <div className="ops-panel-heading"><div><h2>Tạo case từ email</h2><p>Request trả về ngay sau khi ghi DB và enqueue.</p></div></div>
          <div className="ops-form-grid">
            <div className="ops-field"><label>Email khách hàng</label><input type="email" required value={form.customer_email} onChange={(e) => setForm({...form, customer_email:e.target.value})}/></div>
            <div className="ops-field"><label>Tên khách hàng</label><input value={form.customer_name} onChange={(e) => setForm({...form, customer_name:e.target.value})}/></div>
            <div className="ops-field full"><label>Tiêu đề</label><input required value={form.subject} onChange={(e) => setForm({...form, subject:e.target.value})}/></div>
            <div className="ops-field full"><label>Nội dung email</label><textarea rows={7} required value={form.body} onChange={(e) => setForm({...form, body:e.target.value})}/></div>
            <div className="ops-field"><label>Ưu tiên</label><select value={form.priority} onChange={(e) => setForm({...form, priority:e.target.value})}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>URGENT</option></select></div>
          </div>
          <button className="ops-button primary" disabled={submitting}><Send size={16}/>{submitting ? "Đang enqueue…" : "Tạo và chạy nền"}</button>
        </form>

        <div className="ops-panel">
          <div className="ops-panel-heading"><div><h2>Tiến độ workflow</h2><p>{cases.length} case gần nhất.</p></div></div>
          {loading && <div className="ops-empty">Đang tải…</div>}
          {!loading && !cases.length && <div className="ops-empty">Chưa có support case.</div>}
          <div className="ops-stack">
            {cases.map((item) => (
              <article className="ops-list-card" key={item.id}>
                <div className="ops-list-card-head">
                  <div><strong>{item.subject}</strong><small>{item.customer_email} · {item.classification || "Chưa phân loại"}</small></div>
                  <span className={`ops-badge ${item.status === "COMPLETED" ? "success" : item.status === "FAILED" ? "danger" : "warning"}`}>{item.status}</span>
                </div>
                <div className="ops-progress-list">
                  {item.steps.map((step) => (
                    <div key={step.key} className="ops-progress-row">
                      {step.status === "COMPLETED" ? <CheckCircle2 size={16} color="#10b981"/> : <Clock3 size={16} color="#f59e0b"/>}
                      <span>{step.key.replaceAll("_", " ")}</span>
                      <small>{step.status} · {step.attempt_count}/{step.max_attempts}</small>
                    </div>
                  ))}
                </div>
                {item.last_error && <p className="ops-error-text">{item.last_error}</p>}
                {["FAILED","QUEUE_FAILED","RETRY_PENDING"].includes(item.status) && <button className="ops-button secondary" onClick={() => void retry(item.id)}>Retry</button>}
              </article>
            ))}
          </div>
        </div>
      </div>
    </AdminShell>
  );
}
