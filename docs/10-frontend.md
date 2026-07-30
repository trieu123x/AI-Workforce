# 10 - THIẾT KẾ GIAO DIỆN NGUYÊN MẪU & FRONTEND ARCHITECTURE (FRONTEND DESIGN)

## 10.1 Triết Lý UX/UI Modern Hybrid (Notion + Slack + Jira)
Giao diện người dùng của **AI Workforce** được thiết kế nhằm mục đích đem lại cảm giác sang trọng (Modern Enterprise), linh hoạt và giàu tính tương tác:
- **Phong cách Notion**: Quản lý tài liệu tri thức, ghi chú quy trình, giao diện trình bày bài viết sạch sẽ, hỗ trợ Markdown & Code Highlighting.
- **Phong cách Slack**: Kênh chat thời gian thực giữa Human & AI Employees, hiển thị danh sách trạng thái Online/Thinking của từng Agent.
- **Phong cách Jira**: Kanban Board quản lý các Ticket hỗ trợ IT/HR, thẻ công việc (Cards), nhật ký Audit Logs và nút Duyệt Yêu Cầu (Approval Gateways).

```
+-----------------------------------------------------------------------------------+
|  AI WORKFORCE ENTERPRISE                                     [👤 Admin] [🟢 Live] |
+------------------+------------------------------------------+---------------------+
| 📊 CEO Dashboard | 💬 #general-workspace                    | 🛠️ Agent Inspector |
|                  |                                          |                     |
| AI EMPLOYEES     | 👔 CEO Agent:                            | Active: HR Agent    |
| 🟢 HR Agent      | "Đã phân rã công việc Onboard thành 4    | Tool: SQL Query     |
| 🟢 Legal Agent   |  tác vụ cho HR, IT, Finance."            | Latency: 320ms      |
| 🟢 IT Agent      |                                          |                     |
| 🟢 Finance Agent | 🧑‍💼 HR Agent:                             | MEMORY CONTEXT      |
| 🔴 Sales Agent   | [Card: Tạo hồ sơ nhân viên thành công]   | - EmpID: EMP-992    |
| 🟢 Knowledge     |                                          | - Dept: Dev         |
|                  | 🛡️ APPROVAL REQUIRED                     |                     |
| WORKSPACE        | [Phê duyệt cấp quyền VPN cho NV mới]     | AUDIT TRAIL         |
| 📁 Policies 2025 | [ Approve ]   [ Reject ]                 | > Query SQL OK      |
| 📁 IT Tickets    |                                          | > Grant Mail OK     |
+------------------+------------------------------------------+---------------------+
```

## 10.2 Cấu Trúc Dự Án Frontend (Next.js 14 App Router)

```
📂 src/
├── 📂 app/
├── │   ├── 📂 (auth)/              # Trang Login, Register, Forgot Password
├── │   ├── 📂 dashboard/           # Trang CEO Control Room Dashboard
├── │   ├── 📂 agents/              # Trang chi tiết cho từng AI Agent (HR, IT, Legal...)
├── │   ├── 📂 knowledge/           # Kho tài liệu doanh nghiệp kiểu Notion
├── │   └── 📂 workflows/           # Kanban Board theo dõi tiến độ các tác vụ
├── 📂 components/
├── │   ├── 📂 ui/                  # shadcn/ui components (Button, Modal, Card...)
├── │   ├── 📂 chat/                # Chat stream message items, Citation Tooltip
├── │   ├── 📂 graph/               # Mermaid / React Flow DAG Visualizer
├── │   └── 📂 approvals/           # Interactive Approval Action Cards
├── 📂 store/
├── │   ├── useAuthStore.ts         # Authentication state (Zustand)
├── │   └── useAgentStreamStore.ts  # Stream message & DAG execution state
└── 📂 lib/
    ├── api-client.ts           # Axios / Fetch HTTP Gateway Client
    └── websocket-client.ts     # WebSocket Connection Handler
```

## 10.3 Component Card Phê Duyệt Tương Tác (Approval Card Spec)

```tsx
// React / Next.js Component cho Thẻ Phê Duyệt của Quản lý
import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';

interface ApprovalCardProps {
  id: string;
  actionType: string;
  requesterName: string;
  details: string;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export const HumanApprovalCard: React.FC<ApprovalCardProps> = ({
  id, actionType, requesterName, details, onApprove, onReject
}) => {
  return (
    <Card className="border-amber-500/50 bg-amber-950/10">
      <CardHeader>
        <CardTitle className="text-amber-400 text-sm font-semibold">
          🛡️ HÀNH ĐỘNG CẦN PHÊ DUYỆT: {actionType}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-xs space-y-2">
        <p><strong>Người yêu cầu:</strong> {requesterName}</p>
        <p><strong>Chi tiết:</strong> {details}</p>
      </CardContent>
      <CardFooter className="flex gap-2">
        <Button size="sm" className="bg-emerald-600 hover:bg-emerald-500" onClick={() => onApprove(id)}>
          Chấp Thuận (Approve)
        </Button>
        <Button size="sm" variant="destructive" onClick={() => onReject(id)}>
          Từ Chối (Reject)
        </Button>
      </CardFooter>
    </Card>
  );
};
```
