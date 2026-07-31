"use client";

import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/store/useAuthStore";
import api from "@/lib/api";
import NotificationPanel from "@/components/NotificationPanel";
import {
  Bot,
  LayoutDashboard,
  LogOut,
  Users,
  Scale,
  Laptop,
  DollarSign,
  TrendingUp,
  BookOpen,
  ChevronDown,
  Database,
  Settings,
  HelpCircle,
  Ticket,
  Calendar,
  BarChart3,
  ScrollText,
  Bell,
  Cable,
  Headphones,
} from "lucide-react";

// ─── Nav Config ──────────────────────────────────────────────────────────────
const AGENTS = [
  { name: "CEO Agent",       role: "CEO",       emoji: "👔", icon: Bot,        path: "/agents/CEO",       isNew: false },
  { name: "HR Agent",        role: "HR",        emoji: "🧑‍💼", icon: Users,      path: "/agents/HR",        isNew: false },
  { name: "Legal Agent",     role: "LEGAL",     emoji: "⚖️",  icon: Scale,      path: "/agents/LEGAL",     isNew: false },
  { name: "IT Agent",        role: "IT",        emoji: "💻",  icon: Laptop,     path: "/agents/IT",        isNew: false },
  { name: "Finance Agent",   role: "FINANCE",   emoji: "💰",  icon: DollarSign, path: "/agents/FINANCE",   isNew: true  },
  { name: "Sales Agent",     role: "SALES",     emoji: "📈",  icon: TrendingUp, path: "/agents/SALES",     isNew: true  },
  { name: "Knowledge Agent", role: "KNOWLEDGE", emoji: "📚",  icon: BookOpen,   path: "/agents/KNOWLEDGE", isNew: false },
];

interface SidebarProps {
  agentStatuses?: Record<string, boolean>;
}

