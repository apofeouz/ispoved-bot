from PIL import Image, ImageDraw, ImageFont
import math

W = 512
img = Image.new("RGB", (W,W), "#0f0f12")
draw = ImageDraw.Draw(img)

# свеча
# цилиндр
candle_x = W//2
candle_w = 80
candle_h = 220
candle_top = 220
candle_bot = candle_top + candle_h

# тень свечения
for r in range(120, 0, -10):
    alpha = int(30 * (1 - r/120))
    draw.ellipse([candle_x - r, 80 - r//2, candle_x + r, 80 + r//2], fill=f"#ffcc66", outline=None)
    # PIL без альфы, делаем через смешение
# тело свечи - теплый крем
draw.rectangle([candle_x - candle_w//2, candle_top, candle_x + candle_w//2, candle_bot], fill="#f5e6c8", outline="#e6d5b0", width=2)
# блик
draw.rectangle([candle_x - candle_w//2 + 12, candle_top+10, candle_x - candle_w//2 + 22, candle_bot-20], fill="#fff8e6")
# фитиль
draw.rectangle([candle_x-4, candle_top-14, candle_x+4, candle_top], fill="#2b1f14")
# пламя
flame = [(candle_x, 45), (candle_x-18, 85), (candle_x+18, 85)]
draw.polygon(flame, fill="#ffd54a")
draw.polygon([(candle_x, 55),(candle_x-10,78),(candle_x+10,78)], fill="#fff7a0")
# ореол
draw.ellipse([candle_x-28, 58, candle_x+28, 92], outline="#ffcc66", width=2)

# нижняя подложка
draw.ellipse([candle_x-70, candle_bot-12, candle_x+70, candle_bot+18], fill="#1c1a16", outline="#2a2620")

# текст внизу
try:
    # попробуем системный шрифт
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
except:
    font = ImageFont.load_default()
    small = ImageFont.load_default()

# легкая надпись
draw.text((W//2, 460), "Душа и свет", fill="#d9c7a0", font=font, anchor="mm")
draw.text((W//2, 485), "тихая беседа", fill="#8a7f6b", font=small, anchor="mm")

img.save("avatar.png", "PNG")
print("saved avatar.png 512x512")
