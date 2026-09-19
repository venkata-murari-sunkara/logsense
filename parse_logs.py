"""
Step 1: Log Parsing
Reads raw HDFS log lines and uses Drain3 to turn each messy line into a
clean template (fixed words) + variables (the parts that change, like
block IDs or IP addresses).
"""
import re
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

RAW_LOG_PATH = "HDFS_2k.log"

# Drain3 config: keep it simple, in-memory, default settings work well
config = TemplateMinerConfig()
config.profiling_enabled = False

template_miner = TemplateMiner(config=config)

parsed_rows = []

with open(RAW_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
    for line_no, raw_line in enumerate(f, start=1):
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        # HDFS log format: "081109 203615 148 INFO dfs.DataNode$PacketResponder: <message>"
        match = re.match(
            r"^(\d{6})\s+(\d{6})\s+(\d+)\s+(\w+)\s+([\w\.\$]+):\s*(.*)$", raw_line
        )
        if not match:
            continue
        date, time_, pid, level, component, content = match.groups()

        result = template_miner.add_log_message(content)

        parsed_rows.append(
            {
                "line_no": line_no,
                "date": date,
                "time": time_,
                "level": level,
                "component": component,
                "content": content,
                "template_id": result["cluster_id"],
                "template": result["template_mined"],
            }
        )

print(f"Parsed {len(parsed_rows)} log lines")
print(f"Discovered {len(template_miner.drain.clusters)} unique templates\n")

print("Sample discovered templates:")
for cluster in list(template_miner.drain.clusters)[:5]:
    print(f"  [Template {cluster.cluster_id}] {cluster.get_template()}")

# Save structured output for the next step
import csv

with open("parsed_logs.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=parsed_rows[0].keys())
    writer.writeheader()
    writer.writerows(parsed_rows)

print("\nSaved structured output to parsed_logs.csv")