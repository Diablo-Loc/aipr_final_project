# Khai báo sử dụng AI trong đồ án

**Đề tài:** Trợ lý AI hỗ trợ quản lý và phân tích tiến độ dự án bằng RAG, Agent và MCP.

**Hình thức thực hiện:** Cá nhân (1 sinh viên).

**Trạng thái:** Đang thực hiện – cập nhật theo từng phase.

**Quy tắc ghi nhận:** chỉ ghi hỗ trợ đã diễn ra; mục tương lai là kế hoạch, không phải việc đã làm. Tóm tắt prompt không được coi là bản chép nguyên văn. Code gõ lại từ bản AI tạo vẫn cần khai báo nguồn AI; kết quả mock không phải thực nghiệm của repo này.

---

## 1. Công cụ và mục đích sử dụng AI

- **Công cụ đã khai báo trong nhật ký sinh viên:** ChatGPT, OpenAI Codex, Antigravity (Gemini). Lượt cập nhật tài liệu 08/10/2026 này do Codex hỗ trợ; không mặc định mọi công cụ tham gia mọi phase.
- **Mục đích:**
  - Hỗ trợ phân tích yêu cầu từ tài liệu môn học, lên kế hoạch triển khai và checklist từng bước.
  - Hỗ trợ giải thích kiến trúc hệ thống (RAG 2 chế độ, giao thức MCP stdio, vòng lặp Agent loop tự viết).
  - Hỗ trợ bản mẫu kỹ thuật, mã khung và cấu hình Windows; sinh viên dùng bản mẫu làm nguồn để tự học/gõ lại, cần giải thích và sửa được code.
  - Hỗ trợ rà soát cú pháp, type hints và gợi ý kịch bản kiểm thử (test fixtures).
  - Mô phỏng, phân tích kỹ tên đề tài và kết luận có thể triển khai không, có thể hoàn thành như mục đích cuối cùng không và có chuẩn theo yêu cầu không.
- **Nguyên mẫu kỹ thuật tham khảo:** Trước khi triển khai đồ án chính thức, sinh viên sử dụng ChatGPT và Codex để hỗ trợ xây dựng một nguyên mẫu kỹ thuật nhằm nghiên cứu kiến trúc RAG – Agent – MCP, tham khảo cách tổ chức mã nguồn, kiểm thử và xử lý lỗi. Nguyên mẫu được sử dụng làm tài liệu tham khảo; các kết quả thực nghiệm của đồ án chính thức được kiểm chứng riêng trên repository nộp.

---

## 2. Nhật ký sử dụng AI chi tiết theo từng Phase

### Phase 1: Khởi tạo Repo, Môi trường & Khung dự án

- **Công cụ:** ChatGPT, Codex, Antigravity.
- **Phạm vi hỗ trợ:**
  - Phân tích yêu cầu từ 2 tài liệu môn học (`01-De-tai-upload-for-student.pdf` và `02-Yeu-cau-Thuc-hien.pdf`) để xác định phạm vi 3 tầng bắt buộc (Tra cứu – Biến đổi – Hành động).
  - Hỗ trợ xây dựng cấu trúc thư mục dự án, kịch bản khởi tạo môi trường Python 3.11 và tài liệu ban đầu.

- **Tóm tắt các yêu cầu chính đã sử dụng (không phải transcript nguyên văn):**
  1. *"Đọc các tài liệu yêu cầu đồ án môn học AIPR (01-De-tai-upload-for-student.pdf và 02-Yeu-cau-Thuc-hien.pdf), phân tích các tiêu chí bắt buộc (3 tầng tra cứu - biến đổi - hành động, RAG dense/hybrid, MCP stdio, Agent loop tự viết, SQLite verify) và hướng dẫn triển khai từng bước ngắn gọn cho tôi."*
  2. *"Hỗ trợ thiết kế cấu trúc dự án và tạo kịch bản run.py cho môi trường Windows để quản lý venv Python 3.11, cài đặt phụ thuộc từ requirements.lock.txt, điều phối các lệnh demo/eval/test mà không đọc hoặc làm lộ file .env."*
  3. *"Tạo launcher Makefile và make.cmd tương thích trên Windows CMD và PowerShell để hỗ trợ chạy đồ án bằng lệnh chuẩn (make setup, make demo, make eval)."*

