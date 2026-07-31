# 14 - Versioned Knowledge Embedding Pipeline

Pipeline triển khai cho kho tri thức:

1. Lưu file gốc vào object-storage adapter và chỉ lưu `storage_key` trong PostgreSQL.
2. Tạo `knowledge_documents` record với trạng thái `uploaded/parsing`.
3. Parse theo PDF, DOCX, TXT, Markdown, CSV hoặc HTML; PDF giữ marker trang, DOCX/HTML giữ heading.
4. Làm sạch bảo thủ: bỏ control character, page footer, khoảng trắng thừa và nối từ bị ngắt bởi dấu gạch; không xóa Điều/Khoản/Bước/API/path.
5. Tách semantic theo heading, heading đánh số, Điều, Khoản, Mục, Bước, Trách nhiệm, Điều kiện và Phụ lục.
6. Chỉ section dài mới chia token theo `100/450/700`, overlap `80`.
7. Tính SHA-256 cho nội dung chuẩn hóa, loại chunk trùng và tái sử dụng vector cùng model/version.
8. Tạo `embedding_text` từ department, document type/title, section title và content.
9. Embed theo batch, normalize L2, retry exponential và kiểm tra đúng 1024 chiều.
10. Lưu chunk, vector, hash, model/version, page range và governance metadata.
11. Truy xuất dense top 30 qua pgvector và keyword top 30 qua PostgreSQL FTS, hợp nhất bằng RRF rồi rerank. Dùng cosine tuyệt đối và ngưỡng relevance để không trả chunk cho câu hỏi ngoài phạm vi.
12. ACL tenant/department/role/status/effective date được áp dụng trước candidate retrieval; chunk IDs được lưu trong citation và audit log.

Backend mặc định dùng deterministic embedding để test không cần tải model. Production đặt:

```env
EMBEDDING_BACKEND=sentence_transformers
EMBEDDING_MODEL_NAME=Qwen/Qwen3-Embedding-0.6B
EMBEDDING_VERSION=qwen3-embedding-0.6b-v1
EMBEDDING_DIMENSION=1024
EMBEDDING_DEVICE=cpu
EMBEDDING_CACHE_FOLDER=data/models/huggingface/hub
EMBEDDING_LOCAL_FILES_ONLY=true
RAG_MIN_DENSE_SCORE=0.50
RAG_MIN_RELEVANCE_SCORE=0.50
```

và cài `requirements-embeddings.txt` trong embedding worker. Không được tìm kiếm chéo giữa các `embedding_model` hoặc `embedding_version` khác nhau.
