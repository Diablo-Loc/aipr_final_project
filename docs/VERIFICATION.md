# Hồ sơ Kiểm chứng Thực tế (Verification Log)

Tài liệu này ghi nhận các lệnh kiểm chứng đã chạy thật trên repository cá nhân (`do_an_aipr`), kèm ngày giờ, mã thoát, số ca kiểm thử và đường dẫn file log thực tế.

---

## 1. Kiểm chứng Offline & Unit Tests (Phase 1–7 — Đã hoàn thành)

| Hạng mục | Lệnh thực thi | Kết quả thực tế | Tệp bằng chứng / Ghi chú |
|---|---|---|---|
| **Môi trường Python 3.11** | `py -3.11 run.py setup` & `.\.venv\Scripts\python.exe -m pip check` | `Python 3.11.0`, `No broken requirements found` (45 packages) | `requirements.lock.txt` |
| **Phase 2: Corpus & Schema** | Smoke test nạp `Corpus`, lọc `eligible("P001", "2026-10-08")`, `tool_schema` | `Phase 2: PASS` (13 docs; chọn đúng `P001-PLAN`, `P001-W2-V2`, `POLICY-V2`) | `src/models.py`, `src/data.py` |
| **Phase 3: Analyze & SQLite** | Smoke test `Corpus.analyze` & `RequestStore` (`create`/`get`) | `Phase 3: PASS` (`planned: 70.0`, `actual: 48.0`, `behind_pp: 22.0`, `T02 overdue: 1`) | `src/store.py` |
| **Phase 4: Dense & Hybrid RAG** | Smoke test `Retriever(corpus, "offline")` với `dense` & `hybrid` (`top_k=2`) | `Phase 4: PASS` | `src/hybrid.py`, `src/api.py`, `src/rag.py` |
| **Phase 5: MCP Stdio & Interop** | Smoke test `connect` (5 tools) & `.\.venv\Scripts\python.exe run.py interop` | `Phase 5: PASS` & `Interop write/read verification: PASS` | `src/mcp_server.py`, `src/mcp_client.py`, `scripts/second_client.py` |
| **Phase 6: HTTP Stub & Demo Offline** | `.\.venv\Scripts\python.exe run.py demo --backend offline` | `HTTP stub: PASS` & 4 kịch bản demo (`ok`, `ok`, `no_answer`, `action_verified`) PASS | `logs/demo_offline_20261010T165849710869.jsonl` |
| **Phase 7: Testset & 48 Unit Tests** | `.\.venv\Scripts\python.exe run.py test` | `Testset: PASS` & `Ran 48 tests in 2.336s — OK` (sử dụng mock/stub, không nạp `.env` thật) | `tests/test_core.py`, `tests/test_eval.py`, `tests/test_audit.py` |
| **Phase 7: Offline Evaluation** | `cmd /d /c "make eval --backend offline --runs 1"` | 24/24 lượt (`12 dense + 12 hybrid`) đạt `functional_accuracy = 1.0`, `source_completeness_rate = 1.0`; các chỉ số LLM (`faithfulness`, `citation_support_rate`, `grounded_accuracy`) để `null` (`N/A`) | `logs/eval_offline_20261011T090858146657_1b17bf.jsonl`, `results/offline/summary.json`, `results/offline/per_query.csv`, `results/offline/accuracy.png` |

---

## 2. Kiểm chứng Live API (Phase 8 — Đã hoàn thành)

> **Cấu hình thực thi:** Agent LLM `qwen/qwen3.8-27b` (Groq), Judge LLM `openai/gpt-oss-20b` (Groq), Embedding `jina-embeddings-v3` (Jina AI), `top_k = 4`, `max_steps = 8`, `chunk_chars = 1000`.

### 2.1. Ba lượt chạy Smoke Live riêng biệt (`S1`, `S2`, `S3`)

- [x] **Smoke Live S1 (Lookup):**
  - **Lệnh:** `.\.venv\Scripts\python.exe run.py demo --backend live --mode hybrid --query "Ai phụ trách T02 của P001?"`
  - **Kết quả:** `[live / ok] Người phụ trách task T02 của dự án P001 là Minh.` (`facts: {"owner": "Minh", "project_id": "P001", "task_id": "T02"}`), trích dẫn `P001-PLAN, P001-MEETING`.
  - **USAGE:** Agent `{"calls": 1, "prompt_tokens": 2895, "completion_tokens": 119, "max_prompt": 2895, "attempts": 1}`; Embedding `2 calls, 705 tokens, 0 cache_hits`.
  - **Tệp log:** `logs/demo_live_20261011T094646647365.jsonl`

- [x] **Smoke Live S2 (Version comparison):**
  - **Lệnh:** `.\.venv\Scripts\python.exe run.py demo --backend live --mode hybrid --query "Báo cáo P001 ngày 08/10 phiên bản v1 và v2 khác gì? Dùng bản nào?"`
  - **Kết quả:** `[live / ok]` Agent tự động gọi `get_document(doc_id="P001-W2-V1", version=1)`, đối chiếu `old_T02: 50`, `new_T02: 60`, `task_change_pp: 10`, kết luận dùng `P001-W2-V2` (do `supersedes: "P001-W2-V1"`), trích dẫn đủ `P001-W2-V1, P001-W2-V2`.
  - **USAGE:** Agent `{"calls": 2, "prompt_tokens": 5791, "completion_tokens": 351, "max_prompt": 3057, "attempts": 2}`; Embedding `1 call, 35 tokens, 6 cache_hits`.
  - **Tệp log:** `logs/demo_live_20261011T094808143956.jsonl`