- **Mã nguồn hoặc tài liệu có AI hỗ trợ:**
  - File `run.py`, `Makefile`, `make.cmd`, `config.json`: Tái sử dụng và điều chỉnh từ nguyên mẫu kỹ thuật sau khi đối chiếu yêu cầu không để lộ `.env` và tương thích tốt trên môi trường Windows.
  - File `.gitignore`: AI đề xuất danh sách loại trừ nhạy cảm (`.venv/`, `.env*`, `credentials*`, `state/`, `cache/`, `tmp/`).
  - File `README.md`, `ai-usage.md`: AI hỗ trợ soạn thảo khung tài liệu ban đầu; sinh viên trực tiếp rà soát và hiệu chỉnh.

- **Kiểm chứng được sinh viên ghi trong nhật ký trước lượt bổ sung tài liệu này:** các thông tin dưới đây được giữ lại theo ghi nhận của sinh viên, Codex không chạy lại hoặc xác minh Git history trong lượt này. Khi nộp, bổ sung lệnh/output hoặc commit hash thật để đối chiếu.
  - Khởi tạo Git repo cục bộ trên nhánh `main` (`git init -b main`).
  - Chạy lệnh `py -3.11 run.py setup` tạo thành công `.venv` và cài 45 packages theo `requirements.lock.txt`.
  - Xác nhận phiên bản: `.\.venv\Scripts\python.exe --version` trả về `Python 3.11.0`.
  - Xác nhận tính toàn vẹn: `.\.venv\Scripts\python.exe -m pip check` trả về `No broken requirements found`.
  - Xác nhận ignore: `git check-ignore` xác nhận các path mẫu `.env`, `.venv`, `cache`, `state`, `tmp` khớp quy tắc ignore. Điều này không tự chứng minh chưa từng track hoặc đưa bí mật vào history; cần kiểm tra tên tracked/history trước commit/đóng gói.
  - Thực hiện commit Git đầu tiên thành công: `chore: initialize personal AIPR project and Python 3.11 environment`.

- **Trạng thái Phase 1:** Sinh viên đã ghi hoàn thành setup/commit; lượt cập nhật tài liệu này không chạy lại. Source nghiệp vụ và kiểm chứng các phase tiếp theo vẫn chưa hoàn tất.

### Bổ sung tài liệu local ngày 08/10/2026

- **Công cụ:** OpenAI Codex.
- **Yêu cầu thực tế:** thêm bộ tài liệu tối thiểu cho AI tiếp tục đúng thiết kế trên máy khác; cập nhật README và ai-usage. Chỉ local, không copy PDF/sổ tay, không commit/push và không API live.
- **File có AI soạn/chỉnh:** AGENTS.md, docs/ARCHITECTURE.md, docs/SETUP.md, README.md và mục nhật ký này. Sổ tay bên ngoài repo được cập nhật để nhận diện bộ tài liệu mới và đóng gói AGENTS.md khi sinh viên thực hiện về sau.
- **Nguồn đối chiếu:** file công khai của repo thật, code/tài liệu kiến trúc trong mock và sổ tay đã chốt. Không thay đổi source nghiệp vụ, config/lock, mock, Git history hoặc số liệu.
- **Nội dung:** quyền API đang khóa; ranh giới module/tool; setup Windows 3.11; trạng thái hiện có khác thiết kế đích; điều kiện offline/live và bằng chứng nộp.
- **Kiểm chứng tài liệu:** kiểm tra UTF-8, liên kết nội bộ, số cột bảng và parse cú pháp các khối PowerShell, không thực thi lệnh trong khối. Không coi kiểm tra Markdown là pass ứng dụng. Sinh viên cần tự đọc, hiểu và cập nhật theo code thực tế.
- **Kiểm chứng ứng dụng/API trong lượt này:** không chạy setup/tests/demo/eval/live; không đọc .env hoặc API key. Chưa có số liệu LLM/embedding/judge thật của repo này để điền.

