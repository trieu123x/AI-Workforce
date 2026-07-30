# 09 - ĐẶC TẢ RESTFUL API & WEBSOCKET PROTOCOL (API DESIGN SPECIFICATION)

## 9.1 Tổng Quan OpenAPI 3.0 Standard
Toàn bộ hệ thống API được chuẩn hóa theo chuẩn RESTful OpenAPI 3.0 với định dạng dữ liệu truyền nhận JSON. Các Endpoint nhạy cảm bắt buộc đi kèm header `Authorization: Bearer <JWT_TOKEN>`.

---

## 9.2 Danh Sách Các RESTful Endpoints Chính

### 1. Endpoint: `POST /api/v1/auth/login`
- **Mô tả**: Đăng nhập người dùng và nhận JWT Token.
- **Request Body**:
  ```json
  {
    "email": "trieu.nguyen@company.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJKV1QiLC...",
    "token_type": "bearer",
    "user": {
      "id": "u-99201",
      "full_name": "Nguyen Van Triieu",
      "role": "CEO",
      "department": "BOARD"
    }
  }
  ```

### 2. Endpoint: `POST /api/v1/agent/chat/stream`
- **Mô tả**: Khởi tạo phiên làm việc với Agent và nhận response dạng Server-Sent Events (SSE) hoặc Stream.
- **Request Body**:
  ```json
  {
    "agent_role": "CEO",
    "thread_id": "th-8812-4412",
    "message": "Onboard nhân viên mới Lê Văn B vào vị trí IT Support"
  }
  ```

### 3. Endpoint: `GET /api/v1/workflows/{workflow_id}`
- **Mô tả**: Lấy thông tin trạng thái hiện tại của luồng tác vụ LangGraph DAG.
- **Response (200 OK)**:
  ```json
  {
    "workflow_id": "wf-10029",
    "status": "AWAITING_APPROVAL",
    "current_executing_task": "task_hr_leave_grant",
    "dag_plan": [
      { "task_id": "t1", "assigned_agent": "HR", "status": "COMPLETED" },
      { "task_id": "t2", "assigned_agent": "IT", "status": "COMPLETED" },
      { "task_id": "t3", "assigned_agent": "FINANCE", "status": "AWAITING_APPROVAL" }
    ]
  }
  ```

### 4. Endpoint: `POST /api/v1/workflows/approvals/{approval_id}/action`
- **Mô tả**: Đánh giá Chấp thuận / Từ chối cho một Yêu cầu Human-in-the-loop.
- **Request Body**:
  ```json
  {
    "action": "APPROVE", // APPROVE or REJECT
    "comments": "Đồng ý cấp quyền VPN theo đúng yêu cầu công việc."
  }
  ```

---

## 9.3 WebSocket Protocol (Real-Time Live Event Streaming)

Dành cho tính năng hiển thị luồng thực thi Agent theo thời gian thực (LangGraph Execution Graph Visualizer).

- **URL**: `ws://localhost:8000/ws/v1/execution/{thread_id}`
- **Data Payload Event Samples**:
  ```json
  // Event 1: Agent chuyển sang nút mới
  {
    "event": "NODE_TRANSITION",
    "timestamp": "2026-07-27T10:15:30Z",
    "data": {
      "from_node": "CEO_Orchestrator",
      "to_node": "Legal_Agent",
      "reason": "Phát hiện chỉ thị liên quan tới thẩm định hợp đồng"
    }
  }

  // Event 2: Agent bắt đầu thực thi Tool
  {
    "event": "TOOL_CALL_START",
    "timestamp": "2026-07-27T10:15:32Z",
    "data": {
      "agent": "Legal_Agent",
      "tool_name": "ocr_contract_pdf",
      "input": { "file_url": "s3://contracts/doc.pdf" }
    }
  }
  ```
