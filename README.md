# Trợ lý AI hỗ trợ quản lý và phân tích tiến độ dự án

Đồ án môn Lập trình AI với Python (AIPR), thực hiện cá nhân. Hệ thống tra cứu tài liệu có nguồn, tính tiến độ có trọng số và tạo phiếu xử lý rủi ro trong SQLite rồi đọc lại để xác minh. Sử dụng một agent tự viết, RAG dense/hybrid và năm công cụ MCP qua stdio.

## Điều kiện chạy

- Windows, Python 3.11.x; lệnh `python` trên PATH phải trỏ đến Python 3.11.x.
- Có mạng để cài thư viện và gọi Groq/Jina.
- Người chạy tự tạo `.env` theo mẫu `.env.example`, điền `GROQ_API_KEY` và `JINA_API_KEY`. Giữ key trên máy cá nhân, không đưa lên Git hoặc báo cáo.
- Mở PowerShell tại thư mục chứa `make.cmd` và `run.py`.

## Cài đặt và chạy demo bằng một lệnh

```powershell
cmd /d /c "make setup && make demo"
```

Đây là lệnh Windows tương ứng `make setup && make demo` trong yêu cầu môn học. Chương trình tự tạo `.venv`, cài theo `requirements.lock.txt`, khởi chạy MCP server, discover công cụ và chạy demo. Không cần activate venv hoặc mở server riêng. Không cần cài GNU Make trên Windows vì repo có `make.cmd`.

Demo mặc định chạy bốn câu bằng API thật:

| Câu hỏi | Kết quả cần đối chiếu |
|---|---|
| Ai phụ trách T02 của P001? | `ok`, Minh, có nguồn |
| P001 ngày 08/10/2026 chậm bao nhiêu? | `ok`, kế hoạch 70%, thực tế 48%, chậm 22 điểm phần trăm |
| Ngân sách đã chi của P001? | `no_answer`, không đoán ngân sách |
| Tạo yêu cầu xử lý nếu P001 có rủi ro | `action_verified`, ghi SQLite và đọc lại khớp bản ghi |

Màn hình có câu trả lời, citation, USAGE và đường dẫn trace `logs/demo_live_*.jsonl`. CLI chạy xong thì thoát; câu hỏi khác được truyền qua tùy chọn `--query`, hành động ghi cần `--allow-write`. Các tùy chọn này chuyển tiếp qua `make demo`, không phải bước cài đặt thêm.

## Đánh giá

```powershell
cmd /d /c "make eval"
```

Đây là lệnh đánh giá riêng, không cần chạy trước để khởi động demo. Mặc định chạy một đợt gồm 12 câu × dense/hybrid, dùng API agent, embedding và judge. Kết quả lưu ở `logs/eval_live_*.jsonl` và `results/live/`: `per_query.csv`, `summary.json`, `accuracy.png`. Lệnh hoàn tất không đồng nghĩa mọi câu đều PASS; cần đọc điểm từng câu và phân tích ca thất bại.

Số liệu E1 ngày 11/10/2026 đã có trong repo và báo cáo: functional 8/12 mỗi mode, grounded 7/12 dense và 6/12 hybrid, mean faithfulness 0,7500 và 0,7917; correct refusal theo judge 0/4. Các bất đồng judge được phân tích trong báo cáo. Lượt API mới có thể cho câu trả lời/token/điểm khác; giữ log gốc để đối chiếu, không tự sửa kết quả cũ thành đạt.

## Chạy câu hỏi tại buổi bảo vệ

Sau khi đã cài đặt, thay nội dung trong dấu ngoặc kép bằng câu hỏi giảng viên đưa tại chỗ, ngoài testset:

```powershell
cmd /d /c 'make demo --query "P002 ngày 08/10/2026 có chậm tiến độ hoặc có công việc quá hạn không?"'
```

Ví dụ trên không có trong `tests/testset.jsonl`; kết quả cần đối chiếu là kế hoạch 70%, thực tế 75%, đi trước 5 điểm phần trăm và không có công việc quá hạn. Nếu câu hỏi yêu cầu tạo phiếu, thêm `--allow-write` vào cuối lệnh. Chương trình in câu trả lời, nguồn, USAGE và đường dẫn trace như demo mặc định.

Ba lệnh trong README phục vụ ba việc riêng: cài đặt kèm demo, đánh giá và hỏi một câu tùy chọn; không phải chạy liên tiếp cả ba để khởi động. Demo và đánh giá mặc định dùng API thật, chỉ chạy khi người dùng chủ động và có quota. Các lệnh `test`, `interop` và tùy chọn offline dành cho kiểm thử/phát triển, không cần chạy để mở demo; xem `docs/SETUP.md` khi cần.

## Tệp chính

- `src/`: schema, corpus, RAG, API, agent, MCP server/client và SQLite.
- `data/corpus.jsonl`: 13 tài liệu mô phỏng, dùng chung cho truy xuất và tính toán; nguồn gốc ở `data/provenance.md`.
- `vendor/week4/ex2_1_hybrid_search.original.py`: mã bài học tuần 4 để đối chiếu phần tái sử dụng.
- `templates/`: prompt agent và judge đầy đủ.
- `tests/testset.jsonl`: 12 câu, trong đó bốn no_answer; các tệp test Python kiểm tra đơn vị/tích hợp.
- `logs/`, `results/`: bằng chứng chạy và số đo; báo cáo dùng trace S3 và E1 ngày 11/10.
- `report.docx`: báo cáo Word; `ai-usage.md`: khai báo AI và phần tái sử dụng.
- `docs/ARCHITECTURE.md`, `docs/SETUP.md`: kiến trúc và hướng dẫn kiểm tra chi tiết dành cho người phát triển.

## Trạng thái kiểm chứng

Phase 9 đã commit tại `fb4d1d6`. Ngày 17/10/2026, checkout riêng từ commit này và venv mới đã cài thành công, pip check OK, 48/48 tests đạt, demo offline bốn câu đạt, evaluation offline 24/24 functional đạt và client MCP thứ hai ghi–đọc xác minh thành công. Offline không đo chất lượng LLM thật. Cold demo live ở môi trường mới/máy giảng viên chưa được xác minh.

Sản phẩm nộp gồm Word và repo ZIP hoặc link có lịch sử Git, kèm data/prompts/testset/logs/results/ai-usage. Không đóng gói `.env`, `.venv`, cache, state hoặc công cụ kiểm tra ngoài repo. Bản Download ZIP tự động từ GitHub không chứa lịch sử `.git`; nếu nộp ZIP phải chuẩn bị bản có lịch sử theo yêu cầu.
