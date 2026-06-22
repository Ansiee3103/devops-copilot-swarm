import sys

log_path = "d:/devops-copilot-swarm/logs/app.log"

try:
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        print(f"Total lines in app.log: {len(lines)}")
        print("Last 100 lines:")
        for line in lines[-100:]:
            # Clean non-ASCII characters for printing to console safely
            clean_line = line.encode("ascii", "ignore").decode("ascii")
            print(clean_line.strip())
except Exception as e:
    print(f"Failed to read log: {e}")
