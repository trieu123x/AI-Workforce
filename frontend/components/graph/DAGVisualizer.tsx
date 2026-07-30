"use client";

import React from "react";
import { CheckCircle2, Clock, GitCommit, ArrowRight, Zap } from "lucide-react";

interface DAGNode {
  node_id: string;
  assigned_agent: string;
  agent_emoji: string;
  title: string;
  status: "COMPLETED" | "IN_PROGRESS" | "PENDING";
  result?: string;
}

interface DAGVisualizerProps {
  workflowId: string;
  title: string;
  nodes: DAGNode[];
  overallStatus?: string;
}

export const DAGVisualizer: React.FC<DAGVisualizerProps> = ({
  workflowId,
  title,
  nodes,
  overallStatus = "COMPLETED",
}) => {
  return (
    <div
      style={{
        marginTop: "14px",
        padding: "18px 22px",
        borderRadius: "16px",
        background: "rgba(13, 13, 30, 0.7)",
        border: "1px solid rgba(139, 92, 246, 0.3)",
        backdropFilter: "blur(14px)",
        maxWidth: "540px",
      }}
    >
      {/* Visualizer Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#c084fc", fontSize: "0.88rem", fontWeight: 700 }}>
          <GitCommit size={20} />
          {title}
        </div>
        <span
          style={{
            fontSize: "0.7rem",
            padding: "3px 10px",
            borderRadius: "99px",
            background: overallStatus === "COMPLETED" ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)",
            color: overallStatus === "COMPLETED" ? "#10b981" : "#f59e0b",
            fontWeight: 700,
          }}
        >
          {overallStatus}
        </span>
      </div>

      {/* DAG Task Nodes Execution Stream */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {nodes.map((node, idx) => (
          <div key={node.node_id} style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 14px",
                borderRadius: "10px",
                background: "rgba(255, 255, 255, 0.03)",
                border: "1px solid " + (node.status === "COMPLETED" ? "rgba(16, 185, 129, 0.25)" : "rgba(255, 255, 255, 0.08)"),
              }}
            >
              {/* Agent Emoji */}
              <div
                style={{
                  fontSize: "1.2rem",
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: "rgba(99, 102, 241, 0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {node.agent_emoji}
              </div>

              {/* Node Title & Assigned Agent */}
              <div style={{ flex: 1, overflow: "hidden" }}>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)" }}>
                  {node.title}
                </div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                  Phân công: <strong style={{ color: "#8b5cf6" }}>{node.assigned_agent} Agent</strong>
                </div>
              </div>

              {/* Status Badge */}
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                {node.status === "COMPLETED" ? (
                  <CheckCircle2 size={16} color="#10b981" />
                ) : (
                  <Clock size={16} color="#f59e0b" />
                )}
                <span style={{ fontSize: "0.72rem", color: node.status === "COMPLETED" ? "#10b981" : "#f59e0b", fontWeight: 600 }}>
                  {node.status}
                </span>
              </div>
            </div>

            {/* Connecting Arrow */}
            {idx < nodes.length - 1 && (
              <div style={{ display: "flex", justifyContent: "center", padding: "2px 0", color: "rgba(255,255,255,0.2)" }}>
                <ArrowRight size={14} style={{ transform: "rotate(90deg)" }} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
