"""
Tick-Based Backtesting Engine
Complete rewrite of backtester for tick-by-tick simulation

CRITICAL RULE: NO candle data. Only tick data.
Simulates trading as if receiving real-time tick stream.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd
import numpy as np
from dataclasses import asdict

from tick_data_collector import Tick, TickDataCollector
from tick_indicators import TickIndicators
from trailing_stop_manager import TrailingStopManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TickBacktester:
    """Tick-by-tick backtesting engine

    Simulates live trading by processing historical tick data
    sequentially, as if receiving real-time WebSocket stream.

    NO candle assumptions - pure tick-based simulation.
    """

    def __init__(
        self,
        symbols: List[str],
        initial_balance: float = 10000.0,
        leverage: int = 10,
        position_size_pct: float = 0.1,
        taker_fee: float = 0.0005,  # 0.05% Binance Futures Taker
        slippage_pct: float = 0.0001  # 0.01% average slippage
    ):
        """Initialize tick backtester

        Args:
            symbols: Trading symbols
            initial_balance: Starting balance
            leverage: Futures leverage
            position_size_pct: Position size as % of balance per side
            taker_fee: Trading fee rate (default 0.05% Binance Futures)
            slippage_pct: Slippage percentage (default 0.01%)
        """
        self.symbols = symbols
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.position_size_pct = position_size_pct
        self.taker_fee = taker_fee
        self.slippage_pct = slippage_pct

        # Tick data storage
        self.tick_buffers: Dict[str, List[Tick]] = {symbol: [] for symbol in symbols}

        # Trading state
        self.positions: Dict[str, dict] = {}
        self.orders: List[dict] = []
        self.trades: List[dict] = []

        # Fee tracking
        self.total_fees_paid = 0.0

        # Performance tracking
        self.equity_curve: List[dict] = []
        self.max_balance = initial_balance
        self.min_balance = initial_balance

        # Components
        self.tick_indicators = TickIndicators()
        self.trailing_stop_manager = TrailingStopManager()

        logger.info(f"✅ TickBacktester initialized")
        logger.info(f"   Symbols: {', '.join(symbols)}")
        logger.info(f"   Initial balance: ${initial_balance:,.2f}")
        logger.info(f"   Leverage: {leverage}x")
        logger.info(f"   Fees: {taker_fee*100:.3f}% + Slippage: {slippage_pct*100:.3f}%")

    async def load_tick_data_from_file(
        self,
        symbol: str,
        file_path: Path,
        limit: Optional[int] = None
    ) -> List[Tick]:
        """Load historical tick data from file

        Reads JSON Lines format saved by tick_data_collector.py

        Args:
            symbol: Trading symbol
            file_path: Path to tick data file
            limit: Max ticks to load (None = all)

        Returns:
            List of Tick objects
        """
        ticks = []

        try:
            with open(file_path, 'r') as f:
                for i, line in enumerate(f):
                    if limit and i >= limit:
                        break

                    data = json.loads(line)
                    tick = Tick(
                        symbol=data['symbol'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        price=float(data['price']),
                        bid=float(data['bid']),
                        ask=float(data['ask']),
                        bid_qty=float(data.get('bid_qty', 0)),
                        ask_qty=float(data.get('ask_qty', 0)),
                        volume_24h=float(data['volume_24h']),
                        quote_volume_24h=float(data.get('quote_volume_24h', 0)),
                        price_change_pct=float(data.get('price_change_pct', 0))
                    )
                    ticks.append(tick)

            logger.info(f"✅ Loaded {len(ticks):,} ticks from {file_path.name}")
            return ticks

        except Exception as e:
            logger.error(f"❌ Error loading tick data: {e}")
            return []

    async def load_tick_data_live(
        self,
        symbol: str,
        duration_seconds: int = 3600
    ) -> List[Tick]:
        """Collect live tick data for backtesting

        Runs tick collector for specified duration to gather data.

        Args:
            symbol: Trading symbol
            duration_seconds: How long to collect data

        Returns:
            List of collected ticks
        """
        logger.info(f"📡 Collecting {duration_seconds}s of live tick data for {symbol}...")

        collector = TickDataCollector(
            symbols=[symbol],
            buffer_size=100000,
            save_to_disk=True
        )

        # Start collection
        collection_task = asyncio.create_task(collector.start())

        # Wait for duration
        await asyncio.sleep(duration_seconds)

        # Stop collection
        await collector.stop()
        collection_task.cancel()

        # Get collected ticks
        ticks = list(collector.tick_buffers[symbol])
        logger.info(f"✅ Collected {len(ticks):,} ticks")

        return ticks

    def process_tick(self, tick: Tick):
        """Process a single tick (simulate real-time)

        This is the core backtesting function - processes each tick
        as if it just arrived via WebSocket.
        """
        symbol = tick.symbol

        # Add to buffer
        self.tick_buffers[symbol].append(tick)

        # Keep last 10,000 ticks (~16 minutes at 10 ticks/sec)
        if len(self.tick_buffers[symbol]) > 10000:
            self.tick_buffers[symbol].pop(0)

        # Check trailing stops
        self._check_trailing_stops(symbol, tick.price, tick.timestamp)

        # Generate signals (every 10 ticks = ~1 second)
        tick_count = len(self.tick_buffers[symbol])
        if tick_count >= 100 and tick_count % 10 == 0:
            self._generate_and_execute_signals(symbol, tick)

        # Update equity curve (every 100 ticks = ~10 seconds)
        if tick_count % 100 == 0:
            self._record_equity(tick.timestamp)

    def _generate_and_execute_signals(self, symbol: str, tick: Tick):
        """Generate trading signals from tick data"""

        # Get recent ticks (last 1000 = ~100 seconds)
        recent_ticks = self.tick_buffers[symbol][-1000:]

        if len(recent_ticks) < 100:
            return

        # Calculate hybrid volatility (fixes the scale mismatch issue)
        std_vol, atr_vol, hybrid_vol = self.tick_indicators.calculate_hybrid_volatility(
            recent_ticks,
            lookback_seconds=600  # 10 minutes
        )

        # Calculate other tick indicators
        indicators = self.tick_indicators.generate_tick_summary(
            recent_ticks,
            lookback_seconds=600
        )

        # Add hybrid volatility metrics to indicators
        indicators['std_volatility'] = std_vol
        indicators['atr_volatility'] = atr_vol
        indicators['hybrid_volatility'] = hybrid_vol

        # Generate signal
        signal = self._get_tick_signal(symbol, indicators, tick.price)

        if signal['action'] == 'BOTH':
            self._execute_two_way_entry(symbol, tick.price, signal, tick.timestamp)
        elif signal['action'] == 'CLOSE':
            self._close_all_positions(symbol, tick.price, tick.timestamp, signal['reason'])

    def _get_tick_signal(self, symbol: str, indicators: dict, current_price: float) -> dict:
        """Generate signal from tick indicators (using hybrid volatility)"""

        # Use hybrid volatility which properly scales to tick data
        hybrid_vol = indicators.get('hybrid_volatility', 0)
        atr_vol = indicators.get('atr_volatility', 0)
        std_vol = indicators.get('std_volatility', 0)
        bb = indicators.get('bollinger_bands', {})
        bb_position = bb.get('position', 0.5)

        # Two-way entry: SIGNIFICANT volatility + middle BB position
        # 목표: 승률 높이기 + 거래 줄이기 + 한 건당 수익 크게
        #
        # 조건 강화 (Fix: 임계값 로직 수정):
        # 1. 하이브리드 변동성이 가격 대비 충분히 커야 함 (0.15% 이상)
        #    - ETH @ $2,480: $0.372 이상 (기존 $0.48 hybrid 기준)
        # 2. ATR 변동성이 가격 대비 의미있어야 함 (0.3% 이상)
        #    - ETH @ $2,480: $7.44 이상 (median $7.40 기준)
        # 3. Bollinger Band 중간 영역 (진입 안전 구간)
        #
        # 이전 문제: atr_vol >= atr_vol * 0.3 (항상 true)
        # 수정: 가격 대비 절대 % 임계값 사용

        if atr_vol > 0 and hybrid_vol > 0:
            # 가격 대비 % 기준 임계값 (Price-relative thresholds)
            hybrid_pct = (hybrid_vol / current_price) * 100
            atr_pct = (atr_vol / current_price) * 100

            # ADJUSTED THRESHOLDS (based on actual tick data analysis):
            # 하이브리드 변동성: 가격의 0.04% 이상 (median ~0.04% from debug)
            # ATR 변동성: 가격의 0.15% 이상 (median ~0.18% from debug)
            # 목적: 실제 시장 변동성에 맞춘 현실적인 임계값
            if hybrid_pct >= 0.04 and atr_pct >= 0.15:
                # Bollinger Band 중간 영역 (진입 안전 구간)
                if 0.40 < bb_position < 0.60:  # 조금 여유있는 중간 영역
                    return {
                        'action': 'BOTH',
                        'confidence': 0.80,
                        'reason': f'Moderate volatility (H:{hybrid_pct:.2f}% A:{atr_pct:.2f}%) + BB center',
                        'indicators': indicators
                    }

        # Close positions: low volatility OR extreme BB OR profit target
        has_positions = any(p['symbol'] == symbol for p in self.positions.values())
        if has_positions:
            # 1. 변동성 급락 (시장 안정화)
            if hybrid_vol < atr_vol * 0.05:  # ATR의 5% 미만
                return {
                    'action': 'CLOSE',
                    'confidence': 0.85,
                    'reason': f'Volatility collapsed ({hybrid_vol:.4f})'
                }

            # 2. Bollinger Band 극단 (방향 전환 신호)
            if bb_position < 0.15 or bb_position > 0.85:
                return {
                    'action': 'CLOSE',
                    'confidence': 0.80,
                    'reason': f'Extreme BB ({bb_position:.2%})'
                }

        return {'action': 'HOLD', 'confidence': 0.5, 'reason': 'No signal'}

    def _execute_two_way_entry(
        self,
        symbol: str,
        price: float,
        signal: dict,
        timestamp: datetime
    ):
        """Execute two-way simultaneous entry"""

        # Check if already have positions
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

        # Initialize trailing stops FIRST (critical fix)
        # Must call initialize_position() before update_trailing_stop()
        self.trailing_stop_manager.initialize_position(long_key, price, 'LONG')
        self.trailing_stop_manager.initialize_position(short_key, price, 'SHORT')

        # Now update with hybrid volatility as ATR
        hybrid_vol = signal.get('indicators', {}).get('hybrid_volatility', price * 0.01)
        self.trailing_stop_manager.update_trailing_stop(long_key, price, hybrid_vol)
        self.trailing_stop_manager.update_trailing_stop(short_key, price, hybrid_vol)

        logger.debug(f"🎯 TWO-WAY ENTRY: {symbol} @ ${price:.2f} | Vol: ${hybrid_vol:.4f}")

    def _check_trailing_stops(self, symbol: str, current_price: float, timestamp: datetime):
        """Check trailing stops for all positions"""

        positions_to_close = []

        for position_key, position in self.positions.items():
            if position['symbol'] != symbol:
                continue

            # Get volatility as ATR proxy
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
            self._close_position(position_key, current_price, "Trailing Stop", timestamp)

    def _close_position(
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

        # Apply slippage (unfavorable execution)
        entry_price = position['entry_price']
        size = position['size']

        if position['type'] == 'LONG':
            # LONG: buy higher (entry), sell lower (exit)
            entry_with_slippage = entry_price * (1 + self.slippage_pct)
            exit_with_slippage = exit_price * (1 - self.slippage_pct)
            pnl_gross = (exit_with_slippage - entry_with_slippage) * size * self.leverage
        else:  # SHORT
            # SHORT: sell lower (entry), buy higher (exit)
            entry_with_slippage = entry_price * (1 - self.slippage_pct)
            exit_with_slippage = exit_price * (1 + self.slippage_pct)
            pnl_gross = (entry_with_slippage - exit_with_slippage) * size * self.leverage

        # Calculate fees (entry + exit)
        position_value = entry_price * size
        entry_fee = position_value * self.taker_fee
        exit_fee = position_value * self.taker_fee
        total_fee = entry_fee + exit_fee

        # Net P&L after fees and slippage
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

        logger.debug(
            f"{'✅' if pnl_net > 0 else '❌'} CLOSE: {position_key} | "
            f"P&L: ${pnl_net:+.2f} ({pnl_pct:+.2f}%) | Fee: ${total_fee:.2f} | {reason}"
        )

    def _close_all_positions(
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
            self._close_position(position_key, price, reason, timestamp)

    def _record_equity(self, timestamp: datetime):
        """Record current equity for curve"""

        # Calculate unrealized P&L from open positions
        unrealized_pnl = 0
        for position_key, position in self.positions.items():
            symbol = position['symbol']
            if symbol not in self.tick_buffers or not self.tick_buffers[symbol]:
                continue

            current_price = self.tick_buffers[symbol][-1].price
            entry_price = position['entry_price']
            size = position['size']

            if position['type'] == 'LONG':
                unrealized_pnl += (current_price - entry_price) * size * self.leverage
            else:
                unrealized_pnl += (entry_price - current_price) * size * self.leverage

        total_equity = self.balance + unrealized_pnl

        self.equity_curve.append({
            'timestamp': timestamp.isoformat(),
            'balance': self.balance,
            'unrealized_pnl': unrealized_pnl,
            'total_equity': total_equity,
            'num_positions': len(self.positions)
        })

    async def run_backtest(
        self,
        tick_data: Dict[str, List[Tick]],
        progress_interval: int = 10000
    ) -> dict:
        """Run tick-by-tick backtest

        Args:
            tick_data: Dictionary of {symbol: [ticks]}
            progress_interval: Log progress every N ticks

        Returns:
            Backtest results dictionary
        """
        logger.info("\n" + "="*80)
        logger.info("🚀 STARTING TICK-BY-TICK BACKTEST")
        logger.info("="*80)

        # Get all ticks sorted by timestamp
        all_ticks = []
        for symbol, ticks in tick_data.items():
            all_ticks.extend(ticks)

        all_ticks.sort(key=lambda t: t.timestamp)

        total_ticks = len(all_ticks)
        logger.info(f"Total ticks: {total_ticks:,}")
        logger.info(f"Date range: {all_ticks[0].timestamp} → {all_ticks[-1].timestamp}")
        logger.info(f"Duration: {all_ticks[-1].timestamp - all_ticks[0].timestamp}")
        logger.info("="*80 + "\n")

        # Process each tick sequentially
        start_time = datetime.now()

        for i, tick in enumerate(all_ticks):
            self.process_tick(tick)

            # Progress logging
            if (i + 1) % progress_interval == 0:
                pct = ((i + 1) / total_ticks) * 100
                logger.info(
                    f"Progress: {i+1:,}/{total_ticks:,} ticks ({pct:.1f}%) | "
                    f"Balance: ${self.balance:,.2f} | "
                    f"Trades: {len(self.trades)} | "
                    f"Open: {len(self.positions)}"
                )

        # Close any remaining positions
        final_tick = all_ticks[-1]
        for symbol in self.symbols:
            if symbol in self.tick_buffers and self.tick_buffers[symbol]:
                final_price = self.tick_buffers[symbol][-1].price
                self._close_all_positions(
                    symbol,
                    final_price,
                    final_tick.timestamp,
                    "Backtest End"
                )

        # Calculate results
        elapsed = (datetime.now() - start_time).total_seconds()
        results = self._calculate_results(elapsed, total_ticks)

        logger.info("\n" + "="*80)
        logger.info("📊 BACKTEST COMPLETE")
        logger.info("="*80)
        logger.info(f"Total Return: {results['total_return']:+.2f}%")
        logger.info(f"Win Rate: {results['win_rate']:.2f}%")
        logger.info(f"Total Trades: {results['total_trades']}")
        logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown: {results['max_drawdown']:.2f}%")
        logger.info(f"Processing Speed: {results['ticks_per_second']:,.0f} ticks/sec")
        logger.info("="*80 + "\n")

        return results

    def _calculate_results(self, elapsed_seconds: float, total_ticks: int) -> dict:
        """Calculate backtest performance metrics"""

        # Basic metrics
        total_pnl = self.balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100

        # Trade statistics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]

        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        # Profit factor
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        # Sharpe ratio (using equity curve)
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                prev = self.equity_curve[i-1]['total_equity']
                curr = self.equity_curve[i]['total_equity']
                if prev > 0:
                    returns.append((curr - prev) / prev)

            if returns:
                sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0

        # Max drawdown
        max_dd = ((self.max_balance - self.min_balance) / self.max_balance * 100) if self.max_balance > 0 else 0

        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'max_balance': self.max_balance,
            'min_balance': self.min_balance,
            'total_fees_paid': self.total_fees_paid,
            'fee_percentage': (self.total_fees_paid / abs(total_pnl) * 100) if total_pnl != 0 else 0,
            'total_ticks_processed': total_ticks,
            'elapsed_seconds': elapsed_seconds,
            'ticks_per_second': total_ticks / elapsed_seconds if elapsed_seconds > 0 else 0,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }


async def main():
    """Test tick backtester"""

    # Example: Backtest with 1 week of tick data
    symbols = ['BTC/USDT', 'ETH/USDT']

    backtester = TickBacktester(
        symbols=symbols,
        initial_balance=10000.0,
        leverage=10,
        position_size_pct=0.1
    )

    # Option 1: Load from saved tick data files
    tick_data = {}
    for symbol in symbols:
        file_path = Path(f"tick_data/{symbol.replace('/', '_')}_20251017.jsonl")
        if file_path.exists():
            ticks = await backtester.load_tick_data_from_file(symbol, file_path, limit=100000)
            tick_data[symbol] = ticks

    # Option 2: Collect live tick data (uncomment to use)
    # for symbol in symbols:
    #     ticks = await backtester.load_tick_data_live(symbol, duration_seconds=3600)
    #     tick_data[symbol] = ticks

    if tick_data:
        # Run backtest
        results = await backtester.run_backtest(tick_data, progress_interval=5000)

        # Save results
        output_file = Path('claudedocs/tick_backtest_results.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"✅ Results saved to {output_file}")
    else:
        logger.warning("⚠️  No tick data available. Collect data first using tick_data_collector.py")


if __name__ == "__main__":
    asyncio.run(main())
