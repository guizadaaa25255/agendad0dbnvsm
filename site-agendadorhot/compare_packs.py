import json
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler")
with open(BASE / "app/custom_fonts.json", "r", encoding="utf-8") as f:
    fonts = json.load(f)

for name in ["pinkcandyy", "docelaranja", "mfslots2", "isapinkblue", "mfslots"]:
    p = fonts.get(name, {})
    letters = p.get("letters", {})
    print(f"=== {name} ({len(letters)} letters) ===")
    print("A..G:", [f"{k}:{letters[k]}" for k in "ABCDEFG" if k in letters])
