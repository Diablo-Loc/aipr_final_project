# Trợ lý AI hỗ trợ quản lý và phân tích tiến độ dự án bằng RAG, Agent và MCP

Đồ án môn Lập trình AI với Python (AIPR).
Sinh viên thực hiện: Độc lập (1 thành viên).

## Trạng thái và hướng dẫn tiếp tục

Cập nhật tài liệu ngày 08/10/2026. **Đang triển khai, chưa phải bản nộp cuối.** Phạm vi dưới đây là mục tiêu đã chốt, không phải tuyên bố mọi chức năng đã chạy.

| Hạng mục | Trạng thái tại lần cập nhật này |
|---|---|
| Khung repo, launcher, config và dependency lock | Đã có file; tồn tại .git/.venv |
| Setup, pip check, commit đầu | Sinh viên đã ghi hoàn thành trong ai-usage; AI không chạy lại hoặc kiểm tra Git history trong lượt này |
| Corpus và provenance | Đã có file; chưa xác minh bằng loader của repo thật |
| Code nghiệp vụ | src hiện có __init__.py; models/data/store/RAG/MCP/agent chưa viết |
| Tests, demo, evaluation và report của repo thật | Chưa có bằng chứng kiểm chứng trong lượt này; không lấy kết quả của mock |
| API live | KHÓA, cần sinh viên cho phép rõ ràng trước từng đợt |

**Việc tiếp theo:** Phase 2 — sinh viên tự viết src/models.py và src/data.py, đọc/validate corpus và phiên bản; kiểm tra phần này offline trước khi sang phép tính/SQLite. AI giải thích hoặc sửa code theo yêu cầu cụ thể, không tự viết toàn bộ đồ án.

Đọc theo thứ tự: [AGENTS.md](AGENTS.md) → [kiến trúc](docs/ARCHITECTURE.md) → [setup](docs/SETUP.md) → [khai báo AI](ai-usage.md). Đây là bộ hướng dẫn local tối thiểu, không yêu cầu Docker/CI/Git Flow hay dịch vụ bên ngoài. Không copy PDF/sổ tay vào repo, không tự commit/push.

## 1. Mục tiêu và phạm vi đề tài
Xây dựng trợ lý AI phân tích tiến độ dự án theo 3 tầng bắt buộc của yêu cầu đồ án:
1. **Tầng tra cứu (RAG):** Tra cứu kế hoạch, báo cáo tiến độ, quy tắc cảnh báo bằng 2 chế độ Dense Cosine và Hybrid BM25. Trích dẫn `doc_id`, `version`. Nhận diện và từ chối câu ngoài corpus (`no_answer`).
2. **Tầng biến đổi:** Tính toán tiến độ kế hoạch/thực tế có trọng số (giờ công), độ chênh lệch theo điểm phần trăm (`behind_pp`), phát hiện task quá hạn. Báo `insufficient_data` khi thiếu số liệu, không tự suy đoán.
3. **Tầng hành động (MCP & Tool ghi):** Vòng lặp Agent tự điều phối qua giao thức MCP stdio. Khi phân tích đủ dữ liệu cho thấy rủi ro (chậm vượt/ngang ngưỡng hoặc có task quá hạn) và có quyền ghi, tạo bản ghi vào SQLite (`create_followup_request`) và ngay lập tức gọi tool đọc để xác minh (`get_followup_request`).

Giữ một agent tự viết, CLI, năm MCP tool và SQLite. Không thêm UI, multi-agent, framework agent hoặc dự báo ML. Nguồn yêu cầu là hai PDF của giảng viên; bảng đối chiếu tóm tắt nằm trong ARCHITECTURE. Các quyết định tổ chức repo không phải yêu cầu mới của môn.

## 2. Môi trường và cài đặt
- Hệ điều hành: Windows
- Phiên bản Python: Python 3.11.x (đã khóa dependencies qua `requirements.lock.txt`)
- Giao tiếp công cụ: Model Context Protocol (MCP) qua stdio
- Cơ sở dữ liệu: SQLite chuẩn qua thư viện `sqlite3`

