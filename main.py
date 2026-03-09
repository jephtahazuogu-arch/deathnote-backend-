"""
DÉÁTH ÑØTÉ — Backend Server
FastAPI + Binance Integration
Made by Calitech 🐾
"""

import hmac
import hashlib
import time
import asyncio
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ─────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("deathnote")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="DÉÁTH ÑØTÉ Backend",
    description="AI Trading Agent — Binance Integration API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # In production: replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BINANCE_BASE = "https://api.binance.com"
BINANCE_WS   = "wss://stream.binance.com:9443"


# ─────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────
class Credentials(BaseModel):
    api_key: str
    api_secret: str

class OrderRequest(BaseModel):
    api_key: str
    api_secret: str
    symbol: str          # e.g. BTCUSDT
    side: str            # BUY or SELL
    order_type: str      # MARKET or LIMIT
    quantity: float
    price: Optional[float] = None   # required for LIMIT
    time_in_force: Optional[str] = "GTC"

class CancelOrderRequest(BaseModel):
    api_key: str
    api_secret: str
    symbol: str
    order_id: int

class AccountRequest(BaseModel):
    api_key: str
    api_secret: str


# ─────────────────────────────────────────
# BINANCE SIGNING UTILITY
# ─────────────────────────────────────────
def sign_params(params: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for Binance API."""
    query_string = urlencode(params)
    signature = hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return signature

async def binance_signed_request(
    method: str,
    endpoint: str,
    api_key: str,
    api_secret: str,
    params: dict = {},
    body: dict = {},
) -> dict:
    """Make authenticated request to Binance API."""
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000
    params["signature"] = sign_params({**params, **body}, api_secret)

    headers = {"X-MBX-APIKEY": api_key}
    url = f"{BINANCE_BASE}{endpoint}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        if method == "GET":
            response = await client.get(url, params=params, headers=headers)
        elif method == "POST":
            response = await client.post(url, params=params, data=body, headers=headers)
        elif method == "DELETE":
            response = await client.delete(url, params=params, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

    if response.status_code != 200:
        logger.error(f"Binance error {response.status_code}: {response.text}")
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Binance API error: {response.json().get('msg', response.text)}"
        )
    return response.json()

async def binance_public_request(endpoint: str, params: dict = {}) -> dict:
    """Make public (unsigned) request to Binance API."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{BINANCE_BASE}{endpoint}", params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Binance request failed")
    return response.json()


# ─────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "app": "DÉÁTH ÑØTÉ Backend",
        "version": "1.0.0",
        "status": "online",
        "made_by": "Calitech 🐾",
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "alive", "timestamp": int(time.time())}


# ─────────────────────────────────────────
# PUBLIC MARKET DATA
# ─────────────────────────────────────────
@app.get("/market/price/{symbol}", tags=["Market Data"])
@limiter.limit("60/minute")
async def get_price(symbol: str, request: Request):
    """Get latest price for a symbol (e.g. BTCUSDT)."""
    data = await binance_public_request("/api/v3/ticker/price", {"symbol": symbol.upper()})
    return {"symbol": symbol.upper(), "price": float(data["price"])}


@app.get("/market/ticker/{symbol}", tags=["Market Data"])
@limiter.limit("30/minute")
async def get_ticker(symbol: str, request: Request):
    """Get 24h ticker stats for a symbol."""
    data = await binance_public_request("/api/v3/ticker/24hr", {"symbol": symbol.upper()})
    return {
        "symbol": symbol.upper(),
        "price": float(data["lastPrice"]),
        "change": float(data["priceChange"]),
        "change_pct": float(data["priceChangePercent"]),
        "high_24h": float(data["highPrice"]),
        "low_24h": float(data["lowPrice"]),
        "volume": float(data["volume"]),
        "quote_volume": float(data["quoteVolume"]),
    }


