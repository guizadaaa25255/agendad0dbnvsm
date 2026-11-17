import urllib.request
import re

url = "https://t.me/addemoji/pinkcandyy"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8")
        print("Fetched HTML length:", len(html))
        with open("tme_pinkcandyy.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        # Check for stickers or image urls
        imgs = re.findall(r'<img[^>]+src="([^">]+)"', html)
        print("Images found:", len(imgs), imgs[:5])
        
        # Search for any emojis or titles
        title = re.findall(r'<title>(.*?)</title>', html)
        print("Title:", title)
except Exception as e:
    print("Error:", e)
