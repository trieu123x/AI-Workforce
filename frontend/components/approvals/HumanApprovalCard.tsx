"use client";

import React, { useState } from "react";
import { ShieldAlert, CheckCircle2, XCircle, Clock } from "lucide-react";
import api from "@/lib/api";

interface HumanApprovalCardProps {
  id: string;
  actionType: string;
  requesterName: string;
  details: string;
  status?: string;
  onActionComplete?: (status: "APPROVED" | "REJECTED") => void;
}

export const HumanApprovalCard: React.FC<HumanApprovalCardProps> = ({
  id,
  actionType,
  requesterName,
  details,
  status: initialStatus = "WAITING",
  onActionComplete,
}) => {
  const [currentStatus, setCurrentStatus] = useState(initialStatus);
  const [loading, setLoading] = useState(false);
  const [comment, setComment] = useState("");

  const handleAction = async (action: "APPROVE" | "REJECT") => {
    try {
      setLoading(true);
      await api.post(`/api/v1/approvals/${id}/action`, {
        action,
        comments: comment || (action === "APPROVE" ? "Đã phê duyệt" : "Từ chối yêu cầu"),
      });
      const newStatus = action === "APPROVE" ? "APPROVED" : "REJECTED";
      setCurrentStatus(newStatus);
      if (onActionComplete) {
        onActionComplete(newStatus);
      }
    } catch (err) {
      console.error("Failed to submit approval action:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        marginTop: "12px",
        padding: "16px 20px",
        borderRadius: "14px",
        background: "rgba(245, 158, 11, 0.08)",
        border: "1px solid rgba(245, 158, 11, 0.3)",
        backdropFilter: "blur(10px)",
        maxWidth: "480px",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "10px",
          color: "#f59e0b",
          fontSize: "0.85rem",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
        }}
      >
        <ShieldAlert size={18} />
        HÀNH ĐỘNG CẦN PHÊ DUYỆT: {actionType}
      </div>

      {/* Body details */}
      <div style={{ fontSize: "0.83rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "14px" }}>
        <p style={{ margin: "2px 0" }}>
          <strong>Người yêu cầu:</strong> {requesterName}
        </p>
        <p style={{ margin: "2px 0" }}>
          <strong>Chi tiết:</strong> {details}
        </p>
      </div>

      {/* Status or Interactive buttons */}
      {currentStatus === "WAITING" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <input
            type="text"
            className="input-field"
            placeholder="Ghi chú phê duyệt (tùy chọn)..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            style={{ fontSize: "0.78rem", padding: "6px 10px" }}
          />
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => handleAction("APPROVE")}
              disabled={loading}
              style={{
                flex: 1,
                padding: "8px 14px",
                borderRadius: "8px",
                border: "none",
                background: "linear-gradient(135deg, #10b981, #059669)",
                color: "white",
                fontSize: "0.82rem",
                fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
              }}
            >
              <CheckCircle2 size={16} /> Chấp Thuận (Approve)
            </button>
            <button
              onClick={() => handleAction("REJECT")}
              disabled={loading}
              style={{
                flex: 1,
                padding: "8px 14px",
                borderRadius: "8px",
                background: "rgba(239, 68, 68, 0.2)",
                color: "#ef4444",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                fontSize: "0.82rem",
                fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
              }}
            >
              <XCircle size={16} /> Từ Chối (Reject)
            </button>
          </div>
        </div>
      ) : (
        <div
          style={{
            padding: "8px 12px",
            borderRadius: "8px",
            background: currentStatus === "APPROVED" ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
            color: currentStatus === "APPROVED" ? "#10b981" : "#ef4444",
            fontSize: "0.8rem",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          {currentStatus === "APPROVED" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          Trạng thái: {currentStatus === "APPROVED" ? "Đã Chấp Thuận (APPROVED)" : "Đã Từ Chối (REJECTED)"}
        </div>
      )}
    </div>
  );
};
