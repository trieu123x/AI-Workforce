# 03 - KIẾN TRÚC HỆ THỐNG CHI TIẾT (SYSTEM ARCHITECTURE DESIGN)

## 3.1 Sơ Đồ Khối Tổng Thể (High-Level Architecture)

```mermaid
flowchart TD
    subgraph UI_Layer [Frontend Layer - Next.js 14]
        ControlCenter[CEO Control Room Dashboard]
        ChatInterface[Slack/Notion Hybrid Workspace]
        DAGVisualizer[LangGraph Execution Visualizer]
    end

    subgraph API_Layer [API Gateway & Middleware - FastAPI]
        Router[FastAPI Dynamic Router]
        AuthGuard[JWT Auth & RBAC Interceptor]
        WSHandler[WebSocket Manager - Live Stream]
    end

    subgraph Core_Orchestrator [LangGraph Multi-Agent Engine]
        CEONode[CEO Orchestrator Node]
        PlanDAG[DAG Planner & Task Decomposition]
        AgentRouter[State Graph Dispatcher]

        HRNode[HR Agent Node]
        LegalNode[Legal Agent Node]
        ITNode[IT Agent Node]
        FinanceNode[Finance Agent Node]
        SalesNode[Sales Agent Node]
        KnowledgeNode[Knowledge Agent Node]
    end

    subgraph Data_Services [Services & Storage]
        MCPServer[MCP Tool Registry]
        RAGEngine[Hybrid RAG Engine]
        Postgres[(PostgreSQL 16 + pgvector)]
        Redis[(Redis Session & Queue)]
        S3Storage[(Object Storage MinIO/S3)]
    end

    UI_Layer <--> API_Layer
    API_Layer --> AuthGuard --> CEONode
    CEONode --> PlanDAG --> AgentRouter
    AgentRouter --> HRNode & LegalNode & ITNode & FinanceNode & SalesNode & KnowledgeNode
    
    HRNode & LegalNode & ITNode & FinanceNode & SalesNode & KnowledgeNode <--> MCPServer
    HRNode & LegalNode & ITNode & FinanceNode & SalesNode & KnowledgeNode <--> RAGEngine

    MCPServer <--> Postgres
    RAGEngine <--> Postgres
    MCPServer <--> S3Storage
    AgentRouter <--> Redis
```

## 3.2 Luồng Điều Phối Của CEO Agent (Orchestration Sequence Diagram)

Dưới đây là chuỗi xử lý chi tiết khi người dùng đưa ra yêu cầu phức tạp liên quan đến nhiều phòng ban: **"Onboard nhân viên mới Nguyễn Văn A"**.

```mermaid
sequenceDiagram
    autonumber
    actor Manager as User (Human Manager)
    participant CEO as CEO Agent (LangGraph Master)
    participant HR as HR Agent
    participant IT as IT Agent
    participant Finance as Finance Agent
    participant Knowledge as Knowledge Agent
    participant UI as Frontend Workspace

    Manager->>CEO: "Onboard nhân viên mới Nguyễn Văn A vào vị trí Dev"
    CEO->>CEO: Phân rã Task -> Sinh kế hoạch DAG (Plan Execution Graph)
    CEO-->>UI: Hiển thị sơ đồ DAG kế hoạch trên Giao diện

    par Task 1: HR Processing
        CEO->>HR: Exec: Create Profile & Grant Leave Days
        HR->>HR: Call Tool `sql_create_employee`
        HR-->>CEO: Done (ID: EMP-9921)
    and Task 2: IT Provisioning
        CEO->>IT: Exec: Provision Email & VPN Access
        IT->>IT: Call Tool `create_company_email` & `grant_vpn`
        IT-->>CEO: Done (Email: a.nguyen@company.com)
    end

    CEO->>Finance: Task 3: Setup Payroll Profile (Phụ thuộc HR Task)
    Finance->>Finance: Call Tool `setup_payroll_record`
    Finance-->>CEO: Done (Base Salary Registered)

    CEO->>Knowledge: Task 4: Send Employee Handbook & Policy Docs
    Knowledge->>Knowledge: RAG Fetch Onboarding Package
    Knowledge-->>CEO: Package Prepared

    CEO-->>UI: Báo cáo tổng hợp: ✅ Đã hoàn tất Onboarding cho Nguyễn Văn A.
```

## 3.3 Thiết Kế Trạng Thái LangGraph (State Graph Engine)

State chung được truyền qua toàn bộ các Nút (Nodes) trong LangGraph được định nghĩa bằng Schema Python Pydantic:

```python
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AgentTask(BaseModel):
    task_id: str
    assigned_agent: str # HR, LEGAL, IT, FINANCE, SALES, KNOWLEDGE
    description: str
    status: str = "PENDING" # PENDING, IN_PROGRESS, AWAITING_APPROVAL, COMPLETED, FAILED
    result: Optional[Dict[str, Any]] = None
    dependencies: List[str] = []

class MultiAgentState(BaseModel):
    tenant_id: str
    thread_id: str
    initiator_user_id: str
    user_query: str
    dag_plan: List[AgentTask] = []
    current_executing_task_id: Optional[str] = None
    accumulated_context: Dict[str, Any] = {}
    human_approval_required: bool = False
    approval_payload: Optional[Dict[str, Any]] = None
    final_report: str = ""
```

## 3.4 Dynamic LLM Router & Self-Reflection Error Recovery Loop

### 1. Dynamic Model Routing Policy
Để tối ưu hóa chi phí token và thời gian phản hồi, hệ thống áp dụng cơ chế Dynamic LLM Router phân cấp model theo tính chất công việc:

| Loại Tác Vụ (Task Tier) | LLM Recommended | Tiêu chí & Lý do |
| :--- | :--- | :--- |
| **Tier 1: Fast Classification & Routing** | `gpt-4o-mini` / `qwen-2.5-7b` | Phân loại intent, phân tích câu hỏi đơn giản, trích xuất entity cơ bản (Rất nhanh & Rẻ). |
| **Tier 2: General Agent Reasoning & RAG** | `gpt-4o` / `gemini-1.5-pro` | Điều phối multi-agent, trả lời RAG tra cứu tri thức, gọi tools cơ bản. |
| **Tier 3: Complex Reasoning & Legal/Code** | `claude-3-5-sonnet` / `gpt-4o` | Thẩm định hợp đồng pháp lý rủi ro, phân tích hóa đơn tài chính phức tạp, sinh code SQL/Python. |

### 2. Self-Reflection & Fallback Loop Architecture

```mermaid
flowchart TD
    Task[Node Execution Triggered] --> ExecTool[Execute Agent Tool / LLM Call]
    ExecTool --> CheckResult{Lỗi hoặc Trả về Invalid Schema?}
    
    CheckResult -->|Thành công| Success[Chuyển State sang Node tiếp theo]
    CheckResult -->|Thất bại / Exception| RetryCount{Retry Count < 3?}
    
    RetryCount -->|Còn Lượt Retry| ReflectionPrompt[Tự Phản Biện - Self-Reflection Node]
    ReflectionPrompt --> FixPayload[Sửa lại Parameters / Refine Prompt] --> ExecTool
    
    RetryCount -->|Vượt 3 Lượt Retry| SwitchFallback[Dynamic Fallback Model]
    SwitchFallback --> AlternateLLM[Chuyển từ Primary LLM sang Secondary LLM] --> ExecTool
    
    AlternateLLM --> StillFails{Vẫn Lỗi?} -->|Yes| EscalateHuman[Đánh dấu FAILED & Gửi Alert cho Administrator]
```

