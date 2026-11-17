from PIL import Image

img = Image.open(r"C:\Users\Administrator\.gemini\antigravity\brain\3d210137-7130-4524-be94-7f57759474cb\.user_uploaded\media_1794950139700_ef7984cb.png")
print("Size:", img.size)

# The letters are located in the middle-left area above 'Preguicinha boa de terca ne rs'
# Let's crop the text region
w, h = img.size
# Let's crop around the letters
crop = img.crop((50, int(h * 0.4), int(w * 0.8), int(h * 0.85)))
crop.save("crop_letters.png")
print("Saved crop_letters.png", crop.size)
