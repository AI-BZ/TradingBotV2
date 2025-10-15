"""
Paper Trading System - Live simulated trading without real money
"""
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import json
from pathlib import Path

from binance_client import BinanceClient
from technical_indicators import TechnicalIndicators
from trading_strategy import TradingStrategy, RiskManager
from ml_engine import MLEngine
from trailing_stop_manager import TrailingStopManager, MLTrailingStopOptimizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaperTrader:
    """Live paper trading with real-time market data"""

    def __init__(self,
                 initial_balance: float = 10000.0,
                 leverage: int = 10):
        """Initialize paper trader

        Args:
            initial_balance: Starting balance in USDT
            leverage: Leverage for futures trading
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage

        # Initialize Binance client
        self.client = BinanceClient(testnet=True, use_futures=True)

        # Trading components
        self.strategy = TradingStrategy(ml_weight=0.6, technical_weight=0.4)
        self.risk_manager = RiskManager(
            max_position_size=0.2,
            stop_loss_pct=0.03,
            take_profit_pct=0.05
        )
        self.trailing_stop_manager = TrailingStopManager(
            base_atr_multiplier=2.5,
            min_profit_threshold=0.01,
            acceleration_step=0.1
        )
        self.ml_engine = None

        # Trading state
        self.positions = {}
        self.trade_history = []
        self.symbols = []
        self.is_running = False

        # Performance tracking
        self.start_time = None
        self.equity_curve = []
        self.hourly_snapshots = []

        logger.info(f"PaperTrader initialized: ${initial_balance:,.2f} @ {leverage}x leverage")

    def set_ml_engine(self, ml_engine: MLEngine):
        """Set ML engine for predictions"""
        self.ml_engine = ml_engine
        self.strategy.set_ml_engine(ml_engine)

    async def get_market_data(self, symbol: str, interval: str = '1h', limit: int = 100) -> pd.DataFrame:
        """Fetch market data for symbol

        Args:
            symbol: Trading pair symbol
            interval: Candle interval
            limit: Number of candles

        Returns:
            DataFrame with OHLCV data
        """
        klines = await self.client.get_klines(symbol, interval, limit)
        data = pd.DataFrame(klines)
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
        return data

    async def analyze_symbol(self, symbol: str) -> Dict:
        """Analyze symbol and generate trading signal

        Args:
            symbol: Trading pair symbol

        Returns:
            Analysis dictionary with signal and indicators
        """
        # Get market data
        data = await self.get_market_data(symbol)

        # Calculate technical indicators
        indicators = TechnicalIndicators.calculate_all(
            data['high'].tolist(),
            data['low'].tolist(),
            data['close'].tolist(),
            data['volume'].tolist()
        )
        indicators['close'] = data['close'].iloc[-1]

        # Generate signal
        signal = self.strategy.generate_signal(data, indicators)
        signal['symbol'] = symbol
        signal['price'] = float(data['close'].iloc[-1])
        signal['atr'] = indicators.get('atr', signal['price'] * 0.02)

        return signal

    async def execute_trade(self, signal: Dict) -> Optional[Dict]:
        """Execute simulated trade based on signal

        Args:
            signal: Trading signal dictionary

        Returns:
            Trade execution result or None
        """
        symbol = signal['symbol']
        price = signal['price']
        action = signal['signal']

        # Check if we should trade
        if not self.strategy.should_trade(signal, min_confidence=0.5):
            logger.info(f"{symbol}: Signal {action} confidence too low, skipping")
            return None

        # Check risk limits
        if not self.risk_manager.can_open_position(self.balance):
            logger.warning(f"{symbol}: Risk limits reached, cannot open position")
            return None

        # Execute based on signal
        if action == 'BUY' and symbol not in self.positions:
            # Open LONG position
            position_size = self.risk_manager.calculate_position_size(
                self.balance, price, signal['confidence']
            )

            logger.info(f"📈 {symbol}: Opening LONG - Size: {position_size:.6f} @ ${price:,.2f}")

            # Initialize trailing stop
            self.trailing_stop_manager.initialize_position(symbol, price, 'LONG')

            # Store position
            self.positions[symbol] = {
                'type': 'LONG',
                'entry_price': price,
                'size': position_size,
                'entry_time': datetime.now(),
                'signal': signal
            }

            # Update balance (simulated)
            cost = position_size * price / self.leverage
            self.balance -= cost

            trade = {
                'symbol': symbol,
                'action': 'OPEN_LONG',
                'type': 'LONG',
                'price': price,
                'size': position_size,
                'cost': cost,
                'timestamp': datetime.now(),
                'signal': signal
            }
            self.trade_history.append(trade)

            return trade

        elif action == 'SELL' and symbol not in self.positions:
            # Open SHORT position
            position_size = self.risk_manager.calculate_position_size(
                self.balance, price, signal['confidence']
            )

            logger.info(f"📉 {symbol}: Opening SHORT - Size: {position_size:.6f} @ ${price:,.2f}")

            # Initialize trailing stop
            self.trailing_stop_manager.initialize_position(symbol, price, 'SHORT')

            # Store position
            self.positions[symbol] = {
                'type': 'SHORT',
                'entry_price': price,
                'size': position_size,
                'entry_time': datetime.now(),
                'signal': signal
            }

            # Update balance (simulated)
            cost = position_size * price / self.leverage
            self.balance -= cost

            trade = {
                'symbol': symbol,
                'action': 'OPEN_SHORT',
                'type': 'SHORT',
                'price': price,
                'size': position_size,
                'cost': cost,
                'timestamp': datetime.now(),
                'signal': signal
            }
            self.trade_history.append(trade)

            return trade

        elif symbol in self.positions:
            # Close existing position
            position = self.positions[symbol]
            entry_price = position['entry_price']
            size = position['size']
            position_type = position['type']

            # Calculate P&L based on position type
            if position_type == 'LONG':
                pnl = (price - entry_price) * size
                pnl_pct = (price - entry_price) / entry_price
            else:  # SHORT
                pnl = (entry_price - price) * size
                pnl_pct = (entry_price - price) / entry_price

            logger.info(f"💰 {symbol}: Closing {position_type} - P&L: ${pnl:,.2f} ({pnl_pct:+.2%})")

            # Update balance (simulated)
            proceeds = (size * entry_price / self.leverage) + pnl
            self.balance += proceeds

            # Update risk manager
            self.risk_manager.update_daily_pnl(pnl)

            trade = {
                'symbol': symbol,
                'action': f'CLOSE_{position_type}',
                'type': position_type,
                'price': price,
                'size': size,
                'entry_price': entry_price,
                'proceeds': proceeds,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'timestamp': datetime.now(),
                'signal': signal
            }
            self.trade_history.append(trade)

            # Remove position
            del self.positions[symbol]
            self.trailing_stop_manager.remove_position(symbol)

            return trade

        return None

    async def check_trailing_stops(self):
        """Check all positions for trailing stop triggers"""
        for symbol in list(self.positions.keys()):
            try:
                # Get current price
                current_price = await self.client.get_price(symbol)

                # Get market data to calculate ATR
                data = await self.get_market_data(symbol, interval='1h', limit=20)

                # Calculate ATR
                indicators = TechnicalIndicators.calculate_all(
                    data['high'].tolist(),
                    data['low'].tolist(),
                    data['close'].tolist(),
                    data['volume'].tolist()
                )
                atr_value = indicators.get('atr', current_price * 0.02)

                # Update trailing stop and check if should close
                stop_price, should_close = self.trailing_stop_manager.update_trailing_stop(
                    symbol, current_price, atr_value
                )

                if should_close:
                    position = self.positions[symbol]
                    position_type = position['type']

                    logger.info(f"🛑 {symbol}: Trailing stop hit! Closing {position_type} @ ${current_price:,.2f}")

                    # Close position
                    signal = {
                        'symbol': symbol,
                        'signal': 'SELL',
                        'price': current_price,
                        'confidence': 1.0,
                        'source': 'trailing_stop'
                    }
                    await self.execute_trade(signal)

            except Exception as e:
                logger.error(f"Error checking trailing stop for {symbol}: {e}")

    def calculate_current_equity(self) -> float:
        """Calculate current total equity including unrealized P&L

        Returns:
            Total equity value
        """
        return self.balance  # Simplified - could add unrealized P&L

    async def save_snapshot(self):
        """Save current state snapshot"""
        total_equity = self.calculate_current_equity()

        snapshot = {
            'timestamp': datetime.now(),
            'balance': self.balance,
            'equity': total_equity,
            'positions': len(self.positions),
            'total_trades': len(self.trade_history)
        }

        self.hourly_snapshots.append(snapshot)
        self.equity_curve.append({
            'timestamp': datetime.now(),
            'equity': total_equity
        })

    async def trading_loop(self, interval: int = 300):
        """Main paper trading loop

        Args:
            interval: Time between iterations in seconds (default 5 minutes)
        """
        # Load top 10 coins if symbols not set
        if not self.symbols:
            logger.info("Loading top 10 coins by 24h volume...")
            self.symbols = await self.client.get_top_coins(limit=10)
            self.symbols = [s.replace('/', '') for s in self.symbols]

        # Set leverage for all symbols
        for symbol in self.symbols:
            try:
                await self.client.set_leverage(symbol, self.leverage)
            except Exception as e:
                logger.warning(f"Could not set leverage for {symbol}: {e}")

        logger.info(f"\n{'='*80}")
        logger.info(f"PAPER TRADING STARTED")
        logger.info(f"{'='*80}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Initial Balance: ${self.balance:,.2f}")
        logger.info(f"Leverage: {self.leverage}x")

        iteration = 0

        while self.is_running:
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"Iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Balance: ${self.balance:,.2f} | Open Positions: {len(self.positions)}")

            try:
                # Check trailing stops for existing positions
                await self.check_trailing_stops()

                # Analyze each symbol
                for symbol in self.symbols:
                    try:
                        logger.info(f"\nAnalyzing {symbol}...")
                        signal = await self.analyze_symbol(symbol)

                        logger.info(f"  Signal: {signal['signal']} | Confidence: {signal['confidence']:.2%} | Price: ${signal['price']:,.2f}")

                        # Execute trade if conditions met
                        trade = await self.execute_trade(signal)
                        if trade:
                            logger.info(f"  ✅ Trade executed: {trade['action']}")

                    except Exception as e:
                        logger.error(f"Error analyzing {symbol}: {e}")

                # Save snapshot
                await self.save_snapshot()

                # Print summary
                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration Summary:")
                logger.info(f"  Total Trades: {len(self.trade_history)}")
                logger.info(f"  Open Positions: {len(self.positions)}")
                logger.info(f"  Current Balance: ${self.balance:,.2f}")

                if self.trade_history:
                    closed_trades = [t for t in self.trade_history if 'pnl' in t]
                    if closed_trades:
                        total_pnl = sum(t['pnl'] for t in closed_trades)
                        logger.info(f"  Total P&L: ${total_pnl:,.2f}")

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")

            # Wait for next iteration
            logger.info(f"\nWaiting {interval}s until next iteration...")
            await asyncio.sleep(interval)

    async def start(self, duration_hours: float = 2.5):
        """Start paper trading

        Args:
            duration_hours: How long to run (hours)
        """
        self.start_time = datetime.now()
        logger.info(f"Starting Paper Trading for {duration_hours} hours")
        self.is_running = True

        # Start trading loop
        trading_task = asyncio.create_task(self.trading_loop())

        # Run for specified duration
        await asyncio.sleep(duration_hours * 3600)

        # Stop trading
        self.is_running = False
        await trading_task

        # Generate final report
        results = self.generate_report()
        self.save_results(results)

        await self.client.close()

        return results

    async def stop(self):
        """Stop paper trading"""
        logger.info("Stopping Paper Trading...")
        self.is_running = False

    def generate_report(self) -> Dict:
        """Generate comprehensive trading report

        Returns:
            Performance report dictionary
        """
        if not self.trade_history:
            return {
                'error': 'No trades executed',
                'initial_balance': self.initial_balance,
                'final_balance': self.balance
            }

        # Calculate metrics
        closed_trades = [t for t in self.trade_history if 'pnl' in t]
        wins = [t for t in closed_trades if t['pnl'] > 0]
        losses = [t for t in closed_trades if t['pnl'] <= 0]

        total_pnl = sum(t['pnl'] for t in closed_trades)
        total_return = (total_pnl / self.initial_balance) * 100

        win_rate = (len(wins) / len(closed_trades)) * 100 if closed_trades else 0

        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0

        profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0

        # Calculate duration
        duration = datetime.now() - self.start_time if self.start_time else timedelta(0)

        results = {
            'paper_trading_summary': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': datetime.now().isoformat(),
                'duration_hours': duration.total_seconds() / 3600,
                'initial_balance': self.initial_balance,
                'final_balance': self.balance,
                'total_pnl': total_pnl,
                'total_return_pct': total_return
            },
            'trade_statistics': {
                'total_trades': len(closed_trades),
                'winning_trades': len(wins),
                'losing_trades': len(losses),
                'win_rate_pct': win_rate
            },
            'performance_metrics': {
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor
            },
            'trades': closed_trades,
            'equity_curve': self.equity_curve,
            'hourly_snapshots': self.hourly_snapshots
        }

        return results

    def save_results(self, results: Dict, filename: str = 'paper_trading_results.json'):
        """Save paper trading results to file

        Args:
            results: Results dictionary
            filename: Output filename
        """
        output_path = Path(__file__).parent / 'results' / filename
        output_path.parent.mkdir(exist_ok=True)

        # Convert datetime objects to strings
        def convert_timestamps(obj):
            if isinstance(obj, dict):
                return {k: convert_timestamps(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_timestamps(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj

        results_serializable = convert_timestamps(results)

        with open(output_path, 'w') as f:
            json.dump(results_serializable, f, indent=2)

        logger.info(f"Results saved to {output_path}")


async def run_paper_trading_session(duration_hours: float = 2.5):
    """Run paper trading session

    Args:
        duration_hours: Duration in hours
    """
    trader = PaperTrader(initial_balance=10000.0, leverage=10)

    results = await trader.start(duration_hours=duration_hours)

    # Print summary
    print("\n" + "=" * 80)
    print("PAPER TRADING RESULTS")
    print("=" * 80)

    if 'error' not in results:
        summary = results['paper_trading_summary']
        stats = results['trade_statistics']
        metrics = results['performance_metrics']

        print(f"\n⏱️  Trading Session:")
        print(f"  Duration:        {summary['duration_hours']:.2f} hours")
        print(f"  Start:           {summary['start_time']}")
        print(f"  End:             {summary['end_time']}")

        print(f"\n💰 Financial Performance:")
        print(f"  Initial Balance: ${summary['initial_balance']:,.2f}")
        print(f"  Final Balance:   ${summary['final_balance']:,.2f}")
        print(f"  Total P&L:       ${summary['total_pnl']:,.2f}")
        print(f"  Total Return:    {summary['total_return_pct']:+.2f}%")

        print(f"\n📊 Trade Statistics:")
        print(f"  Total Trades:    {stats['total_trades']}")
        print(f"  Winning Trades:  {stats['winning_trades']} ({stats['win_rate_pct']:.1f}%)")
        print(f"  Losing Trades:   {stats['losing_trades']}")

        print(f"\n📈 Performance Metrics:")
        print(f"  Avg Win:         ${metrics['avg_win']:.2f}")
        print(f"  Avg Loss:        ${metrics['avg_loss']:.2f}")
        print(f"  Profit Factor:   {metrics['profit_factor']:.2f}")

    return results


if __name__ == "__main__":
    asyncio.run(run_paper_trading_session(duration_hours=2.5))
