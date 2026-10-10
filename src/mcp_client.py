from contextlib import asynccontextmanager
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from .data import ROOT

class Tools:
    def __init__(self, session, inventory, trace):
        self.session, self.trace = session, trace
        
        # Chuyển danh sách tool thành Dictionary
        self.inventory ={t.name: t for t in inventory}
        
        # Chuyển đổi Schema của MCP sang chuẩn 'Function Calling' của OpenAI/LLMs
        self.schemas = [
            {
                "type": "function", 
                "function": {
                    "name": t.name, 
                    "description": t.description, 
                    "parameters": t.inputSchema
                }
            } 
            for t in inventory
        ]
        
    async def call(self, name: str, args: dict) -> str:
        if name not in self.inventory:
            self.trace.emit("tool", name=name, arguments = args, result="Error: unknown discovered tool")
            return "Error: unknown discovered tool"
        try:
            #Validate tham số truyền vào bằng jsonschema trước khi gửi tới server
            from jsonschema import validate
            validate(args, self.inventory[name].inputSchema)
            result = await self.session.call_tool(name, args)
            text = "\n".join(b.text for b in result.content if hasattr(b, "text"))
            
            #Nếu MCP Server báo lỗi, đầu ra luôn bắt đầu bằng chữ "Error:"
            if result.isError and not text.startswith("Error:"):
                text = "Error: "+ text
        
        except Exception as error:
            text = f"Error: {type(error).__name__} during validation or MCP call"
        self.trace.emit("tool", name=name, arguments=args, result=text)
        return text
    
@asynccontextmanager
async def connect(backend: str, db_path: Path, allow_write: bool, operation_key: str, trace):
    env = os.environ.copy()
    env.update(
        AIPR_BACKEND=backend, 
        AIPR_DB_PATH=str(db_path), 
        AIPR_ALLOW_WRITE="1" if allow_write else "0", 
        AIPR_OPERATION_KEY=operation_key, 
        AIPR_TRACE_PATH=str(trace.path.resolve()), 
        AIPR_TRACE_QUERY_ID=trace.query_id, 
        PYTHONIOENCODING="utf-8"
        )
    params = StdioServerParameters(command=sys.executable, args=["-m", "src.mcp_server"], cwd=str(ROOT), env=env)
    stdeer_path = trace.path.with_suffix(".stderr.log")
    with stdeer_path.open("a", encoding="utf-8") as errors:
        async with stdio_client(params, errlog=errors) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=120))as session:
                await session.initialize()
                inventory = (await session.list_tools()).tools
                trace.emit("discovery", tools=[{"name": t.name, "schema": t.inputSchema} for t in inventory])
                yield Tools(session, inventory, trace)