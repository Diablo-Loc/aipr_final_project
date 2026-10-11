"""Regression cases for the external audit; no real API or credentials."""
import asyncio
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from mcp.types import ToolAnnotations
from src.agent import run_agent
from src.api import Embedder, Trace
from src.data import Corpus
from src.models import AnalysisArgs
from scripts.eval import functional_score, judge, rows_from_log, write_results, evaluate


class AuditTests(unittest.TestCase):
    def write_corpus(self, root, docs):
        path = root / "corpus.jsonl"
        path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in docs), encoding="utf-8")
        return Corpus(path)

    def test_independent_meetings_are_kept(self):
        docs = [asdict(d) for d in Corpus().docs]
        meeting = json.loads(json.dumps(next(d for d in docs if d["metadata"]["kind"] == "meeting")))
        meeting["metadata"]["doc_id"] = "P001-MEETING-OTHER"
        docs.append(meeting)
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.write_corpus(Path(tmp), docs)
            ids = {d.metadata["doc_id"] for d in corpus.eligible("P001", "2026-10-08")}
        self.assertTrue({"P001-MEETING", "P001-MEETING-OTHER"} <= ids)

    def test_same_day_independent_snapshots_are_a_conflict(self):
        docs = [asdict(d) for d in Corpus().docs]
        snapshot = json.loads(json.dumps(next(d for d in docs if d["metadata"]["doc_id"] == "P001-W2-V2")))
        snapshot["metadata"]["doc_id"] = "P001-CONFLICT"
        snapshot["records"]["supersedes"] = ""
        snapshot["content"] = snapshot["content"].replace('supersedes: "P001-W2-V1"', 'supersedes: ""')
        docs.append(snapshot)
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.write_corpus(Path(tmp), docs)
            with self.assertRaisesRegex(ValueError, "Document conflict"):
                corpus.analyze(AnalysisArgs("P001", "2026-10-08"))

    def test_competing_replacements_and_missing_parent_are_rejected(self):
        for parent in ("P001-W2-V1", "NOT-EXISTS"):
            docs = [asdict(d) for d in Corpus().docs]
            duplicate = json.loads(json.dumps(next(d for d in docs if d["metadata"]["doc_id"] == "P001-W2-V2")))
            duplicate["metadata"]["doc_id"] = "P001-OTHER-V2"
            duplicate["records"]["supersedes"] = parent
            duplicate["content"] = duplicate["content"].replace('supersedes: "P001-W2-V1"', f'supersedes: "{parent}"')
            docs.append(duplicate)
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                self.write_corpus(Path(tmp), docs)

    def test_content_records_mismatch_is_rejected(self):
        docs = [asdict(d) for d in Corpus().docs]
        docs[1]["records"]["threshold_pp"] = 25
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "Content/records mismatch"):
            self.write_corpus(Path(tmp), docs)

    def test_duplicate_record_text_is_rejected(self):
        docs = [asdict(d) for d in Corpus().docs]
        docs[1]["content"] = "threshold_pp: 25\n" + docs[1]["content"]
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "Content/records mismatch"):
            self.write_corpus(Path(tmp), docs)

    def test_setup_rejects_unverified_python_before_installing(self):
        import run
        for version in ((3, 10, 0), (3, 12, 0), (3, 14, 0)):
            with patch("run.sys.version_info", version), patch("run.subprocess.run") as execute:
                with self.assertRaisesRegex(SystemExit, "Python 3.11"):
                    run.setup()
                execute.assert_not_called()

    def assess(self, result, claims):
        response = {"content": json.dumps({"claims": claims})}
        with tempfile.TemporaryDirectory() as tmp, patch("src.api.LiveModel.complete", return_value=response):
            return judge(result, "test", Trace(Path(tmp) / "trace.jsonl", "offline"))

    def test_hallucinated_refusal_fails_but_pure_refusal_has_no_claims(self):
        result = {"status": "no_answer", "answer": "Ngân sách là 100 triệu, nhưng chưa đủ thông tin.", "facts": {}, "citations": [], "observations": []}
        assessment = self.assess(result, [{"claim": "Ngân sách là 100 triệu", "supported": False, "citation_supported": False, "source_ids": []}])
        case = {"expected_status": "no_answer", "expected_facts": {}}
        self.assertFalse(functional_score(result, case, assessment))
        self.assertEqual(assessment["faithfulness"], 0)
        result["answer"] = "Không có dữ liệu ngân sách trong các nguồn đã đọc."
        assessment = self.assess(result, [])
        self.assertTrue(functional_score(result, case, assessment))
        self.assertIsNone(assessment["faithfulness"])
        result["facts"] = {"budget": 100}
        self.assertFalse(functional_score(result, case))

    def test_supported_claim_with_wrong_citation_is_rejected(self):
        result = {"status": "ok", "answer": "Minh phụ trách T02", "facts": {"owner": "Minh"}, "citations": ["MEETING"], "observations": [{"doc_id": "PLAN", "text": "Minh phụ trách T02"}, {"doc_id": "MEETING", "text": "Biên bản khác"}]}
        assessment = self.assess(result, [{"claim": "Minh phụ trách T02", "supported": True, "citation_supported": True, "source_ids": ["PLAN"]}])
        self.assertEqual(assessment["faithfulness"], 1)
        self.assertFalse(assessment["citation_support"])

    def test_factual_answer_without_extracted_claims_is_not_source_verified(self):
        result = {"status": "ok", "answer": "Minh", "facts": {}, "citations": ["PLAN"], "observations": [{"doc_id": "PLAN"}]}
        self.assertFalse(self.assess(result, [])["citation_support"])

    def test_embedding_http_and_cache_trace(self):
        response = {"data": [{"index": 0, "embedding": [1, 0]}], "usage": {"total_tokens": 7}}
        def send(url, key, body, trace, scope):
            self.assertEqual(scope, "embedding")
            trace.emit("http_attempt", scope=scope, attempt=1)
            trace.emit("http", scope=scope, status=200)
            return response
        with tempfile.TemporaryDirectory() as tmp, patch("src.api.ROOT", Path(tmp)), patch("src.api.post_json", side_effect=send):
            trace = Trace(Path(tmp) / "trace.jsonl", "live")
            embedder = Embedder("live", trace)
            embedder.embed(["example"], "retrieval.query")
            embedder.embed(["example"], "retrieval.query")
            events = [json.loads(line) for line in trace.path.read_text(encoding="utf-8").splitlines()]
        usage = [e for e in events if e["event"] == "EMBEDDING_USAGE"]
        self.assertEqual((usage[0]["calls"], usage[0]["tokens"], usage[0]["attempts"]), (1, 7, 1))
        self.assertEqual((usage[1]["calls"], usage[1]["cache_hits"]), (0, 1))

    def test_log_uses_original_configuration_and_embedding_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            path = root / "logs/eval_offline_original.jsonl"
            config = {"top_k": 2, "max_steps": 4, "embedding_model": "original-model"}
            events = [
                {"event": "run_start", "configuration": config, "test_count": 1, "modes": ["dense"]},
                {"event": "http_attempt", "scope": "embedding", "query_id": "dense:Q01:0"},
                {"event": "EMBEDDING_USAGE", "query_id": "dense:Q01:0", "calls": 1, "tokens": 7, "cache_hits": 0},
                {"event": "evaluation", "backend": "offline", "mode": "dense", "query_id": "Q01"},
                {"event": "run_end"},
            ]
            path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            with patch("scripts.eval.ROOT", root):
                row = rows_from_log(path, "offline")[0]
            self.assertEqual(json.loads(row["run_configuration"]), config)
            self.assertEqual((row["embedding_calls"], row["embedding_tokens"], row["embedding_attempts"]), (1, 7, 1))
            events[0].pop("configuration")
            path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            with patch("scripts.eval.ROOT", root):
                self.assertEqual(rows_from_log(path, "offline")[0]["run_configuration"], "null")

    def test_summary_does_not_substitute_current_config_for_logged_config(self):
        config = {"top_k": 2, "max_steps": 4, "embedding_model": "original"}
        base = {"run_id": "fixture", "agent_model": "", "judge_model": "", "run_configuration": json.dumps(config), "category": "lookup", "actual_status": "ok", "expected_status": "ok", "functional_pass": True, "source_complete": True, "citation_support": None, "faithfulness": None, "judge_error": "", "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "embedding_trace_available": True}
        base.update({"judge_" + k: 0 for k in ("calls", "prompt_tokens", "completion_tokens")})
        base.update({"embedding_" + k: 0 for k in ("calls", "tokens", "cache_hits", "attempts")})
        rows = [{**base, "mode": mode} for mode in ("dense", "hybrid")]
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.eval.ROOT", Path(tmp)), patch.dict("scripts.eval.CONFIG", {"top_k": 99}):
            write_results("offline", 1, rows)
            summary = json.loads((Path(tmp) / "results/offline/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["configuration"], config)


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_refusal_content_is_judged_and_not_counted_as_correct(self):
        async def ask_stub(query, backend, mode, allow_write, trace, query_id, key, db):
            trace.query_id = query_id
            usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "max_prompt": 0, "attempts": 0}
            trace.emit("USAGE", usage_scope="agent", **usage)
            return {"status": "no_answer", "answer": "100 triệu nhưng chưa đủ thông tin", "facts": {}, "citations": [], "verified": False}, usage
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            case = {"id": "C1", "query": "budget", "category": "no_answer", "expected_status": "no_answer", "expected_facts": {}, "expected_sources": [], "repeat": 1, "allow_write": False}
            (root / "tests/testset.jsonl").write_text(json.dumps(case), encoding="utf-8")
            with patch("scripts.eval.ROOT", root), patch("scripts.eval.snapshot_signature", return_value="audit-test"), patch("scripts.eval.ask", side_effect=ask_stub), patch("scripts.eval.judge", return_value={"faithfulness": 0, "citation_support": False, "refusal_valid": False}) as assessor:
                await evaluate("live", 1)
                summary = json.loads((root / "results/live/summary.json").read_text(encoding="utf-8"))
            self.assertEqual(assessor.call_count, 2)
            for values in summary["modes"].values():
                self.assertEqual(values["correct_refusal_rate"], 0)
                self.assertEqual(values["functional_accuracy"], 0)

    async def test_provider_error_after_retrieval_keeps_analysis_and_write_available(self):
        calls = []
        class Tools:
            schemas = [{"type": "function"}]
            inventory = {name: SimpleNamespace(annotations=ToolAnnotations(readOnlyHint=name != "create_followup_request")) for name in ("search_documents", "analyze_progress", "create_followup_request", "get_followup_request")}
            async def call(self, name, args):
                calls.append(name)
                if name == "search_documents":
                    return json.dumps({"chunks": [{"metadata": {"doc_id": "D1"}}]})
                if name == "analyze_progress":
                    return json.dumps({"status": "ok", "behind_pp": 22, "sources": [{"doc_id": "D1"}]})
                record = {"request_id": "r1"}
                if name == "create_followup_request":
                    return json.dumps({"record": record, "verification": {"tool_name": "get_followup_request", "arguments": {"request_id": "r1"}}})
                return json.dumps(record)
        class Model:
            count = 0
            def complete(self, messages, tools):
                self.count += 1
                if self.count in (1, 3):
                    raise RuntimeError("HTTP 400, code=tool_use_failed")
                self_test.assertIsNotNone(tools)
                if self.count in (2, 4):
                    name = "analyze_progress" if self.count == 2 else "create_followup_request"
                    return {"role": "assistant", "tool_calls": [{"id": str(self.count), "function": {"name": name, "arguments": "{}"}}]}
                return {"role": "assistant", "content": json.dumps({"status": "action_verified", "answer": "Đã lưu", "facts": {"request_id": "r1", "behind_pp": 22}, "citations": ["D1"]})}
        self_test = self
        with tempfile.TemporaryDirectory() as tmp:
            result = await run_agent("write", Tools(), Model(), "dense", True, Trace(Path(tmp) / "trace.jsonl", "offline"))
        self.assertEqual(result["status"], "action_verified")
        self.assertEqual(calls, ["search_documents", "analyze_progress", "create_followup_request", "get_followup_request"])


if __name__ == "__main__":
    unittest.main()
