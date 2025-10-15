"""
Real-Time Data Streaming System
WebSocket을 통해 실시간 시장 데이터를 수집하고 저장하는 시스템
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
from collections import deque
import pandas as pd
from pathlib import Path
import websockets
from binance_client import BinanceClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataStreamer:
    """Real-time market data streamer using WebSocket"""

    def __init__(self, symbols: Optional[List[str]] = None, testnet: bool = False):
        self.testnet = testnet
        self.symbols = symbols or [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT',
            'DOTUSDT', 'MATICUSDT', 'AVAXUSDT', 'UNIUSDT', 'LINKUSDT'
        ]

        # WebSocket URLs
        if testnet:
            self.ws_base_url = "wss://testnet.binance.vision/ws"
        else:
            self.ws_base_url = "wss://stream.binance.com:9443/ws"

        # Data buffers (keep last 1000 ticks per symbol)
        self.tick_buffers: Dict[str, deque] = {
            symbol: deque(maxlen=1000) for symbol in self.symbols
        }

        # Statistics
        self.stats = {
            'total_messages': 0,
            'messages_per_symbol': {symbol: 0 for symbol in self.symbols},
            'start_time': None,
            'last_update': None,
            'errors': 0
        }

        # Callbacks for real-time data
        self.callbacks: List[Callable] = []

        # Storage
        self.data_dir = Path("data/realtime")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.is_running = False

    def add_callback(self, callback: Callable):
        """Add callback function to be called on each tick"""
        self.callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """Remove callback function"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    async def process_tick(self, symbol: str, tick_data: Dict):
        """
        Process incoming tick data

        Args:
            symbol: Trading pair symbol
            tick_data: Tick data from WebSocket
        """
        try:
            # Parse tick data
            tick = {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'price': float(tick_data['c']),  # Current price
                'volume': float(tick_data['v']),  # Volume
                'high': float(tick_data['h']),    # 24h high
                'low': float(tick_data['l']),     # 24h low
                'open': float(tick_data['o']),    # 24h open
                'price_change': float(tick_data['p']),  # 24h price change
                'price_change_pct': float(tick_data['P']),  # 24h price change %
                'trades': int(tick_data['n']),    # Number of trades
            }

            # Add to buffer
            self.tick_buffers[symbol].append(tick)

            # Update statistics
            self.stats['total_messages'] += 1
            self.stats['messages_per_symbol'][symbol] += 1
            self.stats['last_update'] = datetime.now()

            # Call registered callbacks
            for callback in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(tick)
                    else:
                        callback(tick)
                except Exception as e:
                    logger.error(f"Error in callback: {e}")

        except Exception as e:
            logger.error(f"Error processing tick for {symbol}: {e}")
            self.stats['errors'] += 1

    async def stream_symbol(self, symbol: str):
        """
        Stream real-time data for a single symbol

        Args:
            symbol: Trading pair symbol
        """
        stream_name = f"{symbol.lower()}@ticker"
        ws_url = f"{self.ws_base_url}/{stream_name}"

        retry_count = 0
        max_retries = 10

        while self.is_running and retry_count < max_retries:
            try:
                logger.info(f"Connecting to {symbol} stream...")

                async with websockets.connect(ws_url) as websocket:
                    logger.info(f"Connected to {symbol} stream")
                    retry_count = 0  # Reset retry count on successful connection

                    while self.is_running:
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=30.0  # 30 second timeout
                            )

                            data = json.loads(message)
                            await self.process_tick(symbol, data)

                        except asyncio.TimeoutError:
                            logger.warning(f"{symbol}: WebSocket timeout, reconnecting...")
                            break
                        except json.JSONDecodeError as e:
                            logger.error(f"{symbol}: JSON decode error: {e}")
                            continue

            except Exception as e:
                retry_count += 1
                logger.error(f"{symbol}: Connection error (attempt {retry_count}/{max_retries}): {e}")

                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 60)  # Exponential backoff, max 60s
                    logger.info(f"{symbol}: Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"{symbol}: Max retries reached, stopping stream")
                    break

        logger.info(f"{symbol}: Stream stopped")

    async def start_streaming(self):
        """Start streaming data for all symbols"""
        self.is_running = True
        self.stats['start_time'] = datetime.now()

        logger.info("=" * 60)
        logger.info("TradingBot V2 - Real-Time Data Streaming")
        logger.info("=" * 60)
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Testnet: {self.testnet}")
        logger.info("=" * 60)

        # Create tasks for all symbols
        tasks = [self.stream_symbol(symbol) for symbol in self.symbols]

        # Add monitoring task
        tasks.append(self.monitor_streams())

        # Run all tasks concurrently
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping streams...")
            await self.stop_streaming()

    async def stop_streaming(self):
        """Stop streaming data"""
        logger.info("Stopping data streams...")
        self.is_running = False

        # Save final statistics
        await self.save_statistics()

        # Save buffered data
        await self.save_buffers()

        logger.info("Data streaming stopped")

    async def monitor_streams(self):
        """Monitor stream health and display statistics"""
        while self.is_running:
            await asyncio.sleep(30)  # Update every 30 seconds

            if not self.stats['start_time']:
                continue

            # Calculate uptime
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"

            # Calculate message rate
            msg_rate = self.stats['total_messages'] / uptime if uptime > 0 else 0

            logger.info("\n" + "=" * 60)
            logger.info("STREAMING STATISTICS")
            logger.info("=" * 60)
            logger.info(f"Uptime: {uptime_str}")
            logger.info(f"Total Messages: {self.stats['total_messages']:,}")
            logger.info(f"Message Rate: {msg_rate:.2f} msg/s")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"Last Update: {self.stats['last_update']}")
            logger.info("-" * 60)

            # Show per-symbol statistics
            for symbol in self.symbols:
                count = self.stats['messages_per_symbol'][symbol]
                buffer_size = len(self.tick_buffers[symbol])
                latest = self.tick_buffers[symbol][-1] if buffer_size > 0 else None

                if latest:
                    logger.info(
                        f"{symbol:12s}: {count:6,d} msgs | "
                        f"Buffer: {buffer_size:4d} | "
                        f"Price: ${latest['price']:,.2f} | "
                        f"Change: {latest['price_change_pct']:+.2f}%"
                    )

            logger.info("=" * 60)

    async def save_buffers(self):
        """Save buffered data to disk"""
        logger.info("Saving buffered data...")

        for symbol in self.symbols:
            if len(self.tick_buffers[symbol]) == 0:
                continue

            try:
                # Convert buffer to DataFrame
                df = pd.DataFrame(list(self.tick_buffers[symbol]))

                # Save to CSV
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_path = self.data_dir / f"{symbol}_realtime_{timestamp}.csv"
                df.to_csv(csv_path, index=False)

                logger.info(f"{symbol}: Saved {len(df)} ticks to {csv_path}")

            except Exception as e:
                logger.error(f"Error saving {symbol} buffer: {e}")

    async def save_statistics(self):
        """Save statistics to disk"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stats_path = self.data_dir / f"stats_{timestamp}.json"

            # Prepare stats for JSON serialization
            stats_copy = self.stats.copy()
            stats_copy['start_time'] = str(stats_copy['start_time'])
            stats_copy['last_update'] = str(stats_copy['last_update'])

            with open(stats_path, 'w') as f:
                json.dump(stats_copy, f, indent=2)

            logger.info(f"Statistics saved to {stats_path}")

        except Exception as e:
            logger.error(f"Error saving statistics: {e}")

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol"""
        if len(self.tick_buffers[symbol]) == 0:
            return None
        return self.tick_buffers[symbol][-1]['price']

    def get_price_history(self, symbol: str, count: int = 100) -> List[Dict]:
        """Get recent price history for a symbol"""
        buffer = self.tick_buffers[symbol]
        return list(buffer)[-count:]

    def get_statistics(self) -> Dict:
        """Get current streaming statistics"""
        return self.stats.copy()


async def main():
    """Main function to run data streamer"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    testnet = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'

    # Define callback for real-time processing
    async def price_callback(tick: Dict):
        """Example callback - log significant price changes"""
        if abs(tick['price_change_pct']) > 2.0:  # > 2% change
            logger.warning(
                f"⚠️  {tick['symbol']}: Large price movement! "
                f"{tick['price_change_pct']:+.2f}% | "
                f"Price: ${tick['price']:,.2f}"
            )

    # Create streamer
    streamer = DataStreamer(testnet=testnet)

    # Add callback
    streamer.add_callback(price_callback)

    # Start streaming
    try:
        await streamer.start_streaming()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await streamer.stop_streaming()


if __name__ == "__main__":
    asyncio.run(main())
