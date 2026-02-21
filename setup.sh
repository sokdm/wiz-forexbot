#!/bin/bash
echo "🧙‍♂️ Setting up Wiz ForexBot..."

# Create directories
mkdir -p app/static/uploads
mkdir -p app/static/icons

# Generate simple icons
python3 << 'PYEOF'
try:
    from PIL import Image, ImageDraw
    for size in [72, 96, 128, 144, 152, 192, 384, 512]:
        img = Image.new('RGB', (size, size), '#e94560')
        draw = ImageDraw.Draw(img)
        # Add a simple circle
        padding = size // 4
        draw.ellipse([padding, padding, size-padding, size-padding], fill='#ff6b6b')
        img.save(f'app/static/icons/icon-{size}x{size}.png')
    print("✅ Icons created")
except:
    print("⚠️  PIL not available, create icons manually")
PYEOF

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Create GitHub repo: https://github.com/new"
echo "2. git remote add origin https://github.com/YOUR_USERNAME/wiz-forexbot.git"
echo "3. git push -u origin main"
echo "4. Go to https://render.com and connect your repo"
echo "5. Apply for AdSense: https://google.com/adsense"
