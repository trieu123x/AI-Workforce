"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Cable,
  CheckCircle2,
  CircleOff,
  Database,
  ExternalLink,
  PlugZap,
  ShieldCheck,
  TestTube2,
} from "lucide-react";

import AdminShell from "@/components/admin/AdminShell";
import api from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

interface CatalogItem {
  provider: string;
  name: string;
  category: string;
  auth_types: string[];
}

interface Connection {
  id: string;
  provider: string;
  provider_name: string;
  display_name: string;
  auth_type: string;
  permissions: string[];
  allowed_resources: string[];
  allowed_agent_roles: string[];
  status: string;
  connected_at: string | null;
  last_checked_at: string | null;
  last_error: string | null;
  created_by: string | null;
}

export default function IntegrationsPage() {
  const { user } = useAuthStore();
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [authType, setAuthType] = useState("");
  const [credentialReference, setCredentialReference] = useState("");
  const [permissions, setPermissions] = useState("read");
  const [resources, setResources] = useState("");
  const [agents, setAgents] = useState("");
  const [message, setMessage] = useState("");
  const canManage = ["Owner", "Admin", "CEO"].includes(user?.role || "");

  const load = useCallback(async () => {
    const [catalogResponse, connectionResponse] = await Promise.all([
      api.get("/api/v1/integrations/catalog"),
      api.get("/api/v1/integrations"),
    ]);
    setCatalog(catalogResponse.data);
    setConnections(connectionResponse.data);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const selectedCatalog = useMemo(
    () => catalog.find((item) => item.provider === selectedProvider),
    [catalog, selectedProvider]
  );

  function chooseProvider(item: CatalogItem) {
    setSelectedProvider(item.provider);
    setDisplayName(item.name);
    setAuthType(item.auth_types[0]);
    setCredentialReference(`env:${item.provider}_CREDENTIAL`);
  }

  async function connect() {
    try {
      await api.post("/api/v1/integrations", {
        provider: selectedProvider,
        display_name: displayName,
        auth_type: authType,
        credential_reference: credentialReference,
        permissions: permissions.split(",").map((item) => item.trim()).filter(Boolean),
        allowed_resources: resources.split(",").map((item) => item.trim()).filter(Boolean),
        allowed_agent_roles: agents.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
        configuration: {},
      });
      setMessage("Đã đăng ký integration. Hãy chạy kiểm tra cấu hình.");
      setSelectedProvider("");
      await load();
    } catch {
      setMessage("Không thể tạo integration. Kiểm tra resource, quyền và credential reference.");
    }
  }

  async function testConnection(id: string) {
    const response = await api.post(`/api/v1/integrations/${id}/test`);
    setMessage(response.data.message);
    await load();
  }

  async function disconnect(id: string) {
    await api.post(`/api/v1/integrations/${id}/disconnect`);
    setMessage("Đã ngắt integration và tạo audit event.");
    await load();
  }

  return (
    <AdminShell
      title="Enterprise Integrations"
      description="Kết nối công cụ công ty với scope cụ thể; AI Agent không bao giờ được mặc định truy cập toàn bộ dữ liệu."
    >
      {message && <div className="ops-alert">{message}</div>}
      <div className="ops-card">
        <div className="ops-card-header">
          <div><h2>Kết nối hiện có</h2><div className="ops-kpi-note">{connections.length} connection trong workspace</div></div>
          <ShieldCheck size={20} color="#3c50e0"/>
        </div>
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead><tr><th>Integration</th><th>Trạng thái</th><th>Quyền</th><th>Dữ liệu được phép</th><th>AI Agent</th><th>Kiểm tra cuối</th><th></th></tr></thead>
            <tbody>
              {connections.map((connection) => (
                <tr key={connection.id}>
                  <td><strong>{connection.display_name}</strong><br/><span className="ops-muted">{connection.provider_name} · {connection.auth_type}</span></td>
                  <td><span className={`ops-badge ${connection.status === "CONNECTED" ? "success" : connection.status === "ERROR" || connection.status === "DISCONNECTED" ? "error" : "warning"}`}>{connection.status}</span></td>
                  <td>{connection.permissions.join(", ")}</td>
                  <td>{connection.allowed_resources.join(", ")}</td>
                  <td>{connection.allowed_agent_roles.length ? connection.allowed_agent_roles.join(", ") : <span className="ops-muted">Chưa cấp cho agent</span>}</td>
                  <td>{connection.last_checked_at ? new Date(connection.last_checked_at).toLocaleString("vi-VN") : "Chưa kiểm tra"}</td>
                  <td>
                    {canManage && <div className="ops-toolbar" style={{ flexWrap: "nowrap" }}>
                      <button className="ops-icon-button" onClick={() => void testConnection(connection.id)} title="Kiểm tra"><TestTube2 size={15}/></button>
                      <button className="ops-icon-button" onClick={() => void disconnect(connection.id)} title="Ngắt kết nối"><CircleOff size={15}/></button>
                    </div>}
                  </td>
                </tr>
              ))}
              {!connections.length && <tr><td colSpan={7} className="ops-empty">Chưa có integration nào được cấu hình.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="ops-alert" style={{ marginTop: 14, marginBottom: 0 }}>
          “Kiểm tra kết nối” hiện xác minh credential reference và least-privilege scope. OAuth/API handshake chỉ chạy khi connector worker tương ứng được cấu hình.
        </div>
      </div>

      <div className="ops-grid ops-grid-2 ops-section">
        <section className="ops-card">
          <div className="ops-card-header"><h2>Danh mục tích hợp</h2><Cable size={19} color="#64748b"/></div>
          <div className="ops-grid ops-grid-2">
            {catalog.map((item) => (
              <button
                key={item.provider}
                onClick={() => canManage && chooseProvider(item)}
                disabled={!canManage}
                style={{
                  border: selectedProvider === item.provider ? "1px solid #3c50e0" : "1px solid #e2e8f0",
                  borderRadius: 10, padding: 13, background: selectedProvider === item.provider ? "#eef2ff" : "#fff",
                  cursor: canManage ? "pointer" : "default", textAlign: "left", display: "flex", gap: 10,
                }}
              >
                <span className="icon-box" style={{ width: 34, height: 34, background: "#eef2ff", color: "#3c50e0" }}>
                  {item.category === "Database" ? <Database size={16}/> : <PlugZap size={16}/>}
                </span>
                <span><strong style={{ display: "block", fontSize: ".79rem" }}>{item.name}</strong><small className="ops-muted">{item.category}</small></span>
              </button>
            ))}
          </div>
        </section>

        <section className="ops-card">
          <div className="ops-card-header"><h2>Kết nối tài khoản</h2>{selectedProvider ? <CheckCircle2 size={19} color="#10b981"/> : <ExternalLink size={19} color="#94a3b8"/>}</div>
          {!canManage && <div className="ops-alert error">Chỉ Owner/Admin/CEO có thể thay đổi integration.</div>}
          {!selectedProvider ? (
            <div className="ops-empty">Chọn một integration từ danh mục để cấu hình.</div>
          ) : (
            <div className="ops-form-grid">
              <div className="ops-field"><label>Tên hiển thị</label><input value={displayName} onChange={(e) => setDisplayName(e.target.value)}/></div>
              <div className="ops-field"><label>Auth type</label><select value={authType} onChange={(e) => setAuthType(e.target.value)}>{selectedCatalog?.auth_types.map((item) => <option key={item}>{item}</option>)}</select></div>
              <div className="ops-field full"><label>Credential reference (không phải secret)</label><input value={credentialReference} onChange={(e) => setCredentialReference(e.target.value)} placeholder="env:SLACK_CREDENTIAL hoặc vault://company/slack"/></div>
              <div className="ops-field"><label>Permissions, cách nhau dấu phẩy</label><input value={permissions} onChange={(e) => setPermissions(e.target.value)} placeholder="read, create_ticket"/></div>
              <div className="ops-field"><label>Allowed resources</label><input value={resources} onChange={(e) => setResources(e.target.value)} placeholder="inbox:support, project:SALES"/></div>
              <div className="ops-field full"><label>Agent roles được phép (để trống = chưa cấp)</label><input value={agents} onChange={(e) => setAgents(e.target.value)} placeholder="SALES, KNOWLEDGE"/></div>
              <div className="ops-field full"><button className="ops-button" disabled={!displayName || !resources || !permissions} onClick={() => void connect()}><PlugZap size={15}/>Lưu connection an toàn</button></div>
            </div>
          )}
        </section>
      </div>
    </AdminShell>
  );
}