### Phase 2: Dữ liệu, Dataclass và Validation

- **Công cụ:** Antigravity (Gemini).
- **Phạm vi hỗ trợ:**
  - Giải thích yêu cầu kỹ thuật: typing với `dataclass`/`TypedDict` (W1), cơ chế single source of truth của `Corpus` cho RAG và tính toán số học, cơ chế phả hệ tài liệu `supersedes` xử lý phiên bản thay thế.
  - Cung cấp mã nguồn tham khảo cho `src/models.py` và `src/data.py` dựa trên nguyên mẫu kỹ thuật.
  - Review mã nguồn do sinh viên tự tay gõ, chỉ ra chính xác các lỗi cú pháp và lỗi gõ phím (lỗi `type[origin]` thay vì `types[origin]` ở dòng 73 của `src/models.py` dẫn đến `AssertionError`, định dạng ngày thiếu số 0, lỗi typo ở `completion_tokens` và `Answer`) mà không can thiệp sửa trực tiếp vào file của sinh viên để sinh viên tự sửa.
- **Các prompt thực tế sinh viên đã gửi:**
  1. *"từ các file cấu hình trong project, bạn hãy đọc và giúp tôi gợi ý code phần phase 2, có thể giải thích kỹ càng."*
  2. *"tôi viết xong rồi nhờ bạn check lại, có gì sai sót thì chỉ ra để tôi sửa hoặc tối ưu nó"*
- **Mã nguồn hoặc tài liệu có AI hỗ trợ:**
  - `src/models.py`: AI gợi ý định nghĩa dataclass (`Metadata`, `Document`, `Chunk`, `SearchArgs`, `AnalysisArgs`, `ToolSpec`, `tool_schema`, `Source`, `Usage`, `Action`, `Answer`).
  - `src/data.py`: AI gợi ý cấu trúc class `Corpus` (các hàm `__init__`, `eligible`, `get`, `source`, `analyze`).
  - `data/corpus.jsonl` và `data/provenance.md`: Tái sử dụng tập 13 tài liệu tổng hợp và tài liệu nguồn gốc từ nguyên mẫu kỹ thuật.
- **Kiểm chứng thực tế của sinh viên:**
  - Sinh viên tự tay gõ mã nguồn vào 2 file `src/models.py` và `src/data.py`.
  - Nhận diện và tự chỉnh sửa các lỗi typo theo giải thích của AI (sửa `types[origin]`, ngày chuẩn `2026-10-08`, sửa tên biến).
  - Chạy smoke test kiểm tra nạp dữ liệu, lọc phiên bản và schema tại terminal:
    Lệnh: nạp Corpus, kiểm tra đủ 13 docs, eligible P001 tại 2026-10-08 chọn đúng P001-PLAN, P001-W2-V2, POLICY-V2; loại trừ V1 và P002; get P001-W2-V1 trả đúng 50; tool_schema sinh đúng type 'string'.
    Kết quả thực tế trên máy sinh viên: `Phase 2: PASS`.
- **Trạng thái Phase 2:** **ĐÃ HOÀN THÀNH (PASSED)**.

### Phase 3: Phân tích tiến độ và SQLite

- **Công cụ:** Antigravity (Gemini).
- **Phạm vi hỗ trợ:**
  - Giải thích yêu cầu Tầng 2 (Biến đổi): công thức tính tiến độ có trọng số giờ công ước tính ban đầu (`estimated_effort_hours`), độ chậm theo điểm phần trăm (`behind_pp`), phát hiện task quá hạn (`overdue`), và cơ chế từ chối khi thiếu dữ liệu (`insufficient_data`).
  - Giải thích chi tiết sự thay đổi chính sách cảnh báo ngày 04/10 (`POLICY-V1` 20 pp thay bằng `POLICY-V2` 15 pp) để chứng minh khả năng chọn đúng phiên bản chính sách có hiệu lực tại ngày được hỏi (temporal validity).
  - Hướng dẫn thiết kế class `RequestStore` trong `src/store.py` để lưu trữ trạng thái vào SQLite: cơ chế Transaction/commit tự động qua context manager, parameterized query `?` chống SQL Injection, và cơ chế Idempotency qua `operation_key` chống tạo trùng lặp ticket.
