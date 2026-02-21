# Wiz ForexBot

AI-Powered Forex Trading Signals Web App

## Features
- 📊 Real-time market analysis
- 🎯 High accuracy trading signals
- 📱 Installable PWA (Add to Home Screen)
- 💎 Credit system with rewarded ads
- 🔐 User authentication
- 📈 Buy/Sell signals with TP/SL levels

## Installation

```bash
pip install -r requirements.txt
python run.py

## Step 4: Create Render Config

```bash
cat > render.yaml << 'EOF'
services:
  - type: web
    name: wiz-forexbot
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn run:app --bind 0.0.0.0:$PORT --workers 4
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: SECRET_KEY
        generateValue: true
      - key: FLASK_ENV
        value: production
    disk:
      name: uploads
      mountPath: /opt/render/project/src/app/static/uploads
      sizeGB: 1
