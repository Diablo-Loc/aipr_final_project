"""Reproducible two-mode evaluation. Offline rows never claim LLM faithfulness."""
import argparse
import asyncio
import csv
import json
import math
import os
import uuid
import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.api import Trace, LiveModel, CONFIG, run_configuration
from src.cli import ask
from src.agent import source_ids

def same(actual, expected):
    if isinstance(expected, bool):
        return type(actual) is bool and actual == expected
    if isinstance(expected, (float, int)):
        return isinstance(actual, (float, int)) and not isinstance(actual, bool) and math.isclose(actual, expected, abs_tol=0.01)
    return actual == expected

def functional_score(result, case, assessment=None):
    if result["status"] in ("no_answer", "insufficient_data"):
        if result.get("facts") or (assessment is not None and not assessment["refusal_valid"]):
            return False
    return result["status"] == case["expected_status"] and all(same(result.get("facts", {}).get(k),v) for k, v in case["expected_facts"].items())

def judge(result, query, trace):
    model = LiveModel(trace, os.getenv("JUDGE_MODEL", CONFIG["judge_model"]))
    system = (ROOT / "templates/judge.txt").read_text(encoding="utf-8")
    content = {
        "query": query, 
        "context": result["observations"], 
        "status": result["status"], 
        "answer": result["answer"], 
        "facts": result["facts"], 
        "citations": result["citations"]
    }
    response = model.complete([{"role": "system", "content": system}, {"role": "user", "content": json.dumps(content, ensure_ascii=False)}])
    text = response.get("content", "").strip().removeprefix("```json").removesuffix("```").strip()
    assessment = json.loads(text)
    claims = assessment["claims"]
    if not isinstance(claims, list):
        raise ValueError("Invalid judge claim schema")
    for claim in claims:
        if (not isinstance(claim, dict) or not isinstance(claim.get("claim"), str)
            or type(claim.get("supported")) is not bool
            or type(claim.get("citation_supported")) is not bool
            or not isinstance(claim.get("source_ids"), list)
            or any(not isinstance(s, str) for s in claim["source_ids"])):
            
            raise ValueError("Invalid judge claim schema")
    
    observed, cited = source_ids(result["observations"]), set(result["citations"])
    
    for claim in claims:
        ids = set(claim["source_ids"])
        claim["citation_supported"] = claim["supported"] and claim["citation_supported"] and bool(ids) and ids <= observed & cited
    
    refusal = result["status"] in ("no_answer", "insufficient_data")
    faithfulness = sum(c["supported"] for c in claims) / len(claims) if claims else None
    citation_support = all(c["citation_supported"] for c in claims) if claims else (True if refusal else False)
    refusal_valid = refusal and not result["facts"] and citation_support
    
    trace.emit("judge", assessment=assessment, usage= asdict(model.usage), usage_scope="eval_judge")
    return {"faithfulness": faithfulness, "citation_support": citation_support, "refusal_valid": refusal_valid} 


# === PHẦN 2 (HẠ TẦNG ĐỌC/GHI LOG, RESUME, XUẤT CSV & BIỂU ĐỒ - ĐÃ COPY SẴN) ===
def snapshot_signature():
    paths = [*sorted((ROOT / "src").glob("*.py")), *sorted((ROOT / "templates").glob("*.txt")), ROOT / "data/corpus.jsonl", ROOT / "tests/testset.jsonl", ROOT / "config.json", ROOT / "requirements.lock.txt", Path(__file__)]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    digest.update(json.dumps({name: os.getenv(name, CONFIG[field]) for name, field in (("LLM_MODEL", "llm_model"), ("JUDGE_MODEL", "judge_model"), ("EMBEDDING_MODEL", "embedding_model"))}, sort_keys=True).encode())
    return digest.hexdigest()


def resume_candidate(backend, signature):
    for path in sorted((ROOT / "logs").glob(f"eval_{backend}_*.jsonl"), reverse=True):
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        start = next((e for e in events if e["event"] == "run_start"), {})
        if start.get("snapshot_signature") == signature and not any(e["event"] == "run_end" for e in events):
            return path, start["run_id"], {(e["mode"], e["query_id"]) for e in events if e["event"] == "evaluation"}
    return None