- **Các prompt thực tế sinh viên đã gửi:**
  1. *"bắt đầu phase 3 nào"*
  2. *"Phase 3: PASS ok rooif. Nói được công thức và tại sao 04/10 policy đổi quyết định. Hiểu no_answer khác insufficient_data; không ghi khi dữ liệu thiếu ở tầng nghiệp vụ. Nói được transaction/commit, SQL parameters và operation_key. giải thích kỹ này chưa."*
- **Mã nguồn hoặc tài liệu có AI hỗ trợ:**
  - `src/store.py`: AI cung cấp mã nguồn tham khảo cho class `RequestStore` (các hàm `__init__`, `create`, `get`).
  - Kịch bản smoke test Phase 3 kiểm tra liên hoàn phép tính `Corpus.analyze` và cơ chế ghi/đọc của `RequestStore`.
- **Kiểm chứng thực tế của sinh viên:**
  - Sinh viên tự tay gõ mã nguồn vào file `src/store.py`.
  - Chạy smoke test Phase 3 tại terminal:
    Lệnh: chạy tính toán P001 ngày 08/10 xác nhận planned 70.0%, actual 48.0%, behind 22.0 pp; T02 quá hạn 1 ngày; P003 trả về insufficient_data; ghi request vào SQLite `tmp/test_phase3.db` và đọc lại xác minh khớp `request_id`.
    Kết quả thực tế trên máy sinh viên: `Phase 3: PASS`.
- **Trạng thái Phase 3:** **ĐÃ HOÀN THÀNH (PASSED)**.

### Phase 4: Dense và Hybrid RAG

- **Công cụ:** Antigravity (Gemini).
- **Phạm vi hỗ trợ:**
  - Hướng dẫn cấu trúc tái sử dụng thuật toán tuần 4 (`week4/ex2_1_hybrid_search.py`) cho `src/hybrid.py`: chuẩn hóa Min-Max (`normalise_scores`), lập chỉ mục `BM25Okapi` (`build_bm25_index`) và hợp nhất điểm số weighted fusion (`hybrid_search` theo tỷ lệ 0.5 BM25 + 0.5 Cosine).
  - Hướng dẫn thiết kế `src/api.py`: cơ chế `Trace` ghi log JSONL và tự động che giấu bí mật (redact API keys), wrapper HTTP `post_json` với retry 3 lần / timeout 30s / xử lý HTTP 429 rate limit, class `Embedder` có cache file JSON và chế độ offline deterministic hash, class `LiveModel` gọi Groq Chat Completion và log USAGE.
  - Hướng dẫn thiết kế `src/rag.py`: hàm tính độ tương đồng `cosine`, chiến lược chunking theo dòng (line-based) không cắt ngang row task và kế thừa metadata gốc, class `Retriever` hỗ trợ linh hoạt cả 2 chế độ `dense` và `hybrid`.
  - Hỗ trợ review toàn bộ mã nguồn do sinh viên tự tay gõ trong 3 file
- **Các prompt thực tế sinh viên đã gửi:**
  1. *"tiếp tục nào"* (bắt đầu Phase 4).
  2. *"code xong hết rồi, giờ bạn giúp check toàn bộ code vừa thêm, xem lỗi ở đâu không"*
  3. *"Phase 4: PASS giúp tôi update luôn ai-usage.md"*
- **Mã nguồn hoặc tài liệu có AI hỗ trợ:**
  - `src/hybrid.py`: AI gợi ý cấu trúc tái sử dụng từ bài tuần 4 (`vendor/week4/ex2_1_hybrid_search.original.py`).
  - `src/api.py`: AI gợi ý mã nguồn tham khảo từ nguyên mẫu kỹ thuật cho các class `Trace`, `Embedder`, `LiveModel` và hàm `post_json`.
  - `src/rag.py`: AI gợi ý mã nguồn tham khảo cho hàm `chunk_document` và class `Retriever`.
