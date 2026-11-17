import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        if "pinkcandyy" in line and ("0.png" in line or "sample.png" in line or "generate_samples" in line):
            data = json.loads(line)
            print("Step", data.get("step_index"))
            for c in data.get("tool_calls", []):
                print(c.get("name"), str(c.get("args"))[:200])
