"""
Selective Tick Live Trader - Strategy B Implementation
Real-time trading with high-confidence selective entry
7 coins: ETH, SOL, BNB, DOGE, XRP, SUI, 1000PEPE
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
import json

from binance_client import BinanceClient
from tick_indicators import TickIndicators
from trailing_stop_manager import TrailingStopManager
from tick_data_collector import Tick

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SelectiveTickLiveTrader:
    """Strategy B: Selective High-Confidence Live Trading

    Goals (from analysis):
    - Minimum trades (~162/day per symbol, not 809/day)
    - Maximum profit per trade (target $100+ vs $20)
    - Highest win rate (target >85% vs 42%)

    Key Features:
    - Stricter entry: 2x volatility thresholds
    - Cooldown period: 5 minutes between entries
    - Momentum confirmation required
    - Tight BB center (0.48-0.52)
    """

    def __init__(
        self,
        binance_client: BinanceClient,
        symbols: List[str],
        initial_balance: float = 10000.0,
        leverage: int = 10,
        position_size_pct: float = 0.1,
        taker_fee: float = 0.0005,
        slippage_pct: float = 0.0001,
        cooldown_seconds: int = 300  # 5 minutes
    ):
        """Initialize selective live trader

        Args:
            binance_client: Binance API client
            symbols: List of trading symbols (CCXT format: 'ETH/USDT')
            initial_balance: Starting balance
            leverage: Futures leverage
            position_size_pct: Position size per side (% of balance)
            taker_fee: Trading fee rate
            slippage_pct: Slippage percentage
            cooldown_seconds: Minimum seconds between entries per symbol
        """
        self.binance = binance_client
        self.symbols = symbols
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.position_size_pct = position_size_pct
        self.taker_fee = taker_fee
        self.slippage_pct = slippage_pct
        self.cooldown_seconds = cooldown_seconds

        # Tick data storage (per symbol)
        self.tick_buffers: Dict[str, List[Tick]] = {symbol: [] for symbol in symbols}

        # Trading state
        self.positions: Dict[str, dict] = {}
        self.trades: List[dict] = []
        self.total_fees_paid = 0.0

        # Cooldown tracking (per symbol)
        self.last_entry_time: Dict[str, float] = {symbol: 0 for symbol in symbols}

        # Performance tracking
        self.max_balance = initial_balance
        self.min_balance = initial_balance

        # Components
        self.tick_indicators = TickIndicators()
        self.trailing_stop_manager = TrailingStopManager()

        # Stats
        self.signals_generated = 0
        self.signals_skipped_cooldown = 0
        self.signals_skipped_positions = 0

        logger.info(f"✅ SelectiveTickLiveTrader initialized (Strategy B)")
        logger.info(f"   Symbols: {', '.join(symbols)}")
        logger.info(f"   Balance: ${initial_balance:,.2f}")
        logger.info(f"   Leverage: {leverage}x")
        logger.info(f"   Cooldown: {cooldown_seconds}s")
        logger.info(f"   Strategy: SELECTIVE HIGH-CONFIDENCE")

    async def start(self):
        """Start live trading"""
        logger.info("\n" + "="*80)
        logger.info("🚀 STARTING SELECTIVE LIVE TRADING (Strategy B)")
        logger.info("="*80)
        logger.info(f"Strategy: Top 20% Quality Trades Only")
        logger.info(f"Expected: ~162 trades/day per symbol (vs 809 in Strategy A)")
        logger.info(f"Goal: Win Rate >85%, Avg Profit >$80/trade")
        logger.info("="*80 + "\n")

        # Start tick collection for all symbols
        tasks = []
        for symbol in self.symbols:
            task = asyncio.create_task(self._collect_and_trade(symbol))
            tasks.append(task)

        # Wait for all symbols
        await asyncio.gather(*tasks)

    async def _collect_and_trade(self, symbol: str):
        """Collect ticks and trade for a symbol"""
        logger.info(f"📡 Starting tick collection for {symbol}")

        while True:
            try:
                # Fetch current tick data
                tick = await self._fetch_tick(symbol)

                if tick:
                    # Add to buffer
                    self.tick_buffers[symbol].append(tick)

                    # Keep last 10,000 ticks (~16 minutes at 10 ticks/sec)
                    if len(self.tick_buffers[symbol]) > 10000:
                        self.tick_buffers[symbol].pop(0)

                    # Check trailing stops
                    await self._check_trailing_stops(symbol, tick.price, tick.timestamp)

                    # Generate signals (every 10 ticks = ~1 second)
                    tick_count = len(self.tick_buffers[symbol])
                    if tick_count >= 100 and tick_count % 10 == 0:
                        await self._generate_and_execute_signals(symbol, tick)

                # Sleep before next tick (simulate ~10 ticks/sec)
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Error in tick collection for {symbol}: {e}")
                await asyncio.sleep(1)

    async def _fetch_tick(self, symbol: str) -> Tick:
        """Fetch current tick data from Binance"""
        try:
            # Get current price and orderbook
            price = await self.binance.get_price(symbol)
            orderbook = await self.binance.get_orderbook(symbol, limit=5)

            # Get 24h stats
            ticker = await self.binance.get_ticker(symbol)

            tick = Tick(
                symbol=symbol,
                timestamp=datetime.now(),
                price=float(price),
                bid=float(orderbook['bids'][0][0]) if orderbook['bids'] else price,
                ask=float(orderbook['asks'][0][0]) if orderbook['asks'] else price,
                bid_qty=float(orderbook['bids'][0][1]) if orderbook['bids'] else 0,
                ask_qty=float(orderbook['asks'][0][1]) if orderbook['asks'] else 0,
                volume_24h=float(ticker.get('volume', 0)),
                quote_volume_24h=float(ticker.get('quoteVolume', 0)),
                price_change_pct=float(ticker.get('percentage', 0))
            )

            return tick

        except Exception as e:
            logger.error(f"Error fetching tick for {symbol}: {e}")
            return None

    async def _generate_and_execute_signals(self, symbol: str, tick: Tick):
        """Generate and execute SELECTIVE trading signals (Strategy B)"""

        # Get recent ticks
        recent_ticks = self.tick_buffers[symbol][-1000:]

        if len(recent_ticks) < 100:
            return

        # Calculate indicators
        std_vol, atr_vol, hybrid_vol = self.tick_indicators.calculate_hybrid_volatility(
            recent_ticks,
            lookback_seconds=600
        )

        indicators = self.tick_indicators.generate_tick_summary(
            recent_ticks,
            lookback_seconds=600
        )

        indicators['std_volatility'] = std_vol
        indicators['atr_volatility'] = atr_vol
        indicators['hybrid_volatility'] = hybrid_vol

        # Generate SELECTIVE signal (Strategy B)
        signal = self._get_selective_signal(symbol, indicators, tick.price)

        if signal['action'] == 'BOTH':
            self.signals_generated += 1
            await self._execute_two_way_entry(symbol, tick.price, signal, tick.timestamp)
        elif signal['action'] == 'CLOSE':
            await self._close_all_positions(symbol, tick.price, tick.timestamp, signal['reason'])

    def _get_selective_signal(self, symbol: str, indicators: dict, current_price: float) -> dict:
        """Strategy B: SELECTIVE HIGH-CONFIDENCE signal generation

        Key Differences from Strategy A:
        - 2x stricter volatility thresholds (0.08% vs 0.04%)
        - Tighter BB center (0.48-0.52 vs 0.40-0.60)
        - Momentum confirmation required
        - Cooldown period enforced
        """

        hybrid_vol = indicators.get('hybrid_volatility', 0)
        atr_vol = indicators.get('atr_volatility', 0)
        bb = indicators.get('bollinger_bands', {})
        bb_position = bb.get('position', 0.5)
        momentum = indicators.get('momentum', 0)

        # STRATEGY B: SELECTIVE ENTRY CONDITIONS
        if atr_vol > 0 and hybrid_vol > 0:
            # Calculate price-relative percentages
            hybrid_pct = (hybrid_vol / current_price) * 100
            atr_pct = (atr_vol / current_price) * 100

            # STRICTER THRESHOLDS (2x from Strategy A)
            # Strategy A: hybrid >= 0.04%, atr >= 0.15%
            # Strategy B: hybrid >= 0.08%, atr >= 0.30%
            if hybrid_pct >= 0.08 and atr_pct >= 0.30:

                # TIGHTER BB CENTER
                # Strategy A: 0.40-0.60 (wide range)
                # Strategy B: 0.48-0.52 (tight center)
                if 0.48 < bb_position < 0.52:

                    # MOMENTUM CONFIRMATION REQUIRED
                    if abs(momentum) > 0.0001:

                        # CHECK COOLDOWN
                        current_time = datetime.now().timestamp()
                        last_time = self.last_entry_time.get(symbol, 0)

                        if current_time - last_time >= self.cooldown_seconds:
                            # ALL CONDITIONS MET - ENTER
                            return {
                                'action': 'BOTH',
                                'confidence': 0.95,  # Very high confidence
                                'reason': f'HIGH CONFIDENCE: H:{hybrid_pct:.3f}% A:{atr_pct:.3f}% BB:{bb_position:.3f} M:{momentum:.6f}',
                                'indicators': indicators
                            }
                        else:
                            # Cooldown active
                            self.signals_skipped_cooldown += 1
                            remaining = self.cooldown_seconds - (current_time - last_time)
                            logger.debug(f"⏳ {symbol} Cooldown: {remaining:.0f}s remaining")

        # EXIT CONDITIONS (same as Strategy A)
        has_positions = any(p['symbol'] == symbol for p in self.positions.values())
        if has_positions:
            # Volatility collapsed
            if hybrid_vol < atr_vol * 0.05:
                return {
                    'action': 'CLOSE',
                    'confidence': 0.85,
                    'reason': f'Volatility collapsed ({hybrid_vol:.4f})'
                }

            # Extreme BB
            if bb_position < 0.15 or bb_position > 0.85:
                return {
                    'action': 'CLOSE',
                    'confidence': 0.80,
                    'reason': f'Extreme BB ({bb_position:.2%})'
                }
        else:
            self.signals_skipped_positions += 1

        return {'action': 'HOLD', 'confidence': 0.5, 'reason': 'No signal'}

    async def _execute_two_way_entry(
        self,
        symbol: str,
        price: float,
        signal: dict,
        timestamp: datetime
    ):
        """Execute two-way entry (LONG + SHORT straddle)"""

        # Check if already have positions for this symbol
        if any(p['symbol'] == symbol for p in self.positions.values()):
            return

        # Calculate position size
        position_size_usd = self.balance * self.position_size_pct
        position_size = position_size_usd / price

        # LONG position
        long_key = f"{symbol}_LONG_{timestamp.timestamp()}"
        self.positions[long_key] = {
            'symbol': symbol,
            'type': 'LONG',
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'confidence': signal['confidence']
        }

        # SHORT position
        short_key = f"{symbol}_SHORT_{timestamp.timestamp()}"
        self.positions[short_key] = {
            'symbol': symbol,
            'type': 'SHORT',
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'confidence': signal['confidence']
        }

        # Initialize trailing stops
        hybrid_vol = signal.get('indicators', {}).get('hybrid_volatility', price * 0.01)
        self.trailing_stop_manager.initialize_position(long_key, price, 'LONG')
        self.trailing_stop_manager.initialize_position(short_key, price, 'SHORT')
        self.trailing_stop_manager.update_trailing_stop(long_key, price, hybrid_vol)
        self.trailing_stop_manager.update_trailing_stop(short_key, price, hybrid_vol)

        # Update last entry time
        self.last_entry_time[symbol] = timestamp.timestamp()

        logger.info(
            f"🎯 ENTRY: {symbol} @ ${price:.2f} | "
            f"Conf: {signal['confidence']:.0%} | "
            f"{signal['reason']}"
        )

    async def _check_trailing_stops(self, symbol: str, current_price: float, timestamp: datetime):
        """Check trailing stops for all positions"""

        positions_to_close = []

        for position_key, position in self.positions.items():
            if position['symbol'] != symbol:
                continue

            # Get volatility
            recent_ticks = self.tick_buffers[symbol][-100:]
            if len(recent_ticks) < 10:
                continue

            volatility = self.tick_indicators.calculate_tick_volatility(
                recent_ticks,
                lookback_seconds=60
            )

            # Check stop
            stop_price, should_close = self.trailing_stop_manager.update_trailing_stop(
                position_key,
                current_price,
                volatility
            )

            if should_close:
                positions_to_close.append(position_key)

        # Close positions
        for position_key in positions_to_close:
            await self._close_position(position_key, current_price, "Trailing Stop", timestamp)

    async def _close_position(
        self,
        position_key: str,
        exit_price: float,
        reason: str,
        timestamp: datetime
    ):
        """Close a position and record trade"""

        position = self.positions.get(position_key)
        if not position:
            return

        # Apply slippage
        entry_price = position['entry_price']
        size = position['size']

        if position['type'] == 'LONG':
            entry_with_slippage = entry_price * (1 + self.slippage_pct)
            exit_with_slippage = exit_price * (1 - self.slippage_pct)
            pnl_gross = (exit_with_slippage - entry_with_slippage) * size * self.leverage
        else:  # SHORT
            entry_with_slippage = entry_price * (1 - self.slippage_pct)
            exit_with_slippage = exit_price * (1 + self.slippage_pct)
            pnl_gross = (entry_with_slippage - exit_with_slippage) * size * self.leverage

        # Calculate fees
        position_value = entry_price * size
        total_fee = position_value * self.taker_fee * 2  # Entry + Exit

        # Net P&L
        pnl_net = pnl_gross - total_fee
        pnl_pct = (pnl_net / (entry_price * size * self.leverage)) * 100

        # Update balance
        self.balance += pnl_net
        self.total_fees_paid += total_fee
        self.max_balance = max(self.max_balance, self.balance)
        self.min_balance = min(self.min_balance, self.balance)

        # Record trade
        trade = {
            'position_key': position_key,
            'symbol': position['symbol'],
            'type': position['type'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'size': size,
            'pnl_gross': pnl_gross,
            'fees': total_fee,
            'pnl': pnl_net,
            'pnl_pct': pnl_pct,
            'entry_time': position['entry_time'].isoformat(),
            'exit_time': timestamp.isoformat(),
            'hold_time_seconds': (timestamp - position['entry_time']).total_seconds(),
            'reason': reason,
            'balance_after': self.balance
        }
        self.trades.append(trade)

        # Remove position
        del self.positions[position_key]

        logger.info(
            f"{'✅' if pnl_net > 0 else '❌'} CLOSE: {position['symbol']} {position['type']} | "
            f"P&L: ${pnl_net:+.2f} ({pnl_pct:+.2f}%) | "
            f"Fee: ${total_fee:.2f} | {reason}"
        )

    async def _close_all_positions(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        reason: str
    ):
        """Close all positions for a symbol"""

        positions_to_close = [
            key for key, pos in self.positions.items()
            if pos['symbol'] == symbol
        ]

        for position_key in positions_to_close:
            await self._close_position(position_key, price, reason, timestamp)

    async def get_performance(self) -> dict:
        """Get current performance metrics with per-coin breakdown"""

        total_pnl = self.balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100

        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        avg_profit = total_pnl / total_trades if total_trades > 0 else 0

        max_dd = ((self.max_balance - self.min_balance) / self.max_balance * 100) if self.max_balance > 0 else 0

        # Calculate trades per day
        if self.trades:
            first_trade = datetime.fromisoformat(self.trades[0]['entry_time'])
            last_trade = datetime.fromisoformat(self.trades[-1]['entry_time'])
            days = max(1, (last_trade - first_trade).total_seconds() / 86400)
            trades_per_day = total_trades / days
        else:
            trades_per_day = 0

        # Per-coin statistics
        per_coin_stats = {}
        for symbol in self.symbols:
            coin_trades = [t for t in self.trades if t['symbol'] == symbol]
            coin_winning = [t for t in coin_trades if t['pnl'] > 0]
            coin_pnl = sum(t['pnl'] for t in coin_trades)

            per_coin_stats[symbol] = {
                'total_trades': len(coin_trades),
                'winning_trades': len(coin_winning),
                'win_rate': (len(coin_winning) / len(coin_trades) * 100) if coin_trades else 0,
                'total_pnl': coin_pnl,
                'avg_profit_per_trade': coin_pnl / len(coin_trades) if coin_trades else 0,
                'trades_per_day': len(coin_trades) / days if self.trades and days > 0 else 0
            }

        # Active positions details
        active_positions_list = []
        for position_key, position in self.positions.items():
            # Get current price from tick buffer
            current_price = 0
            if position['symbol'] in self.tick_buffers and self.tick_buffers[position['symbol']]:
                current_price = self.tick_buffers[position['symbol']][-1].price

            # Calculate unrealized P&L
            entry_price = position['entry_price']
            size = position['size']

            if current_price > 0:
                if position['type'] == 'LONG':
                    unrealized_pnl = (current_price - entry_price) * size * self.leverage
                else:  # SHORT
                    unrealized_pnl = (entry_price - current_price) * size * self.leverage

                unrealized_pnl_pct = (unrealized_pnl / (entry_price * size * self.leverage)) * 100
            else:
                unrealized_pnl = 0
                unrealized_pnl_pct = 0

            # Calculate hold duration
            hold_duration = (datetime.now() - position['entry_time']).total_seconds()

            active_positions_list.append({
                'symbol': position['symbol'],
                'type': position['type'],
                'entry_price': entry_price,
                'current_price': current_price,
                'size': size,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': unrealized_pnl_pct,
                'hold_duration_seconds': hold_duration,
                'confidence': position.get('confidence', 0)
            })

        return {
            'balance': self.balance,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'total_trades': total_trades,
            'trades_per_day': trades_per_day,
            'winning_trades': len(winning_trades),
            'win_rate': win_rate,
            'avg_profit_per_trade': avg_profit,
            'max_drawdown': max_dd,
            'total_fees_paid': self.total_fees_paid,
            'active_positions': len(self.positions),
            'signals_generated': self.signals_generated,
            'signals_skipped_cooldown': self.signals_skipped_cooldown,
            'strategy': 'Strategy B - Selective High-Confidence',
            'per_coin_stats': per_coin_stats,
            'active_positions_list': active_positions_list
        }

    async def stop(self):
        """Stop trading and save results"""
        logger.info("\n" + "="*80)
        logger.info("🛑 STOPPING SELECTIVE LIVE TRADING")
        logger.info("="*80)

        # Close all remaining positions
        final_time = datetime.now()
        for symbol in self.symbols:
            if symbol in self.tick_buffers and self.tick_buffers[symbol]:
                final_price = self.tick_buffers[symbol][-1].price
                await self._close_all_positions(symbol, final_price, final_time, "Trading Stopped")

        # Get final performance
        performance = await self.get_performance()

        logger.info(f"\n📊 FINAL PERFORMANCE:")
        logger.info(f"   Total Return: {performance['total_return']:+.2f}%")
        logger.info(f"   Win Rate: {performance['win_rate']:.2f}%")
        logger.info(f"   Total Trades: {performance['total_trades']}")
        logger.info(f"   Trades/Day: {performance['trades_per_day']:.1f}")
        logger.info(f"   Avg Profit/Trade: ${performance['avg_profit_per_trade']:.2f}")
        logger.info(f"   Total Fees: ${performance['total_fees_paid']:.2f}")
        logger.info(f"   Max Drawdown: {performance['max_drawdown']:.2f}%")
        logger.info("="*80 + "\n")

        # Save results
        results = {
            'performance': performance,
            'trades': self.trades,
            'timestamp': datetime.now().isoformat()
        }

        output_file = Path('claudedocs/selective_live_trading_results.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"✅ Results saved to {output_file}")


async def main():
    """Main entry point for selective live trading"""

    # Initialize Binance client
    import os
    binance_client = BinanceClient(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        testnet=True,  # Use testnet for safety
        use_futures=True
    )

    # 7 target symbols
    symbols = [
        'ETH/USDT',
        'SOL/USDT',
        'BNB/USDT',
        'DOGE/USDT',
        'XRP/USDT',
        'SUI/USDT',
        '1000PEPE/USDT'
    ]

    # Initialize trader with Strategy B
    trader = SelectiveTickLiveTrader(
        binance_client=binance_client,
        symbols=symbols,
        initial_balance=10000.0,
        leverage=10,
        position_size_pct=0.1,
        taker_fee=0.0005,
        slippage_pct=0.0001,
        cooldown_seconds=300  # 5 minutes
    )

    try:
        # Start trading
        await trader.start()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Keyboard interrupt received")
    finally:
        # Stop and save results
        await trader.stop()
        await binance_client.close()


if __name__ == "__main__":
    asyncio.run(main())
