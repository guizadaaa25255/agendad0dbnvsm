import json
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler")
with open(BASE / "app/custom_fonts.json", "r", encoding="utf-8") as f:
    fonts = json.load(f)

pink = fonts["pinkcandyy"]["letters"]
print(f"Total keys in pinkcandyy: {len(pink)}")
for idx, (k, v) in enumerate(pink.items()):
    print(f"Index {idx:02d}: key='{k}' id={v}")
