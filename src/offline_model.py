"""Deterministic integration driver. NOT an LLM and NOT quality evidence.
Only used to exercise real MCP, SQLite, validation and verification offline.
"""
import json
import re
from .models import Usage


class OfflineModel:
    def __init__(self, allow_write: bool):
        self.allow_write, self.usage, self.count = allow_write, Usage(), 0

    def complete(self, messages: list[dict], tools: list[dict], tool_choice="auto") -> dict:
        self.count += 1
        query = messages[1]["content"]
        q = query.lower()
        project = (re.search(r"P\d{3}", query) or re.search(r"P001", "P001"))[0]
        observations = []
        called = []
        for message in messages:
            if message["role"] == "user" and message["content"].startswith("RAG_CONTEXT\n"):
                called.append("search_documents")
                observations.append(json.loads(message["content"].split("\n", 1)[1]))
            if message.get("tool_calls"):
                called += [c["function"]["name"] for c in message["tool_calls"]]
            if message["role"] == "tool" and not message["content"].startswith("Error:"):
                observations.append(json.loads(message["content"]))

        def call(name, args):
            return {"role": "assistant", "content": None, "tool_calls": [{"id": f"offline_{self.count}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}

        def final(status, facts=None, citations=None):
            return {"role": "assistant", "content": json.dumps({"status": status, "answer": f"Kiểm tra tích hợp offline: {status}; {facts or {}}", "facts": facts or {}, "citations": citations or []}, ensure_ascii=False)}

        if "search_documents" not in called:
            return call("search_documents", {"query": query, "project_id": project, "as_of_date": "2026-10-08"})
        if any(word in q for word in ("ngân sách", "khách hàng", "mức lương")) or project == "P999":
            return final("no_answer")
        # Independent integration rules; never loads the testset/expected answers.
        if "phiên bản v1" in q:
            for doc, version in (("P001-W2-V1", 1), ("P001-W2-V2", 2)):
                if not any(o.get("metadata", {}).get("doc_id") == doc for o in observations):
                    return call("get_document", {"doc_id": doc, "version": version})
            docs = [o for o in observations if "metadata" in o]
            return final("ok", {"old_T02": docs[0]["records"]["actual"]["T02"], "new_T02": docs[1]["records"]["actual"]["T02"]}, ["P001-W2-V1", "P001-W2-V2"])
        if any(word in q for word in ("phụ trách", "deadline", "blocker", "ngưỡng cảnh báo")) and "theo dõi" not in q:
            doc_id, version = ("P001-PLAN", 1) if "phụ trách" in q or "deadline" in q else (("P001-MEETING", 1) if "blocker" in q else ("POLICY-V2", 2))
            if not any(o.get("metadata", {}).get("doc_id") == doc_id for o in observations):
                return call("get_document", {"doc_id": doc_id, "version": version})
            records = observations[-1]["records"]
            if "phụ trách" in q:
                facts = {"owner": next(t["owner"] for t in records["tasks"] if t["task_id"] == "T02")}
            elif "deadline" in q:
                facts = {"deadline": next(t["deadline"] for t in records["tasks"] if t["task_id"] == "T03")}
            else:
                facts = {k: records[k] for k in ("blocker", "threshold_pp") if k in records}
            return final("ok", facts, [doc_id])
        if "analyze_progress" not in called:
            return call("analyze_progress", {"project_id": project, "as_of_date": "2026-10-08", "compare_date": "2026-10-01" if "thay đổi" in q else ""})
        analysis = next((o for o in observations if "sources" in o), {})
        if analysis.get("status") != "ok":
            return final(analysis.get("status", "error"), citations=[s["doc_id"] for s in analysis.get("sources", [])])
        citations = [s["doc_id"] for s in analysis["sources"]]
        if "vì sao" in q:
            if not any(o.get("metadata", {}).get("doc_id") == "P001-MEETING" for o in observations):
                return call("get_document", {"doc_id": "P001-MEETING", "version": 1})
            analysis = {**analysis, "blocker": observations[-1]["records"]["blocker"]}
            citations.append("P001-MEETING")
        if self.allow_write and analysis["risk"]:
            if "create_followup_request" not in called:
                return call("create_followup_request", {"project_id": project, "as_of_date": "2026-10-08"})
            write = next((o for o in observations if "record" in o), {})
            return final("action_verified" if write.get("verified") else "action_failed", {**analysis, "request_id": write.get("record", {}).get("request_id")}, citations)
        return final("ok", analysis, citations)
