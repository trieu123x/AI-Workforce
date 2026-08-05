# AI Workforce

AI Workforce là nền tảng quản trị doanh nghiệp đa tenant, kết hợp các mô-đun nghiệp vụ với trợ lý AI có kiểm soát. Hệ thống tập trung vào quản trị nhân sự, vận hành workflow, truy xuất tri thức nội bộ và thực thi công cụ theo quyền của người dùng.

## Chức năng chính

- Quản lý tổ chức, người dùng, vai trò và phân quyền theo tenant.
- Trợ lý AI chuyên biệt cho HR và các nghiệp vụ doanh nghiệp.
- Phân loại intent để định tuyến câu hỏi sang truy vấn dữ liệu, tìm kiếm tài liệu hoặc yêu cầu làm rõ.
- Tìm kiếm tri thức bằng PostgreSQL/pgvector và cơ chế RAG lai.
- Workflow có bước phê duyệt thủ công cho các thao tác nhạy cảm.
- Theo dõi audit log, phiên làm việc, mức sử dụng và chi phí AI.
- Xuất danh sách nhân sự sang Excel, PDF hoặc JSON theo phạm vi dữ liệu được cấp quyền.

## Kiến trúc

| Thành phần | Vai trò | Cổng mặc định |
| --- | --- | --- |
| `frontend` | Giao diện Next.js | `3000` |
| `backend` | API nghiệp vụ FastAPI | `8000` |
| `worker` | Xử lý tác vụ nền | Không công khai |
| `ai-service` | Embedding, reranking và suy luận AI | `8100` |
| `postgres` | Dữ liệu nghiệp vụ và vector | `5432` |
| `redis` | Hàng đợi và dữ liệu tạm | `6379` |

Luồng xử lý chính:

```text
Browser -> Frontend -> Backend API -> PostgreSQL / Redis
                              |
                              +----> AI Service / LLM providers
```

Backend chịu trách nhiệm xác thực, phân quyền, kiểm soát công cụ và cô lập dữ liệu tenant. AI Service chỉ đảm nhiệm các tác vụ mô hình; các quyết định truy cập dữ liệu vẫn được thực thi tại Backend.

## Công nghệ

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS, TanStack Query, Zustand.
- Backend: Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic.
- AI: OpenAI-compatible providers, Hugging Face, sentence-transformers và cơ chế RAG.
- Dữ liệu: PostgreSQL, pgvector, Redis.
- Hạ tầng: Docker Compose, GitHub Actions, GitHub Container Registry.

## Yêu cầu môi trường

Cách đơn giản nhất để chạy toàn bộ hệ thống là dùng Docker Desktop hoặc Docker Engine có Docker Compose.

Để phát triển từng dịch vụ trực tiếp trên máy, cần:

- Python 3.11.
- Node.js 22 và npm.
- PostgreSQL có extension `pgvector`.
- Redis 7.

File [`docker-compose.yml`](docker-compose.yml) hiện cấu hình AI Service sử dụng NVIDIA GPU. Với máy chỉ có CPU, cần bỏ phần GPU reservation và đặt các biến thiết bị của AI Service thành `cpu`.

## Khởi chạy bằng Docker Compose

1. Tạo file cấu hình Backend:

   ```bash
   cp backend/.env.example backend/.env
   ```

   Trên PowerShell:

   ```powershell
   Copy-Item backend/.env.example backend/.env
   ```

2. Cập nhật tối thiểu `POSTGRES_PASSWORD` và `SECRET_KEY` trong `backend/.env`.

   Nếu bật xác thực nội bộ cho AI Service, tạo file `.env` tại thư mục gốc và đặt `AI_SERVICE_INTERNAL_TOKEN`. Docker Compose sẽ truyền cùng token này cho Backend, Worker và AI Service.

3. Khởi động hệ thống:

   ```bash
   docker compose up --build
   ```

4. Truy cập các địa chỉ:

   - Frontend: <http://localhost:3000>
   - API documentation: <http://localhost:8000/docs>
   - Backend health check: <http://localhost:8000/health>
   - AI Service health check: <http://localhost:8100/health>