@app.get("/market/tickers", tags=["Market Data"])
@limiter.limit("20/minute")
async def get_all_tickers(request: Request, symbols: str = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT"):
    """Get 24h ticker for multiple symbols (comma-separated)."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            client.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", params={"symbol": s})
            for s in symbol_list
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
    for sym, resp in zip(symbol_list, responses):
        if isinstance(resp, Exception): continue
        if resp.status_code != 200: continue
        d = resp.json()
        results.append({
            "symbol": sym,
            "price": float(d["lastPrice"]),
            "change_pct": float(d["priceChangePercent"]),
            "high": float(d["highPrice"]),
            "low": float(d["lowPrice"]),
            "volume": float(d["volume"]),
        })
    return {"tickers": results, "count": len(results)}


@app.get("/market/klines/{symbol}", tags=["Market Data"])
@limiter.limit("30/minute")
async def get_klines(
    symbol: str, request: Request,
    interval: str = "1h",
    limit: int = 100
):
    """Get candlestick (OHLCV) data."""
    valid_intervals = ["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"]
    if interval not in valid_intervals:
        raise HTTPException(status_code=400, detail=f"Invalid interval. Use: {valid_intervals}")
    limit = min(max(limit, 1), 1000)
    data = await binance_public_request("/api/v3/klines", {
        "symbol": symbol.upper(), "interval": interval, "limit": limit
    })
    candles = [{
        "time": k[0], "open": float(k[1]), "high": float(k[2]),
        "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])
    } for k in data]
    return {"symbol": symbol.upper(), "interval": interval, "candles": candles}


@app.get("/market/orderbook/{symbol}", tags=["Market Data"])
@limiter.limit("20/minute")
async def get_orderbook(symbol: str, request: Request, limit: int = 20):
    """Get order book (bids and asks)."""
    data = await binance_public_request("/api/v3/depth", {
        "symbol": symbol.upper(), "limit": min(limit, 100)
    })
    return {
        "symbol": symbol.upper(),
        "bids": [[float(p), float(q)] for p, q in data["bids"][:10]],
        "asks": [[float(p), float(q)] for p, q in data["asks"][:10]],
    }


# ─────────────────────────────────────────
# ACCOUNT (AUTHENTICATED)
# ─────────────────────────────────────────
@app.post("/account/info", tags=["Account"])
@limiter.limit("10/minute")
async def get_account_info(creds: Credentials, request: Request):
    """Get account information and balances."""
    data = await binance_signed_request("GET", "/api/v3/account", creds.api_key, creds.api_secret)
    balances = [
        {"asset": b["asset"], "free": float(b["free"]), "locked": float(b["locked"])}
        for b in data["balances"]
        if float(b["free"]) > 0 or float(b["locked"]) > 0
    ]
    return {
        "account_type": data.get("accountType", "SPOT"),
        "can_trade": data.get("canTrade", False),
        "can_withdraw": data.get("canWithdraw", False),
        "maker_commission": data.get("makerCommission", 0),
        "taker_commission": data.get("takerCommission", 0),
        "balances": balances,
        "total_assets": len(balances),
    }


@app.post("/account/balance/{asset}", tags=["Account"])
@limiter.limit("20/minute")
async def get_asset_balance(asset: str, creds: Credentials, request: Request):
    """Get balance for a specific asset."""
    data = await binance_signed_request("GET", "/api/v3/account", creds.api_key, creds.api_secret)
    for b in data["balances"]:
        if b["asset"].upper() == asset.upper():
            return {
                "asset": asset.upper(),
                "free": float(b["free"]),
                "locked": float(b["locked"]),
                "total": float(b["free"]) + float(b["locked"])
            }
    raise HTTPException(status_code=404, detail=f"Asset {asset.upper()} not found in account")


# ─────────────────────────────────────────
# ORDERS
# ─────────────────────────────────────────
@app.post("/orders/place", tags=["Orders"])
@limiter.limit("10/minute")
async def place_order(order: OrderRequest, request: Request):
    """
    Place a buy or sell order on Binance.
    Supports MARKET and LIMIT orders.
    """
    side = order.side.upper()
    order_type = order.order_type.upper()

    if side not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")
    if order_type not in ["MARKET", "LIMIT"]:
        raise HTTPException(status_code=400, detail="Order type must be MARKET or LIMIT")
    if order_type == "LIMIT" and not order.price:
        raise HTTPException(status_code=400, detail="Price required for LIMIT orders")
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    params = {
        "symbol": order.symbol.upper(),
        "side": side,
        "type": order_type,
        "quantity": f"{order.quantity:.8f}".rstrip("0").rstrip("."),
    }

    if order_type == "LIMIT":
        params["price"] = f"{order.price:.8f}".rstrip("0").rstrip(".")
        params["timeInForce"] = order.time_in_force or "GTC"

    logger.info(f"Placing {side} {order_type} order: {order.symbol} qty={order.quantity}")

    data = await binance_signed_request("POST", "/api/v3/order", order.api_key, order.api_secret, body=params)

    return {
        "success": True,
        "order_id": data.get("orderId"),
        "client_order_id": data.get("clientOrderId"),
        "symbol": data.get("symbol"),
        "side": data.get("side"),
        "type": data.get("type"),
        "status": data.get("status"),
        "quantity": float(data.get("origQty", 0)),
        "price": float(data.get("price", 0)) if data.get("price") != "0.00000000" else None,
        "executed_qty": float(data.get("executedQty", 0)),
        "time": data.get("transactTime"),
        "fills": data.get("fills", []),
    }


@app.post("/orders/test", tags=["Orders"])
@limiter.limit("20/minute")
async def test_order(order: OrderRequest, request: Request):
    """
    Test an order WITHOUT actually placing it.
    Use this to validate order parameters before going live.
    """
    params = {
        "symbol": order.symbol.upper(),
        "side": order.side.upper(),
        "type": order.order_type.upper(),
        "quantity": f"{order.quantity:.8f}",
    }
    if order.order_type.upper() == "LIMIT":
        params["price"] = f"{order.price:.8f}"
        params["timeInForce"] = "GTC"

    await binance_signed_request("POST", "/api/v3/order/test", order.api_key, order.api_secret, body=params)
    return {"success": True, "message": "Order parameters are valid — test passed ✅", "params": params}


@app.post("/orders/open", tags=["Orders"])
@limiter.limit("10/minute")
async def get_open_orders(creds: Credentials, request: Request, symbol: Optional[str] = None):
    """Get all open orders (optionally filtered by symbol)."""
    params = {}
    if symbol:
        params["symbol"] = symbol.upper()
    data = await binance_signed_request("GET", "/api/v3/openOrders", creds.api_key, creds.api_secret, params=params)
    orders = [{
        "order_id": o["orderId"],
        "symbol": o["symbol"],
        "side": o["side"],
        "type": o["type"],
        "status": o["status"],
        "quantity": float(o["origQty"]),
        "price": float(o["price"]),
        "executed_qty": float(o["executedQty"]),
        "time": o["time"],
    } for o in data]
    return {"open_orders": orders, "count": len(orders)}


@app.post("/orders/history", tags=["Orders"])
@limiter.limit("10/minute")
async def get_order_history(creds: Credentials, request: Request, symbol: str = "BTCUSDT", limit: int = 50):
    """Get order history for a symbol."""
    params = {"symbol": symbol.upper(), "limit": min(limit, 500)}
    data = await binance_signed_request("GET", "/api/v3/allOrders", creds.api_key, creds.api_secret, params=params)
    orders = [{
        "order_id": o["orderId"],
        "symbol": o["symbol"],
        "side": o["side"],
        "type": o["type"],
        "status": o["status"],
        "quantity": float(o["origQty"]),
        "price": float(o["price"]),
        "executed_qty": float(o["executedQty"]),
        "time": o["time"],
    } for o in data]
    return {"history": orders, "count": len(orders)}


@app.post("/orders/trades", tags=["Orders"])
@limiter.limit("10/minute")
async def get_trade_history(creds: Credentials, request: Request, symbol: str = "BTCUSDT", limit: int = 50):
    """Get actual trade/fill history."""
    params = {"symbol": symbol.upper(), "limit": min(limit, 500)}
    data = await binance_signed_request("GET", "/api/v3/myTrades", creds.api_key, creds.api_secret, params=params)
    trades = [{
        "trade_id": t["id"],
        "order_id": t["orderId"],
        "symbol": t["symbol"],
        "side": "BUY" if t["isBuyer"] else "SELL",
        "quantity": float(t["qty"]),
        "price": float(t["price"]),
        "commission": float(t["commission"]),
        "commission_asset": t["commissionAsset"],
        "pnl_estimate": None,
        "time": t["time"],
    } for t in data]
    return {"trades": trades, "count": len(trades)}


@app.delete("/orders/cancel", tags=["Orders"])
@limiter.limit("10/minute")
async def cancel_order(cancel: CancelOrderRequest, request: Request):
    """Cancel an open order by order ID."""
    params = {"symbol": cancel.symbol.upper(), "orderId": cancel.order_id}
    data = await binance_signed_request("DELETE", "/api/v3/order", cancel.api_key, cancel.api_secret, params=params)
    return {
        "success": True,
        "order_id": data.get("orderId"),
        "symbol": data.get("symbol"),
        "status": data.get("status"),
        "message": "Order cancelled successfully"
    }


@app.post("/orders/cancel-all", tags=["Orders"])
@limiter.limit("5/minute")
async def cancel_all_orders(creds: Credentials, request: Request, symbol: str = "BTCUSDT"):
    """Cancel ALL open orders for a symbol."""
    params = {"symbol": symbol.upper()}
    data = await binance_signed_request("DELETE", "/api/v3/openOrders", creds.api_key, creds.api_secret, params=params)
    return {
        "success": True,
        "cancelled_count": len(data),
        "symbol": symbol.upper(),
        "message": f"Cancelled {len(data)} orders"
    }


# ─────────────────────────────────────────
# WEBSOCKET — LIVE PRICES
# ─────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WebSocket connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
        logger.info(f"WebSocket disconnected. Total: {len(self.active)}")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()


@app.websocket("/ws/prices/{symbols}")
async def websocket_prices(websocket: WebSocket, symbols: str):
    """
    WebSocket endpoint for live price streaming.
    Connect to: ws://localhost:8000/ws/prices/btcusdt,ethusdt
    Streams real-time price updates from Binance.
    """
    await manager.connect(websocket)
    symbol_list = [s.strip().lower() for s in symbols.split(",")]
    stream = "/".join([f"{s}@miniTicker" for s in symbol_list])
    ws_url = f"{BINANCE_WS}/stream?streams={stream}"

    logger.info(f"Starting price stream for: {symbol_list}")

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", ws_url) as _:
                pass
    except Exception:
        pass

    # Poll prices and push to client
    try:
        while True:
            prices = {}
            async with httpx.AsyncClient(timeout=5.0) as client:
                tasks = [
                    client.get(f"{BINANCE_BASE}/api/v3/ticker/24hr", params={"symbol": s.upper()})
                    for s in symbol_list
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

            for sym, resp in zip(symbol_list, responses):
                if isinstance(resp, Exception): continue
                if resp.status_code != 200: continue
                d = resp.json()
                prices[sym.upper()] = {
                    "symbol": sym.upper(),
                    "price": float(d["lastPrice"]),
                    "change_pct": float(d["priceChangePercent"]),
                    "high": float(d["highPrice"]),
                    "low": float(d["lowPrice"]),
                    "volume": float(d["volume"]),
                    "timestamp": int(time.time() * 1000),
                }

            await websocket.send_json({"type": "prices", "data": prices})
            await asyncio.sleep(3)  # update every 3 seconds

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/ticker/{symbol}")
async def websocket_single_ticker(websocket: WebSocket, symbol: str):
    """
    WebSocket for single symbol live ticker.
    Connect to: ws://localhost:8000/ws/ticker/BTCUSDT
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await binance_public_request("/api/v3/ticker/24hr", {"symbol": symbol.upper()})
            await websocket.send_json({
                "type": "ticker",
                "symbol": symbol.upper(),
                "price": float(data["lastPrice"]),
                "change_pct": float(data["priceChangePercent"]),
                "high": float(data["highPrice"]),
                "low": float(data["lowPrice"]),
                "volume": float(data["volume"]),
                "timestamp": int(time.time() * 1000),
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Ticker WebSocket error: {e}")
        manager.disconnect(websocket)


# ─────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "code": exc.status_code, "message": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": True, "code": 500, "message": "Internal server error"}
    )
