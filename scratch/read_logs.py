import sqlite3
import json

conn = sqlite3.connect("data/agent_os.db")
conn.row_factory = sqlite3.Row

print("=== RECENT EVENT LOGS ===")
events = conn.execute("SELECT * FROM events WHERE id > 165 ORDER BY id ASC").fetchall()
for ev in events:
    print(f"[{ev['timestamp']}] ID: {ev['id']} | Type: {ev['event_type']} | Data: {ev['data']}")
