import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        idx = data.get("step_index", 0)
        if 604 <= idx <= 618:
            print(f"Step {idx}:")
            if data.get("thinking"):
                print("Thinking:", data.get("thinking")[:300])
            for c in data.get("tool_calls", []):
                print("Tool:", c.get("name"), str(c.get("args"))[:200])
