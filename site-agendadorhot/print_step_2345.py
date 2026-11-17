import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        step = data.get("step_index")
        if step in (2345, 2340, 2341, 2342, 2343, 2344):
            print(f"=== Step {step} ===")
            print("Thinking:", data.get("thinking", "")[:200])
            for c in data.get("tool_calls", []):
                print("Tool:", c.get("name"), str(c.get("args"))[:200])