- **Kiểm chứng thực tế của sinh viên:**
  - Sinh viên tự tay gõ mã nguồn vào 3 file `src/hybrid.py`, `src/api.py`, `src/rag.py`.
  - Tự nhận diện và sửa các lỗi thụt lề, lỗi gõ phím theo giải thích của AI.
  - Chạy smoke test Phase 4 tại terminal:
    Lệnh: khởi tạo `Retriever(corpus, 'offline')`, thực hiện tra cứu 'tiến độ P001' với cả 2 chế độ `dense` và `hybrid` với `top_k=2`, kiểm tra trả về đúng 2 chunks, đúng mode và đầy đủ metadata `doc_id`.
    Kết quả thực tế trên máy sinh viên: `Phase 4: PASS`.
- **Trạng thái Phase 4:** **ĐÃ HOÀN THÀNH (PASSED)**.

### Phase 5: MCP Server và MCP Client

- **Công cụ:** Antigravity (Gemini).
- **Phạm vi hỗ trợ:**
  - Hướng dẫn kiến trúc giao tiếp `stdio` JSON-RPC giữa hai tiến trình độc lập, giữ sạch `stdout` và chuyển hướng log lỗi sang `.stderr.log`.
  - Hướng dẫn thiết kế `src/mcp_server.py`: class `Service` quản lý 5 tools (`search_documents`, `get_document`, `analyze_progress`, `create_followup_request`, `get_followup_request`), cơ chế chặn an toàn 3 lớp trước khi ghi SQLite (`allow_write`, bắt buộc gọi `analyze_progress` trước, `risk == True`), trả về contract `verification` và bắt mọi exception trả về chuỗi `"Error: ..."`.
  - Hướng dẫn thiết kế `src/mcp_client.py`: hàm `connect` tự mở subprocess server, gọi `session.list_tools()` để discover động danh sách công cụ và schema mà không hard-code.
  - Hướng dẫn thiết kế `scripts/second_client.py` (điểm cộng Interop): host Python thứ hai độc lập kết nối tới MCP server.
  - Hỗ trợ review mã nguồn do sinh viên tự tay gõ trong 3 file.
- **Các prompt thực tế sinh viên đã gửi:**
  1. *"ok tiếp tục phase 5"*
  2. *"cả 2 lệnh đều pass hết rồi, check xem có lỗi gì không"*
  3. *"đã fix xong, bạn update ai-usage.md"*
- **Mã nguồn hoặc tài liệu có AI hỗ trợ:**
  - `src/mcp_server.py`: AI gợi ý mã nguồn tham khảo từ nguyên mẫu kỹ thuật cho class `Service` và `build_server`.
  - `src/mcp_client.py`: AI gợi ý mã nguồn tham khảo cho class `Tools` và context manager `connect`.
  - `scripts/second_client.py`: AI gợi ý mã nguồn tham khảo cho host thứ hai kiểm thử tính tương thích liên thông (interoperability).
- **Kiểm chứng thực tế của sinh viên:**
  - Sinh viên tự tay gõ mã nguồn vào 3 file `src/mcp_server.py`, `src/mcp_client.py` và `scripts/second_client.py` (kèm chú thích giải thích trực tiếp trong code).
  - Tự chỉnh sửa các lỗi typo (`"Error:"`, `.stderr.log`, `demo.sqlite`, mô tả tool).
  - Chạy smoke test Phase 5 và Interop test tại terminal:
    - Lệnh 1: kiểm tra discover đúng 5 tools, gọi tool không tồn tại trả về `'Error:'`, gọi ghi trước khi analyze trả về `'Error:'`, gọi analyze ra `behind_pp == 22`, gọi ghi và gọi tool đọc verify khớp hoàn toàn bản ghi: `Phase 5: PASS`.
    - Lệnh 2 (`.\.venv\Scripts\python.exe run.py interop`): host thứ hai discover 5 tools và xác nhận `Interop write/read verification: PASS`.
- **Trạng thái Phase 5:** **ĐÃ HOÀN THÀNH (PASSED)**.

### Phase 6: Vòng lặp Agent tự viết, Runtime, Offline Model & CLI

