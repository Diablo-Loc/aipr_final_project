import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.eval import rows_from_log, resume_candidate, snapshot_signature, evaluate


class EvaluationLogTests(unittest.TestCase):
    def test_judge_cost_survives_failure_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            path = root / "logs/eval_offline_test.jsonl"
            events = [
                {"event": "run_start", "test_count": 1, "modes": ["dense"]},
                {"event": "query_start"},
                {"event": "USAGE", "query_id": "dense:Q18:0", "usage_scope": "agent", "calls": 1, "prompt_tokens": 40, "completion_tokens": 4, "max_prompt": 40, "attempts": 1},
                {"event": "query_start"},  # A second repeat does not become judge usage.
                {"event": "llm", "model": "test-agent", "usage": {"prompt_tokens": 100, "completion_tokens": 10}},
                {"event": "USAGE", "query_id": "dense:Q18:1", "usage_scope": "agent", "calls": 1, "prompt_tokens": 100, "completion_tokens": 10, "max_prompt": 100, "attempts": 2},
                {"event": "http_attempt", "scope": "llm"},
                {"event": "http_attempt", "scope": "llm"},
                {"event": "llm", "model": "test-judge", "usage": {"prompt_tokens": 17, "completion_tokens": 3}},
                {"event": "judge_error"},  # Tokens count even if its JSON could not be parsed.
                {"event": "evaluation", "backend": "offline", "mode": "dense", "query_id": "Q18"},
                {"event": "run_end"},
            ]
            path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            with patch("scripts.eval.ROOT", root):
                row = rows_from_log(path, "offline")[0]
            self.assertEqual((row["judge_calls"], row["judge_prompt_tokens"], row["judge_completion_tokens"], row["judge_attempts"]), (1, 17, 3, 2))
            self.assertEqual((row["calls"], row["prompt_tokens"], row["max_prompt"], row["attempts"]), (2, 140, 100, 3))

    def test_resume_only_incomplete_matching_snapshot_including_failed_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            path = root / "logs/eval_live_test.jsonl"
            events = [{"event": "run_start", "run_id": "test", "snapshot_signature": "abc"}, {"event": "evaluation", "mode": "dense", "query_id": "Q09", "functional_pass": False}]
            path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            with patch("scripts.eval.ROOT", root):
                self.assertIsNone(resume_candidate("live", "different-code"))
                self.assertEqual(resume_candidate("live", "abc")[2], {("dense", "Q09")})
                with path.open("a", encoding="utf-8") as f:
                    f.write('\n{"event":"run_end"}')
                self.assertIsNone(resume_candidate("live", "abc"))

    def test_snapshot_signature_detects_prompt_and_data_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("src/a.py", "templates/agent.txt", "data/corpus.jsonl", "tests/testset.jsonl", "config.json", "requirements.lock.txt", "scripts/eval.py"):
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_text("test fixture", encoding="utf-8")
            with patch("scripts.eval.ROOT", root), patch("scripts.eval.__file__", str(root / "scripts/eval.py")):
                initial = snapshot_signature()
                (root / "templates/agent.txt").write_text("changed prompt", encoding="utf-8")
                self.assertNotEqual(initial, snapshot_signature())
                (root / "templates/agent.txt").write_text("test fixture", encoding="utf-8")
                (root / "data/corpus.jsonl").write_text("changed data", encoding="utf-8")
                self.assertNotEqual(initial, snapshot_signature())

    def test_incomplete_log_is_not_a_complete_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            path = root / "logs/eval_offline_test.jsonl"
            path.write_text(json.dumps({"event": "run_start", "test_count": 20, "modes": ["dense", "hybrid"]}), encoding="utf-8")
            with patch("scripts.eval.ROOT", root), self.assertRaises(ValueError):
                rows_from_log(path, "offline")


class ResumeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_judge_quota_checkpoint_preserves_cost_when_resumed(self):
        interrupted = False
        async def ask_stub(query, backend, mode, allow_write, trace, query_id, key, db):
            trace.query_id = query_id
            trace.emit("query_start")
            usage = {"calls": 1, "prompt_tokens": 10, "completion_tokens": 2, "max_prompt": 10, "attempts": 1}
            trace.emit("USAGE", usage_scope="agent", **usage)
            return {"status": "ok", "facts": {}, "citations": ["D1"], "verified": False}, usage
        def judge_stub(result, query, trace):
            nonlocal interrupted
            trace.emit("http_attempt", scope="llm")
            if not interrupted:
                interrupted = True
                raise RuntimeError("rate limit requires 644 seconds")
            trace.emit("llm", model="test-judge", usage={"prompt_tokens": 17, "completion_tokens": 3})
            return {"faithfulness": 1.0, "citation_support": True, "refusal_valid": False}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            case = {"id": "C01", "query": "test", "category": "lookup", "expected_status": "ok", "expected_facts": {}, "expected_sources": ["D1"], "repeat": 1, "allow_write": False}
            (root / "tests/testset.jsonl").write_text(json.dumps(case), encoding="utf-8")
            with patch("scripts.eval.ROOT", root), patch("scripts.eval.snapshot_signature", return_value="stable-snapshot"), patch("scripts.eval.ask", side_effect=ask_stub), patch("scripts.eval.judge", side_effect=judge_stub), patch("scripts.eval.write_results") as output:
                with self.assertRaises(SystemExit):
                    await evaluate("live", 1)
                output.assert_not_called()
                await evaluate("live", 1)
                dense = next(r for r in output.call_args.args[2] if r["mode"] == "dense")
        self.assertEqual((dense["calls"], dense["prompt_tokens"], dense["judge_attempts"], dense["judge_calls"]), (2, 20, 2, 1))

    async def test_resume_skips_finished_cases_and_completes_same_log(self):
        calls, interrupted = [], False
        async def ask_stub(query, backend, mode, allow_write, trace, query_id, key, db):
            nonlocal interrupted
            calls.append(query_id)
            trace.query_id = query_id
            trace.emit("query_start")
            if query_id == "dense:C02:0" and not interrupted:
                interrupted = True
                raise SystemExit("quota unavailable")
            usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "max_prompt": 0, "attempts": 0}
            trace.emit("USAGE", usage_scope="agent", **usage)
            return {"status": "no_answer", "facts": {}, "citations": [], "verified": False}, usage
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            cases = [{"id": name, "query": name, "category": "no_answer", "expected_status": "no_answer", "expected_facts": {}, "expected_sources": [], "repeat": 1, "allow_write": False} for name in ("C01", "C02")]
            (root / "tests/testset.jsonl").write_text("\n".join(json.dumps(c) for c in cases), encoding="utf-8")
            with patch("scripts.eval.ROOT", root), patch("scripts.eval.snapshot_signature", return_value="stable-snapshot"), patch("scripts.eval.ask", side_effect=ask_stub), patch("scripts.eval.write_results") as output:
                with self.assertRaises(SystemExit):
                    await evaluate("offline", 1)
                await evaluate("offline", 1)
                rows = output.call_args.args[2]
                self.assertEqual(len(rows), 4)
                self.assertTrue(all(r["functional_pass"] for r in rows))
                self.assertEqual(len(list((root / "logs").glob("*.jsonl"))), 1)
        self.assertEqual(calls.count("dense:C01:0"), 1)
        self.assertEqual(calls.count("dense:C02:0"), 2)


if __name__ == "__main__":
    unittest.main()
