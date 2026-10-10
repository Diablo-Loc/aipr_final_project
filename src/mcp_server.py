"""The student's server: five tools, stdio, all business errors are observations."""
import json
import os
import asyncio
from dataclasses import asdict
from pathlib import Path
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import ToolAnnotations, Tool,TextContent
from jsonschema import validate
from .data import Corpus, ROOT
from .models import SearchArgs, AnalysisArgs, RequestArgs, DocumentArgs, ReadRequestArgs, ToolSpec, tool_schema
from .rag import Retriever
from .store import RequestStore
from .api import Trace

# Low-level SDK has no FastMCP Settings object and never searches .env.
class Service:
    def __init__(self, backend: str, db_path: Path, allow_write: bool, operation_key: str, trace=None):
        self.corpus = Corpus()
        self.retriever=Retriever(self.corpus, backend, trace)
        self.store = RequestStore(db_path)
        self.allow_write, self.operation_key = allow_write, operation_key
        self.last_analysis = None
        
    def analyze(self, args: AnalysisArgs):
        """Analyze the project process and save the results to the `last_analysis` cache."""
        self.last_analysis = self.corpus.analyze(args)
        return self.last_analysis
    
    def create(self, args: RequestArgs):
        """Create a follow-up request in SQLite with strict constraints."""
        if not self.allow_write:
            raise ValueError("User has not granted a write action")
        result = self.corpus.analyze(AnalysisArgs(args.project_id, args.as_of_date))
        if not self.last_analysis or any(self.last_analysis.get(k) != result.get(k) for k in ("project_id", "as_of_date")):
            raise ValueError("Call analyze_progress for this project/date before writing")
        if result["status"] != "ok" or not result["risk"]:
            raise ValueError("Insufficient evidence or no risk; no request was created")
        record = self.store.create(self.operation_key, result)
        return {"record": record, "verification": {"tool_name":"get_followup_request", "arguments": {"request_id": record["request_id"]}}}
    
def build_server(service: Service) -> Server:
    """Initialize and configure the MCP Server with 5 tools."""
    server = Server("project-progress")
    specs = [
        ToolSpec("search_documents", "Find project evidence and global policies. Returns chunks and related_documents with IDs/versions for older replaced reports. Current retrieval excludes versions; read related_documents with get_document for historical comparison. Scores do not prove an answer exists. Use first; dense/hybrid supported.", SearchArgs, service.retriever.search),
        ToolSpec("get_document", "Read an exact document version, including historical sources for comparison. Use IDs found in observed evidence, not guessed IDs.", DocumentArgs, lambda a: asdict(service.corpus.get(a.doc_id, a.version))),
        ToolSpec("analyze_progress", "Calculate weighted planned/actual progress, behind_pp in percentage points, overdue calendar days, threshold and sources. compare_date optionally compares exact snapshots. Missing data returns insufficient_data.", AnalysisArgs, service.analyze),
        ToolSpec("create_followup_request", "Write a persistent SQLite request only after analysis shows risk and the user grants a write. Server builds the reason from validated facts. Host MUST immediately call the returned read verification tool.", RequestArgs, service.create, False),
        ToolSpec("get_followup_request", "Read a persisted request by ID to VERIFY its fields after writing. Unknown ID returns Error:.", ReadRequestArgs, lambda a:service.store.get(a.request_id)),
    ]
    registry = {spec.name: spec for spec in specs}
    
    # Handler đăng ký danh sách tool với MCP protocol
    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name=s.name, 
                description=s.description, 
                inputSchema=tool_schema(s.input_model), 
                annotations=ToolAnnotations(readOnlyHint=s.read_only, destructiveHint=False, idempotentHint=True)
            ) 
            for s in specs
        ]
    
    # Handler thực thi tool khi Client gửi request
    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict):
        try:
            spec = registry[name]
            validate(arguments, tool_schema(spec.input_model))
            result = spec.handler(spec.input_model(**arguments))
            text =json.dumps(result, ensure_ascii=False)
        except Exception as error:
            text = f"Error: {type(error).__name__}: {error}"
        return [TextContent(type="text",text=text)]
    return server

async def main():
    backend = os.getenv("AIPR_BACKEND", "offline")
    trace = Trace(Path(os.environ["AIPR_TRACE_PATH"]),backend) if os.getenv("AIPR_TRACE_PATH") else None
    if trace:
        trace.query_id = os.getenv("AIPR_TRACE_QUERY_ID", "")

    service = Service(
        backend, 
        Path(os.getenv("AIPR_DB_PATH", str(ROOT / "state/demo.sqlite"))), 
        os.getenv("AIPR_ALLOW_WRITE") == "1", 
        os.getenv("AIPR_OPERATION_KEY", "demo"), 
        trace
    )   
    
    server = build_server(service)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())
        
if __name__ == "__main__":
    asyncio.run(main())