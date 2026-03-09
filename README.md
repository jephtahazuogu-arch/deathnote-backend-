# DÉÁTH ÑØTÉ — Backend Server
### AI Trading Agent • Binance Integration API
**Made by Calitech 🐾**

---

## 📋 WHAT THIS DOES

This is the backend server for the DÉÁTH ÑØTÉ trading app.
It handles all Binance API communication securely — including
HMAC-SHA256 order signing, so your API keys never get exposed.

### Features:
- ✅ Live crypto prices from Binance
- ✅ Candlestick (OHLCV) chart data
- ✅ Place BUY/SELL orders (Market & Limit)
- ✅ Test orders before going live
- ✅ Account balance & info
- ✅ Order history & trade history
- ✅ Cancel orders
- ✅ WebSocket live price streaming
- ✅ Rate limiting & security
- ✅ Auto API docs at /docs

---

## 🚀 QUICK START (Local)

### Step 1 — Install Python
Download Python 3.11+ from https://python.org
Make sure to check "Add Python to PATH" during install.

Verify: open terminal and run:
```
python --version
```

### Step 2 — Download this folder
Save the `deathnote-backend` folder to your computer.
Example: `C:\Users\YourName\deathnote-backend`

### Step 3 — Open terminal in the folder
**Windows:** Open the folder → right-click → "Open in Terminal"
**Mac/Linux:** Open Terminal, then type:
```
cd /path/to/deathnote-backend
```

### Step 4 — Create virtual environment
```bash
python -m venv venv
```

Activate it:
- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

You should see `(venv)` at the start of your terminal line.

### Step 5 — Install dependencies
```bash
pip install -r requirements.txt
```
This will take about 1-2 minutes.

### Step 6 — Set up environment file
Copy `.env.example` to `.env`:
- **Windows:** `copy .env.example .env`
- **Mac/Linux:** `cp .env.example .env`

Open `.env` and change the SECRET_KEY to something random.

### Step 7 — Run the server!
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Step 8 — Test it works
Open your browser and go to:
```
http://localhost:8000
```
You should see: `{"app": "DÉÁTH ÑØTÉ Backend", "status": "online"}`

View full API docs at:
```
http://localhost:8000/docs
```

---

## 🌐 DEPLOY TO CLOUD (Free)

### Option A: Railway (Recommended — easiest)

1. Create free account at https://railway.app
2. Install Railway CLI:
   ```
   npm install -g @railway/cli
   ```
3. In your backend folder, run:
   ```
   railway login
   railway init
   railway up
   ```
4. Railway gives you a live URL like:
   `https://deathnote-backend-production.up.railway.app`

5. Copy that URL into your DÉÁTH ÑØTÉ frontend app settings.

### Option B: Render (Also free)

1. Create free account at https://render.com
2. Click "New" → "Web Service"
3. Connect your GitHub repo (push this folder to GitHub first)
4. Render auto-detects `render.yaml` and deploys
5. Your URL: `https://deathnote-backend.onrender.com`

### Option C: Push to GitHub first
```bash
git init
git add .
git commit -m "DÉÁTH ÑØTÉ backend v1.0"
git remote add origin https://github.com/YOUR_USERNAME/deathnote-backend.git
git push -u origin main
```
Then connect to Railway or Render.

---

## 🔗 API ENDPOINTS

### Public (no auth needed)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Server status |
| GET | `/market/price/{symbol}` | Latest price |
| GET | `/market/ticker/{symbol}` | 24h stats |
| GET | `/market/tickers` | Multiple tickers |
| GET | `/market/klines/{symbol}` | Candlestick data |
| GET | `/market/orderbook/{symbol}` | Order book |

### Authenticated (pass api_key + api_secret in body)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/account/info` | Account balances |
| POST | `/account/balance/{asset}` | Single asset balance |
| POST | `/orders/place` | Place order |
| POST | `/orders/test` | Test order (no execution) |
| POST | `/orders/open` | Open orders |
| POST | `/orders/history` | Order history |
| POST | `/orders/trades` | Trade history |
| DELETE | `/orders/cancel` | Cancel order |
| POST | `/orders/cancel-all` | Cancel all orders |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/prices/btcusdt,ethusdt` | Multi-symbol live prices |
| `ws://host/ws/ticker/BTCUSDT` | Single symbol ticker |

---

## 📱 CONNECT TO YOUR FRONTEND

In your DÉÁTH ÑØTÉ app settings, set the backend URL to:
- **Local:** `http://localhost:8000`
- **Railway:** `https://your-app.up.railway.app`
- **Render:** `https://your-app.onrender.com`

---

## 🔒 SECURITY NOTES

- ✅ API keys are passed per-request — never stored on server
- ✅ HMAC-SHA256 signing happens server-side
- ✅ Rate limiting prevents abuse
- ✅ NEVER enable "Withdrawal" permission on your Binance API key
- ✅ Only enable "Enable Spot & Margin Trading"
- ✅ Whitelist your server's IP in Binance API settings

---

## 🆘 TROUBLESHOOTING

**Port already in use:**
```bash
uvicorn main:app --reload --port 8001
```

**Module not found:**
Make sure venv is activated (`venv\Scripts\activate` on Windows)

**Binance API errors:**
- Check your API key has "Spot Trading" enabled
- Make sure system clock is accurate (Binance requires timestamp within 5s)
- Check API key IP restrictions on Binance

**CORS errors from frontend:**
Update `allow_origins` in `main.py` with your frontend URL.

---

## 📞 SUPPORT

App: DÉÁTH ÑØTÉ AI Trading Agent
Made by: Calitech 🐾
Version: 1.0.0