- [x] **Smoke Live S3 (Write & Verify + HTTP 429 Recovery):**
  - **Lệnh:** `.\.venv\Scripts\python.exe run.py demo --backend live --mode hybrid --allow-write --query "Nếu P001 vượt ngưỡng ngày 08/10/2026, hãy tạo yêu cầu xử lý và xác nhận đã lưu."`
  - **Kết quả:** `[live / action_verified]` Chuỗi gọi tool: `analyze_progress` (`planned: 70.0, actual: 48.0, behind_pp: 22.0, threshold_pp: 15, risk: true`) $\rightarrow$ `create_followup_request` $\rightarrow$ tự động gọi ngay `get_followup_request` xác nhận `verified: true` cho `request_id: 8ddfc682-c592-484c-b6c1-c00df680b922`, trích dẫn `P001-PLAN, P001-W2-V2, POLICY-V2`.
  - **USAGE:** Agent `{"calls": 4, "prompt_tokens": 13901, "completion_tokens": 490, "max_prompt": 4288, "attempts": 6}` (tự động xử lý 2 lần HTTP `429` với `retry-after: 22.0s` và `35.0s`); Embedding `1 call, 37 tokens, 6 cache_hits`.
  - **Tệp log:** `logs/demo_live_20261011T094919566238.jsonl`

### 2.2. Đánh giá Bộ chính Live E1 (`12 câu × 2 modes = 24 lượt`)

- [x] **Live Evaluation E1:**
  - **Lệnh:** `.\.venv\Scripts\python.exe run.py eval --backend live --runs 1`
  - **Tệp log:** `logs/eval_live_20261011T095314888391_572f75.jsonl` (signature: `2deac83356736eb51dbdd50a8507d4d61ed022da3cdcd820d17322bec223953c`)
  - **Tạo phẩm xuất ra:** `results/live/summary.json`, `results/live/per_query.csv`, `results/live/accuracy.png`

| Độ đo / Thống kê | Chế độ `dense` (12 câu) | Chế độ `hybrid` (12 câu) | Nhận xét kiểm tra tay trên Log |
|---|---|---|---|
| `functional_accuracy` | `0.6667` (`8/12`) | `0.6667` (`8/12`) | Agent trả lời đúng 100% nhãn và số liệu cả 12/12 câu; 4 câu `no_answer` bị Judge bắt lỗi claim từ chối (xem phân tích bên dưới) |
| `label_refusal_rate` | `1.0000` (`4/4`) | `1.0000` (`4/4`) | Cả 4 câu ngoài phạm vi (`Q11–Q14`) Agent đều trả về đúng `status = "no_answer"`, `facts = {}` |
| `correct_refusal_rate` | `0.0000` (`0/4`) | `0.0000` (`0/4`) | Judge (`openai/gpt-oss-20b`) trích xuất chính câu từ chối *"Corpus không có thông tin..."* thành 1 claim nên bị tính thiếu `citation_support` |
| `false_refusal_rate` | `0.0000` (`0/7`) | `0.0000` (`0/7`) | Không từ chối nhầm bất kỳ câu hỏi có đáp án nào |
| `source_completeness_rate` | `1.0000` (`8/8`) | `1.0000` (`8/8`) | Trích dẫn đầy đủ 100% tài liệu nguồn kỳ vọng ở mọi câu có đáp án |
| `citation_support_rate` | `0.5833` (`7/12`) | `0.5000` (`6/12`) | Chênh lệch ở `Q11–Q14` (refusal claim), `Q15` (Judge gán UUID `request_id` vào `source_ids`) và `hybrid:Q03` (Judge bắt bẻ ngày 08/10 vs 04/10) |
| `faithfulness` | `0.7500` (`12` mẫu) | `0.7917` (`12` mẫu) | Các câu có đáp án (`Q01–Q10, Q15, Q19`) đạt faithfulness `1.0` (trừ `hybrid:Q03` đạt `0.5`) |
| `grounded_accuracy` | `0.5833` (`7/12`) | `0.5000` (`6/12`) | Đạt `True` ở `Q01, Q03 (dense), Q05, Q06, Q09, Q10, Q19` |
| **Agent Usage (`calls` / `prompt` / `completion`)** | `24` / `73,096` / `3,104` | `22` / `65,031` / `2,800` | Chế độ `hybrid` tiết kiệm hơn `2` lần gọi LLM và `~8,065` prompt tokens (do `dense:Q05` cần thêm 1 vòng sửa lỗi thiếu citation `POLICY-V2`) |
| **Judge Usage (`calls` / `prompt` / `completion`)** | `12` / `19,792` / `2,881` | `12` / `18,827` / `2,681` | Đủ 24/24 lượt chấm Judge (`judge_errors = 0`) |
| **Embedding Usage (`calls` / `tokens` / `cache_hits`)** | `12` / `580` / `77` | `0` / `0` / `83` | Chế độ `hybrid` chạy sau nên tận dụng 100% cache Jina (`83` cache hits, `0` HTTP calls) |
