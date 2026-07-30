"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/useAuthStore";
import { Bot, Building2, Eye, EyeOff, Loader2, ArrowRight, ArrowLeft } from "lucide-react";
import Link from "next/link";

const DEPARTMENTS = ["BOARD", "HR", "LEGAL", "IT", "FINANCE", "SALES", "ALL"];

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuthStore();

  const [form, setForm] = useState({
    email: "",
    fullName: "",
    password: "",
    tenantName: "",
    department: "BOARD",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(
        form.email,
        form.fullName,
        form.password,
        form.tenantName
      );
      router.push("/dashboard");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      let msg: string;
      if (Array.isArray(detail)) {
        // Pydantic validation errors: [{type, loc, msg, input, ctx}, ...]
        msg = detail.map((d: { msg?: string; loc?: string[] }) =>
          d.loc ? `${d.loc.slice(-1)[0]}: ${d.msg}` : d.msg ?? String(d)
        ).join("; ");
      } else if (typeof detail === "string") {
        msg = detail;
      } else {
        msg = "Đăng ký thất bại. Vui lòng thử lại.";
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
    >
      <div className="fade-in-up" style={{ width: "100%", maxWidth: "480px" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "36px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "60px",
              height: "60px",
              borderRadius: "16px",
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              marginBottom: "16px",
              boxShadow: "0 8px 32px rgba(99,102,241,0.35)",
            }}
          >
            <Bot size={30} color="white" />
          </div>
          <h1 className="gradient-text" style={{ fontSize: "1.6rem", fontWeight: 800, marginBottom: "6px" }}>
            Tạo Tổ Chức Mới
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
            Đăng ký tài khoản CEO và khởi tạo AI Workforce
          </p>
        </div>

        <div className="glass-card" style={{ padding: "36px", borderRadius: "20px" }}>
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {/* Tenant Name */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="reg-tenant" style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Tên Tổ Chức / Công Ty
              </label>
              <input
                id="reg-tenant"
                name="tenantName"
                type="text"
                className="input-field"
                placeholder="Ví dụ: Công Ty TNHH ABC Technology"
                value={form.tenantName}
                onChange={handleChange}
                required
              />
            </div>

            {/* Full Name */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="reg-name" style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Họ và Tên
              </label>
              <input
                id="reg-name"
                name="fullName"
                type="text"
                className="input-field"
                placeholder="Nguyễn Văn A"
                value={form.fullName}
                onChange={handleChange}
                required
              />
            </div>

            {/* Email */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="reg-email" style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Email
              </label>
              <input
                id="reg-email"
                name="email"
                type="email"
                className="input-field"
                placeholder="ceo@company.com"
                value={form.email}
                onChange={handleChange}
                required
              />
            </div>

            {/* Department */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="reg-dept" style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Phòng Ban
              </label>
              <select
                id="reg-dept"
                name="department"
                className="input-field"
                value={form.department}
                onChange={handleChange}
                style={{ cursor: "pointer" }}
              >
                {DEPARTMENTS.map((d) => (
                  <option key={d} value={d} style={{ background: "#0d0d1a" }}>
                    {d}
                  </option>
                ))}
              </select>
            </div>

            {/* Password */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label htmlFor="reg-password" style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Mật Khẩu
              </label>
              <div style={{ position: "relative" }}>
                <input
                  id="reg-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  className="input-field"
                  placeholder="Tối thiểu 8 ký tự"
                  value={form.password}
                  onChange={handleChange}
                  required
                  style={{ paddingRight: "48px" }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: "absolute",
                    right: "14px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--text-muted)",
                    display: "flex",
                    alignItems: "center",
                  }}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div
                style={{
                  background: "var(--danger-bg)",
                  border: "1px solid rgba(239,68,68,0.3)",
                  borderRadius: "10px",
                  padding: "12px 16px",
                  fontSize: "0.875rem",
                  color: "#fca5a5",
                }}
              >
                {error}
              </div>
            )}

            <button
              id="register-submit-btn"
              type="submit"
              className="btn-gradient"
              disabled={loading}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                marginTop: "8px",
                padding: "14px",
              }}
            >
              {loading ? (
                <>
                  <Loader2 size={18} style={{ animation: "spin 1s linear infinite" }} />
                  Đang tạo tổ chức...
                </>
              ) : (
                <>
                  <Building2 size={18} />
                  Tạo tổ chức & Đăng ký
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          <div style={{ marginTop: "20px", textAlign: "center" }}>
            <Link
              href="/login"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "0.875rem",
                color: "var(--text-secondary)",
                textDecoration: "none",
              }}
            >
              <ArrowLeft size={15} />
              Đã có tài khoản? Đăng nhập
            </Link>
          </div>
        </div>
      </div>
      <style jsx global>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </main>
  );
}