async def evaluate(backend: str, runs: int):
    cases = [json.loads(line) for line in (ROOT / "tests/testset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    run_paths = []
    signature = snapshot_signature()
    for _ in range(runs):
        resume = resume_candidate(backend, signature)
        if resume:
            path, stamp, completed = resume
            trace = Trace(path, backend)
            trace.emit("run_resumed", completed_cases=len(completed), snapshot_signature=signature)
            print(f"Resuming {path.name}: {len(completed)}/{len(cases) * 2} cases already evaluated", flush=True)
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "_" + uuid.uuid4().hex[:6]
            trace = Trace(ROOT / "logs" / f"eval_{backend}_{stamp}.jsonl", backend)
            completed = set()
            trace.emit("run_start", run_id=stamp, modes=["dense", "hybrid"], test_count=len(cases), mock_llm=backend != "live", snapshot_signature=signature, configuration=run_configuration())
        run_paths.append(trace.path)
        for mode in ("dense", "hybrid"):
            for case in cases:
                if (mode, case["id"]) in completed:
                    continue
                db = ROOT / "state" / f"eval_{stamp}_{mode}_{case['id']}.sqlite"
                key = f"{stamp}:{mode}:{case['id']}"
                result, usage = None, {}
                repeat_ids = []
                combined_usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "max_prompt": 0, "attempts": 0}
                for repeat in range(case["repeat"]):
                    result, usage = await ask(case["query"], backend, mode, case["allow_write"], trace, f"{mode}:{case['id']}:{repeat}", key, db)
                    repeat_ids.append(result.get("facts", {}).get("request_id"))
                    for field in combined_usage:
                        combined_usage[field] = max(combined_usage[field], usage[field]) if field == "max_prompt" else combined_usage[field] + usage[field]
                    if backend == "live" and result["status"] == "error" and (usage["calls"] == 0 or "rate limit" in result["answer"] or "HTTP 429" in result["answer"]):
                        trace.emit("run_aborted", reason="LLM unavailable; no fake offline fallback")
                        raise SystemExit("Live API unavailable; inspect sanitized trace")
                usage = combined_usage
                assessment, judge_error = None, ""
                if backend == "live" and result["status"] != "error":
                    try:
                        assessment = judge(result, case["query"], trace)
                    except Exception as error:
                        judge_error = type(error).__name__
                        trace.emit("judge_error", error=judge_error)
                        if isinstance(error, RuntimeError):
                            trace.emit("run_aborted", reason="Judge API unavailable; resume after quota/config recovery")
                            raise SystemExit("Live judge unavailable; checkpoint retained")
                passed = functional_score(result, case, assessment)
                if backend == "live" and case["expected_status"] in ("no_answer", "insufficient_data"):
                    passed = passed and assessment is not None and assessment["refusal_valid"]
                if case["repeat"] > 1:
                    passed = passed and bool(repeat_ids[0]) and len(set(repeat_ids)) == 1
                row = {
                    "run_id": stamp, "backend": backend, "mode": mode, "query_id": case["id"],
                    "category": case["category"], "expected_status": case["expected_status"],
                    "actual_status": result["status"], "functional_pass": passed,
                    "source_complete": set(case["expected_sources"]) <= set(result["citations"]),
                    "verified": result["verified"], "judge_error": judge_error,
                    "faithfulness": assessment["faithfulness"] if assessment else None,
                    "citation_support": assessment["citation_support"] if assessment else None,
                    "refusal_valid": assessment["refusal_valid"] if assessment else (False if backend == "live" else None),
                    **usage,
                }
                row["grounded_pass"] = passed and row["source_complete"] and bool(assessment and assessment["citation_support"]) if backend == "live" else None
                trace.emit("evaluation", **row)
                print(f"{backend} {mode} {case['id']}: functional {'PASS' if passed else 'FAIL'} ({result['status']}); sources={row['source_complete']}; grounded={row['grounded_pass']}", flush=True)
        trace.emit("run_end", evaluated=len(cases) * 2)
    all_rows = [row for path in run_paths for row in rows_from_log(path, backend)]
    write_results(backend, runs, all_rows)


def rows_from_log(path, backend):
    path = Path(path)
    path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if path.parent != (ROOT / "logs").resolve() or not path.name.startswith(f"eval_{backend}_") or path.suffix != ".jsonl":
        raise ValueError("Only this project's evaluation JSONL logs are accepted")
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    starts = [r for r in events if r["event"] == "run_start"]
    if not starts or not any(r["event"] == "run_end" for r in events):
        raise ValueError("Incomplete run: do not present partial results as a full evaluation")
    rows, after_agent, judge_usage = [], False, {}
    pending_usage = {}
    pending_judge = {}
    pending_embedding = {}
    agent_models, judge_models = set(), set()
    for event in events:
        if event["event"] == "EMBEDDING_USAGE" or (event["event"] == "http_attempt" and event.get("scope") == "embedding"):
            pair = tuple(event["query_id"].split(":")[:2])
            embedding = pending_embedding.setdefault(pair, {k: 0 for k in ("calls", "tokens", "cache_hits", "attempts")})
            if event["event"] == "http_attempt":
                embedding["attempts"] += 1
            else:
                for k in ("calls", "tokens", "cache_hits"):
                    embedding[k] += event[k]
        if event["event"] == "query_start":
            after_agent = False
            agent_models, judge_models = set(), set()
        if event["event"] == "llm":
            (judge_models if after_agent else agent_models).add(event["model"])
        if event["event"] == "USAGE" and event.get("usage_scope") == "agent":
            pair = tuple(event["query_id"].split(":")[:2])
            combined = pending_usage.setdefault(pair, {k: 0 for k in ("calls", "prompt_tokens", "completion_tokens", "max_prompt", "attempts")})
            for field in combined:
                combined[field] = max(combined[field], event[field]) if field == "max_prompt" else combined[field] + event[field]
            after_agent = True
            judge_usage = pending_judge.setdefault(pair, {k: 0 for k in ("calls", "prompt_tokens", "completion_tokens", "max_prompt", "attempts")})
        if after_agent and event["event"] == "http_attempt" and event.get("scope") == "llm":
            judge_usage["attempts"] += 1
        if after_agent and event["event"] == "llm":
            judge_usage["calls"] += 1
            for k in ("prompt_tokens", "completion_tokens"):
                judge_usage[k] += event["usage"][k]
            judge_usage["max_prompt"] = max(judge_usage["max_prompt"], event["usage"]["prompt_tokens"])
        if event["event"] == "evaluation":
            agent_usage = pending_usage.pop((event["mode"], event["query_id"]), {})
            pending_judge.pop((event["mode"], event["query_id"]), None)
            embedding = pending_embedding.pop((event["mode"], event["query_id"]), None)
            rows.append({
                **{k: v for k, v in event.items() if k not in ("timestamp", "event")}, **agent_usage,
                **{f"judge_{k}": v for k, v in judge_usage.items()},
                "embedding_trace_available": embedding is not None,
                **{f"embedding_{k}": v for k, v in (embedding or {k: 0 for k in ("calls", "tokens", "cache_hits", "attempts")}).items()},
                "agent_model": ",".join(sorted(agent_models)), "judge_model": ",".join(sorted(judge_models)),
                "run_configuration": json.dumps(starts[0].get("configuration"), ensure_ascii=False, sort_keys=True),
            })
            after_agent = False
    if len(rows) != starts[0]["test_count"] * len(starts[0]["modes"]) or any(r["backend"] != backend for r in rows):
        raise ValueError("Run size or backend does not match its metadata")
    return rows


def write_results(backend, runs, all_rows):
    destination = ROOT / "results" / backend
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "per_query.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    configurations = [json.loads(c) for c in sorted({r["run_configuration"] for r in all_rows})]
    summary = {
        "backend": backend, "real_llm_evidence": backend == "live", "runs": runs,
        "source_log_files": sorted({f"eval_{backend}_{r['run_id']}.jsonl" for r in all_rows}),
        "configuration": configurations[0] if len(configurations) == 1 else configurations,
        "configuration_complete": all(c is not None for c in configurations),
        "observed_models": {
            "agent": sorted({r['agent_model'] for r in all_rows if r['agent_model']}),
            "judge": sorted({r['judge_model'] for r in all_rows if r['judge_model']}),
        },
        "modes": {},
    }
    for mode in ("dense", "hybrid"):
        rows = [r for r in all_rows if r["mode"] == mode]
        no_answer = [r for r in rows if r["category"] == "no_answer"]
        answerable = [r for r in rows if r["category"] not in ("no_answer", "insufficient_data")]
        faith = [r["faithfulness"] for r in rows if r["faithfulness"] is not None]
        source_rows = [r for r in rows if r["expected_status"] not in ("no_answer", "insufficient_data")]
        citations = [r["citation_support"] for r in rows if r.get("citation_support") is not None]
        summary["modes"][mode] = {
            "cases": len(rows), "functional_accuracy": sum(r["functional_pass"] for r in rows) / len(rows),
            "label_refusal_rate": sum(r["actual_status"] == "no_answer" for r in no_answer) / len(no_answer) if no_answer else None,
            "correct_refusal_rate": sum(r.get("refusal_valid") is True and r["actual_status"] == "no_answer" for r in no_answer) / len(no_answer) if no_answer and all(r.get("refusal_valid") is not None for r in no_answer) else None,
            "false_refusal_rate": sum(r["actual_status"] in ("no_answer", "insufficient_data") for r in answerable) / len(answerable) if answerable else None,
            "source_completeness_rate": sum(r["source_complete"] for r in source_rows) / len(source_rows) if source_rows else None,
            "citation_support_rate": sum(citations) / len(citations) if citations else None,
            "faithfulness": sum(faith) / len(faith) if faith else None, "faithfulness_samples": len(faith),
            "judge_errors": sum(bool(r["judge_error"]) for r in rows),
            "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
            "completion_tokens": sum(r["completion_tokens"] for r in rows),
            "calls": sum(r["calls"] for r in rows),
        }
        summary["modes"][mode]["grounded_accuracy"] = sum(r.get("grounded_pass") is True for r in rows) / len(rows) if all(r.get("grounded_pass") is not None for r in rows) else None
        for k in ("calls", "prompt_tokens", "completion_tokens"):
            summary["modes"][mode][f"judge_{k}"] = sum(r[f"judge_{k}"] for r in rows)
        for k in ("calls", "tokens", "cache_hits", "attempts"):
            summary["modes"][mode][f"embedding_{k}"] = sum(r[f"embedding_{k}"] for r in rows)
        summary["modes"][mode]["embedding_trace_complete"] = all(r["embedding_trace_available"] for r in rows)
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    # Standalone figures are generated from measured rows, never invented values.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(["dense", "hybrid"], [summary["modes"][m]["functional_accuracy"] for m in ("dense", "hybrid")])
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Functional accuracy")
    ax.set_title(f"{backend.upper()} - {'LLM' if backend == 'live' else 'integration fixture only'}")
    fig.tight_layout()
    fig.savefig(destination / "accuracy.png", dpi=150)
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["live", "offline"], default="live")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--from-log", help="Rebuild measured CSV/summary/figure from one completed JSONL, without API calls")
    args = parser.parse_args()
    if not 1 <= args.runs <= 3:
        parser.error("runs must be 1..3 to keep costs bounded")
    if args.from_log:
        write_results(args.backend, 1, rows_from_log(args.from_log, args.backend))
        raise SystemExit(0)
    if args.backend == "live":
        from src.runtime import load_runtime_env
        load_runtime_env()
    asyncio.run(evaluate(args.backend, args.runs))