- **Công cụ:** Antigravity (Gemini).
- **Phạm vi hỗ trợ:**
  - Giải thích cơ chế vòng lặp Agent tự viết hoàn toàn bằng Python (`src/agent.py`) không dùng LangChain hay AgentExecutor ẩn: khởi tạo ngữ cảnh `RAG_CONTEXT` ban đầu (`retrieval_bootstrap`), vòng lặp `for turn in range(max_steps)` với `MAX_STEPS = 8`, phân biệt lỗi JSON/schema thông thường với `EvidenceError` (bắt buộc gọi thêm tool thật khi thiếu bằng chứng số liệu hoặc trích dẫn ngoài tập tài liệu đã quan sát), kiểm tra ngân sách bước trước khi ghi (`tool_steps + 2 <= max_steps`) để luôn dành chỗ cho bước đọc lại xác minh (`verify`).
  - Giải thích cơ chế `src/runtime.py` nạp biến môi trường `.env` an toàn cho tiến trình cha khi chạy live mà không in giá trị khóa ra màn hình, và `src/cli.py` điều phối 4 kịch bản demo kèm ghi vết `Trace` JSONL.
  - Hỗ trợ review mã nguồn do sinh viên tự tay gõ trong `src/runtime.py`, `src/agent.py`, `src/cli.py` và chỉ ra các lỗi gõ phím (`removeperfix` -> `removeprefix`, `request-id` -> `request_id`, `"Error "` -> `"Error:"`, `action.aguments` -> `action.arguments`, `startwith` -> `startswith`, thiếu biến `args.query` trong `cli.py`) để sinh viên tự sửa trực tiếp.
- **Các prompt thực tế sinh viên đã gửi:**
  1. *"ok tiếp tục phase 6"*
  2. *"bạn check code toàn bộ tôi vừa thêm đi"*
  3. *"ok chưa, file src/offline_model.py copy nên có gì note lại."*
- **Mã nguồn hoặc tài liệu có AI hỗ trợ (phân biệt rõ phần tự gõ và phần tái sử dụng):**
  - `src/runtime.py`, `src/agent.py`, `src/cli.py`: AI cung cấp mã tham khảo từ nguyên mẫu kỹ thuật; **sinh viên tự tay gõ toàn bộ mã nguồn** và tự sửa các lỗi cú pháp/typo sau khi AI review.
  - `src/offline_model.py` và `templates/agent.txt`, `templates/judge.txt`: **Sao chép (tái sử dụng nguyên bản) từ nguyên mẫu kỹ thuật**. Trong đó `src/offline_model.py` đóng vai trò bộ điều khiển giả lập tất định (deterministic offline test driver) để kiểm thử luồng Agent – MCP – SQLite khi không gọi API thật, còn `templates/*.txt` là mẫu system prompt cho Agent và Judge.
- **Kiểm chứng thực tế của sinh viên:**
  - Chạy kiểm thử HTTP 401 stub bằng `unittest.mock.patch('httpx.Client.post')`: xác nhận mã lỗi 401 dừng ngay lập tức không retry (`send.call_count == 1`), kết quả: `HTTP stub: PASS`.
  - Chạy lệnh `.\.venv\Scripts\python.exe run.py demo --backend offline`:
    - Kịch bản D1 (*"Ai phụ trách T02 của P001?"*): trả về `[offline / ok]` với `{'owner': 'Minh'}`, nguồn `P001-PLAN`.
    - Kịch bản D2 (*"P001 ngày 08/10/2026 chậm bao nhiêu so với kế hoạch?"*): trả về `[offline / ok]` với `planned_progress: 70.0`, `actual_progress: 48.0`, `behind_pp: 22.0`, `risk: True`, nguồn `P001-PLAN, P001-W2-V2, POLICY-V2`.
    - Kịch bản D3 (*"Ngân sách đã chi của P001 là bao nhiêu?"*): trả về `[offline / no_answer]` với `{}`.
    - Kịch bản D4 (*"Nếu P001 vượt ngưỡng ngày 08/10/2026, hãy tạo yêu cầu xử lý và xác nhận đã lưu."*): trả về `[offline / action_verified]` kèm `request_id` đã đối chiếu khớp trong SQLite và xuất file trace `logs/demo_offline_20261010T165849710869.jsonl`.
