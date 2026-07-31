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
  role: "Owner" | "Admin" | "Manager" | "Employee" | "CEO" | "Guest";
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

interface PaginatedUsersResponse {
  items: UserItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

interface UpdatedUserResponse {
  message: string;
  user: UserItem;
}

const PAGE_SIZE = 30;
const ROLE_FILTERS = ["Owner", "Admin", "Manager", "Employee", "CEO", "Guest"];

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
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [updatingUserIds, setUpdatingUserIds] = useState<Set<string>>(new Set());
  const [showAdd, setShowAdd] = useState(false);
  const [showDepartment, setShowDepartment] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [employee, setEmployee] = useState({
    full_name: "", email: "", password: "Password123!", role: "Employee", department: "SALES",
  });
  const [newDepartment, setNewDepartment] = useState({ code: "", name: "" });

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<PaginatedUsersResponse>("/api/v1/users-mgmt", {
        params: {
          page,
          page_size: PAGE_SIZE,
          q: debouncedQuery || undefined,
          department: departmentFilter || undefined,
          role: roleFilter || undefined,
        },
      });
      setUsers(data.items);
      setTotalUsers(data.pagination.total);
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, departmentFilter, page, roleFilter]);

  const fetchDepartments = useCallback(async () => {
    try {
      const { data } = await api.get<Department[]>("/api/v1/workspace/departments");
      setDepartments(data);
      setEmployee((value) =>
        data.some((item) => item.code === value.department)
          ? value
          : { ...value, department: data[0]?.code || "ALL" },
      );
    } catch (reason) {
      setError(messageFrom(reason));
    }
  }, []);

  useEffect(() => {
    if (!hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    const timer = window.setTimeout(() => void fetchDepartments(), 0);
    return () => window.clearTimeout(timer);
  }, [fetchDepartments, hasHydrated, isAuthenticated, router]);

  useEffect(() => {
    if (!hasHydrated || !isAuthenticated) return;
    const timer = window.setTimeout(() => void fetchUsers(), 0);
    return () => window.clearTimeout(timer);
  }, [fetchUsers, hasHydrated, isAuthenticated]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setDebouncedQuery(query.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  const createEmployee = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/api/v1/users-mgmt", employee);
      setEmployee((value) => ({ ...value, full_name: "", email: "", password: "Password123!" }));
      setShowAdd(false);
      setPage(1);
      await Promise.all([fetchUsers(), fetchDepartments()]);
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  const updateUser = async (userId: string, payload: Partial<Pick<UserItem, "is_active" | "role" | "department">>) => {
    const previousIndex = users.findIndex((item) => item.id === userId);
    const previousUser = users[previousIndex];
    if (!previousUser || updatingUserIds.has(userId)) return;

    const optimisticUser = { ...previousUser, ...payload };
    const leavesCurrentFilter = (
      (departmentFilter && optimisticUser.department !== departmentFilter) ||
      (roleFilter && optimisticUser.role !== roleFilter)
    );
    const departmentChanged = payload.department !== undefined && payload.department !== previousUser.department;

    setError(null);
    setUpdatingUserIds((current) => new Set(current).add(userId));
    setUsers((current) => leavesCurrentFilter
      ? current.filter((item) => item.id !== userId)
      : current.map((item) => item.id === userId ? optimisticUser : item));
    if (leavesCurrentFilter) setTotalUsers((current) => Math.max(0, current - 1));
    if (departmentChanged) {
      setDepartments((current) => current.map((department) => {
        if (department.code === previousUser.department) {
          return { ...department, member_count: Math.max(0, department.member_count - 1) };
        }
        if (department.code === payload.department) {
          return { ...department, member_count: department.member_count + 1 };
        }
        return department;
      }));
    }

    try {
      const { data } = await api.patch<UpdatedUserResponse>(
        `/api/v1/users-mgmt/${userId}/status`,
        payload,
      );
      if (!leavesCurrentFilter) {
        setUsers((current) => current.map((item) => item.id === userId ? data.user : item));
      }
    } catch (reason) {
      setUsers((current) => {
        if (current.some((item) => item.id === userId)) {
          return current.map((item) => item.id === userId ? previousUser : item);
        }
        const restored = [...current];
        restored.splice(Math.min(previousIndex, restored.length), 0, previousUser);
        return restored;
      });
      if (leavesCurrentFilter) setTotalUsers((current) => current + 1);
      if (departmentChanged) {
        setDepartments((current) => current.map((department) => {
          if (department.code === previousUser.department) {
            return { ...department, member_count: department.member_count + 1 };
          }
          if (department.code === payload.department) {
            return { ...department, member_count: Math.max(0, department.member_count - 1) };
          }
          return department;
        }));
      }
      setError(messageFrom(reason));
    } finally {
      setUpdatingUserIds((current) => {
        const next = new Set(current);
        next.delete(userId);
        return next;
      });
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
      await fetchDepartments();
    } catch (reason) {
      setError(messageFrom(reason));
    }
  };

  if (!hasHydrated || !isAuthenticated) return null;
  const canManage = ["Owner", "Admin", "CEO"].includes(currentUser?.role || "");
  const totalPages = Math.max(1, Math.ceil(totalUsers / PAGE_SIZE));

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

          <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 1fr) 220px 190px", gap: 10, marginBottom: 14 }}>
            <div style={{ position: "relative" }}>
              <Search size={15} style={{ position: "absolute", top: 12, left: 11 }} />
              <input className="ta-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo tên hoặc email..." style={{ paddingLeft: 34 }} />
            </div>
            <select
              className="ta-input"
              value={departmentFilter}
              onChange={(event) => { setDepartmentFilter(event.target.value); setPage(1); }}
            >
              <option value="">Tất cả phòng ban</option>
              {departments.map((department) => (
                <option key={department.id} value={department.code}>{department.name} ({department.code})</option>
              ))}
            </select>
            <select
              className="ta-input"
              value={roleFilter}
              onChange={(event) => { setRoleFilter(event.target.value); setPage(1); }}
            >
              <option value="">Tất cả vai trò</option>
              {ROLE_FILTERS.map((role) => <option key={role} value={role}>{role}</option>)}
            </select>
          </div>
          <div className="ta-card" style={{ overflowX: "auto" }}>
            <table className="ta-table">
              <thead><tr><th>Nhân viên</th><th>Phòng ban</th><th>Vai trò</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={5}>Đang tải...</td></tr> : users.length === 0 ? (
                  <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--text-muted)", padding: 24 }}>Không tìm thấy nhân viên phù hợp.</td></tr>
                ) : users.map((item) => (
                  <tr key={item.id}>
                    <td><strong>{item.full_name}</strong><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{item.email}</div></td>
                    <td>
                      <select className="ta-input" value={item.department} disabled={!canManage || updatingUserIds.has(item.id)} onChange={(event) => void updateUser(item.id, { department: event.target.value })}>
                        <option value="ALL">ALL</option>
                        {departments.filter((department) => department.is_active).map((department) => <option key={department.id} value={department.code}>{department.code}</option>)}
                      </select>
                    </td>
                    <td>
                      <select className="ta-input" value={item.role} disabled={!canManage || item.role === "Owner" || updatingUserIds.has(item.id)} onChange={(event) => void updateUser(item.id, { role: event.target.value as UserItem["role"] })}>
                        {!['Employee', 'Manager', 'Admin', 'Owner'].includes(item.role) && <option value={item.role}>{item.role}</option>}
                        {["Employee", "Manager", "Admin", "Owner"].map((role) => <option key={role}>{role}</option>)}
                      </select>
                    </td>
                    <td><span className={`ta-badge ${item.is_active ? "ta-badge-success" : "ta-badge-danger"}`}>{item.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
                    <td>
                      {canManage && item.id !== currentUser?.id && <button className="ta-btn ta-btn-ghost" disabled={updatingUserIds.has(item.id)} onClick={() => void updateUser(item.id, { is_active: !item.is_active })}>
                        {item.is_active ? <Lock size={14} /> : <Unlock size={14} />} {item.is_active ? "Khóa" : "Mở"}
                      </button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14, color: "var(--text-muted)", fontSize: 13 }}>
            <span>{totalUsers.toLocaleString("vi-VN")} nhân viên · 30 người/trang</span>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button className="ta-btn ta-btn-ghost" disabled={page <= 1 || loading} onClick={() => setPage((current) => Math.max(1, current - 1))}>Trước</button>
              <strong style={{ color: "var(--text-dark)" }}>Trang {page} / {totalPages}</strong>
              <button className="ta-btn ta-btn-ghost" disabled={page >= totalPages || loading} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Sau</button>
            </div>
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