### Khởi tạo môi trường
Chạy lệnh sau tại thư mục gốc của đồ án:
```powershell
py -3.11 run.py setup
if ($LASTEXITCODE -ne 0) { throw 'Setup chưa đạt.' }
```
Lệnh trên cần Python 3.11.x, tạo `.venv` nếu chưa có và cài theo `requirements.lock.txt`. Nó cần mạng tải packages, không gọi API mô hình; không tự chuyển venv sai phiên bản sang 3.11. Nếu không có py nhưng python đã đúng 3.11.x, dùng python run.py setup.

### Lệnh thực thi offline sau khi viết đủ module

Hiện chưa viết CLI/evaluator/test cases, nên không chạy các lệnh dưới đây để kết luận pass. Ran 0 tests không phải bằng chứng kiểm thử. Không nạp .env trong chế độ offline.

```powershell
# Chạy bộ kiểm thử (offline)
.\.venv\Scripts\python.exe run.py test

# Chạy demo CLI
.\.venv\Scripts\python.exe run.py demo --backend offline

# Đánh giá benchmark (eval)
.\.venv\Scripts\python.exe run.py eval --backend offline --runs 1
```
### Lệnh tái lập live — đang khóa

Windows dùng make.cmd qua CMD, không cần GNU Make. Chuẩn bị python 3.11 trên PATH như SETUP. Không chạy lệnh này khi chưa có source đầy đủ và quyền API riêng:

```text
cmd /d /c "make setup && make demo"
cmd /d /c "make eval"
```

Không tự chạy demo/eval mặc định, preflight hoặc judge; không mở/đọc/hiển thị .env hay API key. Live eval chưa được xác minh cho repo thật. Hai lệnh trên không cấp quyền tự chạy cả hai hoặc lặp lại khi hết quota.

## 3. Cấu trúc thư mục đích

Cấu trúc dưới đây gồm các phần sẽ viết, chưa phản ánh tất cả file đã tồn tại:

- `AGENTS.md`: Quy tắc AI, giới hạn quyền và quy trình bàn giao.
- `docs/ARCHITECTURE.md`, `docs/SETUP.md`: Kiến trúc chốt và cách setup/kiểm chứng trên máy mới.
- `src/`: Mã nguồn chính (models, data loader, store, rag, mcp server/client, agent loop, cli).
- `data/`: Corpus 13 tài liệu tổng hợp và tài liệu nguồn gốc provenance.
- `templates/`: Prompt templates (agent prompt, judge prompt).
- `scripts/`: Evaluator và host MCP thứ hai dự kiến; preflight không cần thêm vào phạm vi chính.
- `tests/`: Bộ kiểm thử đơn vị và testset benchmark 12 câu.
- `logs/`: Lưu trữ trace JSONL chi tiết cho từng phiên chạy.
- `results/`: Kết quả tổng hợp đánh giá và file CSV.

## 4. Bằng chứng và cập nhật

- Bộ testset chính dự kiến 12 câu, có ít nhất 4 no_answer; so sánh dense/hybrid cho 24 lượt. Số unit tests không phải tiêu chí cố định của PDF.
- Trước nộp cần số liệu faithfulness/refusal/USAGE thật, ít nhất ba run JSONL đúng revision/config, report Word 8–9 trang, Git/đóng góp thật và khả năng vấn đáp/sửa code.
- Không copy logs/results/report có số đo hoặc Git history của mock thành bằng chứng cá nhân. Code/dữ liệu tái dùng phải khai báo trong ai-usage.
- Sau mỗi phase cập nhật bảng trạng thái, việc tiếp theo và lệnh kiểm chứng thực sự đã chạy. Chưa chạy ghi chưa chạy; kiểm tra tài liệu không thay unit/integration/live tests.
- Repo hiện chỉ được chỉnh local theo yêu cầu. Sinh viên tự quyết định commit/backup/nộp; AI không tự tạo remote hoặc push.
