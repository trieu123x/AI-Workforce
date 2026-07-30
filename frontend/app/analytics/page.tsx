"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Bot,
  CheckCircle2,
  Clock3,
  Coins,
  Gauge,
  Heart,
  ShieldCheck,
  Sparkles,
  Timer,
  Workflow,
} from "lucide-react";

import AdminShell from "@/components/admin/AdminShell";
import api from "@/lib/api";

interface AnalyticsData {
  period: { key: string; from: string; to: string; department_scope: string };
  kpis: {
    tasks_completed: number;
    success_rate: number;
    average_execution_seconds: number;
    human_approval_rate: number;
    pending_approvals: number;
    failed_workflows: number;
    token_usage: number;
    estimated_cost_usd: number;
    hours_saved: number;
    active_agents: number;
    user_satisfaction: number;
  };
  task_health: {
    total: number;
    failed: number;
    overdue: number;
    at_risk: number;
    attention: Array<{
      id: string;
      title: string;
      status: string;
      priority: string;
      due_date: string | null;
      assignee: string | null;
    }>;
  };
  agent_performance: Array<{
    role: string;
    name: string;
    executions: number;
    failures: number;
    success_rate: number;
    average_execution_seconds: number;
  }>;
  workflow_failures: Array<{ workflow: string; failures: number }>;
  methodology: Record<string, string>;
}

const KPI_META = [
  ["tasks_completed", "Tasks completed", CheckCircle2, "Công việc hoàn tất"],
  ["success_rate", "Success rate", Gauge, "Tỷ lệ thành công", "%"],
  ["average_execution_seconds", "Avg. execution", Timer, "Thời gian trung bình", "s"],
  ["human_approval_rate", "Approval rate", ShieldCheck, "Quyết định được duyệt", "%"],
  ["pending_approvals", "Need approval", Clock3, "Đang chờ xử lý"],
  ["failed_workflows", "Failed workflows", Workflow, "Workflow cần điều tra"],
  ["token_usage", "Token usage", Activity, "Provider-reported tokens"],
  ["estimated_cost_usd", "Estimated cost", Coins, "Chi phí AI", " USD"],
  ["hours_saved", "Hours saved", Sparkles, "Ước tính minh bạch", "h"],
  ["active_agents", "Active agents", Bot, "AI Employees hoạt động"],
  ["user_satisfaction", "User satisfaction", Heart, "Phản hồi tích cực", "%"],
] as const;

