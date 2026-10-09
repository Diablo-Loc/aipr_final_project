"""HTTP integration. Read process variables only; never read credential files."""
import hashlib
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import httpx
import numpy as np
from .data import ROOT
from .models import Usage, Answer, tool_schema

CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

def run_configuration():
    import sys
    return {**CONFIG, **{field: os.getenv(name, CONFIG[field]) for name, field in (("LLM_MODEL", "llm_model"), ("JUDGE_MODEL", "judge_model"),("EMBEDDING_MODEL", "embedding_model"))}, "python":sys.version.split()[0]}

#Ghi lại nhật ký các sự kiện
class Trace:
    def __init__(self, path: Path, backend: str):
        self.path, self.backend = path, backend
        path.parent.mkdir(parents=True, exist_ok=True)
        self.query_id =""
        self.attempts ={}
    
    def emit(self, event: str, **values):
        if event == "http_attempt":
            scope = values["scope"]
            self.attempts[scope] = self.attempts.get(scope, 0) + 1
        row = {"timestamp": datetime.now(timezone.utc).isoformat(), "backend": self.backend, "query_id": self.query_id, "event": event, **values}
        text = json.dumps(row, ensure_ascii=False)
        for name in ("GROQ_API_KEY", "JINA_API_KEY"):
            secret = os.getenv(name)
            if secret:
                text = text.replace(secret, "REDACTED")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(text + "\n")
    
def post_json(url: str, key: str, body: dict, trace: Trace | None = None, scope: str = "api") -> dict:
    if not key:
        raise RuntimeError(f"Missing runtime credential for {scope}")
    for attempt in range(CONFIG["max_attempts"]):
        try:
            if trace:
                trace.emit("http_attempt", scope=scope, attempt=attempt + 1)
            with httpx.Client(timeout=CONFIG["timeout_seconds"]) as client:
                response = client.post(url, headers={"Authorization": f"Bearer {key}"}, json=body)
            if trace:
                trace.emit("http", scope=scope, attempt=attempt + 1, status=response.status_code)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            code = None
            diagnostic = {}
            if status is not None:
                try:
                    provider_error = error.response.json().get("error", {})
                    candidate = provider_error.get("code")
                    if candidate in ("tool_use_failed", "model_not_found", "context_length_exceeded", "invalid_request_error", "rate_limit_exceeded", "invalid_api_key"):
                        code = candidate
                    if status == 400 or code == "tool_use_failed":
                        for field in (("message", "failed_generation") if code == "tool_use_failed" else ("message",)):
                            value = str(provider_error.get(field, ""))
                            for name in ("GROQ_API_KEY", "JINA_API_KEY"):
                                if os.getenv(name):
                                    value = value.replace(os.environ[name], "[REDACTED]")
                            diagnostic[field] = value[:500]
                except (ValueError, AttributeError):
                    pass
            if trace:
                trace.emit("http_error", scope=scope, attempt=attempt + 1, status=status, error=type(error).__name__, provider_code=code, diagnostic=diagnostic)
            if attempt + 1 == CONFIG["max_attempts"] or (status is not None and status not in (429, 500, 502, 503, 504)):
                raise RuntimeError(f"{scope}: {type(error).__name__}, HTTP {status}, code={code}") from None
            delay = min(2 ** attempt, 4)
            if status == 429:
                try:
                    delay = max(delay, float(error.response.headers.get("retry-after", "15")))
                except ValueError:
                    delay = 15
                if trace:
                    trace.emit("rate_limit", scope=scope, retry_after_seconds=delay)
                if not 0 <= delay <= 60:
                    raise RuntimeError(f"{scope}: rate limit requires {delay:g} seconds; retry later") from None
            if trace:
                trace.emit("http_retry", scope=scope, wait_seconds=delay)
            time.sleep(delay)
    raise RuntimeError("Retry budget exhausted")

