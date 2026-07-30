"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Filter, RefreshCw, Shield } from "lucide-react";

import AdminShell from "@/components/admin/AdminShell";
import api from "@/lib/api";

interface AuditEvent {
  id: string;
  actor: { id: string; name: string; email: string; department: string } | null;
  actor_type: string;
  agent_role: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  input_parameters: Record<string, unknown> | null;
  output_result: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  status: string;
  error_message: string | null;
  execution_time_ms: number | null;
  created_at: string;
}

export default function AuditLogsPage() {
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [actorType, setActorType] = useState("");
  const [status, setStatus] = useState("");
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (actorType) params.set("actor_type", actorType);
      if (status) params.set("status", status);
      if (action.trim()) params.set("action", action.trim());
      if (dateFrom) params.set("date_from", new Date(`${dateFrom}T00:00:00`).toISOString());
      if (dateTo) params.set("date_to", new Date(`${dateTo}T23:59:59`).toISOString());
      const response = await api.get(`/api/v1/audit/events?${params.toString()}`);
      setItems(response.data.items);
      setTotal(response.data.total);
    } finally {
      setLoading(false);
    }
  }, [action, actorType, dateFrom, dateTo, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <AdminShell
      title="Audit Log"
      description="Dòng thời gian bất biến: người dùng hoặc AI nào đã làm gì, trên dữ liệu nào và kết quả ra sao."
      action={<button className="ops-button secondary" onClick={() => void load()}><RefreshCw size={15}/>Làm mới</button>}
    >
      <div className="ops-card">
        <div className="ops-card-header">
          <div>
            <h2>Bộ lọc điều tra</h2>
            <div className="ops-kpi-note">{total} sự kiện phù hợp · tối đa 200 bản ghi/lần</div>
          </div>
          <Filter size={18} color="#64748b" />
        </div>
        <div className="ops-toolbar">
          <select value={actorType} onChange={(event) => setActorType(event.target.value)}>
            <option value="">Tất cả actor</option>
            <option value="USER">Người dùng</option>
            <option value="AGENT">AI Agent</option>
            <option value="SYSTEM">Hệ thống</option>
          </select>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Tất cả kết quả</option>
            <option value="SUCCESS">Thành công</option>
            <option value="FAILED">Thất bại</option>
            <option value="PENDING">Đang chờ</option>
          </select>
          <input value={action} onChange={(event) => setAction(event.target.value)} placeholder="Tìm hành động…" />
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} aria-label="Từ ngày" />
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} aria-label="Đến ngày" />
        </div>
      </div>

      <div className="ops-card ops-section" style={{ padding: 0, overflow: "hidden" }}>
        <div className="ops-table-wrap" style={{ border: 0, borderRadius: 0 }}>
          <table className="ops-table">
            <thead>
              <tr><th>Thời gian</th><th>Actor</th><th>Hành động</th><th>Resource</th><th>Thiết bị/IP</th><th>Kết quả</th><th></th></tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <Fragment key={item.id}>
                  <tr>
                    <td>{new Date(item.created_at).toLocaleString("vi-VN")}</td>
                    <td>
                      <strong>{item.actor?.name || item.agent_role || "System"}</strong><br/>
                      <span className="ops-muted">{item.actor_type} {item.actor?.department ? `· ${item.actor.department}` : ""}</span>
                    </td>
                    <td><strong>{item.action}</strong><br/><span className="ops-muted">{item.execution_time_ms ?? 0} ms</span></td>
                    <td>{item.resource_type || "—"}<br/><span className="ops-muted">{item.resource_id || ""}</span></td>
                    <td>{item.ip_address || "—"}<br/><span className="ops-muted" title={item.user_agent || ""}>{item.user_agent ? item.user_agent.slice(0, 28) + "…" : ""}</span></td>
                    <td><span className={`ops-badge ${item.status === "SUCCESS" ? "success" : item.status === "FAILED" ? "error" : "warning"}`}>{item.status}</span></td>
                    <td>
                      <button className="ops-icon-button" onClick={() => setExpanded(expanded === item.id ? null : item.id)} aria-label="Xem chi tiết">
                        {expanded === item.id ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}
                      </button>
                    </td>
                  </tr>
                  {expanded === item.id && (
                    <tr>
                      <td colSpan={7} style={{ background: "#f8fafc" }}>
                        <div className="ops-grid ops-grid-3">
                          <DiffBox title="Dữ liệu trước" value={item.before_data || item.input_parameters} />
                          <DiffBox title="Dữ liệu sau" value={item.after_data || item.output_result} />
                          <div>
                            <h3 style={{ display: "flex", gap: 6, alignItems: "center" }}><Shield size={15}/> Điều tra</h3>
                            <p className="ops-muted" style={{ fontSize: ".76rem" }}>
                              {item.error_message || "Không ghi nhận lỗi."}
                            </p>
                            <code style={{ fontSize: ".7rem" }}>{item.id}</code>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {!loading && !items.length && <tr><td colSpan={7} className="ops-empty">Không có audit event phù hợp.</td></tr>}
              {loading && <tr><td colSpan={7} className="ops-empty">Đang tải audit trail…</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </AdminShell>
  );
}

function DiffBox({ title, value }: { title: string; value: Record<string, unknown> | null }) {
  return (
    <div>
      <h3>{title}</h3>
      <pre style={{ margin: "8px 0 0", maxHeight: 220, overflow: "auto", padding: 12, borderRadius: 8, background: "#0f172a", color: "#dbeafe", fontSize: ".7rem", whiteSpace: "pre-wrap" }}>
        {value ? JSON.stringify(value, null, 2) : "Không có dữ liệu"}
      </pre>
    </div>
  );
}
