import json

transcript_path = r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.system_generated\logs\transcript_full.jsonl"
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        if "Total documentos em pinkcandyy: 43" in line or "pinkcandyy" in line and "Index 29:" in line:
            data = json.loads(line)
            print("Content:", data.get("content"))
