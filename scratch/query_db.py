import sqlite3
import json
import os

dbs = [
    "d:/devops-copilot-swarm/database/devops.db",
    "d:/devops-copilot-swarm/database/devops_swarm.db",
    "d:/devops-copilot-swarm/database/test.db"
]

def query_db(db_path):
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist.")
        return
    print(f"\n================ QUERYING {db_path} ================")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables: {tables}")
        if "deployments" in tables:
            cursor.execute("SELECT id, service_name, status, risk_score, logs, created_at FROM deployments ORDER BY id DESC LIMIT 5")
            rows = cursor.fetchall()
            for row in rows:
                dep_id, service_name, status, risk_score, logs_str, created_at = row
                print(f"ID: {dep_id} | Service: {service_name} | Status: {status} | Risk Score: {risk_score} | Created At: {created_at}")
                try:
                    logs = json.loads(logs_str) if logs_str else []
                    print("Logs:")
                    for log in logs:
                        print(f"  {log}")
                except Exception as e:
                    print(f"  Raw logs: {logs_str}")
                print("-" * 30)
        else:
            print("No deployments table found.")
    except Exception as e:
        print(f"Query failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    for db in dbs:
        query_db(db)
