"""Independent second MCP host; no agent or LLM dependency."""
import asyncio
import json
import os
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

async def main():
    env = os.environ.copy() #tạo một bản sao để truyền cho subprocess, tránh phải mutate environment của client.
    env.update(
        AIPR_BACKEND="offline", 
        AIPR_DB_PATH=str(ROOT / "state/second-client.sqlite"), 
        AIPR_ALLOW_WRITE="1", AIPR_OPERATION_KEY="second-client", 
        PYTHONIOENCODING="utf-8"
    )
    params = StdioServerParameters(
        command=sys.executable, 
        args=["-m", "src.mcp_server"], 
        cwd=str(ROOT), env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            inventory = (await session.list_tools()).tools
            print("Second host discovered:", [t.name for t in inventory])
            
            analysis = await session.call_tool("analyze_progress", {"project_id": "P001", "as_of_date": "2026-10-08"})
            print(analysis.content[0].text)
            
            created = await session.call_tool("create_followup_request", {"project_id": "P001", "as_of_date": "2026-10-08"})
            record = json.loads(created.content[0].text)
            # Kết quả trả về của `created` chứa thông tin chi tiết về tool dùng để đối soát (tool_name và arguments)
            verify = await session.call_tool(record["verification"]["tool_name"], record["verification"]["arguments"])
            # Dùng assert để kiểm tra dữ liệu vừa tạo có khớp chính xác với dữ liệu đọc lại từ CSDL hay không
            assert json.loads(verify.content[0].text) == record["record"]
            print("Interop write/read verification: PASS")
            
if __name__ == "__main__":
    asyncio.run(main())