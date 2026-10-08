"""One corpus is authoritative for retrieval and numeric calculations."""
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from .models import Document, Source, AnalysisArgs

ROOT = Path(__file__).resolve().parents[1]

class Corpus:
    def __init__(self, path: Path = ROOT / "data/corpus.jsonl"):
            self.docs = [Document(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            ids = set()
            for doc in self.docs:
                m = doc.metadata
                if not all(k in m for k in ("doc_id", "title", "date", "version", "owner", "project_id", "kind")):
                    raise ValueError("Missing document metadata")
                date.fromisoformat(m["date"])
                if m["doc_id"] in ids:
                    raise ValueError("Duplicate doc_id")
                ids.add(m["doc_id"])
                # Fixture text ends with the exact JSON record block used for maths.
                block = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in doc.records.items())
                if not block or not doc.content.endswith(block) or any(sum(line.startswith(k + ": ") for line in doc.content.splitlines()) != 1 for k in doc.records):
                    raise ValueError(f"Content/records mismatch: {m['doc_id']}")
            by_id = {d.metadata["doc_id"]: d for d in self.docs}
            self.families = {}
            children = {}
            for doc in self.docs:
                current, seen = doc, set()
                while current.records.get("supersedes"):
                    parent_id = current.records["supersedes"]
                    if parent_id not in by_id or parent_id in seen:
                        raise ValueError("Missing/cyclic supersedes document")
                    seen.add(parent_id)
                    parent = by_id[parent_id]
                    old, new = parent.metadata, current.metadata
                    if any(old[k] != new[k] for k in ("project_id", "kind")) or old["version"] >= new["version"] or old["date"] > new["date"] or parent.records.get("snapshot_date") != current.records.get("snapshot_date"):
                        raise ValueError("Invalid document replacement")
                    current = parent
                self.families[doc.metadata["doc_id"]] = current.metadata["doc_id"]
                parent_id = doc.records.get("supersedes")
                if parent_id:
                    if parent_id in children:
                        raise ValueError("Document conflict: competing replacements")
                    children[parent_id] = doc.metadata["doc_id"]

    def eligible(self, project: str, as_of: str)->list[Document]:
        date.fromisoformat(as_of)
        candidates = [d for d in self.docs if d.metadata["project_id"] in (project, "GLOBAL")and d.metadata["date"]<=as_of]
        latest = {}
        for d in candidates:
            m = d.metadata
            key = self.families[m["doc_id"]]
            rank =(m["date"], m["version"])
            if key not in latest or rank > (latest[key].metadata["date"], latest[key].metadata["version"]):
                latest[key] = d
            # Meetings are independent. Two active baselines/policies/same-day
            # snapshots are ambiguous; never silently choose whichever came first.
        slots = set()       
        for d in latest.values():
            if d.metadata["kind"] in ("plan", "policy", "snapshot"):
                slot =(d.metadata["project_id"], d.metadata["kind"], d.records.get("snapshot_date",""))
                if slot in slots:
                    raise ValueError(f"Document conflict: {slot}")
                slots.add(slot)
        return list(latest.values())
    
    #Cho phép tra cứu trực tiếp tài liệu theo đúng ID và phiên bản cụ thể.
    def get(self, doc_id: str, version:int)-> Document:
        doc = next((d for d in self.docs if d.metadata["doc_id"]==doc_id and d.metadata["version"]==version), None)
        if doc is None:
            raise ValueError("Unknown document/version")
        return doc
    
    @staticmethod
    #Trả về dict nguồn để dùng cho trích dẫn nguồn
    def source(d: Document) ->dict:
        return asdict(Source(d.metadata["doc_id"], d.metadata["version"],d.metadata["title"]))
    
    #tính toán tiến độ
    def analyze(self, args: AnalysisArgs) -> dict:
            docs = self.eligible(args.project_id, args.as_of_date)
            owned = [d for d in docs if d.metadata["project_id"] == args.project_id]
            if not owned:
                return {"status": "no_answer", "missing": ["project"], "sources": []}
            plan = next((d for d in owned if d.metadata["kind"] == "plan"), None)
            snapshot = next((d for d in owned if d.metadata["kind"] == "snapshot" and d.records["snapshot_date"] == args.as_of_date), None)
            policy = next((d for d in docs if d.metadata["kind"] == "policy"), None)
            sources = [self.source(d) for d in (plan, snapshot, policy) if d]
            if not plan or not snapshot or not policy:
                return {"status": "insufficient_data", "missing": [k for k, v in (("baseline", plan), ("snapshot", snapshot), ("policy", policy)) if not v], "sources": sources}
            actuals = snapshot.records["actual"]
            planned = plan.records["planned"].get(args.as_of_date)
            tasks = plan.records["tasks"]
            missing = []
            for task in tasks:
                tid = task["task_id"]
                if task.get("estimated_effort_hours") is None or not planned or planned.get(tid) is None or actuals.get(tid) is None:
                    missing.append(tid)
            if missing:
                return {"status": "insufficient_data", "missing": missing, "sources": sources}
            weights = [t["estimated_effort_hours"] for t in tasks]
            if any(w <= 0 for w in weights) or any(not 0 <= value <= 100 for values in (planned, actuals) for value in values.values()):
                raise ValueError("Invalid weight or progress outside [0,100]")
            total = sum(weights)
            expected = sum(t["estimated_effort_hours"] * planned[t["task_id"]] for t in tasks) / total
            actual = sum(t["estimated_effort_hours"] * actuals[t["task_id"]] for t in tasks) / total
            overdue = [{"task_id": t["task_id"], "days": (date.fromisoformat(args.as_of_date) - date.fromisoformat(t["deadline"])).days} for t in tasks if actuals[t["task_id"]] < 100 and t["deadline"] < args.as_of_date]
            result = {"status": "ok", "project_id": args.project_id, "as_of_date": args.as_of_date, "planned_progress": round(expected, 4), "actual_progress": round(actual, 4), "behind_pp": round(expected - actual, 4), "threshold_pp": policy.records["threshold_pp"], "overdue": overdue, "sources": sources}
            result["risk"] = result["behind_pp"] >= result["threshold_pp"] or bool(overdue)
            if args.compare_date:
                previous = self.analyze(AnalysisArgs(args.project_id, args.compare_date))
                if previous["status"] != "ok":
                    return {"status": "insufficient_data", "missing": ["comparison snapshot/baseline"], "sources": sources}
                result["change_pp"] = round(actual - previous["actual_progress"], 4)
                result["compare_date"] = args.compare_date
                result["previous_actual_progress"] = previous["actual_progress"]
                result["sources"] += [s for s in previous["sources"] if s not in result["sources"]]
            return result        