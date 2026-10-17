# Trợ lý AI hỗ trợ quản lý và phân tích tiến độ dự án bằng RAG, Agent và MCP

Đồ án môn Lập trình AI với Python (AIPR).
Sinh viên thực hiện: Độc lập (1 thành viên).

## Trạng thái và hướng dẫn tiếp tục

Cập nhật ngày 17/10/2026 sau đối chiếu hai PDF, source, report, lịch sử Git và bằng chứng. **Source giữ nguyên logic Phase 8; report.docx đã được chuẩn bị và kiểm tra. Commit Phase 9; Phase 10 chưa thực hiện cold start/bảo vệ.** Hoàn tất 24 lượt E1 không có nghĩa 24/24 functional hoặc grounded PASS.

Audit 17/10: 48/48 tests offline OK (2,828 giây), integration 24/24 bằng stub qua MCP stdio và SQLite thật, host thứ hai verify PASS; pip check OK, CSV/summary từ logs cũ khớp. S1 đã chạy trong lịch sử nhưng hiện thiếu ở working tree, vẫn còn trong HEAD; ba log live hoàn chỉnh đang có là S1/S2/S3/E1. Báo cáo dùng S3/E1; Xem mục audit mới trong [VERIFICATION](docs/VERIFICATION.md). Không chạy API mới trong audit.

| Hạng mục | Trạng thái hiện tại |
|---|---|
| Khung repo, launcher, config và dependency lock | Python 3.11.0; 44 distributions khóa phiên bản, 0 lệch lock trong audit; 46 distributions đang cài |
| Corpus và provenance | 13 tài liệu tổng hợp hợp lệ; lọc supersedes/GLOBAL/project/date, gồm P001–P004 với các ca thiếu dữ liệu |
| Code nghiệp vụ (`src/`, `scripts/`, `templates/`) | Đã hoàn thành đầy đủ (`models`, `data`, `store`, `hybrid`, `api`, `rag`, `mcp_server`, `mcp_client`, `runtime`, `agent`, `offline_model`, `cli`, `second_client`, `eval`) |
| Kiểm thử Offline & Unit/Integration Tests | Đã PASS (`48/48` tests OK, `interop` PASS, `demo --backend offline` 4/4 PASS, `eval --backend offline --runs 1` 24/24 PASS) |
| Thực nghiệm Live API (Phase 8) | Đã hoàn thành 3 lượt Smoke (`S1`, `S2`, `S3`) và 1 lượt Full Eval (`E1`: 24/24 lượt trên Groq & Jina AI — chi tiết tại [docs/VERIFICATION.md](docs/VERIFICATION.md)) |
| Audit Phase 8 | 48/48 tests chạy lại đạt; signature E1 khớp source, CSV/summary tái dựng đúng; xem [audit](docs/AUDIT_PHASE8_20261011.md) |

Đọc theo thứ tự: [AGENTS.md](AGENTS.md) → [kiến trúc](docs/ARCHITECTURE.md) → [setup](docs/SETUP.md) → [kiểm chứng](docs/VERIFICATION.md) → [khai báo AI](ai-usage.md). Đây là bộ hướng dẫn local tối thiểu, không yêu cầu Docker/CI/Git Flow hay dịch vụ bên ngoài. Không copy PDF/sổ tay vào repo, không tự commit/push.

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

CLI/evaluator/test cases đã có và đã kiểm chứng offline. Các lệnh dưới đây là cách chạy lại khi cần; không nạp .env thật. Ran 0 tests không phải bằng chứng đạt.

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

Không tự chạy demo/eval mặc định, preflight hoặc judge; không mở/đọc/hiển thị .env hay API key. E1 đã có và log được audit; quyền API cho lượt mới vẫn khóa. Hai lệnh trên không cấp quyền tự chạy cả hai hoặc lặp lại khi hết quota. Cold start trên máy bảo vệ chưa được xác minh.

## 3. Cấu trúc repo

Cấu trúc ứng dụng đã triển khai; report.docx đã chuẩn bị, chờ sinh viên duyệt và tự commit:

- `AGENTS.md`: Quy tắc AI, giới hạn quyền và quy trình bàn giao.
- `docs/ARCHITECTURE.md`, `docs/SETUP.md`: Kiến trúc chốt và cách setup/kiểm chứng trên máy mới.
- `src/`: Mã nguồn chính (models, data loader, store, rag, mcp server/client, agent loop, cli).
- `data/`: Corpus 13 tài liệu tổng hợp và tài liệu nguồn gốc provenance.
- `templates/`: Prompt templates (agent prompt, judge prompt).
- `scripts/`: Evaluator và host MCP thứ hai. Launcher còn target phụ audit/report/preflight nhưng script tương ứng không có trong repo; không dùng các target đó. Bản Word được dựng ngoài repo.
- `tests/`: Bộ kiểm thử đơn vị và testset benchmark 12 câu.
- `logs/`: Lưu trữ trace JSONL chi tiết cho từng phiên chạy.
- `results/`: Kết quả tổng hợp đánh giá và file CSV.
- `report.docx`: Báo cáo Word theo tên sản phẩm PDF; đặt cạnh README.md là quy ước repo để nộp thuận tiện. PDF không bắt buộc phải commit Word hoặc đặt ở root.

## 4. Bằng chứng và cập nhật

- Bộ testset chính có 12 câu, bốn no_answer và một insufficient_data; E1 so sánh dense/hybrid trên 24 lượt. Số unit tests không phải tiêu chí cố định của PDF.
- Raw E1: functional accuracy 8/12 mỗi mode; grounded 7/12 dense và 6/12 hybrid; mean faithfulness 0,75/0,7917. Correct refusal auto judge 0/4 không được diễn giải thành hệ thống bịa mọi câu ngoài corpus: các sai lệch đã phân tích trong audit. Giữ nguyên raw số liệu và phân biệt rà tay với auto judge.
- Source completeness summary 7/7 ở mỗi mode, loại no_answer và insufficient_data khỏi mẫu số. CSV vẫn kiểm tra expected_sources của Q19 riêng.
- Trước nộp cần số liệu faithfulness/refusal/USAGE thật, ít nhất ba run JSONL đúng revision/config, report Word 8–9 trang, Git/đóng góp thật và khả năng vấn đáp/sửa code.
- Không copy logs/results/report có số đo hoặc Git history của mock thành bằng chứng cá nhân. Code/dữ liệu tái dùng phải khai báo trong ai-usage.
- Sau mỗi phase cập nhật bảng trạng thái, việc tiếp theo và lệnh kiểm chứng thực sự đã chạy. Chưa chạy ghi chưa chạy; kiểm tra tài liệu không thay unit/integration/live tests.
- Repo hiện chỉ được chỉnh local theo yêu cầu. Sinh viên tự quyết định commit/backup/nộp; AI không tự tạo remote hoặc push.
