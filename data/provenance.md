# Nguồn dữ liệu và mã tái sử dụng

## 1. Nguồn gốc dữ liệu Corpus
- Corpus là tập dữ liệu giả lập/tổng hợp do sinh viên xây dựng (với sự hỗ trợ sinh dữ liệu mẫu từ AI), phục vụ bài toán quản lý và phân tích tiến độ dự án. Đây không phải là dữ liệu của doanh nghiệp thật hay sao chép từ nhóm khác.
- Tập dữ liệu gồm 13 tài liệu ngắn:
  - 2 tài liệu chính sách cảnh báo (`POLICY-V1`, `POLICY-V2` thay thế bản cũ).
  - 1 tài liệu kế hoạch ban đầu (`P001-PLAN`).
  - 2 phiên bản báo cáo tiến độ cùng mốc ngày (`P001-W2-V1` và bản đính chính `P001-W2-V2`).
  - 1 báo cáo mốc lịch sử (`P001-W1`).
  - 1 biên bản cuộc họp ghi nhận sự cố blocker (`P001-MEETING`).
  - 2 dự án thiếu dữ liệu có chủ đích để kiểm thử từ chối (`P003`, `P004`).
  - Dự án mẫu đối chiếu (`P002`).
- Mỗi tài liệu có đầy đủ metadata bắt buộc: `doc_id`, `title`, `date`, `version`, `owner`, `project_id`, `kind`. Khối records có cấu trúc ở cuối nội dung khớp 100% với text mô tả.

## 2. Mã nguồn tái sử dụng từ bài học trên lớp
- **Hybrid Search (Tuần 4):**
  - Tái sử dụng các hàm `normalise_scores`, `build_bm25_index` và trọng số kết hợp (fusion) từ bài tập `week4/ex2_1_hybrid_search.py`.
  - Điều chỉnh tích hợp: nhận vector cosine scores từ pipeline thay vì gọi API trực tiếp trong hàm; chuẩn hóa cấu trúc chunk (`chunk.text`, `chunk.metadata`); bổ sung kiểm tra an toàn danh sách rỗng.
- **Kiến thức bài học khác:**
  - Dataclass và Type hints: bài học Tuần 1 và Tuần 3.
  - Vòng lặp Agent: bài học Tuần 6.
  - Giao tiếp MCP client/server qua stdio: bài học Tuần 7.
  - Định dạng đo lường chi phí `USAGE`: tham khảo mẫu bài học Tuần 8 (`calls`, `prompt_tokens`, `completion_tokens`, `max_prompt`).

## 3. Chiến lược phân đoạn (Chunking)
- Phân đoạn văn bản theo ranh giới đoạn/dòng logic (khoảng 800–1000 ký tự), tuyệt đối không cắt ngang giữa các dòng dữ liệu công việc (task rows) để bảo toàn tính toàn vẹn của số liệu.
- Mọi chunk đều kế thừa đầy đủ metadata của tài liệu gốc (`doc_id`, `version`, `date`, `owner`, `project_id`).

## 4. Tài liệu tham khảo kỹ thuật
- Model Context Protocol (MCP) Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Groq Tool Calling API: https://console.groq.com/docs/tool-use/overview
- Jina Embeddings v3: https://jina.ai/embeddings/
