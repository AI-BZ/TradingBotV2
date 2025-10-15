"""
Binance API Client - Real-time market data integration
Supports both REST API and WebSocket streams
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime
import ccxt.async_support as ccxt
import websockets

logger = logging.getLogger(__name__)

class BinanceClient:
    """Async Binance API client for trading bot"""

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        """Initialize Binance client

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet (default: True)
        """
        self.testnet = testnet
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'test': testnet
            }
        })

        # WebSocket URLs
        if testnet:
            self.ws_base_url = "wss://testnet.binance.vision/ws"
        else:
            self.ws_base_url = "wss://stream.binance.com:9443/ws"

        self.ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.callbacks: Dict[str, List[Callable]] = {}

        logger.info(f"BinanceClient initialized (testnet={testnet})")

    async def get_price(self, symbol: str) -> float:
        """Get current price for a symbol

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')

        Returns:
            Current price as float
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            raise

    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get prices for multiple symbols concurrently

        Args:
            symbols: List of trading pairs

        Returns:
            Dictionary of symbol: price
        """
        tasks = [self.get_price(symbol) for symbol in symbols]
        prices = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for symbol, price in zip(symbols, prices):
            if isinstance(price, Exception):
                logger.error(f"Error fetching {symbol}: {price}")
                result[symbol] = 0.0
            else:
                result[symbol] = price

        return result

    async def get_klines(
        self,
        symbol: str,
        interval: str = '1m',
        limit: int = 100
    ) -> List[Dict]:
        """Get candlestick (klines) data

        Args:
            symbol: Trading pair
            interval: Timeframe ('1m', '5m', '1h', '1d', etc.)
            limit: Number of candles

        Returns:
            List of OHLCV data
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol,
                timeframe=interval,
                limit=limit
            )

            # Convert to dict format
            klines = []
            for candle in ohlcv:
                klines.append({
                    'timestamp': candle[0],
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })

            return klines
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            raise

    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to real-time ticker updates via WebSocket

        Args:
            symbol: Trading pair (e.g., 'btcusdt')
            callback: Async function to call with ticker data
        """
        stream_name = f"{symbol.lower()}@ticker"
        ws_url = f"{self.ws_base_url}/{stream_name}"

        if stream_name not in self.callbacks:
            self.callbacks[stream_name] = []
        self.callbacks[stream_name].append(callback)

        # Start WebSocket connection if not exists
        if stream_name not in self.ws_connections:
            asyncio.create_task(self._ws_handler(ws_url, stream_name))

        logger.info(f"Subscribed to {symbol} ticker updates")

    async def _ws_handler(self, ws_url: str, stream_name: str):
        """Handle WebSocket connection and messages

        Args:
            ws_url: WebSocket URL
            stream_name: Stream identifier
        """
        try:
            async with websockets.connect(ws_url) as websocket:
                self.ws_connections[stream_name] = websocket
                logger.info(f"WebSocket connected: {stream_name}")

                async for message in websocket:
                    data = json.loads(message)

                    # Call all registered callbacks
                    callbacks = self.callbacks.get(stream_name, [])
                    for callback in callbacks:
                        try:
                            await callback(data)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

        except Exception as e:
            logger.error(f"WebSocket error for {stream_name}: {e}")
            # Remove from connections
            if stream_name in self.ws_connections:
                del self.ws_connections[stream_name]

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None
    ) -> Dict:
        """Place a trading order

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            amount: Order quantity
            price: Limit price (required for limit orders)

        Returns:
            Order information
        """
        try:
            if order_type == 'market':
                order = await self.exchange.create_market_order(
                    symbol, side, amount
                )
            elif order_type == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                order = await self.exchange.create_limit_order(
                    symbol, side, amount, price
                )
            else:
                raise ValueError(f"Invalid order type: {order_type}")

            logger.info(f"Order placed: {side} {amount} {symbol} @ {price or 'market'}")
            return order

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    async def get_balance(self, currency: str = 'USDT') -> float:
        """Get account balance for a currency

        Args:
            currency: Currency symbol (default: 'USDT')

        Returns:
            Available balance
        """
        try:
            balance = await self.exchange.fetch_balance()
            return float(balance[currency]['free'])
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            raise

    async def close(self):
        """Close all connections"""
        await self.exchange.close()

        # Close WebSocket connections
        for ws in self.ws_connections.values():
            await ws.close()

        logger.info("BinanceClient closed")


# Example usage
async def main():
    """Test Binance client"""
    client = BinanceClient(testnet=True)

    try:
        # Get single price
        btc_price = await client.get_price('BTC/USDT')
        print(f"BTC Price: ${btc_price:,.2f}")

        # Get multiple prices
        prices = await client.get_prices(['BTC/USDT', 'ETH/USDT', 'BNB/USDT'])
        for symbol, price in prices.items():
            print(f"{symbol}: ${price:,.2f}")

        # Get klines
        klines = await client.get_klines('BTC/USDT', '1h', 24)
        print(f"\nFetched {len(klines)} hourly candles")
        print(f"Latest close: ${klines[-1]['close']:,.2f}")

        # Subscribe to real-time ticker
        async def on_ticker(data):
            print(f"Real-time: {data['s']} = ${float(data['c']):,.2f}")

        await client.subscribe_ticker('btcusdt', on_ticker)

        # Keep running for 10 seconds
        await asyncio.sleep(10)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
