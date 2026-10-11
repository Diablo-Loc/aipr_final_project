import asyncio
import json
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from mcp.types import ToolAnnotations
from src.agent import parse_action, run_agent
from src.api import post_json, Trace, LiveModel
from src.data import Corpus
from src.hybrid import hybrid_search, normalise_scores
from src.models import AnalysisArgs, RequestArgs, SearchArgs, Answer, tool_schema
from src.mcp_server import Service
from src.mcp_client import connect
from src.rag import cosine, Retriever


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus()

    def test_weighted_progress_and_overdue(self):
        result = self.corpus.analyze(AnalysisArgs("P001", "2026-10-08"))
        self.assertEqual((result["planned_progress"], result["actual_progress"], result["behind_pp"]), (70, 48, 22))
        self.assertEqual(result["overdue"], [{"task_id": "T02", "days": 1}])

    def test_policy_version_changes_decision(self):
        result = self.corpus.analyze(AnalysisArgs("P001", "2026-10-04"))
        self.assertEqual(result["behind_pp"], 17)
        self.assertEqual(result["threshold_pp"], 15)
        self.assertTrue(result["risk"])
        self.assertFalse(result["behind_pp"] >= 20)

    def test_compare_two_snapshots(self):
        result = self.corpus.analyze(AnalysisArgs("P001", "2026-10-08", "2026-10-01"))
        self.assertEqual(result["change_pp"], 13)
        self.assertEqual(result["previous_actual_progress"], 35)
        self.assertEqual(result["compare_date"], "2026-10-01")

    def test_no_answer_differs_from_insufficient(self):
        self.assertEqual(self.corpus.analyze(AnalysisArgs("P999", "2026-10-08"))["status"], "no_answer")
        for project in ("P003", "P004"):
            self.assertEqual(self.corpus.analyze(AnalysisArgs(project, "2026-10-08"))["status"], "insufficient_data")

    def test_filter_project_version_and_global(self):
        ids = {d.metadata["doc_id"] for d in self.corpus.eligible("P001", "2026-10-08")}
        self.assertIn("POLICY-V2", ids)
        self.assertIn("P001-W2-V2", ids)
        self.assertNotIn("POLICY-V1", ids)
        self.assertNotIn("P001-W2-V1", ids)
        self.assertFalse(any(d.startswith("P002") for d in ids))

    def test_retrieval_links_old_version_without_returning_old_facts(self):
        result = Retriever(self.corpus, "offline").search(SearchArgs("P001 2026-10-08 báo cáo tiến độ", top_k=8))
        self.assertIn({"doc_id": "P001-W2-V1", "version": 1, "title": "Báo cáo tiến độ P001 ngày 2026-10-08", "superseded_by": "P001-W2-V2"}, result["related_documents"])
        self.assertNotIn("P001-W2-V1", [c["metadata"]["doc_id"] for c in result["chunks"]])
        self.assertEqual(self.corpus.get("P001-W2-V1", 1).records["actual"]["T02"], 50)

    def test_bad_dates(self):
        with self.assertRaises(ValueError):
            self.corpus.analyze(AnalysisArgs("P001", "08/10/2026"))

    def test_cosine_zero_and_dimension(self):
        self.assertEqual(cosine([0, 0], [1, 1]), 0)
        self.assertAlmostEqual(cosine([1, 0], [1, 0]), 1)
        with self.assertRaises(ValueError):
            cosine([1], [1, 2])

    def test_class_hybrid_edge_cases(self):
        self.assertEqual(normalise_scores([2, 4, 6]), [0, 0.5, 1])
        self.assertEqual(normalise_scores([0, 0]), [1, 1])
        self.assertEqual(hybrid_search("x", [], []), [])

    def test_parser_malformed_json(self):
        with self.assertRaises(ValueError):
            parse_action({"id": "x", "function": {"name": "search_documents", "arguments": '{"query":'}})

    def test_write_requires_analysis_and_user_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Service("offline", Path(tmp) / "test.sqlite", True, "key")
            with self.assertRaises(ValueError):
                service.create(RequestArgs("P001", "2026-10-08"))
            service.analyze(AnalysisArgs("P001", "2026-10-08"))
            service.allow_write = False
            with self.assertRaises(ValueError):
                service.create(RequestArgs("P001", "2026-10-08"))

    def test_sqlite_write_read_and_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.sqlite"
            service = Service("offline", path, True, "key")
            service.analyze(AnalysisArgs("P001", "2026-10-08"))
            first = service.create(RequestArgs("P001", "2026-10-08"))
            second = service.create(RequestArgs("P001", "2026-10-08"))
            self.assertEqual(first, second)
            self.assertEqual(service.store.get(first["record"]["request_id"]), first["record"])
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)

    def test_nonrisk_or_missing_never_writes(self):
        for project in ("P002", "P003", "P004"):
            with tempfile.TemporaryDirectory() as tmp:
                service = Service("offline", Path(tmp) / "test.sqlite", True, "key")
                service.analyze(AnalysisArgs(project, "2026-10-08"))
                with self.assertRaises(ValueError):
                    service.create(RequestArgs(project, "2026-10-08"))

    def test_http_401_no_retry(self):
        response = httpx.Response(401, request=httpx.Request("POST", "https://example.test"))
        with patch("httpx.Client.post", return_value=response) as send:
            with self.assertRaises(RuntimeError):
                post_json("https://example.test", "test-credential", {}, scope="test")
            self.assertEqual(send.call_count, 1)

    def test_http_429_retry_then_success(self):
        req = httpx.Request("POST", "https://example.test")
        with patch("httpx.Client.post", side_effect=[httpx.Response(429, request=req), httpx.Response(200, json={"ok": True}, request=req)]) as send, patch("time.sleep"):
            self.assertEqual(post_json("https://example.test", "test-credential", {}, scope="test"), {"ok": True})
            self.assertEqual(send.call_count, 2)

    def test_http_429_honors_retry_after(self):
        req = httpx.Request("POST", "https://example.test")
        with patch("httpx.Client.post", side_effect=[httpx.Response(429, request=req, headers={"retry-after": "12"}), httpx.Response(200, json={"ok": True}, request=req)]), patch("time.sleep") as wait:
            self.assertEqual(post_json("https://example.test", "test-credential", {}, scope="test"), {"ok": True})
            wait.assert_called_once_with(12)

    def test_local_final_schema_is_typed_and_not_a_mcp_action(self):
        schema = tool_schema(Answer)
        self.assertEqual(schema["properties"]["citations"], {"type": "array", "items": {"type": "string"}})
        final = json.dumps({"status": "ok", "answer": "Minh", "citations": ["D1"], "facts": {"owner": "Minh"}})
        response = {"usage": {"prompt_tokens": 12, "completion_tokens": 8}, "choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "f", "function": {"name": "final_answer", "arguments": final}}]}}]}
        with tempfile.TemporaryDirectory() as tmp, patch("src.api.post_json", return_value=response) as send:
            model = LiveModel(Trace(Path(tmp) / "trace.jsonl", "offline"))
            message = model.complete([], [{"type": "function", "function": {"name": "search_documents"}}])
        self.assertEqual(message["content"], final)
        self.assertNotIn("tool_calls", message)
        self.assertEqual(send.call_args.args[2]["tools"][-1]["function"]["name"], "final_answer")
        self.assertEqual(send.call_args.args[2]["tool_choice"], "required")
        self.assertEqual(model.usage.prompt_tokens, 12)

    def test_runtime_reads_only_explicit_file_and_preserves_shell(self):
        from src.runtime import load_runtime_env
        with tempfile.TemporaryDirectory() as tmp, patch("src.runtime.ROOT", Path(tmp)), patch.dict("os.environ", {"GROQ_API_KEY": "shell-test-value"}, clear=True):
            (Path(tmp) / ".env").write_text("GROQ_API_KEY=file-test-value\nJINA_API_KEY=embedding-test-value\nUNRELATED_KEY=ignored\n", encoding="utf-8")
            load_runtime_env()
            import os
            self.assertEqual(os.getenv("GROQ_API_KEY"), "shell-test-value")
            self.assertEqual(os.getenv("JINA_API_KEY"), "embedding-test-value")
            self.assertIsNone(os.getenv("UNRELATED_KEY"))

    def test_json_repair_preserves_tool_history_without_native_calls(self):
        messages = [{"role": "system", "content": "Return JSON"}, {"role": "assistant", "tool_calls": [{"id": "t1", "function": {"name": "analyze_progress", "arguments": "{}"}}]}, {"role": "tool", "tool_call_id": "t1", "content": '{"actual_progress":48}'}]
        response = {"usage": {"prompt_tokens": 12, "completion_tokens": 8}, "choices": [{"message": {"role": "assistant", "content": '{}'}}]}
        with tempfile.TemporaryDirectory() as tmp, patch("src.api.post_json", return_value=response) as send:
            LiveModel(Trace(Path(tmp) / "trace.jsonl", "offline")).complete(messages)
        body = send.call_args.args[2]
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertFalse(any(m["role"] == "tool" or m.get("tool_calls") for m in body["messages"]))
        self.assertIn("analyze_progress", body["messages"][1]["content"])
        self.assertIn('"actual_progress":48', body["messages"][2]["content"])


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_task_version_difference_does_not_require_project_analysis(self):
        class ToolStub:
            schemas = []
            inventory = {"get_document": SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=True))}
            async def call(self, name, args):
                return json.dumps({"doc_id": args["doc_id"], "actual": {"T02": 50 if args["doc_id"] == "OLD" else 60}})
        class ModelStub:
            count = 0
            def complete(self, messages, tools, tool_choice="auto"):
                self.count += 1
                if self.count <= 2:
                    return {"role": "assistant", "tool_calls": [{"id": str(self.count), "function": {"name": "get_document", "arguments": json.dumps({"doc_id": "OLD" if self.count == 1 else "NEW"})}}]}
                return {"role": "assistant", "content": json.dumps({"status": "ok", "answer": "T02 đổi giữa hai bản.", "citations": ["OLD", "NEW"], "facts": {"old_T02": 50, "new_T02": 60, "task_change_pp": 10}})}
        with tempfile.TemporaryDirectory() as tmp:
            result = await run_agent("compare versions", ToolStub(), ModelStub(), "dense", False, Trace(Path(tmp) / "trace.jsonl", "offline"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["facts"]["task_change_pp"], 10)

    async def test_final_json_retry_keeps_retrieved_evidence(self):
        class ToolStub:
            schemas = [{"function": {"name": "search_documents"}}]
            inventory = {"search_documents": SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=True))}
            async def call(self, name, args):
                return json.dumps({"chunks": [{"metadata": {"doc_id": "D1"}, "text": "Owner Minh"}]})
        class ModelStub:
            count = 0
            def complete(self, messages, tools, tool_choice="auto"):
                self.count += 1
                if self.count == 1:
                    raise RuntimeError("HTTP 400, code=tool_use_failed")
                assert tools is not None  # Retrieval must not disable business tools.
                assert any("Owner Minh" in m.get("content", "") for m in messages)
                return {"role": "assistant", "content": json.dumps({"status": "ok", "answer": "Owner Minh", "citations": ["D1"], "facts": {"owner": "Minh"}})}
        with tempfile.TemporaryDirectory() as tmp:
            model = ModelStub()
            result = await run_agent("test", ToolStub(), model, "dense", False, Trace(Path(tmp) / "trace.jsonl", "offline"))
        self.assertEqual(model.count, 2)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["citations"], ["D1"])

    async def test_project_numbers_require_analysis_and_match_it(self):
        class ToolStub:
            inventory = {"analyze_progress": SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=True))}
            schemas = []
            async def call(self, name, args):
                return json.dumps({"status": "ok", "sources": [{"doc_id": "D1"}], "actual_progress": 75, "planned_progress": 70, "behind_pp": -5, "risk": False})
        class ModelStub:
            count = 0
            def complete(self, messages, tools, tool_choice="auto"):
                step = self.count
                self.count += 1
                if step == 1:
                    return {"role": "assistant", "tool_calls": [{"id": "a", "function": {"name": "analyze_progress", "arguments": "{}"}}]}
                facts = {"actual_progress": {"T03": 50}, "risk": False} if step == 0 else {"actual_progress": 75, "behind_pp": 0 if step == 2 else -5, "risk": False}
                return {"role": "assistant", "content": json.dumps({"status": "ok", "answer": "Không có rủi ro theo quy tắc.", "citations": [] if step == 0 else ["D1"], "facts": facts})}
        with tempfile.TemporaryDirectory() as tmp:
            model = ModelStub()
            result = await run_agent("test", ToolStub(), model, "dense", False, Trace(Path(tmp) / "trace.jsonl", "offline"))
        self.assertEqual(model.count, 4)
        self.assertEqual(result["facts"]["behind_pp"], -5)

    async def test_provider_rejected_tool_action_can_recover(self):
        class ModelStub:
            count = 0
            def complete(self, messages, tools, tool_choice="auto"):
                self.count += 1
                if self.count == 1:
                    raise RuntimeError("llm: HTTP 400, code=tool_use_failed")
                assert messages[-1]["content"].startswith("Error:")
                return {"role": "assistant", "content": json.dumps({"status": "no_answer", "answer": "Không có dữ liệu.", "citations": [], "facts": {}})}
        with tempfile.TemporaryDirectory() as tmp:
            model = ModelStub()
            result = await run_agent("test", SimpleNamespace(schemas=[], inventory={}), model, "dense", False, Trace(Path(tmp) / "trace.jsonl", "offline"))
        self.assertEqual(model.count, 2)
        self.assertEqual(result["status"], "no_answer")

    async def test_retrieval_gate_config_top_k_and_progress_unit(self):
        called = []
        class ToolStub:
            inventory = {n: SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=True)) for n in ("search_documents", "analyze_progress")}
            schemas = [{"function": {"name": n}} for n in inventory]
            async def call(self, name, args):
                called.append(name)
                if name == "search_documents":
                    self_check = args["top_k"]
                    from src.api import CONFIG
                    assert self_check == CONFIG["top_k"]
                return json.dumps({"status": "ok", "sources": [{"doc_id": "D1"}], "behind_pp": 22})
        class ModelStub:
            count = 0
            def complete(self, messages, tools, tool_choice="auto"):
                step = self.count
                self.count += 1
                assert tool_choice == "auto"
                if step == 0:
                    return {"role": "assistant", "tool_calls": [{"id": "a", "function": {"name": "analyze_progress", "arguments": "{}"}}]}
                return {"role": "assistant", "content": json.dumps({"status": "ok", "answer": "Chậm 22%." if step == 1 else "Chậm 22 điểm phần trăm.", "citations": ["D1"], "facts": {"behind_pp": 22}})}
        with tempfile.TemporaryDirectory() as tmp:
            model = ModelStub()
            result = await run_agent("test", ToolStub(), model, "dense", False, Trace(Path(tmp) / "trace.jsonl", "offline"))
        self.assertEqual(called, ["search_documents", "analyze_progress"])
        self.assertEqual(model.count, 3)
        self.assertEqual(result["status"], "ok")
        self.assertIn("điểm phần trăm", result["answer"])

    async def test_invalid_final_shape_recovers_without_crashing(self):
        valid = {"status": "no_answer", "answer": "Không có dữ liệu.", "citations": [], "facts": {}}
        for invalid in ([], {**valid, "facts": None}, {**valid, "citations": [{}]}):
            class ModelStub:
                count = 0
                def complete(self, messages, tools, tool_choice="auto"):
                    self.count += 1
                    if self.count == 2:
                        self_check = messages[-1]["content"]
                        assert self_check.startswith("Error:")
                    return {"role": "assistant", "content": json.dumps(invalid if self.count == 1 else valid)}
            with tempfile.TemporaryDirectory() as tmp:
                model = ModelStub()
                result = await run_agent("test", SimpleNamespace(schemas=[], inventory={}), model, "dense", False, Trace(Path(tmp) / "trace.jsonl", "offline"))
            self.assertEqual(result["status"], "no_answer")
            self.assertEqual(model.count, 2)

    async def test_real_stdio_discovery_schema_error_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp) / "trace.jsonl", "offline")
            async with connect("offline", Path(tmp) / "db.sqlite", False, "test", trace) as tools:
                self.assertEqual(len(tools.inventory), 5)
                self.assertTrue((await tools.call("missing", {})).startswith("Error:"))
                self.assertTrue((await tools.call("analyze_progress", {"project_id": 123, "as_of_date": "2026-10-08"})).startswith("Error:"))
                self.assertTrue((await tools.call("get_followup_request", {"request_id": "missing"})).startswith("Error:"))
                result = json.loads(await tools.call("analyze_progress", {"project_id": "P001", "as_of_date": "2026-10-08"}))
                self.assertEqual(result["actual_progress"], 48)

    async def test_immediate_verify_and_failed_verify(self):
        for fail in (False, True):
            record = {"request_id": "r1", "project_id": "P001"}
            calls = []
            class ToolStub:
                schemas = []
                inventory = {"write": SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=False)), "read": SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=True))}
                async def call(self, name, args):
                    calls.append(name)
                    if name == "write":
                        return json.dumps({"record": record, "verification": {"tool_name": "read", "arguments": {"request_id": "r1"}}})
                    return "Error: unavailable" if fail else json.dumps(record)
            class ModelStub:
                count = 0
                def complete(self, messages, tools, tool_choice="auto"):
                    self.count += 1
                    if self.count == 1:
                        return {"role": "assistant", "content": None, "tool_calls": [{"id": "t1", "function": {"name": "write", "arguments": "{}"}}]}
                    return {"role": "assistant", "content": json.dumps({"status": "action_failed" if fail else "no_answer", "answer": "test", "citations": [], "facts": {}})}
            with tempfile.TemporaryDirectory() as tmp:
                result = await run_agent("test", ToolStub(), ModelStub(), "dense", True, Trace(Path(tmp) / "trace.jsonl", "offline"))
            self.assertEqual(calls, ["write", "read"])
            self.assertEqual(result["verified"], not fail)

    async def test_max_steps_returns_controlled_error(self):
        class ToolStub:
            schemas = []
            inventory = {"search": SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=True))}
            async def call(self, name, args):
                return "{}"
        class ModelStub:
            def complete(self, messages, tools, tool_choice="auto"):
                return {"role": "assistant", "tool_calls": [{"id": "t", "function": {"name": "search", "arguments": "{}"}}]}
        with tempfile.TemporaryDirectory() as tmp:
            result = await run_agent("test", ToolStub(), ModelStub(), "dense", False, Trace(Path(tmp) / "trace.jsonl", "offline"), max_steps=2)
        self.assertEqual(result["status"], "error")
        self.assertIn("MAX_STEPS", result["answer"])


if __name__ == "__main__":
    unittest.main()
