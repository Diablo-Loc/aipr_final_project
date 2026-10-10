import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from .agent import run_agent
from .api import Trace, LiveModel, run_configuration
from .data import ROOT
from .mcp_client import connect
from .offline_model import OfflineModel

async def ask(query: str, backend: str, mode: str, allow_write: bool, trace: Trace, query_id: str, operation_key: str, db_path=None):
    trace.query_id = query_id
    db_path = db_path or ROOT /"state/demo.sqlite"
    
    trace.emit("query_start", query= query, mode=mode, allow_write=allow_write)
    model = LiveModel(trace) if backend =="live" else OfflineModel(allow_write)
    async with connect(backend, db_path, allow_write, operation_key, trace) as tools:
        result = await run_agent(query, tools, model, mode, allow_write, trace)
    
    trace.emit("final", result=result)
    trace.emit("USAGE", **asdict(model.usage), usage_scope="agent", simulated=backend != "live")
    return result, asdict(model.usage)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["live", "offline"], default="live")
    parser.add_argument("--mode", choices=["dense", "hybrid"], default="hybrid")
    parser.add_argument("--query")
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--trace-details", action="store_true")
    
    args = parser.parse_args()
    
    if args.backend == "live":
        from .runtime import load_runtime_env
        load_runtime_env()
    
    #KHỞI TẠO FILE TRACE LOG -JSON Lines- (.jsonl) VỚI TIMESTAMPS
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    trace =  Trace(ROOT / "logs" / f"demo_{args.backend}_{stamp}.jsonl", args.backend)
    trace.emit("run_start", configuration=run_configuration(), mock_llm=args.backend != "live")
    
    examples = [(args.query, args.allow_write)] if args.query else [
            ("Ai phụ trách T02 của P001?", False),                                                        # Kịch bản 1: Q&A thông tin dự án
            ("P001 ngày 08/10/2026 chậm bao nhiêu so với kế hoạch?", False),                              # Kịch bản 2: Phân tích tiến độ (Analysis)
            ("Ngân sách đã chi của P001 là bao nhiêu?", False),                                           # Kịch bản 3: Tra cứu tài chính
            ("Nếu P001 vượt ngưỡng ngày 08/10/2026, hãy tạo yêu cầu xử lý và xác nhận đã lưu.", True)     # Kịch bản 4: Phân tích + Ghi dữ liệu + Verification
        ]  
    failed = False
    for i, (query, write) in enumerate(examples):
        result, usage = await ask(query, args.backend, args.mode, write, trace, f"D{i+1}", f"demo:{stamp}:{i}")
        print(f"\nCâu hỏi: {query}\n[{args.backend} / {result['status']}] {result['answer']}")
        
        if result["citations"]:
            print("Nguồn:", ", ".join(result["citations"]))
        
        print("USAGE:", json.dumps(usage))
        
        if args.trace_details:
            print(json.dumps(result, ensure_ascii=False, indent= 2))
        
        failed = failed or result["status"] == "error"
        
        if result["status"] == "error" and usage["calls"] == 0 and args.backend == "live":
            break
        
    print(f"Trace: {trace.path}")
    trace.emit("run_end", success= not failed)
    
    if failed:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())