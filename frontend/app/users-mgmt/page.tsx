"use client";

import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Lock, Plus, Search, Unlock, UserPlus, Users } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import api from "@/lib/api";
import { useAuthStore } from "@/store/useAuthStore";

interface UserItem {
  id: string;
  email: string;
  full_name: string;
  role: "Owner" | "Admin" | "Manager" | "Employee";
  department: string;
  is_active: boolean;
  created_at: string;
}

interface Department {
  id: string;
  code: string;
  name: string;
  member_count: number;
  is_active: boolean;
}

function messageFrom(error: unknown) {
  return axios.isAxiosError(error)
    ? String(error.response?.data?.detail || error.message)
    : "Không thể xử lý yêu cầu.";
}

export default function UsersManagementPage() {
  const router = useRouter();
  const { isAuthenticated, hasHydrated, user: currentUser } = useAuthStore();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [query, setQuery] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [showDepartment, setShowDepartment] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [employee, setEmployee] = useState({
    full_name: "", email: "", password: "Password123!", role: "Employee", department: "SALES",
  });
  const [newDepartment, setNewDepartment] = useState({ code: "", name: "" });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersResponse, departmentsResponse] = await Promise.all([
        api.get<UserItem[]>("/api/v1/users-mgmt"),
        api.get<Department[]>("/api/v1/workspace/departments"),
      ]);
      setUsers(usersResponse.data);
      setDepartments(departmentsResponse.data);
      setEmployee((value) =>
        departmentsResponse.data.some((item) => item.code === value.department)
          ? value
          : { ...value, department: departmentsResponse.data[0]?.code || "ALL" },
      );
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

  const createEmployee = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/api/v1/users-mgmt", employee);
      setEmployee((value) => ({ ...value, full_name: "", email: "", password: "Password123!" }));
      setShowAdd(false);
      await fetchData();
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  const updateUser = async (userId: string, payload: Partial<Pick<UserItem, "is_active" | "role" | "department">>) => {
    setError(null);
    try {
      await api.patch(`/api/v1/users-mgmt/${userId}/status`, payload);
      await fetchData();
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  const createDepartment = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/api/v1/workspace/departments", {
        code: newDepartment.code.trim().toUpperCase().replace(/\s+/g, "_"),
        name: newDepartment.name.trim(),
      });
      setNewDepartment({ code: "", name: "" });
      setShowDepartment(false);
      await fetchData();
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  if (!hasHydrated || !isAuthenticated) return null;
  const canManage = ["Owner", "Admin", "CEO"].includes(currentUser?.role || "");
  const filtered = users.filter((item) =>
    [item.full_name, item.email, item.department, item.role]
      .some((value) => value.toLowerCase().includes(query.toLowerCase())),
  );

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--body-bg)" }}>
      <Sidebar />
      <div style={{ flex: 1, minWidth: 0 }}>
        <header className="ta-topbar">
          <div className="breadcrumb"><span>Home</span><span className="breadcrumb-sep">›</span><span className="breadcrumb-current">Công ty & nhân viên</span></div>
          {canManage && <div style={{ display: "flex", gap: 8 }}>
            <button className="ta-btn ta-btn-ghost" onClick={() => setShowDepartment(true)}><Building2 size={15} /> Thêm phòng ban</button>
            <button className="ta-btn ta-btn-primary" onClick={() => setShowAdd(true)}><UserPlus size={15} /> Thêm nhân viên</button>
          </div>}
        </header>
        <main style={{ padding: "24px 32px" }}>
          <h1 style={{ display: "flex", alignItems: "center", gap: 9, fontSize: "1.5rem", fontWeight: 800 }}><Users size={24} color="var(--primary)" /> Quản lý công ty & phân quyền</h1>
          <p style={{ color: "var(--text-muted)", margin: "6px 0 18px" }}>Owner, Admin, Manager và Employee được giới hạn theo workspace/phòng ban.</p>
          {error && <div className="ta-card" style={{ color: "#B91C1C", padding: 13, marginBottom: 14 }}>{error}</div>}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 18 }}>
            {departments.map((department) => (
              <div className="ta-card" key={department.id} style={{ padding: 14 }}>
                <strong>{department.name}</strong><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{department.code} · {department.member_count} thành viên</div>
              </div>
            ))}
          </div>

          <div style={{ position: "relative", width: 380, marginBottom: 14 }}>
            <Search size={15} style={{ position: "absolute", top: 12, left: 11 }} />
            <input className="ta-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm nhân viên..." style={{ paddingLeft: 34 }} />
          </div>
          <div className="ta-card" style={{ overflowX: "auto" }}>
            <table className="ta-table">
              <thead><tr><th>Nhân viên</th><th>Phòng ban</th><th>Vai trò</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={5}>Đang tải...</td></tr> : filtered.map((item) => (
                  <tr key={item.id}>
                    <td><strong>{item.full_name}</strong><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.email}</div></td>
                    <td>
                      <select className="ta-input" value={item.department} disabled={!canManage} onChange={(event) => void updateUser(item.id, { department: event.target.value })}>
                        <option value="ALL">ALL</option>
                        {departments.filter((department) => department.is_active).map((department) => <option key={department.id} value={department.code}>{department.code}</option>)}
                      </select>
                    </td>
                    <td>
                      <select className="ta-input" value={item.role} disabled={!canManage || item.role === "Owner"} onChange={(event) => void updateUser(item.id, { role: event.target.value as UserItem["role"] })}>
                        {["Employee", "Manager", "Admin", "Owner"].map((role) => <option key={role}>{role}</option>)}
                      </select>
                    </td>
                    <td><span className={`ta-badge ${item.is_active ? "ta-badge-success" : "ta-badge-danger"}`}>{item.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
                    <td>
                      {canManage && item.id !== currentUser?.id && <button className="ta-btn ta-btn-ghost" onClick={() => void updateUser(item.id, { is_active: !item.is_active })}>
                        {item.is_active ? <Lock size={14} /> : <Unlock size={14} />} {item.is_active ? "Khóa" : "Mở"}
                      </button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </main>
      </div>

      {showAdd && <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 100 }}>
        <form className="ta-card" onSubmit={createEmployee} style={{ width: 430, padding: 22, display: "grid", gap: 12 }}>
          <h2 style={{ fontWeight: 750 }}>Thêm nhân viên</h2>
          <input className="ta-input" placeholder="Họ và tên" value={employee.full_name} onChange={(event) => setEmployee({ ...employee, full_name: event.target.value })} required />
          <input className="ta-input" type="email" placeholder="Email công ty" value={employee.email} onChange={(event) => setEmployee({ ...employee, email: event.target.value })} required />
          <input className="ta-input" type="password" minLength={8} value={employee.password} onChange={(event) => setEmployee({ ...employee, password: event.target.value })} required />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <select className="ta-input" value={employee.role} onChange={(event) => setEmployee({ ...employee, role: event.target.value })}>{["Employee", "Manager", "Admin"].map((role) => <option key={role}>{role}</option>)}</select>
            <select className="ta-input" value={employee.department} onChange={(event) => setEmployee({ ...employee, department: event.target.value })}>{departments.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.code}>{item.code}</option>)}</select>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}><button type="button" className="ta-btn ta-btn-ghost" onClick={() => setShowAdd(false)}>Hủy</button><button className="ta-btn ta-btn-primary"><Plus size={14} /> Tạo tài khoản</button></div>
        </form>
      </div>}

      {showDepartment && <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", zIndex: 100 }}>
        <form className="ta-card" onSubmit={createDepartment} style={{ width: 400, padding: 22, display: "grid", gap: 12 }}>
          <h2 style={{ fontWeight: 750 }}>Tạo phòng ban</h2>
          <input className="ta-input" placeholder="Mã, ví dụ MARKETING" value={newDepartment.code} onChange={(event) => setNewDepartment({ ...newDepartment, code: event.target.value })} required />
          <input className="ta-input" placeholder="Tên phòng ban" value={newDepartment.name} onChange={(event) => setNewDepartment({ ...newDepartment, name: event.target.value })} required />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}><button type="button" className="ta-btn ta-btn-ghost" onClick={() => setShowDepartment(false)}>Hủy</button><button className="ta-btn ta-btn-primary"><Plus size={14} /> Tạo</button></div>
        </form>
      </div>}
    </div>
  );
}
