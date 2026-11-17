from PIL import Image

img = Image.open(r"C:\Users\Administrator\AppData\Local\Programs\antigravity\crop_letters.png")
w, h = img.size

# Save slice of each character
# Let's see the width of crop_letters.png is 279, height is 74
# Let's crop just the letters row: y from 0 to 45
letters_strip = img.crop((0, 0, w, 45))
letters_strip.save(r"C:\Users\Administrator\AppData\Local\Programs\antigravity\strip.png")
