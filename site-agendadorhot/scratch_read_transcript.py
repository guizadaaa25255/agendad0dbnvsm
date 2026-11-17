import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if idx in (619, 621, 623, 625, 637, 639):
            data = json.loads(line)
            print(f"=== Line {idx} ===")
            print(data.get("content", "")[:1000])
