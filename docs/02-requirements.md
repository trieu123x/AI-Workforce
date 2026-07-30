# 02 - PHÂN TÍCH YÊU CẦU NGHỆP VỤ & KỸ THUẬT (REQUIREMENTS SPECIFICATION)

## 2.1 Yêu Cầu Chức Năng (Functional Requirements - FR)

### FR-01: Quản Lý Phân Quyền & Tổ Chức (RBAC & Tenancy)
- **FR-01.1**: Hệ thống hỗ trợ 4 vai trò chính: `CEO`, `Manager`, `Employee`, `Guest`.
- **FR-01.2**: Phân vùng dữ liệu nghiêm ngặt theo Tenant (Doanh nghiệp) và phòng ban. Nhân viên phòng Sales không thể xem hợp đồng pháp lý của Legal ngoại trừ file công khai.

### FR-02: Bộ Máy Multi-Agent Orchestration
- **FR-02.1**: **CEO Agent** có khả năng tự phân rã yêu cầu phức tạp của người dùng thành biểu đồ tác vụ không chu trình (DAG - Directed Acyclic Graph).
- **FR-02.2**: Hỗ trợ thực thi song song các sub-tasks khi không bị phụ thuộc dữ liệu.
- **FR-02.3**: Quản lý trạng thái bằng LangGraph Checkpointer, cho phép tạm dừng tác vụ để chờ duyệt (Human-in-the-loop) và tiếp tục sau khi được cấp phép.

### FR-03: Nghiệp Vụ Chuyên Môn Của Từng Agent
- **FR-03.1 (HR Agent)**:
  - Tra cứu số ngày phép khả dụng của nhân viên.
  - Xử lý đơn xin nghỉ phép và gửi card duyệt cho Manager.
  - Tự động hóa quy trình Onboarding nhân viên mới.
- **FR-03.2 (Legal Agent)**:
  - Upload file hợp đồng PDF/Word.
  - Trích xuất và phát hiện điều khoản rủi ro (Risk Clause Detection).
  - Tự động xuất bản hợp đồng đề xuất chỉnh sửa dưới dạng `.docx`.
- **FR-03.3 (IT Agent)**:
  - Trả lời thắc mắc sự cố hạ tầng qua RAG.
  - Tự động tạo Ticket sự cố (Jira format) khi không thể tự khắc phục.
- **FR-03.4 (Finance Agent)**:
  - OCR hóa đơn VAT (PDF/Ảnh).
  - Trích xuất số tiền, VAT, đối chiếu với đơn đặt hàng SQL.
  - Gửi cảnh báo lệch tiền cho CFO.
- **FR-03.5 (Sales Agent)**:
  - Tra cứu catalog sản phẩm & tồn kho kho hàng.
  - Tự động sinh báo giá PDF gửi khách hàng qua Email.
- **FR-03.6 (Knowledge Agent)**:
  - Tìm kiếm lai (Hybrid Search: Vector + Keyword) trên toàn bộ kho tài liệu doanh nghiệp.
  - Trả về câu trả lời kèm thẻ trích dẫn chính xác (Citation Tags).

## 2.2 Yêu Cầu Phi Chức Năng (Non-Functional Requirements - NFR)

### NFR-01: Hiệu Năng & Thời Gian Phản Hồi (Performance)
- **Streaming Response**: Giao diện hiển thị token kết quả dưới 500ms (Time-to-First-Token).
- **Hybrid RAG Query**: Thời gian tra cứu tài liệu & rerank < 1.5 giây.
- **Async Task Handling**: Các tác vụ nặng (OCR, Sinh PDF, Vector Embedding) được đẩy vào Celery Worker queue, không gây nghẽn main API Gateway thread.

### NFR-02: Bảo Mật & Tuân Thủ (Security & Compliance)
- **Token Masking / PII Anonymization**: Tự động lọc các thông tin nhạy cảm (Số CMND/CCCD, Số thẻ tín dụng) trước khi gửi tới LLM Cloud APIs.
- **Audit Logging**: Ghi vết toàn bộ hành động gọi Tool, truy vấn DB và duyệt chấp thuận của người dùng vào bảng `audit_logs`.

### NFR-03: Tính Khả Dụng & Mở Rộng (Reliability & Scalability)
- Cấu trúc Stateless API Gateway dễ dàng scale horizontally.
- Lưu giữ trạng thái State Graph trong PostgreSQL & Redis để chống mất dữ liệu khi hệ thống gặp sự cố kĩ thuật.
