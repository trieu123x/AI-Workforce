# 01 - TỔNG QUAN SẢN PHẨM VÀ SỨ MỆNH (PRODUCT OVERVIEW)

## 1.1 Bối Cảnh & Vấn Đề (Problem Statement)
Trong hầu hết các doanh nghiệp hiện nay, việc ứng dụng Generative AI thường chỉ dừng lại ở mức **Chatbot cá nhân** (User hỏi - AI đáp) hoặc các công cụ tự động hóa riêng lẻ. Điều này dẫn đến các hạn chế lớn:
1. **Thiếu tính phối hợp phòng ban**: Chatbot không có khả năng trao đổi thông tin chéo giữa HR, Finance, IT hay Legal.
2. **Thiếu khả năng thực thi tác vụ end-to-end**: Chatbot chỉ đưa ra câu chữ chứ không thực sự ghi dữ liệu vào SQL Database, không tạo ticket Jira, không gửi email hay xuất file báo cáo.
3. **Thiếu phân quyền và bảo mật doanh nghiệp**: Không thể giới hạn dữ liệu nhạy cảm theo cấp bậc (CEO, Manager, Employee).
4. **Không có cơ chế duyệt (Human-in-the-loop)**: Hành động của AI tự phát sinh dễ gây hậu quả nghiêm trọng nếu không có con người phê duyệt.

## 1.2 Giải Pháp: AI Workforce - Enterprise Multi-Agent Platform
**AI Workforce** tái cấu trúc cách doanh nghiệp vận hành bằng cách biến hệ thống phần mềm thành một **Bộ Máy Nhân Viên AI (Digital AI Employees)** làm việc song song với nhân viên con người.

```
                    CEO Agent (Orchestrator)
                               │
         ┌────────────┬────────┼────────────┬────────────┐
         │            │        │            │            │
      HR AI        Legal AI  IT AI      Finance AI    Sales AI   Knowledge AI
         │            │        │            │            │            │
    (Leave/Onb)  (Contract) (Ticket)    (Invoice)    (Quotation)    (RAG Docs)
```

## 1.3 Cấu Trúc Đơn Vị "AI Employee"
Mỗi AI Agent trong hệ thống được định nghĩa là một thực thể hoàn chỉnh gồm 6 thành tố:

1. **Identity (Định danh)**: Tên, Chức vụ, Phòng ban, Avatar, System Prompt phong cách làm việc.
2. **Permissions (Quyền hạn RBAC)**: Giới hạn các bảng DB và file tài liệu agent được phép truy cập.
3. **Memory (Bộ nhớ 3 tầng)**: Short-term (hội thoại), Long-term (sở thích/thực thể), Company Knowledge (SOP/Policy).
4. **Tools (Bộ công cụ)**: Các hàm Python/MCP được phép gọi (ví dụ: SQL Executor, Document Parser, Email Sender).
5. **Workflows (Quy trình)**: Đồ thị trạng thái LangGraph định nghĩa các bước thực thi từ tiếp nhận đến hoàn thành tác vụ.
6. **Performance & Monitoring**: Ghi log token, latency, chi phí LLM, và tỷ lệ thành công của tác vụ.

## 1.4 Lợi Ích Doanh Nghiệp (Value Proposition)
- **Giảm 80% thời gian xử lý thủ công**: Cho các tác vụ Onboarding, Kiểm tra hợp đồng, Xin nghỉ phép, Xử lý sự cố IT cơ bản.
- **Minh bạch & Tra cứu nhanh**: Truy xuất tài liệu công ty với nguồn trích dẫn chính xác tuyệt đối.
- **Sẵn sàng 24/7**: Phản hồi yêu cầu của nhân viên tức thì bất kể ca làm việc.
