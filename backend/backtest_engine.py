"""
Backtesting Engine
Test trading strategies on historical data
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class BacktestEngine:
    """Backtest trading strategies on historical data"""

    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission: float = 0.001,  # 0.1%
        slippage: float = 0.0005    # 0.05%
    ):
        """Initialize backtest engine

        Args:
            initial_balance: Starting capital (USDT)
            commission: Trading commission percentage
            slippage: Slippage percentage
        """
        self.initial_balance = initial_balance
        self.commission = commission
        self.slippage = slippage

        # State
        self.balance = initial_balance
        self.position = 0.0  # Current position size
        self.entry_price = 0.0
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []

        logger.info(f"BacktestEngine initialized with ${initial_balance:,.2f}")

    def buy(self, price: float, amount: float, timestamp: datetime):
        """Execute buy order

        Args:
            price: Entry price
            amount: Position size (in base currency)
            timestamp: Order timestamp
        """
        # Apply slippage (price goes up)
        execution_price = price * (1 + self.slippage)

        # Calculate cost
        cost = execution_price * amount
        fee = cost * self.commission
        total_cost = cost + fee

        if total_cost > self.balance:
            logger.warning(f"Insufficient balance: ${self.balance:.2f} < ${total_cost:.2f}")
            return

        # Execute
        self.balance -= total_cost
        self.position = amount
        self.entry_price = execution_price

        logger.info(f"BUY: {amount:.6f} @ ${execution_price:.2f} | Cost: ${total_cost:.2f} | Balance: ${self.balance:.2f}")

    def sell(self, price: float, timestamp: datetime):
        """Execute sell order

        Args:
            price: Exit price
            timestamp: Order timestamp
        """
        if self.position == 0:
            logger.warning("No position to sell")
            return

        # Apply slippage (price goes down)
        execution_price = price * (1 - self.slippage)

        # Calculate proceeds
        proceeds = execution_price * self.position
        fee = proceeds * self.commission
        net_proceeds = proceeds - fee

        # Calculate P&L
        pnl = (execution_price - self.entry_price) * self.position - (fee * 2)  # Entry + exit fees
        pnl_percent = (pnl / (self.entry_price * self.position)) * 100

        # Record trade
        trade = {
            'entry_time': timestamp - timedelta(minutes=1),  # Approximate
            'exit_time': timestamp,
            'entry_price': self.entry_price,
            'exit_price': execution_price,
            'amount': self.position,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'balance_after': self.balance + net_proceeds
        }
        self.trades.append(trade)

        # Execute
        self.balance += net_proceeds
        self.position = 0.0
        self.entry_price = 0.0

        logger.info(f"SELL: @ ${execution_price:.2f} | P&L: ${pnl:.2f} ({pnl_percent:+.2f}%) | Balance: ${self.balance:.2f}")

    def run_backtest(
        self,
        data: pd.DataFrame,
        strategy_func,
        **strategy_params
    ) -> Dict:
        """Run backtest on historical data

        Args:
            data: DataFrame with OHLCV data
            strategy_func: Strategy function that returns signals
            strategy_params: Additional parameters for strategy

        Returns:
            Backtest results dictionary
        """
        logger.info(f"Starting backtest with {len(data)} candles")

        for i in range(len(data)):
            row = data.iloc[i]
            timestamp = row.get('timestamp', datetime.now())
            close = row['close']

            # Record equity
            current_equity = self.balance + (self.position * close if self.position > 0 else 0)
            self.equity_curve.append(current_equity)

            # Get strategy signal
            signal = strategy_func(data.iloc[:i+1], **strategy_params)

            # Execute trades based on signal
            if signal == 'BUY' and self.position == 0:
                # Calculate position size (use 95% of balance)
                amount = (self.balance * 0.95) / close
                self.buy(close, amount, timestamp)

            elif signal == 'SELL' and self.position > 0:
                self.sell(close, timestamp)

        # Close any open position at the end
        if self.position > 0:
            self.sell(data.iloc[-1]['close'], data.iloc[-1].get('timestamp', datetime.now()))

        # Calculate metrics
        results = self.calculate_metrics()

        logger.info(f"Backtest complete: Total P&L: ${results['total_pnl']:.2f} ({results['total_return']:.2f}%)")

        return results

    def calculate_metrics(self) -> Dict:
        """Calculate backtest performance metrics

        Returns:
            Dictionary of performance metrics
        """
        if len(self.trades) == 0:
            return {
                'total_pnl': 0.0,
                'total_return': 0.0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'total_trades': 0
            }

        # Basic metrics
        total_pnl = self.balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100

        # Win/Loss analysis
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]

        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0

        # Profit factor
        total_wins = sum(t['pnl'] for t in wins) if wins else 0
        total_losses = abs(sum(t['pnl'] for t in losses)) if losses else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Maximum drawdown
        equity_array = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = abs(drawdown.min()) * 100

        # Sharpe ratio (simplified)
        if len(self.equity_curve) > 1:
            returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0

        # Average trade metrics
        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0

        return {
            'total_pnl': total_pnl,
            'total_return': total_return,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'final_balance': self.balance
        }


# Example strategy
def simple_ma_crossover(data: pd.DataFrame, fast_period: int = 20, slow_period: int = 50) -> str:
    """Simple moving average crossover strategy

    Args:
        data: OHLCV dataframe
        fast_period: Fast MA period
        slow_period: Slow MA period

    Returns:
        Signal: 'BUY', 'SELL', or 'HOLD'
    """
    if len(data) < slow_period:
        return 'HOLD'

    fast_ma = data['close'].rolling(window=fast_period).mean()
    slow_ma = data['close'].rolling(window=slow_period).mean()

    # Get last two values
    fast_current = fast_ma.iloc[-1]
    fast_previous = fast_ma.iloc[-2]
    slow_current = slow_ma.iloc[-1]
    slow_previous = slow_ma.iloc[-2]

    # Bullish crossover
    if fast_previous <= slow_previous and fast_current > slow_current:
        return 'BUY'

    # Bearish crossover
    if fast_previous >= slow_previous and fast_current < slow_current:
        return 'SELL'

    return 'HOLD'


# Example usage
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=1000, freq='1H')
    base_price = 43000

    # Random walk with trend
    price_changes = np.random.randn(1000) * 100 + 5  # Slight upward trend
    closes = base_price + np.cumsum(price_changes)

    data = pd.DataFrame({
        'timestamp': dates,
        'open': closes,
        'high': closes + np.random.rand(1000) * 50,
        'low': closes - np.random.rand(1000) * 50,
        'close': closes,
        'volume': np.random.rand(1000) * 1000000
    })

    # Run backtest
    engine = BacktestEngine(initial_balance=10000.0)
    results = engine.run_backtest(
        data,
        simple_ma_crossover,
        fast_period=20,
        slow_period=50
    )

    # Print results
    print("\n=== Backtest Results ===")
    print(f"Initial Balance: ${engine.initial_balance:,.2f}")
    print(f"Final Balance: ${results['final_balance']:,.2f}")
    print(f"Total P&L: ${results['total_pnl']:,.2f} ({results['total_return']:.2f}%)")
    print(f"Total Trades: {results['total_trades']}")
    print(f"Win Rate: {results['win_rate']:.2f}%")
    print(f"Profit Factor: {results['profit_factor']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
