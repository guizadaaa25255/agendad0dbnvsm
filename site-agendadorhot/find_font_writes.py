import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if "custom_fonts.json" in line:
            data = json.loads(line)
            calls = data.get("tool_calls", [])
            for c in calls:
                if c.get("name") in ["write_file", "edit_file"]:
                    print(f"Step {data.get('step_index')} wrote to custom_fonts.json")