- **Trạng thái Phase 6:** **ĐÃ HOÀN THÀNH (PASSED)**.

---

### Phase 7–10: Kế hoạch cập nhật tiếp theo

| Phase | Thành phần dự kiến | Tóm tắt prompt chính dự kiến | Nội dung AI hỗ trợ | Trách nhiệm của sinh viên | Trạng thái |
|---|---|---|---|---|---|
| **Phase 2** | models.py, data.py | Gợi ý schema/review code tay | Hướng dẫn cấu trúc & chỉ lỗi typo | Tự tay gõ, sửa lỗi và pass smoke test | ĐÃ HOÀN THÀNH (PASSED) |
| **Phase 3** | store.py, analyze | Giải thích phép tính/SQLite | Hướng dẫn RequestStore, công thức & SQLite | Tự gõ code, kiểm tra tính toán và lưu SQLite | ĐÃ HOÀN THÀNH (PASSED) |
| **Phase 4** | api.py, hybrid.py, rag.py | Đối chiếu tuần 4 / review code tay | Hướng dẫn RAG, BM25, API & review lỗi | Tự tay gõ 3 file, sửa lỗi và pass smoke test | ĐÃ HOÀN THÀNH (PASSED) |
| **Phase 5** | MCP server/client, interop | Hướng dẫn stdio/discovery/review | Hướng dẫn 5 tools, client động, host thứ 2 & review | Tự tay gõ 3 file, sửa typo và pass cả 2 lệnh | ĐÃ HOÀN THÀNH (PASSED) |
| **Phase 6** | agent/runtime/CLI, offline_model | Giải thích loop/recovery & review code | Review code tay 3 file; ghi nhận copy offline_model & templates | Tự gõ runtime/agent/cli, sửa lỗi và pass demo offline | ĐÃ HOÀN THÀNH (PASSED) |
| **Phase 7** | Tests/evaluator | Review refusal/citation/metrics | Đề xuất ca lỗi và kiểm tra evaluator | Tự chạy, ghi số ca/kết quả thực | Đang bắt đầu |
| **Phase 8** | Live eval/logs | Lập ngân sách live | Chỉ hỗ trợ live sau cho phép rõ ràng | Tự cấp key, kiểm chứng và phân tích log | Chưa thực hiện; API khóa |
| **Phase 9** | Report/README | Review Word 8–9 trang | Kiểm tra nội dung theo số liệu đã có | Viết failure/hạn chế/đóng góp thật | Chưa thực hiện |
| **Phase 10** | Cold start/đóng gói/bảo vệ | Luyện vấn đáp/sửa code | Đặt câu hỏi và kiểm tra hồ sơ theo quyền | Tự giải thích, sửa code, commit và nộp | Chưa thực hiện |

---

## 3. Trách nhiệm & Cam kết liêm chính học thuật

- **Trách nhiệm mã nguồn:** Sinh viên chịu trách nhiệm 100% về mọi dòng code trong sản phẩm nộp, hiểu rõ từng module và sẵn sàng trả lời vấn đáp kỹ thuật cũng như sửa code trực tiếp tại chỗ theo yêu cầu của Giảng viên.
- **Tính trung thực dữ liệu:** Toàn bộ kết quả thực nghiệm, file trace JSONL và bảng đo `USAGE` trong báo cáo sẽ được sinh ra từ các lần chạy thật trên repo cá nhân, không lấy số đo giả lập hay tự tạo số liệu khống.
- **Bảo mật thông tin:** Tuyệt đối không lưu trữ API key trên Git hay tài liệu nộp.

- **Cách cập nhật nhật ký:** với mỗi mốc thật, ghi ngày, công cụ, yêu cầu tóm tắt, file/dòng hoặc commit liên quan, phần AI hỗ trợ, phần sinh viên tự sửa, lệnh kiểm chứng và giới hạn. Không điền trước pass/commit hash/số liệu API; không gửi key hoặc diff chứa bí mật vào chat.