function formatValue(value: number, key: string, suffix = "") {
  if (key === "estimated_cost_usd") return `$${value.toFixed(4)}`;
  if (key === "token_usage") return new Intl.NumberFormat("vi-VN").format(value);
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

export default function ManagementAnalyticsPage() {
  const [period, setPeriod] = useState("30d");
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const response = await api.get(`/api/v1/management/dashboard?period=${period}`);
      setData(response.data);
    } catch {
      setError("Không thể tải Management Analytics. Hãy kiểm tra quyền truy cập.");
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <AdminShell
      title="Management Analytics"
      description="Số liệu vận hành để tìm công việc chậm, agent lỗi, workflow thất bại và chi phí thực."
      action={
        <select
          value={period}
          onChange={(event) => setPeriod(event.target.value)}
          className="ta-input"
          aria-label="Khoảng thời gian"
          style={{ width: 125, padding: "9px 11px" }}
        >
          <option value="7d">7 ngày</option>
          <option value="30d">30 ngày</option>
          <option value="90d">90 ngày</option>
        </select>
      }
    >
      {error && <div className="ops-alert error">{error}</div>}
      {loading && <div className="ops-card ops-empty">Đang tổng hợp dữ liệu vận hành…</div>}
      {!loading && data && (
        <>
          <div className="ops-alert">
            Phạm vi: <strong>{data.period.department_scope}</strong> · Dữ liệu từ{" "}
            {new Date(data.period.from).toLocaleDateString("vi-VN")} đến{" "}
            {new Date(data.period.to).toLocaleDateString("vi-VN")}.
          </div>
          <div className="ops-grid ops-grid-kpi">
            {KPI_META.map(([key, label, Icon, note, suffix]) => (
              <article className="ops-card" key={key}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <span className="ops-kpi-label">{label}</span>
                  <Icon size={18} color="#3C50E0" />
                </div>
                <div className="ops-kpi-value">
                  {formatValue(data.kpis[key], key, suffix || "")}
                </div>
                <div className="ops-kpi-note">{note}</div>
              </article>
            ))}
          </div>

          <div className="ops-grid ops-grid-2 ops-section">
            <article className="ops-card">
              <div className="ops-card-header">
                <div>
                  <h2>Task cần chú ý</h2>
                  <div className="ops-kpi-note">
                    {data.task_health.overdue} quá hạn · {data.task_health.at_risk} sắp hết hạn
                  </div>
                </div>
                <span className="ops-badge warning">{data.task_health.failed} failed</span>
              </div>
              <div className="ops-table-wrap">
                <table className="ops-table">
                  <thead>
                    <tr><th>Task</th><th>Trạng thái</th><th>Ưu tiên</th><th>Hạn</th></tr>
                  </thead>
                  <tbody>
                    {data.task_health.attention.map((task) => (
                      <tr key={task.id}>
                        <td><strong>{task.title}</strong><br/><span className="ops-muted">{task.assignee || "Chưa giao"}</span></td>
                        <td><span className={`ops-badge ${task.status === "OVERDUE" ? "error" : "warning"}`}>{task.status}</span></td>
                        <td>{task.priority}</td>
                        <td>{task.due_date ? new Date(task.due_date).toLocaleString("vi-VN") : "—"}</td>
                      </tr>
                    ))}
                    {!data.task_health.attention.length && (
                      <tr><td colSpan={4} className="ops-empty">Không có task quá hạn hoặc sắp đến hạn.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="ops-card">
              <div className="ops-card-header">
                <div>
                  <h2>Agent performance</h2>
                  <div className="ops-kpi-note">Xếp theo success rate và số lượt thực thi</div>
                </div>
              </div>
              <div className="ops-table-wrap">
                <table className="ops-table">
                  <thead>
                    <tr><th>Agent</th><th>Runs</th><th>Success</th><th>Lỗi</th><th>Avg.</th></tr>
                  </thead>
                  <tbody>
                    {data.agent_performance.map((agent) => (
                      <tr key={agent.role}>
                        <td><strong>{agent.name}</strong><br/><span className="ops-muted">{agent.role}</span></td>
                        <td>{agent.executions}</td>
                        <td>{agent.success_rate}%</td>
                        <td>{agent.failures}</td>
                        <td>{agent.average_execution_seconds}s</td>
                      </tr>
                    ))}
                    {!data.agent_performance.length && (
                      <tr><td colSpan={5} className="ops-empty">Chưa có execution log trong kỳ.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </div>

          <div className="ops-grid ops-grid-2 ops-section">
            <article className="ops-card">
              <div className="ops-card-header"><h2>Workflow thường thất bại</h2></div>
              {data.workflow_failures.map((item) => (
                <div
                  key={item.workflow}
                  style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid #eef2f7" }}
                >
                  <span>{item.workflow}</span>
                  <span className="ops-badge error">{item.failures} lỗi</span>
                </div>
              ))}
              {!data.workflow_failures.length && <div className="ops-empty">Không có workflow thất bại trong kỳ.</div>}
            </article>
            <article className="ops-card">
              <div className="ops-card-header"><h2>Cách tính chỉ số</h2></div>
              {Object.entries(data.methodology).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 13 }}>
                  <strong style={{ display: "block", fontSize: ".76rem", textTransform: "uppercase", color: "#475569" }}>{key.replaceAll("_", " ")}</strong>
                  <span className="ops-muted" style={{ fontSize: ".78rem" }}>{value}</span>
                </div>
              ))}
            </article>
          </div>
        </>
      )}
    </AdminShell>
  );
}