Migration cơ sở dữ liệu được áp dụng khi container Backend khởi động.

## Phát triển cục bộ

### Backend

Backend cần PostgreSQL và Redis đang hoạt động trước khi khởi chạy.

```bash
cd backend
python -m venv .venv
python -m pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

Kích hoạt virtual environment trước khi cài dependency:

- PowerShell: `.venv\Scripts\Activate.ps1`
- Linux/macOS: `source .venv/bin/activate`

### AI Service

```bash
cd apps/ai-service
python -m venv .venv
python -m pip install -e ".[test]"
cp .env.example .env
python -m uvicorn app.main:app --reload --port 8100
```

Để chạy embedding và reranking bằng model Hugging Face cục bộ, cài thêm extra `huggingface`:

```bash
python -m pip install -e ".[huggingface,test]"
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Frontend mặc định gọi Backend qua `NEXT_PUBLIC_API_URL=http://localhost:8000`. Có thể thay đổi giá trị này trong `frontend/.env.local`.

## Cấu hình

Các mẫu cấu hình nằm tại:

- [`backend/.env.example`](backend/.env.example)
- [`apps/ai-service/.env.example`](apps/ai-service/.env.example)

Những nhóm biến quan trọng gồm:

| Nhóm | Biến tiêu biểu |
| --- | --- |
| Cơ sở dữ liệu | `DATABASE_URL`, `POSTGRES_*` |
| Xác thực | `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` |
| AI providers | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` |
| AI Service | `AI_SERVICE_URL`, `AI_SERVICE_INTERNAL_TOKEN`, `AI_SERVICE_TIMEOUT_SECONDS` |
| Embedding | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` |
| Hàng đợi | `REDIS_URL`, `REDIS_QUEUE_NAME` |
| Email và lưu trữ | `SMTP_*`, `MINIO_*`, `CLOUDINARY_*` |

Không commit file `.env`, API key, mật khẩu hoặc token vào repository. Khi triển khai production, nên quản lý secret bằng cơ chế của nền tảng triển khai.

## Migration cơ sở dữ liệu

Áp dụng migration mới nhất:

```bash
cd backend
alembic upgrade head
```

Kiểm tra revision hiện tại:

```bash
alembic current
```

## Kiểm thử và kiểm tra chất lượng

Backend:

```bash
cd backend
python -m pytest -q
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Pipeline CI thực hiện migration trên cơ sở dữ liệu sạch, chạy test Backend, lint/build Frontend và kiểm tra khả năng build các container chính.

## Mô hình bảo mật

- Mọi truy vấn dữ liệu nghiệp vụ phải được giới hạn theo tenant hiện tại.
- Quyền người dùng được kiểm tra trước khi công cụ AI được phép thực thi.
- Các thao tác nhạy cảm có thể yêu cầu phê duyệt thủ công.
- Dữ liệu xuất file tuân theo phạm vi quyền và được ghi audit log.
- Kết quả từ tài liệu nội bộ không được dùng để vượt qua chính sách truy cập dữ liệu có cấu trúc.

Các cơ chế trên hỗ trợ kiểm soát rủi ro nhưng không thay thế việc rà soát cấu hình, secret, hạ tầng và chính sách bảo mật trước khi triển khai production.

## Cấu trúc repository

```text
.
├── apps/ai-service/       # Dịch vụ AI độc lập
├── backend/               # API, worker, migration và test
├── frontend/              # Ứng dụng web Next.js
├── docs/                  # Tài liệu kiến trúc, API và triển khai
├── docker-compose.yml     # Môi trường chạy tích hợp
└── .github/workflows/     # Pipeline CI/CD
```

## Tài liệu bổ sung

- [Tổng quan tài liệu](docs/README.md)
- [Kiến trúc hệ thống](docs/03-system-architecture.md)
- [Thiết kế agent](docs/05-agent-design.md)
- [Thiết kế API](docs/09-api-design.md)
- [Hướng dẫn triển khai](docs/11-deployment.md)
- [Kiến trúc AI Service](docs/AI_SERVICE_ARCHITECTURE.md)