class Embedder:
    def __init__(self, backend: str, trace: Trace |None = None):
        self.backend, self.trace = backend, trace
        self.model = os.getenv("EMBEDDING_MODEL", CONFIG["embedding_model"])
        self.path = ROOT /"cache" /f"embeddings_{backend}.json"
        self.path.parent.mkdir(exist_ok=True)
        self.cache =json.loads(self.path.read_text(encoding="utf-8"))if self.path.exists() else {}
        self.usage ={"calls": 0, "tokens": 0, "cache_hits": 0}
    
    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        before = dict(self.usage)
        attempts_before = self.trace.attempts.get("embedding", 0)if self.trace else 0
        keys = [hashlib.sha256(f"{self.model}:{task}:{t}".encode()).hexdigest() for t in texts]
        pending = {k: t for k, t in zip(keys, texts) if k not in self.cache}
        self.usage["cache_hits"] +=sum(k in self.cache for k in keys)
        if pending:
            if self.backend =="live":
                response = post_json("https://api.jina.ai/v1/embeddings", os.getenv("JINA_API_KEY", ""), {"model": self.model, "task": task, "input": list(pending.values())}, self.trace, scope="embedding")
                vectors = [item["embedding"] for item in sorted(response["data"], key=lambda x: x["index"])]
                self.usage["calls"]+=1
                self.usage["tokens"]+=response.get("usage", {}).get("total_tokens", 0)
            else:
                # Deterministic integration fixture, NOT a semantic embedding model.
                import re
                vectors = []
                for text in pending.values():
                    v = np.zeros(128)
                    for word in re.findall(r"\w+", text.lower()):
                        v[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 128] += 1
                    vectors.append(v.tolist())
            if len(vectors) != len(pending):
                raise ValueError("Embedding count mismatch")
            self.cache.update(zip(pending, vectors))
            temp = self.path.with_suffix(f".{os.getpid()}.tmp")
            temp.write_text(json.dumps(self.cache), encoding="utf-8")
            temp.replace(self.path)
        if self.trace:
            self.trace.emit("EMBEDDING_USAGE", model=self.model, task=task, usage_scope="embedding", simulated=self.backend != "live", **{k: self.usage[k] - before[k] for k in before}, attempts=self.trace.attempts.get("embedding", 0)- attempts_before)
        return [self.cache[k] for k in keys]
    
class LiveModel:
    def __init__(self, trace: Trace, model_name: str |None = None):
        self.trace, self.usage = trace, Usage()
        self.model = model_name or os.getenv("LLM_MODEL", CONFIG["llm_model"])
    
    def complete(self, messages: list[dict], tools: list[dict] | None= None, tool_choice:str | dict ="required")->dict:
        body= {"model": self.model, "messages": messages, "temperature": 0, "max_completion_tokens": 900}
        if self.model.startswith("openai/gpt-oss-"):
            body["reasoning_effort"] = "low"
        elif self.model.startswith("qwen/"):
            body["reasoning_effort"] = "none"
        if tools:
            body["tools"] = [*tools, {"type": "function", "function": {"name": "final_answer", "description": "Submit the final grounded answer with status, source citations and facts. This is the local response schema, not a business action. Use instead of calling json/JSON.", "parameters": tool_schema(Answer)}}]
            body["tool_choice"] = tool_choice
            body["parallel_tool_calls"] = False
        else:
            # JSON repair has no native tools. Preserve evidence as plain history.
            plain =[]
            for message in messages:
                if message.get("tool_calls"):
                    plain.append({"role": "assistant", "content": "PREVIOUS_TOOL_ACTIONS\n" + json.dumps(message["tool_calls"], ensure_ascii=False)})
                elif message["role"] == "tool":
                    plain.append({"role": "user", "content": "TOOL_OBSERVATION\n" + message["content"]})
                else:
                    plain.append(message)
            body["messages"]=plain
            body["tool_choice"]= "none"
            body["response_format"] = {"type": "json_object"}
        before = self.trace.attempts.get("llm",0)
        try:
            response = post_json(os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/") + "/chat/completions", os.getenv("GROQ_API_KEY", ""), body, self.trace, "llm")
        finally:
            self.usage.attempts += self.trace.attempts.get("llm", 0) - before
        usage = response.get("usage")
        if not usage:
            raise RuntimeError("Provider response has no USAGE; cannot record valid evaluation")
        self.usage.calls +=1
        self.usage.prompt_tokens += usage["prompt_tokens"]
        self.usage.completion_tokens += usage["completion_tokens"]
        self.usage.max_prompt = max(self.usage.max_prompt, usage["prompt_tokens"])
        message = {k: v for k, v in response["choices"][0]["message"].items() if k in ("role", "content", "tool_calls")}
        raw_message = response["choices"][0]["message"]
        self.trace.emit("llm", model=self.model, usage=usage, message=message, message_fields=list(raw_message), finish_reason=response["choices"][0].get("finish_reason"), legacy_function=raw_message.get("function_call"))
        calls = message.get("tool_calls") or []
        if len(calls) ==1 and calls[0]["function"]["name"] == "final_answer":
            return {"role": "assistant", "content": calls[0]["function"]["arguments"]}
        return message                   