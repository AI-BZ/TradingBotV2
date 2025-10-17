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

    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True, use_futures: bool = True):
        """Initialize Binance client

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet (default: True)
            use_futures: Use futures market (default: True for LONG/SHORT trading)
        """
        self.testnet = testnet
        self.use_futures = use_futures
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future' if use_futures else 'spot',
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

    async def get_ticker(self, symbol: str) -> Dict:
        """Get 24h ticker statistics for a symbol

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')

        Returns:
            Dictionary with volume, percentage change, etc.
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            raise

    async def get_orderbook(self, symbol: str, limit: int = 5) -> Dict:
        """Get orderbook (bids/asks) for a symbol

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            limit: Number of bids/asks to fetch

        Returns:
            Dictionary with 'bids' and 'asks' arrays
        """
        try:
            orderbook = await self.exchange.fetch_order_book(symbol, limit)
            return orderbook
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {e}")
            raise

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

    async def set_leverage(self, symbol: str, leverage: int = 10):
        """Set leverage for futures trading

        Args:
            symbol: Trading pair
            leverage: Leverage multiplier (1-125)
        """
        if not self.use_futures:
            logger.warning("Leverage setting only available for futures trading")
            return

        try:
            await self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")
            raise

    async def open_long_position(
        self,
        symbol: str,
        amount: float,
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.05
    ) -> Dict:
        """Open a LONG position (buy futures contract)

        Args:
            symbol: Trading pair
            amount: Position size
            stop_loss_pct: Stop loss percentage (default 3%)
            take_profit_pct: Take profit percentage (default 5%)

        Returns:
            Order information with stop loss and take profit
        """
        try:
            # Get current price
            current_price = await self.get_price(symbol)

            # Open LONG position (market buy)
            order = await self.exchange.create_market_order(
                symbol, 'buy', amount
            )

            # Calculate stop loss and take profit prices
            stop_loss_price = current_price * (1 - stop_loss_pct)
            take_profit_price = current_price * (1 + take_profit_pct)

            logger.info(f"LONG position opened: {amount} {symbol} @ ${current_price:.2f}")
            logger.info(f"  Stop Loss: ${stop_loss_price:.2f} (-{stop_loss_pct:.1%})")
            logger.info(f"  Take Profit: ${take_profit_price:.2f} (+{take_profit_pct:.1%})")

            # Place stop loss order
            try:
                stop_order = await self.exchange.create_order(
                    symbol, 'STOP_MARKET', 'sell', amount,
                    params={'stopPrice': stop_loss_price}
                )
                order['stop_loss_order'] = stop_order
            except Exception as e:
                logger.warning(f"Could not place stop loss: {e}")

            # Place take profit order
            try:
                tp_order = await self.exchange.create_order(
                    symbol, 'TAKE_PROFIT_MARKET', 'sell', amount,
                    params={'stopPrice': take_profit_price}
                )
                order['take_profit_order'] = tp_order
            except Exception as e:
                logger.warning(f"Could not place take profit: {e}")

            return order

        except Exception as e:
            logger.error(f"Error opening LONG position: {e}")
            raise

    async def open_short_position(
        self,
        symbol: str,
        amount: float,
        stop_loss_pct: float = 0.03,
        take_profit_pct: float = 0.05
    ) -> Dict:
        """Open a SHORT position (sell futures contract)

        Args:
            symbol: Trading pair
            amount: Position size
            stop_loss_pct: Stop loss percentage (default 3%)
            take_profit_pct: Take profit percentage (default 5%)

        Returns:
            Order information with stop loss and take profit
        """
        try:
            # Get current price
            current_price = await self.get_price(symbol)

            # Open SHORT position (market sell)
            order = await self.exchange.create_market_order(
                symbol, 'sell', amount
            )

            # Calculate stop loss and take profit prices
            stop_loss_price = current_price * (1 + stop_loss_pct)  # Higher for shorts
            take_profit_price = current_price * (1 - take_profit_pct)  # Lower for shorts

            logger.info(f"SHORT position opened: {amount} {symbol} @ ${current_price:.2f}")
            logger.info(f"  Stop Loss: ${stop_loss_price:.2f} (+{stop_loss_pct:.1%})")
            logger.info(f"  Take Profit: ${take_profit_price:.2f} (-{take_profit_pct:.1%})")

            # Place stop loss order
            try:
                stop_order = await self.exchange.create_order(
                    symbol, 'STOP_MARKET', 'buy', amount,
                    params={'stopPrice': stop_loss_price}
                )
                order['stop_loss_order'] = stop_order
            except Exception as e:
                logger.warning(f"Could not place stop loss: {e}")

            # Place take profit order
            try:
                tp_order = await self.exchange.create_order(
                    symbol, 'TAKE_PROFIT_MARKET', 'buy', amount,
                    params={'stopPrice': take_profit_price}
                )
                order['take_profit_order'] = tp_order
            except Exception as e:
                logger.warning(f"Could not place take profit: {e}")

            return order

        except Exception as e:
            logger.error(f"Error opening SHORT position: {e}")
            raise

    async def close_position(self, symbol: str, position_type: str) -> Dict:
        """Close an open futures position

        Args:
            symbol: Trading pair
            position_type: 'LONG' or 'SHORT'

        Returns:
            Order information
        """
        try:
            # Get current position
            positions = await self.exchange.fetch_positions([symbol])
            position = next((p for p in positions if p['symbol'] == symbol), None)

            if not position or position['contracts'] == 0:
                logger.warning(f"No open position for {symbol}")
                return None

            amount = abs(position['contracts'])
            side = 'sell' if position_type == 'LONG' else 'buy'

            # Close position with market order
            order = await self.exchange.create_market_order(symbol, side, amount)

            logger.info(f"{position_type} position closed: {amount} {symbol}")
            return order

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            raise

    async def get_open_positions(self) -> List[Dict]:
        """Get all open futures positions

        Returns:
            List of open positions
        """
        try:
            positions = await self.exchange.fetch_positions()
            open_positions = [p for p in positions if p['contracts'] != 0]
            return open_positions
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    async def get_top_coins(self, limit: int = 10, quote_currency: str = 'USDT',
                          filter_volatile: bool = True, max_volatility: float = 0.05) -> List[str]:
        """Get top trading coins by 24h volume with volatility filtering

        Args:
            limit: Number of top coins to return
            quote_currency: Quote currency (default: 'USDT')
            filter_volatile: Filter out extremely volatile coins (default: True)
            max_volatility: Maximum 24h price change % to allow (default: 5%)

        Returns:
            List of top trading symbols (stable, liquid, major coins)
        """
        try:
            # Fetch all tickers
            tickers = await self.exchange.fetch_tickers()

            # Filter by quote currency, volume, and volatility
            usdt_pairs = []

            for symbol, ticker in tickers.items():
                if quote_currency not in symbol or not ticker['quoteVolume']:
                    continue

                # Calculate 24h volatility
                price_change_pct = abs(ticker.get('percentage', 0) / 100) if ticker.get('percentage') else 0

                # Skip extremely volatile coins if filtering enabled
                if filter_volatile and price_change_pct > max_volatility:
                    logger.debug(f"Skipping {symbol}: Too volatile ({price_change_pct:.2%})")
                    continue

                usdt_pairs.append({
                    'symbol': symbol,
                    'volume': ticker['quoteVolume'],
                    'volatility': price_change_pct
                })

            # Sort by volume descending
            sorted_pairs = sorted(usdt_pairs, key=lambda x: x['volume'], reverse=True)

            # Get top N symbols and clean format
            # Remove :USDT suffix that CCXT adds for futures (ETH/USDT:USDT → ETH/USDT)
            top_symbols = []
            for pair in sorted_pairs[:limit]:
                symbol = pair['symbol']
                # Clean symbol format: remove :USDT suffix if present
                clean_symbol = symbol.split(':')[0] if ':' in symbol else symbol
                top_symbols.append(clean_symbol)

            logger.info(f"Top {limit} coins by 24h volume (filtered): {', '.join(top_symbols)}")
            return top_symbols

        except Exception as e:
            logger.error(f"Error fetching top coins: {e}")
            # Fallback to safe, major coins only
            return [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT'
            ]

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
