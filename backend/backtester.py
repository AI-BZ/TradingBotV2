"""
Backtesting System - Historical strategy performance analysis
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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


class Backtester:
    """Historical trading strategy backtester"""

    def __init__(self,
                 initial_balance: float = 10000.0,
                 leverage: int = 10,
                 symbols: Optional[List[str]] = None):
        """Initialize backtester

        Args:
            initial_balance: Starting balance in USDT
            leverage: Leverage for futures trading
            symbols: List of symbols to test (None = auto Top 10)
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.symbols = symbols or []

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

        # State tracking
        self.positions = {}
        self.trade_history = []
        self.daily_balances = []
        self.equity_curve = []

        logger.info(f"Backtester initialized: ${initial_balance:,.2f} @ {leverage}x leverage")

    def set_ml_engine(self, ml_engine: MLEngine):
        """Set ML engine for predictions"""
        self.ml_engine = ml_engine
        self.strategy.set_ml_engine(ml_engine)

    async def load_historical_data(
        self,
        client: BinanceClient,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = '1h'
    ) -> pd.DataFrame:
        """Load historical market data

        Args:
            client: Binance client
            symbol: Trading pair
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Candle interval

        Returns:
            DataFrame with OHLCV data
        """
        try:
            logger.info(f"Loading {symbol} data: {start_date} to {end_date}")

            # Convert dates to timestamps
            start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

            # Calculate number of candles needed
            interval_ms = {
                '1m': 60000, '5m': 300000, '15m': 900000,
                '1h': 3600000, '4h': 14400000, '1d': 86400000
            }
            ms_per_candle = interval_ms.get(interval, 3600000)
            total_candles = (end_ts - start_ts) // ms_per_candle

            all_klines = []
            batch_size = 1000  # Binance API limit

            # Fetch in batches
            current_ts = start_ts
            batches = (total_candles // batch_size) + 1

            for batch in range(batches):
                if current_ts >= end_ts:
                    break

                logger.info(f"  Fetching batch {batch + 1}/{batches}...")

                klines = await client.get_klines(symbol, interval, batch_size)
                if not klines:
                    break

                # Filter by date range
                valid_klines = [k for k in klines if start_ts <= k['timestamp'] <= end_ts]
                all_klines.extend(valid_klines)

                if len(klines) < batch_size:
                    break

                # Update timestamp for next batch
                current_ts = klines[-1]['timestamp'] + ms_per_candle

                # Rate limiting
                await asyncio.sleep(0.2)

            if not all_klines:
                logger.warning(f"No data loaded for {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(all_klines)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('timestamp').reset_index(drop=True)

            logger.info(f"  Loaded {len(df)} candles for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error loading data for {symbol}: {e}")
            return pd.DataFrame()

    def analyze_bar(self, data: pd.DataFrame, idx: int) -> Optional[Dict]:
        """Analyze single bar and generate signal

        Args:
            data: Historical data
            idx: Current bar index

        Returns:
            Trading signal or None
        """
        if idx < 100:  # Need enough history for indicators
            return None

        # Get data up to current bar
        history = data.iloc[:idx + 1]

        # Calculate technical indicators
        indicators = TechnicalIndicators.calculate_all(
            history['high'].tolist(),
            history['low'].tolist(),
            history['close'].tolist(),
            history['volume'].tolist()
        )
        indicators['close'] = float(history['close'].iloc[-1])

        # Generate signal
        signal = self.strategy.generate_signal(history, indicators)
        signal['price'] = float(history['close'].iloc[-1])
        signal['timestamp'] = history['timestamp'].iloc[-1]
        signal['atr'] = indicators.get('atr', signal['price'] * 0.02)

        return signal

    def execute_backtest_trade(self, signal: Dict, symbol: str) -> Optional[Dict]:
        """Execute simulated trade based on signal

        Args:
            signal: Trading signal
            symbol: Trading symbol

        Returns:
            Trade result or None
        """
        price = signal['price']
        action = signal['signal']
        timestamp = signal['timestamp']
        atr = signal['atr']

        # Check if should trade
        if not self.strategy.should_trade(signal, min_confidence=0.5):
            return None

        # Check risk limits
        if not self.risk_manager.can_open_position(self.balance):
            return None

        # Open LONG position
        if action == 'BUY' and symbol not in self.positions:
            position_size = self.risk_manager.calculate_position_size(
                self.balance, price, signal['confidence']
            )

            # Initialize trailing stop
            self.trailing_stop_manager.initialize_position(symbol, price, 'LONG')

            # Store position
            self.positions[symbol] = {
                'type': 'LONG',
                'entry_price': price,
                'size': position_size,
                'entry_time': timestamp,
                'signal': signal,
                'highest_price': price
            }

            # Update balance
            cost = position_size * price / self.leverage
            self.balance -= cost

            return {
                'action': 'OPEN_LONG',
                'symbol': symbol,
                'price': price,
                'size': position_size,
                'timestamp': timestamp
            }

        # Open SHORT position
        elif action == 'SELL' and symbol not in self.positions:
            position_size = self.risk_manager.calculate_position_size(
                self.balance, price, signal['confidence']
            )

            # Initialize trailing stop
            self.trailing_stop_manager.initialize_position(symbol, price, 'SHORT')

            # Store position
            self.positions[symbol] = {
                'type': 'SHORT',
                'entry_price': price,
                'size': position_size,
                'entry_time': timestamp,
                'signal': signal,
                'lowest_price': price
            }

            # Update balance
            cost = position_size * price / self.leverage
            self.balance -= cost

            return {
                'action': 'OPEN_SHORT',
                'symbol': symbol,
                'price': price,
                'size': position_size,
                'timestamp': timestamp
            }

        return None

    def check_trailing_stop_backtest(self, symbol: str, current_price: float, atr: float, timestamp: datetime) -> Optional[Dict]:
        """Check trailing stop for backtest

        Args:
            symbol: Trading symbol
            current_price: Current price
            atr: Current ATR value
            timestamp: Current timestamp

        Returns:
            Close trade result or None
        """
        if symbol not in self.positions:
            return None

        # Update trailing stop
        stop_price, should_close = self.trailing_stop_manager.update_trailing_stop(
            symbol, current_price, atr
        )

        if should_close:
            position = self.positions[symbol]
            entry_price = position['entry_price']
            size = position['size']
            position_type = position['type']

            # Calculate P&L
            if position_type == 'LONG':
                pnl = (current_price - entry_price) * size
                pnl_pct = (current_price - entry_price) / entry_price
            else:  # SHORT
                pnl = (entry_price - current_price) * size
                pnl_pct = (entry_price - current_price) / entry_price

            # Update balance
            proceeds = (size * entry_price / self.leverage) + pnl
            self.balance += proceeds

            # Update risk manager
            self.risk_manager.update_daily_pnl(pnl)

            # Remove position
            del self.positions[symbol]
            self.trailing_stop_manager.remove_position(symbol)

            # Record trade
            trade = {
                'symbol': symbol,
                'action': f'CLOSE_{position_type}',
                'type': position_type,
                'entry_price': entry_price,
                'exit_price': current_price,
                'size': size,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'entry_time': position['entry_time'],
                'exit_time': timestamp,
                'duration_hours': (timestamp - position['entry_time']).total_seconds() / 3600,
                'exit_reason': 'trailing_stop'
            }
            self.trade_history.append(trade)

            return trade

        return None

    async def run_backtest(
        self,
        start_date: str,
        end_date: str,
        interval: str = '1h'
    ) -> Dict:
        """Run complete backtest

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Candle interval

        Returns:
            Backtest results
        """
        logger.info("=" * 80)
        logger.info(f"BACKTESTING: {start_date} to {end_date}")
        logger.info("=" * 80)

        # Initialize Binance client
        client = BinanceClient(testnet=True, use_futures=True)

        try:
            # Get symbols if not set
            if not self.symbols:
                logger.info("Loading Top 10 coins by volume...")
                self.symbols = await client.get_top_coins(limit=10)
                # Convert to format without /
                self.symbols = [s.replace('/', '') for s in self.symbols]
                logger.info(f"Testing symbols: {', '.join(self.symbols)}")

            # Load historical data for all symbols
            historical_data = {}
            for symbol in self.symbols:
                ccxt_symbol = symbol.replace('USDT', '/USDT') if '/' not in symbol else symbol
                data = await self.load_historical_data(client, ccxt_symbol, start_date, end_date, interval)
                if not data.empty:
                    historical_data[symbol] = data

            if not historical_data:
                logger.error("No historical data loaded!")
                return {}

            # Run backtest simulation
            logger.info("\nStarting backtest simulation...")

            # Get common timeline (use first symbol as reference)
            reference_symbol = list(historical_data.keys())[0]
            timestamps = historical_data[reference_symbol]['timestamp'].tolist()

            total_bars = len(timestamps)
            progress_interval = max(1, total_bars // 20)  # Log every 5%

            for idx, timestamp in enumerate(timestamps):
                if idx < 100:  # Skip initial bars (need history)
                    continue

                # Progress logging
                if idx % progress_interval == 0:
                    progress = (idx / total_bars) * 100
                    logger.info(f"Progress: {progress:.1f}% ({idx}/{total_bars}) - Balance: ${self.balance:,.2f}")

                # Check trailing stops for all open positions
                for symbol in list(self.positions.keys()):
                    if symbol not in historical_data:
                        continue

                    data = historical_data[symbol]
                    if idx >= len(data):
                        continue

                    current_price = float(data.iloc[idx]['close'])

                    # Calculate ATR
                    history = data.iloc[:idx + 1]
                    if len(history) >= 14:
                        indicators = TechnicalIndicators.calculate_all(
                            history['high'].tolist()[-50:],
                            history['low'].tolist()[-50:],
                            history['close'].tolist()[-50:],
                            history['volume'].tolist()[-50:]
                        )
                        atr = indicators.get('atr', current_price * 0.02)
                    else:
                        atr = current_price * 0.02

                    # Check trailing stop
                    self.check_trailing_stop_backtest(symbol, current_price, atr, timestamp)

                # Analyze each symbol for new signals
                for symbol, data in historical_data.items():
                    if idx >= len(data):
                        continue

                    signal = self.analyze_bar(data, idx)
                    if signal:
                        signal['symbol'] = symbol
                        trade = self.execute_backtest_trade(signal, symbol)

                # Track equity curve
                total_equity = self.balance
                for symbol, position in self.positions.items():
                    if symbol in historical_data and idx < len(historical_data[symbol]):
                        current_price = float(historical_data[symbol].iloc[idx]['close'])
                        entry_price = position['entry_price']
                        size = position['size']

                        if position['type'] == 'LONG':
                            unrealized_pnl = (current_price - entry_price) * size
                        else:
                            unrealized_pnl = (entry_price - current_price) * size

                        total_equity += unrealized_pnl

                self.equity_curve.append({
                    'timestamp': timestamp,
                    'equity': total_equity
                })

            # Calculate results
            results = self.calculate_results()

            logger.info("\n" + "=" * 80)
            logger.info("BACKTEST COMPLETE")
            logger.info("=" * 80)

            return results

        finally:
            await client.close()

    def calculate_results(self) -> Dict:
        """Calculate backtest performance metrics

        Returns:
            Performance metrics dictionary
        """
        if not self.trade_history:
            return {
                'error': 'No trades executed',
                'initial_balance': self.initial_balance,
                'final_balance': self.balance
            }

        # Separate wins and losses
        closed_trades = [t for t in self.trade_history if 'pnl' in t]
        wins = [t for t in closed_trades if t['pnl'] > 0]
        losses = [t for t in closed_trades if t['pnl'] <= 0]

        # Calculate metrics
        total_pnl = sum(t['pnl'] for t in closed_trades)
        total_return = (total_pnl / self.initial_balance) * 100

        win_rate = (len(wins) / len(closed_trades)) * 100 if closed_trades else 0

        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0

        profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else 0

        # Calculate max drawdown
        equity_values = [e['equity'] for e in self.equity_curve]
        peak = equity_values[0]
        max_drawdown = 0
        for equity in equity_values:
            if equity > peak:
                peak = equity
            drawdown = ((peak - equity) / peak) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Calculate Sharpe ratio (simplified)
        returns = [t['pnl_pct'] for t in closed_trades]
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (avg_return / std_return * np.sqrt(365)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        results = {
            'backtest_summary': {
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
                'profit_factor': profit_factor,
                'max_drawdown_pct': max_drawdown,
                'sharpe_ratio': sharpe_ratio
            },
            'trades': closed_trades,
            'equity_curve': self.equity_curve
        }

        return results

    def save_results(self, results: Dict, filename: str = 'backtest_results.json'):
        """Save backtest results to file

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


async def run_comprehensive_backtest():
    """Run 3-year comprehensive backtest"""
    backtester = Backtester(initial_balance=10000.0, leverage=10)

    # 3-year backtest (2022-10-01 to 2025-10-16)
    results = await backtester.run_backtest(
        start_date='2022-10-01',
        end_date='2025-10-16',
        interval='1h'
    )

    # Save results
    backtester.save_results(results, 'backtest_3year_results.json')

    # Print summary
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 80)

    if 'error' not in results:
        summary = results['backtest_summary']
        stats = results['trade_statistics']
        metrics = results['performance_metrics']

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
        print(f"  Max Drawdown:    {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Sharpe Ratio:    {metrics['sharpe_ratio']:.2f}")

    return results


if __name__ == "__main__":
    asyncio.run(run_comprehensive_backtest())
