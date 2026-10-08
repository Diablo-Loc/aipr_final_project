# Setup và tiếp tục trên máy Windows khác

Lệnh trong tài liệu là hướng dẫn, chưa được chạy trong lần bổ sung tài liệu này. Xem README để biết module nào đã có; không chạy demo/eval khi source còn thiếu.

## Điều kiện

- Windows, PowerShell/CMD, Git và Python 3.11.x. Không mặc định dùng được lock với Python 3.12 trở lên.
- Có repo/source cá nhân của sinh viên, không lấy .git/history của mock. Không cần giữ nguyên đường dẫn ổ D trên máy mới.
- Mạng tải dependency cần cho setup nếu máy chưa có; setup không gọi Groq/Jina/LLM. AI không tự cài khi tác vụ chỉ yêu cầu sửa tài liệu.
- Không chuyển .venv/cache/state/tmp hoặc file key từ máy cũ. Thiết lập môi trường mới theo lock.

## Setup an toàn

Mở PowerShell tại root repo (có run.py), rồi chủ động chạy:

```powershell
git --version
py -3.11 --version
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
# INSTALL: tải packages, không gọi API mô hình.
py -3.11 run.py setup
if ($LASTEXITCODE -ne 0) { throw 'Setup chưa đạt; dừng ở đây.' }
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check chưa đạt.' }
```

Kỳ vọng Python 3.11.x và pip không báo dependency bị hỏng. Nếu không có py nhưng python đã đúng 3.11.x, thay py -3.11 bằng python. Nếu venv cũ sai phiên bản, dừng để sinh viên chọn cách xử lý; không tự xóa thư mục. Không cần activate hoặc đổi ExecutionPolicy.

## Offline sau khi viết đủ module

Chỉ chạy test khi có ca test thực sự; báo Ran 0 tests không phải bằng chứng đạt. CLI cần agent/MCP/RAG và prompts; eval cần scripts/eval.py cùng testset. Hiện các phần này chưa được viết tại snapshot tài liệu.

```powershell
# OFFLINE: chỉ sau khi các module/test của phase tương ứng đã đủ.
.\.venv\Scripts\python.exe run.py test
if ($LASTEXITCODE -ne 0) { throw 'Tests chưa đạt.' }
.\.venv\Scripts\python.exe run.py demo --backend offline
if ($LASTEXITCODE -ne 0) { throw 'Offline demo chưa đạt.' }
.\.venv\Scripts\python.exe run.py eval --backend offline --runs 1
if ($LASTEXITCODE -ne 0) { throw 'Offline evaluation chưa đạt.' }
```

Ghi lệnh, ngày, exit code, số ca thật và đường dẫn log sau khi chạy. Không điền trước số pass của mock. Stub/offline không chứng minh chất lượng embedding/LLM/judge thật. Offline không được nạp .env.

## Launcher Windows

make.cmd dùng python từ PATH và chuyển tiếp arguments. Chuẩn bị Python 3.11 trong phiên PowerShell; CMD tìm launcher cục bộ, không cần cài GNU Make:

```powershell
$taskPythonBin = (& py -3.11 -c "import sys; from pathlib import Path; print(Path(sys.executable).parent)").Trim()
$env:PATH = "$taskPythonBin;$env:PATH"
python --version
cmd /d /c "where make"
# OFFLINE: chỉ khi CLI/evaluator đã đủ.
cmd /d /c "make demo --backend offline"
if ($LASTEXITCODE -ne 0) { throw 'Offline launcher chưa đạt.' }
cmd /d /c "make eval --backend offline --runs 1"
if ($LASTEXITCODE -ne 0) { throw 'Offline eval launcher chưa đạt.' }
```

Nếu máy có GNU Make thì Makefile là lựa chọn riêng; Makefile hiện không chuyển tiếp flag CLI như make.cmd. Không suy luận where make thành công là demo đã pass. run.py không có target kiểm tra riêng thì không tự thêm target chỉ để setup trông đầy đủ.

## Live đang khóa

Các lệnh dưới đây chỉ là lệnh dự kiến phục vụ yêu cầu tái lập; **KHÔNG chạy hiện tại**. Demo/eval không truyền backend offline mặc định là live. Không chạy run.py không arguments vì mặc định demo.

```powershell
# LIVE — CHƯA CÓ QUYỀN: chỉ sau sinh viên cho phép riêng và module đã đủ.
cmd /d /c "make setup && make demo"
cmd /d /c "make eval"
```

Hai lệnh là hai tác vụ khác nhau, không phải quyền tự động chạy cả hai. Sinh viên tự cấp key; AI không đọc/hiển thị file key hay dump môi trường. Không tự chạy preflight/judge/live khi quota hồi phục. Chốt số lượt/ngân sách trước mỗi đợt và dừng khi lỗi/quota, ghi đúng phần chưa hoàn tất. Hiện chưa xác minh API thật hoặc chạy trên máy bảo vệ.

## Bàn giao cho AI trên máy mới

Yêu cầu AI: “Đọc AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/SETUP.md và ai-usage.md. Kiểm tra file hiện có, tóm tắt phase đang làm và bước tiếp theo. Chỉ hỗ trợ phần tôi yêu cầu; không đọc .env, không gọi API live, không commit/push.”

Sau mỗi phase, cập nhật mục trạng thái trong README và ghi AI thực sự hỗ trợ trong ai-usage. Nếu thiếu PDF/mã tuần 4/sổ tay ở máy mới, nói rõ thiếu nguồn khi công việc cần đối chiếu; không tự đoán nội dung. Các tài liệu local giúp tiếp tục đúng thiết kế, không bảo đảm mọi công cụ AI sẽ tự nhận diện hoặc tuân thủ hoàn toàn.
