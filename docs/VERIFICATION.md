# Hồ sơ Kiểm chứng Thực tế (Verification Log)

Tài liệu này ghi nhận các lệnh kiểm chứng đã chạy thật trên repository cá nhân (`do_an_aipr`), kèm ngày giờ, mã thoát, số ca kiểm thử và đường dẫn file log thực tế.

---

## 1. Kiểm chứng Offline & Unit Tests (Phase 1–7 — Đã hoàn thành)

| Hạng mục | Lệnh thực thi | Kết quả thực tế | Tệp bằng chứng / Ghi chú |
|---|---|---|---|
| **Môi trường Python 3.11** | `py -3.11 run.py setup` & `.\.venv\Scripts\python.exe -m pip check` | Python 3.11.0, No broken requirements found; audit 11/10 xác nhận 44 distributions khóa và 0 lệch lock, 46 installed distributions | requirements.lock.txt; số packages cài ở setup không đồng nhất với số dòng lock |
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
| `functional_accuracy` | `0.6667` (`8/12`) | `0.6667` (`8/12`) | Status/expected_facts khớp 12/12 mỗi mode; đây không phải functional/grounded PASS 100%. Functional score còn phụ thuộc refusal_valid của judge |
| `label_refusal_rate` | `1.0000` (`4/4`) | `1.0000` (`4/4`) | Cả 4 câu ngoài phạm vi (`Q11–Q14`) Agent đều trả về đúng `status = "no_answer"`, `facts = {}` |
| `correct_refusal_rate` | `0.0000` (`0/4`) | `0.0000` (`0/4`) | Số raw auto judge. Q11/Q12/Q14 bị phân loại câu từ chối thành claim cần citation; Q13 có chi tiết factual Minh cần rà riêng, không mặc định pure refusal |
| `false_refusal_rate` | `0.0000` (`0/7`) | `0.0000` (`0/7`) | Không từ chối nhầm bất kỳ câu hỏi có đáp án nào |
| `source_completeness_rate` | `1.0000` (`7/7`) | `1.0000` (`7/7`) | Summary loại cả no_answer và insufficient_data khỏi mẫu số. Q19 có expected_sources đủ ở per-query nhưng không nằm trong mẫu số này |
| `citation_support_rate` | `0.5833` (`7/12`) | `0.5000` (`6/12`) | Sai lệch refusal; Q15: UUID không phải doc_id; hybrid:Q03: judge nhầm ngày bắt đầu hiệu lực với ngày đang có hiệu lực, trong khi dense có cùng answer được chấm đúng |
| `faithfulness` | `0.7500` (`12` mẫu) | `0.7917` (`12` mẫu) | Trung bình per-query của các claim judge trích, kể cả claim refusal bị phân loại sai. Không suy ra đây là tỉ lệ thông tin dự án bị bịa |
| `grounded_accuracy` | `0.5833` (`7/12`) | `0.5000` (`6/12`) | Đạt `True` ở `Q01, Q03 (dense), Q05, Q06, Q09, Q10, Q19` |
| **Agent Usage (`calls` / `prompt` / `completion`)** | `24` / `73,096` / `3,104` | `22` / `65,031` / `2,800` | Hybrid ít hơn 2 calls và 8.065 prompt tokens trong đúng E1; dense:Q05 có recovery. Chưa đủ run để khái quát hybrid luôn rẻ hơn |
| **Judge Usage (`calls` / `prompt` / `completion`)** | `12` / `19,792` / `2,881` | `12` / `18,827` / `2,681` | Đủ 24/24 lượt chấm Judge (`judge_errors = 0`) |
| **Embedding Usage (`calls` / `tokens` / `cache_hits`)** | `12` / `580` / `77` | `0` / `0` / `83` | Chế độ `hybrid` chạy sau nên tận dụng 100% cache Jina (`83` cache hits, `0` HTTP calls) |

### 2.3. Diễn giải giới hạn đánh giá

`judge_errors = 0` chỉ nghĩa response parse được, không chứng minh judge đúng. Giữ nguyên E1/CSV/summary và ghi đây là raw auto-judge metrics. Các ca bất đồng có phân tích trong [audit Phase 8](AUDIT_PHASE8_20261011.md); report cần phân biệt bảng rà tay với auto judge, không tự đổi fail thành pass trong log.

Failure thật để phân tích: dense:Q05 sinh answer thiếu POLICY-V2; host trả EvidenceError "Cite the source documents used by analyze_progress", agent sửa và final ok có đủ ba citation. Q15 có write/read equality đúng, dù judge đưa request UUID vào source_ids nên grounded false. Hybrid:Q03 không phải bằng chứng policy sai; cần đọc lại POLICY-V2 cùng answer.

## 3. Audit độc lập ngày 11/10/2026

- Chạy lại `.venv/Scripts/python.exe -m unittest discover -s tests -v`: 48/48 OK, 2,126 giây, exit 0; mạng ngoài và file key thật bị chặn bằng guard riêng.
- Host thứ hai discover năm tool, analyze → write → read equality PASS trên DB tạm riêng; không ghi đè state live.
- Tái dựng CSV/summary từ E1 và log offline khớp kết quả gốc; signature E1 khớp source hiện tại. Không gọi API mới, không đọc .env thật, không commit/push.
- Git có tám commit theo phase, HEAD e0c3295 ở thời điểm audit. Signature không bao phủ toàn bộ repo; ba smoke chỉ có config, không có signature riêng.
- Cold start trên môi trường sạch/máy GV chưa thực hiện. Sửa tài liệu không làm số đo E1 đổi; nếu sửa source/prompt/evaluator phải ghi revision và kiểm chứng phù hợp riêng.

## 4. Trạng thái Phase 9

 File nộp cuối là `report.docx` tại root do_an_aipr. Theo [checklist Phase 9](PHASE9_CHECKLIST.md), chỉ đánh dấu hoàn thành và commit sau khi bản cuối có đủ chín mục.
