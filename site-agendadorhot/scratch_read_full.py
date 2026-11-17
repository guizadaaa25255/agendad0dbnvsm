import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if 625 <= idx <= 650:
            data = json.loads(line)
            step = data.get("step_index")
            t = data.get("thinking", "")
            c = data.get("content", "")
            if t:
                print(f"Step {step} Thinking: {t[:300]}...")
            if c:
                print(f"Step {step} Content: {c[:300]}...")
