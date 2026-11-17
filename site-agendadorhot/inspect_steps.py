import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        step = data.get("step_index")
        if step in (659, 685, 783, 840):
            print(f"=== Step {step} ===")
            print("Thinking:", data.get("thinking", "")[:300])
            for c in data.get("tool_calls", []):
                print("Tool:", c.get("name"))
                if c.get("name") == "write_file":
                    print("Content preview:", c.get("args", {}).get("Content", "")[:400])
                elif c.get("name") == "edit_file":
                    print("Target:", c.get("args", {}).get("Target", "")[:200])
                    print("Replacement:", c.get("args", {}).get("Replacement", "")[:200])
