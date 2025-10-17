"""
Real-time Tick Data Trading System
Uses Binance WebSocket for tick-by-tick price updates and real-time trading

Features:
- WebSocket tick stream (millisecond updates)
- Real-time signal generation
- Immediate order execution
- Live position management
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List
from pathlib import Path
import ccxt.async_support as ccxt

from binance_client import BinanceClient
from tick_data_collector import TickDataCollector, Tick
from tick_indicators import TickIndicators
from trailing_stop_manager import TrailingStopManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealtimeTickTrader:
    """Real-time trading system using WebSocket tick data"""

    def __init__(self, symbols: List[str], initial_balance: float = 10000.0):
        """Initialize real-time trading system

        Args:
            symbols: List of trading symbols (e.g., ['BTC/USDT', 'ETH/USDT'])
            initial_balance: Starting balance for trading
        """
        self.symbols = symbols
        self.balance = initial_balance
        self.initial_balance = initial_balance

        # Trading components
        self.binance_client = BinanceClient(testnet=True, use_futures=True)
        self.tick_collector = TickDataCollector(symbols=symbols, buffer_size=10000, save_to_disk=True)
        self.tick_indicators = TickIndicators()
        self.trailing_stop_manager = TrailingStopManager()

        # Real-time data storage
        self.current_prices: Dict[str, float] = {}
        self.tick_counts: Dict[str, int] = {}
        self.positions: Dict[str, dict] = {}
        self.orders: Dict[str, dict] = {}

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        logger.info(f"🚀 Realtime Tick Trader initialized")
        logger.info(f"   Symbols: {', '.join(symbols)}")
        logger.info(f"   Balance: ${initial_balance:,.2f}")

    async def start_websocket_streams(self):
        """Start WebSocket tick streams for all symbols"""
        logger.info("\n🔴 Starting WebSocket tick streams...")

        # Create tasks for each symbol
        tasks = []
        for symbol in self.symbols:
            task = asyncio.create_task(self.subscribe_ticker_stream(symbol))
            tasks.append(task)

        # Run all streams concurrently
        await asyncio.gather(*tasks)

    async def subscribe_ticker_stream(self, symbol: str):
        """Subscribe to real-time ticker stream for a symbol

        This provides:
        - Best bid/ask prices
        - 24h volume
        - Last price
        - Price change %

        Update frequency: ~100ms (10 times per second)
        """
        exchange_symbol = symbol.replace('/', '').lower()  # BTC/USDT → btcusdt

        logger.info(f"📡 Subscribing to {symbol} ticker stream...")

        try:
            # WebSocket endpoint
            ws_url = f"wss://fstream.binance.com/ws/{exchange_symbol}@ticker"

            async with self.binance_client.exchange.ws_connect(ws_url) as websocket:
                logger.info(f"✅ Connected to {symbol} stream")

                self.tick_counts[symbol] = 0

                async for message in websocket:
                    try:
                        data = json.loads(message)

                        # Extract tick data
                        tick = {
                            'symbol': symbol,
                            'price': float(data['c']),  # Last price
                            'bid': float(data['b']),    # Best bid
                            'ask': float(data['a']),    # Best ask
                            'volume': float(data['v']),  # 24h volume
                            'timestamp': datetime.fromtimestamp(data['E'] / 1000)
                        }

                        # Process tick
                        await self.on_tick(tick)

                        # Log every 100 ticks
                        self.tick_counts[symbol] += 1
                        if self.tick_counts[symbol] % 100 == 0:
                            logger.debug(f"{symbol}: {self.tick_counts[symbol]} ticks processed")

                    except Exception as e:
                        logger.error(f"Error processing {symbol} tick: {e}")

        except Exception as e:
            logger.error(f"WebSocket error for {symbol}: {e}")
            # Reconnect after 5 seconds
            await asyncio.sleep(5)
            await self.subscribe_ticker_stream(symbol)

    async def on_tick(self, tick: dict):
        """Handle incoming tick data

        Called 10 times per second for each symbol

        Process:
        1. Update current price
        2. Check trailing stops
        3. Generate trading signals (every N ticks)
        4. Execute orders if signals generated
        """
        symbol = tick['symbol']
        price = tick['price']

        # Update current price
        old_price = self.current_prices.get(symbol)
        self.current_prices[symbol] = price

        # Check trailing stops for open positions
        await self.check_trailing_stops(symbol, price, tick['timestamp'])

        # Generate signals every 10 ticks (~1 second) to avoid over-trading
        if self.tick_counts[symbol] % 10 == 0:
            await self.generate_and_execute_signals(symbol, price, tick)

    async def check_trailing_stops(self, symbol: str, current_price: float, timestamp: datetime):
        """Check trailing stops for all open positions"""
        positions_to_close = []

        for position_key, position in self.positions.items():
            if position['symbol'] != symbol:
                continue

            # Get ATR (simplified: use 1% of price)
            atr = current_price * 0.01

            # Check stop
            stop_price, should_close = self.trailing_stop_manager.update_trailing_stop(
                position_key, current_price, atr
            )

            if should_close:
                positions_to_close.append(position_key)

        # Close positions that hit stops
        for position_key in positions_to_close:
            await self.close_position(position_key, current_price, "Trailing Stop", timestamp)

    async def generate_and_execute_signals(self, symbol: str, price: float, tick: dict):
        """Generate trading signals using TICK DATA ONLY - NO CANDLES!"""
        try:
            # Get tick buffer (NO CANDLE DATA)
            recent_ticks = self.tick_collector.get_recent_ticks(symbol, count=1000)  # ~100 seconds of data

            if len(recent_ticks) < 100:
                return  # Need minimum ticks for indicators

            # Calculate tick-based indicators (replaces candle-based analysis)
            indicators = self.tick_indicators.generate_tick_summary(recent_ticks, lookback_seconds=600)

            # Generate signal based on tick indicators
            signal = self._generate_tick_based_signal(symbol, indicators, price)

            if not signal or signal['action'] == 'HOLD':
                return

            # Execute signal
            if signal['action'] == 'BOTH':  # Two-way entry
                await self.execute_two_way_entry(symbol, price, signal, tick['timestamp'])
            elif signal['action'] == 'CLOSE':
                await self.close_all_positions(symbol, price, tick['timestamp'])

        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")

    def _generate_tick_based_signal(self, symbol: str, indicators: dict, current_price: float) -> dict:
        """Generate trading signal using tick-based indicators only

        Replaces strategy.generate_signal() which uses candle data.
        Uses tick indicators: VWAP, volatility, momentum, Bollinger bands, trend.
        """
        # Extract tick indicators
        vwap = indicators.get('vwap', current_price)
        volatility = indicators.get('volatility', 0)
        momentum = indicators.get('momentum', 0)
        bb = indicators.get('bollinger_bands', {})
        bb_position = bb.get('position', 0.5)
        trend = indicators.get('trend', 'NEUTRAL')

        # Two-way entry conditions (straddle strategy)
        # Enter when: high volatility + price at middle of Bollinger Bands
        if volatility > current_price * 0.01:  # 1% volatility threshold
            if 0.4 < bb_position < 0.6:  # Price in middle 20% of BB
                return {
                    'action': 'BOTH',
                    'confidence': 0.75,
                    'reason': f'High volatility ({volatility:.2f}) + BB middle position ({bb_position:.2%})',
                    'indicators': indicators
                }

        # Close positions conditions
        # Close when: low volatility OR price at extreme BB position
        has_positions = any(p['symbol'] == symbol for p in self.positions.values())
        if has_positions:
            if volatility < current_price * 0.005:  # Low volatility
                return {
                    'action': 'CLOSE',
                    'confidence': 0.80,
                    'reason': f'Low volatility ({volatility:.2f}) - consolidation',
                    'indicators': indicators
                }
            if bb_position < 0.1 or bb_position > 0.9:  # Extreme BB position
                return {
                    'action': 'CLOSE',
                    'confidence': 0.85,
                    'reason': f'Extreme BB position ({bb_position:.2%})',
                    'indicators': indicators
                }

        return {'action': 'HOLD', 'confidence': 0.5, 'reason': 'No signal conditions met'}

    async def execute_two_way_entry(self, symbol: str, entry_price: float, signal: dict, timestamp: datetime):
        """Execute two-way simultaneous entry (straddle)"""
        # Check if we already have positions
        if any(p['symbol'] == symbol for p in self.positions.values()):
            logger.debug(f"{symbol}: Already have positions, skipping entry")
            return

        # Calculate position size (10% each side = 20% total)
        position_size_usd = self.balance * 0.1
        position_size = position_size_usd / entry_price

        # LONG position
        long_key = f"{symbol}_LONG"
        self.positions[long_key] = {
            'symbol': symbol,
            'type': 'LONG',
            'entry_price': entry_price,
            'size': position_size,
            'entry_time': timestamp,
            'confidence': signal.get('confidence', 0.5)
        }

        # SHORT position
        short_key = f"{symbol}_SHORT"
        self.positions[short_key] = {
            'symbol': symbol,
            'type': 'SHORT',
            'entry_price': entry_price,
            'size': position_size,
            'entry_time': timestamp,
            'confidence': signal.get('confidence', 0.5)
        }

        # Initialize trailing stops
        atr = entry_price * 0.01  # Simplified ATR
        self.trailing_stop_manager.update_trailing_stop(long_key, entry_price, atr)
        self.trailing_stop_manager.update_trailing_stop(short_key, entry_price, atr)

        logger.info(f"🎯 TWO-WAY ENTRY: {symbol} @ ${entry_price:.2f}")
        logger.info(f"   LONG: {position_size:.4f} units")
        logger.info(f"   SHORT: {position_size:.4f} units")
        logger.info(f"   Confidence: {signal.get('confidence', 0):.2%}")

    async def close_position(self, position_key: str, exit_price: float, reason: str, timestamp: datetime):
        """Close a position and calculate P&L"""
        position = self.positions.get(position_key)
        if not position:
            return

        # Calculate P&L
        entry_price = position['entry_price']
        size = position['size']

        if position['type'] == 'LONG':
            pnl = (exit_price - entry_price) * size * 10  # 10x leverage
        else:  # SHORT
            pnl = (entry_price - exit_price) * size * 10

        pnl_pct = (pnl / (entry_price * size * 10)) * 100

        # Update balance
        self.balance += pnl

        # Update statistics
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Calculate hold time
        hold_time = timestamp - position['entry_time']

        # Remove position
        del self.positions[position_key]

        # Log
        status = "✅ PROFIT" if pnl > 0 else "❌ LOSS"
        logger.info(f"{status}: {position_key} @ ${exit_price:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)")
        logger.info(f"   Reason: {reason} | Hold: {hold_time}")
        logger.info(f"   Balance: ${self.balance:,.2f}")

    async def close_all_positions(self, symbol: str, price: float, timestamp: datetime):
        """Close all positions for a symbol"""
        positions_to_close = [
            key for key, pos in self.positions.items()
            if pos['symbol'] == symbol
        ]

        for position_key in positions_to_close:
            await self.close_position(position_key, price, "Signal Close", timestamp)

    async def get_performance_metrics(self) -> dict:
        """Get real-time performance metrics"""
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        return {
            'balance': self.balance,
            'total_return': total_return,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'active_positions': len(self.positions),
            'timestamp': datetime.now().isoformat()
        }

    async def start_trading(self):
        """Start real-time trading system"""
        logger.info("\n" + "="*80)
        logger.info("🚀 STARTING REAL-TIME TICK TRADING SYSTEM")
        logger.info("="*80)
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Initial Balance: ${self.initial_balance:,.2f}")
        logger.info("="*80 + "\n")

        try:
            # Start WebSocket streams
            await self.start_websocket_streams()

        except KeyboardInterrupt:
            logger.info("\n⏸️  Trading stopped by user")
        except Exception as e:
            logger.error(f"❌ Trading system error: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Shutdown trading system gracefully"""
        logger.info("\n🛑 Shutting down trading system...")

        # Close all positions
        logger.info(f"Closing {len(self.positions)} open positions...")
        for position_key, position in list(self.positions.items()):
            symbol = position['symbol']
            price = self.current_prices.get(symbol, position['entry_price'])
            await self.close_position(position_key, price, "System Shutdown", datetime.now())

        # Display final performance
        metrics = await self.get_performance_metrics()

        logger.info("\n" + "="*80)
        logger.info("📊 FINAL PERFORMANCE")
        logger.info("="*80)
        logger.info(f"Final Balance:   ${metrics['balance']:,.2f}")
        logger.info(f"Total Return:    {metrics['total_return']:+.2f}%")
        logger.info(f"Total Trades:    {metrics['total_trades']}")
        logger.info(f"Win Rate:        {metrics['win_rate']:.2f}%")
        logger.info(f"Winning Trades:  {metrics['winning_trades']}")
        logger.info(f"Losing Trades:   {metrics['losing_trades']}")
        logger.info("="*80 + "\n")

        # Close exchange connection
        await self.binance_client.close()
        logger.info("✅ Shutdown complete")


async def main():
    """Main entry point for real-time trading"""
    # Load optimized strategy configuration
    import json
    with open('coin_specific_params.json', 'r') as f:
        config = json.load(f)

    # Get active symbols (exclude removed coins)
    active_symbols = [
        symbol for symbol, params in config['coin_parameters'].items()
        if not params.get('excluded', False)
    ]

    logger.info(f"Using optimized strategy v{config.get('version', 'unknown')}")
    logger.info(f"Active symbols: {', '.join(active_symbols)}")

    # Create trader
    trader = RealtimeTickTrader(
        symbols=active_symbols,
        initial_balance=10000.0
    )

    # Start trading
    await trader.start_trading()


if __name__ == "__main__":
    asyncio.run(main())
