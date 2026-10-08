from dataclasses import MISSING, dataclass, field,fields
from typing import Any, TypedDict, Callable, get_args, get_origin

class Metadata(TypedDict):
    doc_id: str
    title: str
    date: str
    version:int
    owner: str
    project_id: str
    kind: str

@dataclass
class Document:
    metadata: Metadata
    content: str
    records: dict[str, Any] = field(default_factory=dict)

@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: Metadata

#tham số tra cứu RAG
@dataclass
class SearchArgs:
    query: str
    project_id: str ="P001"
    as_of_date: str="2026-10-08"
    mode: str ="hybrid"
    top_k: int = 4

#tham số tính toán tiến độ
@dataclass
class AnalysisArgs:
    project_id: str
    as_of_date: str
    compare_date: str = ""

#tham số tạo yêu cầu xử lý rủi ro
@dataclass
class RequestArgs:
    project_id: str
    as_of_date: str

@dataclass
class DocumentArgs:
    doc_id: str
    version: int

#đọc lại yêu cầu đã lưu.
@dataclass
class ReadRequestArgs:
    request_id: str


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type
    handler: Callable[[Any],Any]
    read_only: bool = True

#hàm tự động sinh json schema
def tool_schema(model: type) -> dict[str,Any]:
    """JSON wire schema is derived from the dataclass, not handwritten dicts."""
    types = {str: "string", int: "integer", float:"number",bool:"boolean",list:"array",dict: "object"}
    properties, required = {},[]
    for f in fields(model):
        origin = get_origin(f.type) or f.type
        properties[f.name] = {"type": types[origin]}
        if origin is list:
            properties[f.name]["items"] = {"type": types[get_args(f.type)[0]]}
        if f.default is MISSING:
            required.append(f.name)
        else:
            properties[f.name]["default"] = f.default
    return {"type":"object", "properties": properties, "required":required, "additionalProperties": False}

@dataclass
class Source:
    doc_id: str
    version: int
    title: str
    
@dataclass
class Usage:
    calls: int =0 
    prompt_tokens: int =0
    completion_tokens: int = 0
    max_prompt: int = 0
    attempts: int =0

@dataclass
class Action:
    call_id:str
    name: str
    arguments: dict[str, Any]# validated JSON at the wire boundary

@dataclass
class Answer:
    status: str
    answer: str
    citations: list[str] = field(default_factory=list)
    facts: dict[str,Any] = field(default_factory=dict)