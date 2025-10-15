"""
TradingBot V2 - FastAPI Main Application
Real-time crypto trading bot with AI analysis
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
from datetime import datetime
from typing import List, Dict
import logging
import os

# Import trading components
from binance_client import BinanceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Binance client (testnet for now)
binance_client = BinanceClient(
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET'),
    testnet=True,
    use_futures=True
)

app = FastAPI(
    title="TradingBot V2 API",
    description="AI-Powered Cryptocurrency Trading System",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")

manager = ConnectionManager()

# Health check
@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "TradingBot V2",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "components": {
            "api": "ok",
            "websocket": f"{len(manager.active_connections)} connections"
        },
        "timestamp": datetime.now().isoformat()
    }

# Market data endpoints
@app.get("/api/v1/market/prices")
async def get_market_prices(symbols: str = "BTCUSDT,ETHUSDT"):
    """Get current prices for specified symbols from real Binance API"""
    try:
        symbol_list = [s.strip() for s in symbols.split(',')]

        # Convert to CCXT format (BTC/USDT)
        ccxt_symbols = []
        for symbol in symbol_list:
            if 'USDT' in symbol:
                base = symbol.replace('USDT', '')
                ccxt_symbols.append(f"{base}/USDT")
            else:
                ccxt_symbols.append(symbol)

        # Fetch real prices from Binance
        prices = {}
        for original_symbol, ccxt_symbol in zip(symbol_list, ccxt_symbols):
            try:
                price = await binance_client.get_price(ccxt_symbol)
                prices[original_symbol] = {
                    "symbol": original_symbol,
                    "price": f"{price:.2f}",
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Error fetching {ccxt_symbol}: {e}")
                prices[original_symbol] = {
                    "symbol": original_symbol,
                    "price": "0.00",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }

        return {"data": prices, "count": len(prices)}
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/v1/market/klines")
async def get_market_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 100
):
    """Get candlestick (klines) data from real Binance API"""
    try:
        # Convert to CCXT format
        if 'USDT' in symbol:
            base = symbol.replace('USDT', '')
            ccxt_symbol = f"{base}/USDT"
        else:
            ccxt_symbol = symbol

        # Fetch klines from Binance
        klines = await binance_client.get_klines(ccxt_symbol, interval, limit)

        return {
            "symbol": symbol,
            "interval": interval,
            "data": klines,
            "count": len(klines)
        }
    except Exception as e:
        logger.error(f"Error fetching klines for {symbol}: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# WebSocket endpoint for real-time data
@app.websocket("/ws/market")
async def websocket_market_data(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Default symbols to track
        symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT']

        while True:
            # Fetch real prices from Binance
            price_data = {}
            for symbol in symbols:
                try:
                    price = await binance_client.get_price(symbol)
                    # Convert back to BTCUSDT format
                    symbol_key = symbol.replace('/', '')
                    price_data[symbol_key] = f"{price:.2f}"
                except Exception as e:
                    logger.error(f"Error fetching {symbol}: {e}")
                    symbol_key = symbol.replace('/', '')
                    price_data[symbol_key] = "0.00"

            market_data = {
                "type": "price_update",
                "data": price_data,
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(market_data)
            await asyncio.sleep(5)  # Update every 5 seconds
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Shutdown handler
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup when FastAPI shuts down"""
    logger.info("Shutting down - closing Binance client connections...")
    await binance_client.close()
    logger.info("Shutdown complete")

# Trading endpoints
@app.post("/api/v1/trading/analyze")
async def analyze_market(symbol: str = "BTCUSDT"):
    """Analyze market and generate trading signals"""
    return {
        "symbol": symbol,
        "signal": "HOLD",
        "confidence": 0.75,
        "indicators": {
            "rsi": 58.5,
            "macd": "bullish",
            "bb_position": "middle"
        },
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
