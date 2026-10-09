import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

class RequestStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents= True, exist_ok= True)
        self.path = path
        with closing(sqlite3.connect(path)) as db, db: #kết nối tự động commit và tự động đóng an toàn
            db.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, operation_key TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)")
            
    def create(self, operation_key:str, analysis:dict)->dict:
        payload = {"request_id": str(uuid.uuid4()), "project_id": analysis["project_id"], "as_of_date": analysis["as_of_date"],"status": "open", "reason": f"Chậm {analysis['behind_pp']} điểm phần trăm; ngưỡng {analysis['threshold_pp']}; quá hạn {analysis['overdue']}", "analysis": analysis, "created_at": datetime.now(timezone.utc).isoformat()}
        with closing(sqlite3.connect(self.path)) as db,db :
            row = db.execute("SELECT payload FROM requests WHERE operation_key=?", (operation_key,)).fetchone()
            if row:
                existing = json.loads(row[0])
                if (existing["project_id"], existing["as_of_date"]) != (analysis["project_id"], analysis["as_of_date"]):
                    raise ValueError("Idempotency key reused for different action")
                return existing
            db.execute("INSERT INTO requests VALUES (?, ?, ?)", (payload["request_id"], operation_key, json.dumps(payload, ensure_ascii=False)))
        return payload
    
    def get(self, request_id: str)-> dict:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT payload FROM requests WHERE request_id=?", (request_id,)).fetchone()
        if not row:
            raise ValueError("Unknown request_id")
        return json.loads(row[0])