"""The explicit agent loop. No LangChain, routing framework or hidden executor."""
import json
import re
from datetime import date
from dataclasses import asdict
from .api import CONFIG
from .data import ROOT
from .models import Action, Answer, SearchArgs

class EvidenceError(ValueError):
    """The answer needs another real tool observation, not just JSON repair."""

def source_ids(value) ->set[str]:
    """A recursive function that scans and extracts all `doc_id`s present
    in the results returned by the Tool (Observation).
    """
    if isinstance(value, dict):
        found = {value["doc_id"]} if isinstance(value.get("doc_id"), str) else set()
        for key, child in value.items():
            if key != "related_documents": # A link is not the old document's evidence.
                found.update(source_ids(child))
        return found
    if isinstance(value, list):
        return set().union(*(source_ids(child) for child in value))
    return set()

def initial_search_args(query: str, mode: str) -> SearchArgs:
    """Automatically prepare initial search parameters"""
    # Tìm mã dự án vidu: P001, P002..
    project = re.search(r"\bP\d{3}\b", query, re.I)

    # Tìm các định dạng ngày: DD/MM/YYYY hoặc YYYY-MM-DD
    dates = [date(int(y), int(m), int(d)).isoformat() for d, m, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", query)]

    dates += [date.fromisoformat(d).isoformat() for d in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", query)]
    return SearchArgs(query, project[0].upper() if project else "P001", max(dates) if dates else "2026-10-08", mode, CONFIG["top_k"])

def parse_action(call: dict) -> Action:
    """Convert data tool calls from the LLM into Action objects."""
    arguments = json.loads(call["function"]["arguments"])
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object")
    return Action(call["id"], call["function"]["name"], arguments)

def parse_answer(text: str)-> Answer:
    """Parse chuỗi JSON trả về từ LLM thành đối tượng Answer và kiểm tra cấu hình chuẩn (Validation)."""
    if text.strip().startswith("```"):
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    
    value = json.loads(text)
    
    if not isinstance(value, dict):
        raise ValueError("Final answer must be JSON object")
    
    # Đảm bảo trạng thái trả về hợp lệ
    if value.get("status") not in ("ok", "no_answer", "insufficient_data", "action_verified", "action_failed", "error"):
        raise ValueError("Invalid final status")
    
    if not isinstance(value.get("answer"), str) or not isinstance(value.get("citations", []), list):
        raise ValueError("Invalid final answer fields")
    
    if any(not isinstance(c, str) for c in value.get("citations", [])) or not isinstance(value.get("facts", {}), dict):
        raise ValueError("Citations must be strings and facts must be an object")
    
    return Answer(value["status"], value["answer"], value.get("citations", []), value.get("facts", {}))

async def run_agent(query: str, tools, model, mode:str, allow_write: bool, trace, max_steps: int =CONFIG["max_steps"])-> dict:
    # 1. Nạp System Prompt và khởi tạo Lịch sử trò chuyện (Messages)
    prompt = (ROOT /"templates/agent.txt").read_text(encoding="utf-8").replace("{mode}", mode).replace("{allow_write}", str(allow_write))
    messages = [{"role": "system", "content": prompt}, {"role":"user", "content":query}]
    observations, verified, known_ids, tool_steps = [], False, set(),0
    analysis, verified_record = None, None
    force_final = False
    
    # 2. BƯỚC BOOTSTRAP: bước đầu để cung cấp context trước cho LLM
    if "search_documents" in tools.inventory:
        try:
            args = initial_search_args(query, mode)
            trace.emit("retrieval_bootstrap", actor="host", arguments=asdict(args))
            result = await tools.call("search_documents", asdict(args))
            
            if result.startswith("Error:"):
                raise ValueError(result)
            
            observation = json.loads(result)
            observations.append(observation)
            known_ids.update(source_ids(observation))# Lưu vết các doc_id đã quan sát được
            tool_steps = 1
            messages.append({"role": "user", "content": "RAG_CONTEXT\n" + result})
        except (ValueError, TypeError) as error:
            return {"status": "error", "answer": f"Error: initial retrieval: {error}", "citations":[], "facts": {}, "verified": False, "observations": observations}
    
    # 3. VÒNG LẶP CHÍNH
    for turn in range(max_steps):
        try:
            # Gọi LLM sinh phản hồi tiếp theo
            message = model.complete(messages, None if force_final else tools.schemas)
        except Exception as error:
            # Xử lý trường hợp LLM sinh sai định dạng tool call
            if "tool_use_failed" in str(error):
                # Retrieval alone does not finish analysis or an authorised write.
                force_final = False
                trace.emit("action_error", error="Provider rejected generated tool action; requesting a valid action")
                messages.append(
                    {"role": "user", 
                     "content": f"Error: generated tool action was invalid. Available business tools: {', '.join(tools.inventory)}. Never call json/JSON. To finish, use final_answer or final JSON in assistant content; otherwise call an available business tool with valid JSON arguments."
                    }
                )
                continue
            return {"status": "error", "answer": str(error), "citations": [], "facts": {}, "verified": verified, "observations": observations}
        calls = message.get("tool_calls", [])
        
        # KỊCH BẢN A: LLM không gọi thêm tool nào -> Đưa ra CÂU TRẢ LỜI CUỐI CÙNG
        if not calls:
            try:
                answer = parse_answer(message.get("content") or "")
                
                # Guardrail 1: Không được suy đoán số liệu (facts) nếu từ chối trả lời
                if answer.status in ("no_answer", "insufficient_data") and answer.facts:
                    raise EvidenceError("A refusal must not invent answer facts")
                
                # Guardrail 2: Citations phải nằm trong danh sách các doc_id 
                if not set(answer.citations) <= known_ids:
                    raise EvidenceError("Citation not present in observed sources; read the actual document before citing a link")
                
                # Guardrail 3: Câu trả lời khẳng định bắt buộc phải kèm Trích dẫn
                if answer.status in ("ok", "action_verified") and not answer.citations:
                    raise ValueError("Factual answer needs source citations")
                
                # Guardrail 4: Kiểm tra trạng thái xác minh khi ghi
                if answer.status == "action_verified" and not verified:
                    raise EvidenceError("Action not verified")
                
                if answer.status == "action_verified" and answer.facts.get("request_id") != verified_record["request_id"]:
                    raise ValueError("Use the verified request_id in final facts")

                # Guardrail 5: Ràng buộc tính chính xác của số liệu phân tích
                calculated = ("actual_progress", "planned_progress", "behind_pp", "change_pp", "previous_actual_progress", "overdue", "risk")
                if any(k in answer.facts for k in calculated):
                    
                    # Bắt buộc phải chạy tool `analyze_progress` trước khi trả về số liệu
                    if not analysis or analysis.get("status") != "ok":
                        raise EvidenceError("Call analyze_progress before reporting project calculation facts")
                    
                    # Tất cả các chỉ số trong facts phải khớp 100% với kq `analyze_progress`
                    for key in (*calculated, "threshold_pp"):
                        if key in answer.facts and (key not in analysis or answer.facts[key] != analysis[key] or (key == "risk" and type(answer.facts[key]) is not bool)):
                            raise ValueError(f"Final {key} must match analyze_progress; task/version differences use task_change_pp, not project change_pp") 
                    
                    # Trích dẫn nguồn tài liệu đã được `analyze_progress` sử dụng
                    if not source_ids(analysis) <= set(answer.citations):
                        raise EvidenceError("Cite the source documents used by analyze_progress")
                
                # Guardrail 6: Chuẩn hóa ngôn ngữ Tiếng Việt 
                if "behind_pp" in answer.facts and ("chậm" in answer.answer.lower() or "chênh" in answer.answer.lower()) and "điểm phần trăm" not in answer.answer.lower():
                    raise ValueError("State behind_pp in điểm phần trăm, not %")
                return {**asdict(answer), "verified": verified, "observations": observations}
            except (ValueError, TypeError, KeyError) as error:
                #nếu vi phạm trên thì yêu cầu LLM sửa Json hoặc bổ sung bằng chứng
                force_final = bool(observations) and not isinstance(error, EvidenceError)
                trace.emit("parse_error", error=str(error))
                messages += [{"role": "assistant", "content": message.get("content") or ""}, {"role": "user", "content": f"Error: {error}. Return the required JSON; do not invent sources."}]
                continue
        
        # KỊCH BẢN B: LLM yêu cầu GỌI TOOL
        messages.append(message)
        
        # Sequential execution is essential: no tool may interleave write and verify.
        for raw in calls:
            result = "Error: invalid action JSON or arguments"
            try:
                action = parse_action(raw)
                info = tools.inventory.get(action.name)
                is_write = info is not None and info.annotations is not None and info.annotations.readOnlyHint is False
                
                if tool_steps >= max_steps or (is_write and (not allow_write or tool_steps +2 > max_steps)):
                    result = "Error: no write permission or insufficient step budget for verification"
                else:
                    # Cache lại kết quả nếu là tool phân tích tiến độ
                    if action.name == "search_documents":
                        action.arguments["mode"] = mode
                        action.arguments["top_k"] = CONFIG["top_k"]
                    result = await tools.call(action.name, action.arguments)
                    tool_steps += 1
                    
                    if not result.startswith("Error:"):
                        observation = json.loads(result)
                        
                        if action.name =="analyze_progress":
                            analysis = observation
                        
                        # cơ chế đối soát tự động khi ghi
                        if is_write:
                            contract = observation.get("verification", {})
                            name = contract.get("tool_name")
                            read = tools.inventory.get(name)
                            
                            # Bắt buộc kết quả ghi phải cung cấp 1 tool đọc (read-only) để xác minh
                            if not read or not read.annotations or read.annotations.readOnlyHint is not True:
                                raise ValueError("Write result lacks a discovered read-only verification tool")
                            
                            # Tự động gọi tool đọc ngay lập tức để check dữ liệu ghi vào csdl chưa
                            read_result = await tools.call(name, contract["arguments"])
                            tool_steps +=1
                            
                            #đánh giá ghi dữ liệu thành công chỉ khi kq đọc khớp với bản ghi đầu
                            verified = not read_result.startswith("Error:") and json.loads(read_result) == observation["record"]
                            verified_record = observation["record"] if verified else None
                            trace.emit("verify", success=verified, request_id=observation["record"]["request_id"])
                            observation["verified"] = verified
                            observation["read_back"] = json.loads(read_result) if not read_result.startswith("Error:") else read_result
                            result = json.dumps(observation, ensure_ascii=False)
                        observations.append(observation)
                        known_ids.update(source_ids(observation))
            except (ValueError, TypeError, KeyError) as error:
                result = f"Error: {type(error).__name__}: {error}"
                trace.emit("action_error", error=result)
            messages.append({"role": "tool", "tool_call_id": raw.get("id", f"invalid_{turn}"), "content": result})
    return {"status": "error", "answer": "MAX_STEPS reached; only verified observations are retained.", "citations": [], "facts": {}, "verified": verified, "observations": observations}