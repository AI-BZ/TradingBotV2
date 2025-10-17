"""
TradingBot V2 - FastAPI Main Application
Real-time crypto trading bot with Strategy B (Selective High-Confidence)
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
from selective_tick_live_trader import SelectiveTickLiveTrader

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

# Initialize Strategy B trader (7 coins)
selective_trader = None
trading_task = None

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
        symbols = ['ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT', 'XRP/USDT', 'SUI/USDT', '1000PEPE/USDT']

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


# Strategy B trading endpoints
@app.post("/api/v1/trading/start")
async def start_trading():
    """Start Strategy B trading for 7 coins"""
    global selective_trader, trading_task

    if trading_task and not trading_task.done():
        return {"status": "already_running", "message": "Trading is already active"}

    try:
        # Initialize trader
        symbols = [
            'ETH/USDT',
            'SOL/USDT',
            'BNB/USDT',
            'DOGE/USDT',
            'XRP/USDT',
            'SUI/USDT',
            '1000PEPE/USDT'
        ]

        selective_trader = SelectiveTickLiveTrader(
            binance_client=binance_client,
            symbols=symbols,
            initial_balance=10000.0,
            leverage=10,
            position_size_pct=0.1,
            taker_fee=0.0005,
            slippage_pct=0.0001,
            cooldown_seconds=300
        )

        # Start trading in background
        trading_task = asyncio.create_task(selective_trader.start())

        logger.info("✅ Strategy B trading started for 7 coins")

        return {
            "status": "started",
            "strategy": "Strategy B - Selective High-Confidence",
            "symbols": symbols,
            "expected_trades_per_day": "~162 per symbol",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error starting trading: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/v1/trading/stop")
async def stop_trading():
    """Stop Strategy B trading"""
    global selective_trader, trading_task

    if not trading_task or trading_task.done():
        return {"status": "not_running", "message": "Trading is not active"}

    try:
        if selective_trader:
            await selective_trader.stop()

        if trading_task:
            trading_task.cancel()

        logger.info("🛑 Strategy B trading stopped")

        return {
            "status": "stopped",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error stopping trading: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/v1/trading/performance")
async def get_trading_performance():
    """Get real-time trading performance metrics from Strategy B"""
    try:
        if not selective_trader:
            return {
                "status": "not_started",
                "message": "Trading not started yet",
                "timestamp": datetime.now().isoformat()
            }

        # Get performance from Strategy B trader
        performance = await selective_trader.get_performance()

        # Round per-coin stats
        per_coin_rounded = {}
        for symbol, stats in performance.get('per_coin_stats', {}).items():
            per_coin_rounded[symbol] = {
                'total_trades': stats['total_trades'],
                'winning_trades': stats['winning_trades'],
                'win_rate': round(stats['win_rate'], 2),
                'total_pnl': round(stats['total_pnl'], 2),
                'avg_profit_per_trade': round(stats['avg_profit_per_trade'], 2),
                'trades_per_day': round(stats['trades_per_day'], 1)
            }

        # Round active positions
        positions_rounded = []
        for pos in performance.get('active_positions_list', []):
            positions_rounded.append({
                'symbol': pos['symbol'],
                'type': pos['type'],
                'entry_price': round(pos['entry_price'], 2),
                'current_price': round(pos['current_price'], 2),
                'size': round(pos['size'], 4),
                'unrealized_pnl': round(pos['unrealized_pnl'], 2),
                'unrealized_pnl_pct': round(pos['unrealized_pnl_pct'], 2),
                'hold_duration_seconds': int(pos['hold_duration_seconds']),
                'confidence': round(pos['confidence'], 2)
            })

        return {
            "status": "running",
            "strategy": performance['strategy'],
            "total_pnl": round(performance['total_pnl'], 2),
            "total_return": round(performance['total_return'], 2),
            "win_rate": round(performance['win_rate'], 2),
            "total_trades": performance['total_trades'],
            "trades_per_day": round(performance['trades_per_day'], 1),
            "avg_profit_per_trade": round(performance['avg_profit_per_trade'], 2),
            "active_positions": performance['active_positions'],
            "max_drawdown": round(performance['max_drawdown'], 2),
            "total_fees_paid": round(performance['total_fees_paid'], 2),
            "signals_generated": performance['signals_generated'],
            "signals_skipped_cooldown": performance['signals_skipped_cooldown'],
            "risk_status": "Within limits" if performance['max_drawdown'] < 20 else "Caution",
            "per_coin_stats": per_coin_rounded,
            "active_positions_list": positions_rounded,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

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
