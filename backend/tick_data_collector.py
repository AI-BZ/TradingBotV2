"""
Tick Data Collection System
Real-time tick data collection using Binance Futures WebSocket

CRITICAL RULE: This is the ONLY data source for the entire trading system.
NO candle data (1m, 5m, 1h, etc.) should ever be used in live trading.

Update Frequency: ~100ms (10 times per second)
Data Source: wss://fstream.binance.com/ws/{symbol}@ticker
Latency: < 500ms target (vs 0-3,600,000ms with 1h candles)
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Deque, Optional
from collections import deque
from dataclasses import dataclass, asdict
import websockets
import pandas as pd
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Tick:
    """Single tick data point"""
    symbol: str
    timestamp: datetime
    price: float           # Last traded price
    bid: float            # Best bid price
    ask: float            # Best ask price
    bid_qty: float        # Best bid quantity
    ask_qty: float        # Best ask quantity
    volume_24h: float     # 24-hour volume
    quote_volume_24h: float  # 24-hour quote volume
    price_change_pct: float  # 24-hour price change %

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'bid': self.bid,
            'ask': self.ask,
            'bid_qty': self.bid_qty,
            'ask_qty': self.ask_qty,
            'volume_24h': self.volume_24h,
            'quote_volume_24h': self.quote_volume_24h,
            'price_change_pct': self.price_change_pct
        }


class TickDataCollector:
    """Real-time tick data collector using Binance Futures WebSocket

    This is the FOUNDATION of the entire trading system.
    All trading decisions, indicators, and signals MUST use tick data from this collector.
    """

    def __init__(
        self,
        symbols: List[str],
        buffer_size: int = 10000,
        save_to_disk: bool = False,
        data_dir: str = "tick_data"
    ):
        """Initialize tick data collector

        Args:
            symbols: List of symbols to collect (e.g., ['BTC/USDT', 'ETH/USDT'])
            buffer_size: Number of ticks to keep in memory per symbol (default: 10,000)
            save_to_disk: Whether to save ticks to disk for backtesting
            data_dir: Directory to save tick data files
        """
        self.symbols = symbols
        self.buffer_size = buffer_size
        self.save_to_disk = save_to_disk
        self.data_dir = Path(data_dir)

        # Create data directory if saving to disk
        if self.save_to_disk:
            self.data_dir.mkdir(exist_ok=True)

        # In-memory circular buffers (10,000 ticks per symbol = ~16 minutes at 10 ticks/sec)
        self.tick_buffers: Dict[str, Deque[Tick]] = {
            symbol: deque(maxlen=buffer_size) for symbol in symbols
        }

        # WebSocket connection tracking
        self.ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.connection_status: Dict[str, bool] = {symbol: False for symbol in symbols}

        # Statistics
        self.tick_counts: Dict[str, int] = {symbol: 0 for symbol in symbols}
        self.last_tick_time: Dict[str, datetime] = {}
        self.reconnect_counts: Dict[str, int] = {symbol: 0 for symbol in symbols}

        # Running flag
        self.is_running = False

        logger.info(f"✅ TickDataCollector initialized")
        logger.info(f"   Symbols: {', '.join(symbols)}")
        logger.info(f"   Buffer size: {buffer_size:,} ticks/symbol (~{buffer_size/10/60:.1f} minutes)")
        logger.info(f"   Save to disk: {save_to_disk}")

    def get_ws_url(self, symbol: str) -> str:
        """Get WebSocket URL for a symbol

        Binance Futures Ticker Stream provides:
        - Last price, bid/ask prices and quantities
        - 24h volume and price change
        - Update frequency: ~100ms (10 times per second)
        """
        # Convert BTC/USDT → btcusdt
        exchange_symbol = symbol.replace('/', '').lower()
        return f"wss://fstream.binance.com/ws/{exchange_symbol}@ticker"

    async def subscribe_ticker_stream(self, symbol: str):
        """Subscribe to real-time ticker stream for a symbol

        This provides TRUE tick-by-tick data at ~100ms intervals.
        NO candle data is used.
        """
        ws_url = self.get_ws_url(symbol)

        while self.is_running:
            try:
                logger.info(f"📡 Connecting to {symbol} ticker stream...")

                async with websockets.connect(ws_url) as websocket:
                    self.ws_connections[symbol] = websocket
                    self.connection_status[symbol] = True
                    logger.info(f"✅ Connected to {symbol} stream")

                    # Receive and process ticks
                    async for message in websocket:
                        if not self.is_running:
                            break

                        try:
                            data = json.loads(message)

                            # Parse tick data
                            tick = Tick(
                                symbol=symbol,
                                timestamp=datetime.fromtimestamp(data['E'] / 1000),
                                price=float(data['c']),          # Last price
                                bid=float(data['b']),            # Best bid
                                ask=float(data['a']),            # Best ask
                                bid_qty=float(data['B']),        # Best bid qty
                                ask_qty=float(data['A']),        # Best ask qty
                                volume_24h=float(data['v']),     # 24h volume
                                quote_volume_24h=float(data['q']), # 24h quote volume
                                price_change_pct=float(data['P']) # 24h price change %
                            )

                            # Store in buffer
                            self.tick_buffers[symbol].append(tick)
                            self.tick_counts[symbol] += 1
                            self.last_tick_time[symbol] = tick.timestamp

                            # Save to disk if enabled
                            if self.save_to_disk and self.tick_counts[symbol] % 100 == 0:
                                await self._save_ticks_to_disk(symbol)

                            # Log every 100 ticks
                            if self.tick_counts[symbol] % 100 == 0:
                                logger.debug(
                                    f"{symbol}: {self.tick_counts[symbol]:,} ticks | "
                                    f"Price: ${tick.price:,.2f} | "
                                    f"Buffer: {len(self.tick_buffers[symbol]):,}/{self.buffer_size:,}"
                                )

                        except Exception as e:
                            logger.error(f"Error processing {symbol} tick: {e}")
                            continue

            except websockets.exceptions.ConnectionClosed:
                self.connection_status[symbol] = False
                logger.warning(f"⚠️  {symbol} connection closed, reconnecting in 5s...")
                self.reconnect_counts[symbol] += 1
                await asyncio.sleep(5)

            except Exception as e:
                self.connection_status[symbol] = False
                logger.error(f"❌ {symbol} WebSocket error: {e}")
                self.reconnect_counts[symbol] += 1
                await asyncio.sleep(5)

    async def _save_ticks_to_disk(self, symbol: str):
        """Save recent ticks to disk for backtesting"""
        try:
            # Get last 100 ticks
            recent_ticks = list(self.tick_buffers[symbol])[-100:]

            # Create filename with date
            date_str = datetime.now().strftime('%Y%m%d')
            filename = self.data_dir / f"{symbol.replace('/', '_')}_{date_str}.jsonl"

            # Append to file (JSON Lines format)
            with open(filename, 'a') as f:
                for tick in recent_ticks:
                    f.write(json.dumps(tick.to_dict()) + '\n')

        except Exception as e:
            logger.error(f"Error saving {symbol} ticks to disk: {e}")

    async def start(self):
        """Start collecting tick data for all symbols"""
        logger.info("\n" + "="*80)
        logger.info("🚀 STARTING TICK DATA COLLECTION SYSTEM")
        logger.info("="*80)
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Expected update rate: ~10 ticks/second/symbol")
        logger.info("="*80 + "\n")

        self.is_running = True

        # Create tasks for each symbol
        tasks = [
            asyncio.create_task(self.subscribe_ticker_stream(symbol))
            for symbol in self.symbols
        ]

        # Run all streams concurrently
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("\n⏸️  Tick collection stopped by user")
        except Exception as e:
            logger.error(f"❌ Tick collection error: {e}", exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """Stop all tick collection streams"""
        logger.info("\n🛑 Stopping tick data collection...")

        self.is_running = False

        # Close all WebSocket connections
        for symbol, ws in self.ws_connections.items():
            try:
                await ws.close()
                logger.info(f"✅ Closed {symbol} connection")
            except Exception as e:
                logger.error(f"Error closing {symbol} connection: {e}")

        # Display final statistics
        logger.info("\n" + "="*80)
        logger.info("📊 TICK COLLECTION SUMMARY")
        logger.info("="*80)
        for symbol in self.symbols:
            logger.info(
                f"{symbol}: "
                f"{self.tick_counts[symbol]:,} ticks collected | "
                f"{self.reconnect_counts[symbol]} reconnects | "
                f"Buffer: {len(self.tick_buffers[symbol]):,} ticks"
            )
        logger.info("="*80 + "\n")

    def get_recent_ticks(self, symbol: str, count: int = 100) -> List[Tick]:
        """Get recent ticks for a symbol

        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
            count: Number of recent ticks to retrieve

        Returns:
            List of Tick objects, most recent last
        """
        buffer = self.tick_buffers.get(symbol, deque())
        return list(buffer)[-count:]

    def get_tick_buffer_as_df(self, symbol: str, count: Optional[int] = None) -> pd.DataFrame:
        """Get tick buffer as pandas DataFrame for analysis

        Args:
            symbol: Trading symbol
            count: Number of recent ticks (None = all in buffer)

        Returns:
            DataFrame with columns: timestamp, price, bid, ask, volume_24h, etc.
        """
        ticks = self.get_recent_ticks(symbol, count) if count else list(self.tick_buffers[symbol])

        if not ticks:
            return pd.DataFrame()

        df = pd.DataFrame([tick.to_dict() for tick in ticks])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

        return df

    def get_latest_tick(self, symbol: str) -> Optional[Tick]:
        """Get most recent tick for a symbol"""
        buffer = self.tick_buffers.get(symbol, deque())
        return buffer[-1] if buffer else None

    def get_statistics(self) -> dict:
        """Get collection statistics"""
        return {
            'is_running': self.is_running,
            'symbols': self.symbols,
            'tick_counts': self.tick_counts,
            'connection_status': self.connection_status,
            'reconnect_counts': self.reconnect_counts,
            'last_tick_times': {
                symbol: time.isoformat() if time else None
                for symbol, time in self.last_tick_time.items()
            },
            'buffer_sizes': {
                symbol: len(buffer)
                for symbol, buffer in self.tick_buffers.items()
            }
        }


async def main():
    """Test tick data collector"""
    # Load active symbols from config
    import json
    with open('coin_specific_params.json', 'r') as f:
        config = json.load(f)

    # Get active symbols (non-excluded)
    active_symbols = [
        symbol for symbol, params in config['coin_parameters'].items()
        if not params.get('excluded', False)
    ]

    logger.info(f"Using {len(active_symbols)} active symbols from v{config['version']}")

    # Create collector
    collector = TickDataCollector(
        symbols=active_symbols,
        buffer_size=10000,  # ~16 minutes of data
        save_to_disk=True,  # Save for backtesting
        data_dir="tick_data"
    )

    # Start collection
    await collector.start()


if __name__ == "__main__":
    asyncio.run(main())
