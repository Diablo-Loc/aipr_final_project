# Hồ sơ Kiểm chứng Thực tế (Verification Log)

Tài liệu này ghi nhận các lệnh kiểm chứng đã chạy thật trên repository cá nhân (`do_an_aipr`), kèm ngày giờ, mã thoát, số ca kiểm thử và đường dẫn file log thực tế.

---

## 1. Kiểm chứng Offline & Unit Tests (Đã hoàn thành)

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

## 2. Kiểm chứng Live API (Phase 8 — Đang chờ thực hiện)

> **Trạng thái hiện tại:** Chưa chạy Live API. Các mục dưới đây chỉ được cập nhật sau khi chạy thật với API key hợp lệ trong Phase 8.

- [ ] **Smoke Live S1 (Lookup):** `.\.venv\Scripts\python.exe run.py demo --backend live --mode hybrid --query "Ai phụ trách T02 của P001?"` — *Pending*
- [ ] **Smoke Live S2 (Version comparison):** `.\.venv\Scripts\python.exe run.py demo --backend live --mode hybrid --query "Báo cáo P001 ngày 08/10 phiên bản v1 và v2 khác gì? Dùng bản nào?"` — *Pending*
- [ ] **Smoke Live S3 (Write & Verify):** `.\.venv\Scripts\python.exe run.py demo --backend live --mode hybrid --allow-write --query "Nếu P001 vượt ngưỡng ngày 08/10/2026, hãy tạo yêu cầu xử lý và xác nhận đã lưu."` — *Pending*
- [ ] **Live Evaluation E1 (12 câu × 2 modes = 24 lượt):** `.\.venv\Scripts\python.exe run.py eval --backend live --runs 1` — *Pending*