// ─── Badge "NEW" ────────────────────────────────────────────────────────────
function NewBadge() {
  return (
    <span
      style={{
        fontSize: "0.6rem",
        fontWeight: 700,
        padding: "2px 6px",
        borderRadius: "999px",
        background: "#10B981",
        color: "#FFFFFF",
        letterSpacing: "0.04em",
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      NEW
    </span>
  );
}

// ─── Status dot ─────────────────────────────────────────────────────────────
function OnlineDot({ online }: { online: boolean }) {
  return (
    <span
      style={{
        width: "7px",
        height: "7px",
        borderRadius: "50%",
        background: online ? "#10B981" : "#F59E0B",
        flexShrink: 0,
        boxShadow: online ? "0 0 5px #10B981" : "none",
      }}
    />
  );
}

// ─── Main Sidebar ────────────────────────────────────────────────────────────
export default function Sidebar({ agentStatuses = {} }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const handleUnreadChange = useCallback((count: number) => setUnreadNotifications(count), []);

  // Accordion: which group is expanded
  const [expandedGroup, setExpandedGroup] = useState<string | null>(
    AGENTS.some((a) => pathname === a.path) ? "ai-agents" : null
  );

  const toggleGroup = (key: string) =>
    setExpandedGroup((prev) => (prev === key ? null : key));

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  useEffect(() => {
    if (!user) return;
    let active = true;
    const loadUnread = async () => {
      try {
        const { data } = await api.get("/api/v1/notifications", { params: { limit: 1 } });
        if (active) setUnreadNotifications(data.unread_count);
      } catch {
        // The sidebar remains usable when notifications are temporarily unavailable.
      }
    };
    void loadUnread();
    const interval = window.setInterval(() => void loadUnread(), 60_000);
    return () => { active = false; window.clearInterval(interval); };
  }, [user]);

  const isAgentsGroupActive = AGENTS.some((a) => pathname === a.path);

  return (
    <>
    <aside
      style={{
        width: "270px",
        minWidth: "270px",
        height: "100vh",
        background: "#FFFFFF",
        borderRight: "1px solid #E2E8F0",
        display: "flex",
        flexDirection: "column",
        position: "sticky",
        top: 0,
        overflow: "hidden",
        zIndex: 50,
      }}
    >
      {/* ── Employee identity and notifications ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "14px 16px",
          borderBottom: "1px solid #F1F5F9",
          flexShrink: 0,
        }}
      >
        <button onClick={() => router.push("/account")} style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0, padding: 0, border: 0, background: "transparent", cursor: "pointer", textAlign: "left" }}>
          {user?.avatar_url ? (
            <Image src={user.avatar_url} alt={user.full_name} width={38} height={38} unoptimized style={{ width: 38, height: 38, borderRadius: "50%", objectFit: "cover", border: "2px solid #E0E7FF" }}/>
          ) : (
            <span style={{ width: 38, height: 38, borderRadius: "50%", background: "linear-gradient(135deg,#3C50E0,#8B5CF6)", color: "#fff", display: "grid", placeItems: "center", fontWeight: 800, flexShrink: 0 }}>
              {user?.full_name?.charAt(0).toUpperCase() || "U"}
            </span>
          )}
          <span style={{ minWidth: 0 }}>
            <strong style={{ display: "block", fontSize: 13, color: "#1C2434", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{user?.full_name || "Nhân viên"}</strong>
            <span style={{ display: "block", fontSize: 11, color: "#64748B", marginTop: 2 }}>{user?.role || "Employee"} · {user?.department || "ALL"}</span>
          </span>
        </button>
        <button onClick={() => setNotificationsOpen((current) => !current)} aria-label="Mở thông báo" title="Thông báo" style={{ width: 36, height: 36, borderRadius: 10, border: "1px solid #E2E8F0", background: notificationsOpen ? "#EEF2FF" : "#fff", color: notificationsOpen ? "#4F46E5" : "#64748B", cursor: "pointer", display: "grid", placeItems: "center", position: "relative", flexShrink: 0 }}>
          <Bell size={17}/>
          {unreadNotifications > 0 && <span style={{ position: "absolute", right: -5, top: -6, minWidth: 17, height: 17, padding: "0 4px", borderRadius: 9, background: "#EF4444", color: "#fff", fontSize: 9, fontWeight: 800, display: "grid", placeItems: "center", border: "2px solid #fff" }}>{unreadNotifications > 99 ? "99+" : unreadNotifications}</span>}
        </button>
      </div>

      {/* ── Scrollable Nav ── */}
      <nav
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 0",
        }}
      >
        {/* ── MENU Section ── */}
        <div
          style={{
            fontSize: "0.67rem",
            fontWeight: 700,
            color: "#94A3B8",
            letterSpacing: "0.10em",
            textTransform: "uppercase",
            padding: "0 24px",
            marginBottom: "8px",
          }}
        >
          Menu
        </div>

        {/* Dashboard */}
        <NavItem
          icon={<LayoutDashboard size={18} />}
          label="CEO Dashboard"
          href="/dashboard"
          active={pathname === "/dashboard"}
        />

        <NavItem
          icon={<BarChart3 size={18} />}
          label="Management Analytics"
          href="/analytics"
          active={pathname === "/analytics"}
          badge="NEW"
        />

        {/* Quản Lý Chi Phí AI */}
        <NavItem
          icon={<DollarSign size={18} />}
          label="Quản Lý Chi Phí AI"
          href="/costs"
          active={pathname === "/costs"}
          badge="NEW"
        />

        {/* Knowledge Base */}
        <NavItem
          icon={<Database size={18} />}
          label="Kho Tri Thức (RAG)"
          href="/knowledge"
          active={pathname === "/knowledge"}
        />

        {/* Quản lý Công Việc Tasks */}
        <NavItem
          icon={<Ticket size={18} />}
          label="Quản Lý Task (Kanban)"
          href="/tasks"
          active={pathname === "/tasks"}
        />

        {/* Lịch Công Việc Calendar */}
        <NavItem
          icon={<Calendar size={18} />}
          label="Lịch Công Việc"
          href="/calendar"
          active={pathname === "/calendar"}
        />

        {/* Workflow Automation */}
        <NavItem
          icon={<Settings size={18} />}
          label="Workflow Automation"
          href="/workflows"
          active={pathname === "/workflows"}
        />

        <NavItem
          icon={<Headphones size={18} />}
          label="Customer Support Ops"
          href="/customer-support"
          active={pathname === "/customer-support"}
          badge="NEW"
        />

        {/* Trung Tâm Phê Duyệt */}
        <NavItem
          icon={<Scale size={18} />}
          label="Trung Tâm Phê Duyệt"
          href="/approvals"
          active={pathname === "/approvals"}
        />

        {/* Quản lý Nhân Viên & Phân Quyền */}
        <NavItem
          icon={<Users size={18} />}
          label="Nhân Viên & Phân Quyền"
          href="/users-mgmt"
          active={pathname === "/users-mgmt"}
        />

        <NavItem
          icon={<ScrollText size={18} />}
          label="Audit Log"
          href="/audit-logs"
          active={pathname === "/audit-logs"}
        />

        <NavItem
          icon={<Cable size={18} />}
          label="Tích hợp doanh nghiệp"
          href="/integrations"
          active={pathname === "/integrations"}
        />

        {/* ── AI EMPLOYEES Section ── */}
        <div
          style={{
            fontSize: "0.67rem",
            fontWeight: 700,
            color: "#94A3B8",
            letterSpacing: "0.10em",
            textTransform: "uppercase",
            padding: "0 24px",
            marginTop: "20px",
            marginBottom: "8px",
          }}
        >
          AI Employees
        </div>

        {/* Expandable group */}
        <div>
          {/* Group header */}
          <button
            onClick={() => toggleGroup("ai-agents")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              width: "100%",
              padding: "9px 24px",
              background: "none",
              border: "none",
              cursor: "pointer",
              transition: "background 0.15s",
              color: isAgentsGroupActive ? "#3C50E0" : "#374151",
              borderLeft: isAgentsGroupActive
                ? "3px solid #3C50E0"
                : "3px solid transparent",
            }}
            onMouseEnter={(e) => {
              if (!isAgentsGroupActive)
                (e.currentTarget as HTMLButtonElement).style.background = "#F8FAFC";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "none";
            }}
          >
            <Bot
              size={18}
              style={{
                color: isAgentsGroupActive ? "#3C50E0" : "#6B7280",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                flex: 1,
                textAlign: "left",
                fontSize: "0.875rem",
                fontWeight: isAgentsGroupActive ? 600 : 500,
              }}
            >
              AI Agents
            </span>

            {/* Chevron */}
            <ChevronDown
              size={15}
              style={{
                color: "#94A3B8",
                transition: "transform 0.2s ease",
                transform: expandedGroup === "ai-agents" ? "rotate(180deg)" : "rotate(0deg)",
                flexShrink: 0,
              }}
            />
          </button>

          {/* Sub-items */}
          {expandedGroup === "ai-agents" && (
            <div
              style={{
                background: "#F8FAFC",
                borderTop: "1px solid #F1F5F9",
                borderBottom: "1px solid #F1F5F9",
                paddingTop: "4px",
                paddingBottom: "4px",
              }}
            >
              {AGENTS.map((agent) => {
                const isActive = pathname === agent.path;
                const isOnline = agentStatuses[agent.role] !== false;
                return (
                  <Link
                    key={agent.role}
                    href={agent.path}
                    style={{ textDecoration: "none", display: "block" }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "8px 24px 8px 44px",
                        background: isActive ? "#EEF2FF" : "transparent",
                        borderLeft: isActive ? "3px solid #3C50E0" : "3px solid transparent",
                        transition: "background 0.15s",
                        cursor: "pointer",
                        marginLeft: "0",
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive)
                          (e.currentTarget as HTMLDivElement).style.background = "#EEF2FF80";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLDivElement).style.background = isActive
                          ? "#EEF2FF"
                          : "transparent";
                      }}
                    >
                      {/* Bullet / emoji */}
                      <span style={{ fontSize: "0.95rem", flexShrink: 0, lineHeight: 1 }}>
                        {agent.emoji}
                      </span>

                      {/* Name */}
                      <span
                        style={{
                          flex: 1,
                          fontSize: "0.85rem",
                          fontWeight: isActive ? 600 : 400,
                          color: isActive ? "#3C50E0" : "#374151",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {agent.name}
                      </span>

                      {/* NEW badge */}
                      {agent.isNew && <NewBadge />}

                      {/* Online dot */}
                      <OnlineDot online={isOnline} />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* ── SUPPORT Section ── */}
        <div
          style={{
            fontSize: "0.67rem",
            fontWeight: 700,
            color: "#94A3B8",
            letterSpacing: "0.10em",
            textTransform: "uppercase",
            padding: "0 24px",
            marginTop: "20px",
            marginBottom: "8px",
          }}
        >
          Support
        </div>

        <NavItem
          icon={<Settings size={18} />}
          label="Cài đặt công ty"
          href="/settings"
          active={pathname === "/settings"}
        />
        <NavItem
          icon={<HelpCircle size={18} />}
          label="Trợ giúp"
          href="#"
          active={false}
          disabled
        />
      </nav>

      {/* ── User Profile + Logout ── */}
      <div
        style={{
          borderTop: "1px solid #E2E8F0",
          padding: "14px 16px",
          flexShrink: 0,
          background: "#FAFBFC",
        }}
      >
        {/* Logout */}
        <button
          id="logout-btn"
          onClick={handleLogout}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            width: "100%",
            padding: "8px 12px",
            borderRadius: "8px",
            background: "none",
            border: "1px solid #FEE2E2",
            cursor: "pointer",
            color: "#DC2626",
            fontSize: "0.85rem",
            fontWeight: 500,
            fontFamily: "inherit",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "#FFF5F5";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "none";
          }}
        >
          <LogOut size={15} />
          <span>Đăng xuất</span>
        </button>
      </div>
    </aside>
    <NotificationPanel open={notificationsOpen} onClose={() => setNotificationsOpen(false)} onUnreadChange={handleUnreadChange}/>
    </>
  );
}

// ─── NavItem Component ───────────────────────────────────────────────────────
function NavItem({
  icon,
  label,
  href,
  active,
  badge,
  disabled = false,
}: {
  icon: React.ReactNode;
  label: string;
  href: string;
  active: boolean;
  badge?: string;
  disabled?: boolean;
}) {
  const content = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "9px 24px",
        background: active ? "#EEF2FF" : "transparent",
        borderLeft: active ? "3px solid #3C50E0" : "3px solid transparent",
        cursor: disabled ? "default" : "pointer",
        transition: "background 0.15s",
        opacity: disabled ? 0.5 : 1,
      }}
      onMouseEnter={(e) => {
        if (!active && !disabled)
          (e.currentTarget as HTMLDivElement).style.background = "#F8FAFC";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = active ? "#EEF2FF" : "transparent";
      }}
    >
      {/* Icon */}
      <span style={{ color: active ? "#3C50E0" : "#6B7280", flexShrink: 0, display: "flex" }}>
        {icon}
      </span>

      {/* Label */}
      <span
        style={{
          flex: 1,
          fontSize: "0.875rem",
          fontWeight: active ? 600 : 500,
          color: active ? "#3C50E0" : "#374151",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {label}
      </span>

      {/* Badge */}
      {badge && (
        <span
          style={{
            fontSize: "0.6rem",
            fontWeight: 700,
            padding: "2px 6px",
            borderRadius: "999px",
            background: "#10B981",
            color: "#FFFFFF",
            letterSpacing: "0.04em",
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  );

  if (disabled || href === "#") return content;

  return (
    <Link href={href} style={{ textDecoration: "none", display: "block" }}>
      {content}
    </Link>
  );
}
