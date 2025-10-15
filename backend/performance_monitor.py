"""
Performance Monitoring System
트레이딩 성과를 실시간으로 모니터링하고 분석하는 시스템
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TradeMetrics:
    """Individual trade metrics"""
    trade_id: str
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    side: str  # 'LONG' or 'SHORT'
    pnl: Optional[float]
    pnl_pct: Optional[float]
    duration_minutes: Optional[int]
    reason: str  # 'signal', 'stop_loss', 'take_profit', 'manual'


@dataclass
class PerformanceSnapshot:
    """Snapshot of trading performance"""
    timestamp: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    avg_trade_duration_minutes: float
    active_positions: int


class PerformanceMonitor:
    """Real-time trading performance monitor"""

    def __init__(self, initial_balance: float = 10000.0, data_dir: str = "data/performance"):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.peak_balance = initial_balance

        # Trade history
        self.trades: List[TradeMetrics] = []
        self.active_positions: Dict[str, TradeMetrics] = {}

        # Performance tracking
        self.equity_curve: List[Dict] = []
        self.daily_returns: List[float] = []

        # Risk limits
        self.max_daily_loss = initial_balance * 0.10  # 10% daily loss limit
        self.max_drawdown_limit = initial_balance * 0.25  # 25% max drawdown limit

        # Alerts
        self.alerts: List[Dict] = []

        # Storage
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.start_time = datetime.now()
        self.last_snapshot = None

    def record_trade_entry(self, trade_id: str, symbol: str, entry_price: float,
                          quantity: float, side: str = 'LONG') -> TradeMetrics:
        """
        Record a new trade entry

        Args:
            trade_id: Unique trade identifier
            symbol: Trading pair symbol
            entry_price: Entry price
            quantity: Position size
            side: 'LONG' or 'SHORT'

        Returns:
            TradeMetrics object
        """
        trade = TradeMetrics(
            trade_id=trade_id,
            symbol=symbol,
            entry_time=datetime.now(),
            exit_time=None,
            entry_price=entry_price,
            exit_price=None,
            quantity=quantity,
            side=side,
            pnl=None,
            pnl_pct=None,
            duration_minutes=None,
            reason='signal'
        )

        self.active_positions[trade_id] = trade
        logger.info(f"Trade opened: {trade_id} | {symbol} {side} @ ${entry_price:.2f} | Qty: {quantity:.4f}")

        return trade

    def record_trade_exit(self, trade_id: str, exit_price: float, reason: str = 'signal') -> Optional[TradeMetrics]:
        """
        Record a trade exit and calculate P&L

        Args:
            trade_id: Unique trade identifier
            exit_price: Exit price
            reason: Exit reason ('signal', 'stop_loss', 'take_profit', 'manual')

        Returns:
            Completed TradeMetrics object
        """
        if trade_id not in self.active_positions:
            logger.warning(f"Trade {trade_id} not found in active positions")
            return None

        trade = self.active_positions.pop(trade_id)
        trade.exit_time = datetime.now()
        trade.exit_price = exit_price
        trade.reason = reason

        # Calculate P&L
        if trade.side == 'LONG':
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        else:  # SHORT
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity

        trade.pnl_pct = (trade.pnl / (trade.entry_price * trade.quantity)) * 100

        # Calculate duration
        duration = trade.exit_time - trade.entry_time
        trade.duration_minutes = int(duration.total_seconds() / 60)

        # Update balance
        self.current_balance += trade.pnl

        # Update equity curve
        self.equity_curve.append({
            'timestamp': trade.exit_time,
            'balance': self.current_balance,
            'trade_id': trade_id,
            'pnl': trade.pnl
        })

        # Update peak and drawdown
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

        # Add to completed trades
        self.trades.append(trade)

        # Check risk limits
        self.check_risk_limits()

        logger.info(
            f"Trade closed: {trade_id} | {trade.symbol} | "
            f"P&L: ${trade.pnl:+,.2f} ({trade.pnl_pct:+.2f}%) | "
            f"Duration: {trade.duration_minutes}min | "
            f"Reason: {reason} | "
            f"Balance: ${self.current_balance:,.2f}"
        )

        return trade

    def calculate_metrics(self) -> PerformanceSnapshot:
        """
        Calculate comprehensive performance metrics

        Returns:
            PerformanceSnapshot with current metrics
        """
        if not self.trades:
            return PerformanceSnapshot(
                timestamp=datetime.now(),
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                current_drawdown=0.0,
                sharpe_ratio=0.0,
                avg_trade_duration_minutes=0.0,
                active_positions=len(self.active_positions)
            )

        # Basic metrics
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        total_trades = len(self.trades)
        num_winning = len(winning_trades)
        num_losing = len(losing_trades)

        win_rate = num_winning / total_trades if total_trades > 0 else 0.0

        # P&L metrics
        total_pnl = sum(t.pnl for t in self.trades)
        total_wins = sum(t.pnl for t in winning_trades) if winning_trades else 0
        total_losses = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0

        avg_win = total_wins / num_winning if num_winning > 0 else 0
        avg_loss = total_losses / num_losing if num_losing > 0 else 0

        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Drawdown calculation
        current_drawdown = self.peak_balance - self.current_balance
        current_drawdown_pct = (current_drawdown / self.peak_balance * 100) if self.peak_balance > 0 else 0

        # Max drawdown
        max_dd = 0.0
        peak = self.initial_balance
        for equity_point in self.equity_curve:
            balance = equity_point['balance']
            if balance > peak:
                peak = balance
            dd = peak - balance
            if dd > max_dd:
                max_dd = dd

        max_drawdown_pct = (max_dd / self.initial_balance * 100) if self.initial_balance > 0 else 0

        # Sharpe ratio (simplified - assuming daily returns)
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                prev_balance = self.equity_curve[i-1]['balance']
                curr_balance = self.equity_curve[i]['balance']
                ret = (curr_balance - prev_balance) / prev_balance
                returns.append(ret)

            if returns:
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                sharpe_ratio = (avg_return / std_return * np.sqrt(365)) if std_return > 0 else 0.0
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        # Average trade duration
        durations = [t.duration_minutes for t in self.trades if t.duration_minutes]
        avg_duration = np.mean(durations) if durations else 0.0

        snapshot = PerformanceSnapshot(
            timestamp=datetime.now(),
            total_trades=total_trades,
            winning_trades=num_winning,
            losing_trades=num_losing,
            win_rate=win_rate * 100,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown_pct,
            current_drawdown=current_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            avg_trade_duration_minutes=avg_duration,
            active_positions=len(self.active_positions)
        )

        self.last_snapshot = snapshot
        return snapshot

    def check_risk_limits(self):
        """Check if risk limits have been breached"""
        current_dd = self.peak_balance - self.current_balance

        # Check daily loss limit
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_trades = [t for t in self.trades if t.exit_time >= today_start]
        today_pnl = sum(t.pnl for t in today_trades)

        if today_pnl < -self.max_daily_loss:
            alert = {
                'timestamp': datetime.now(),
                'type': 'DAILY_LOSS_LIMIT',
                'severity': 'CRITICAL',
                'message': f'Daily loss limit exceeded: ${today_pnl:,.2f} / ${-self.max_daily_loss:,.2f}',
                'action': 'Stop trading for today'
            }
            self.alerts.append(alert)
            logger.critical(f"⛔ {alert['message']}")

        # Check max drawdown limit
        if current_dd > self.max_drawdown_limit:
            alert = {
                'timestamp': datetime.now(),
                'type': 'MAX_DRAWDOWN',
                'severity': 'CRITICAL',
                'message': f'Max drawdown exceeded: ${current_dd:,.2f} / ${self.max_drawdown_limit:,.2f}',
                'action': 'Close all positions and pause trading'
            }
            self.alerts.append(alert)
            logger.critical(f"⛔ {alert['message']}")

        # Warning levels (80% of limits)
        if today_pnl < -self.max_daily_loss * 0.8:
            logger.warning(f"⚠️  Approaching daily loss limit: ${today_pnl:,.2f}")

        if current_dd > self.max_drawdown_limit * 0.8:
            logger.warning(f"⚠️  Approaching max drawdown: ${current_dd:,.2f}")

    def print_performance_report(self):
        """Print comprehensive performance report"""
        snapshot = self.calculate_metrics()

        uptime = datetime.now() - self.start_time
        uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}m"

        print("\n" + "=" * 70)
        print("📊 TRADING PERFORMANCE REPORT")
        print("=" * 70)
        print(f"Report Time: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Uptime: {uptime_str}")
        print("-" * 70)

        # Account metrics
        pnl_pct = ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
        print(f"Initial Balance:  ${self.initial_balance:12,.2f}")
        print(f"Current Balance:  ${self.current_balance:12,.2f}")
        print(f"Total P&L:        ${snapshot.total_pnl:+12,.2f} ({pnl_pct:+.2f}%)")
        print(f"Peak Balance:     ${self.peak_balance:12,.2f}")
        print("-" * 70)

        # Trading metrics
        print(f"Total Trades:     {snapshot.total_trades:12,d}")
        print(f"Winning Trades:   {snapshot.winning_trades:12,d}")
        print(f"Losing Trades:    {snapshot.losing_trades:12,d}")
        print(f"Win Rate:         {snapshot.win_rate:12.2f}%")
        print(f"Active Positions: {snapshot.active_positions:12,d}")
        print("-" * 70)

        # Performance metrics
        print(f"Average Win:      ${snapshot.avg_win:12,.2f}")
        print(f"Average Loss:     ${snapshot.avg_loss:12,.2f}")
        print(f"Profit Factor:    {snapshot.profit_factor:12.2f}")
        print(f"Sharpe Ratio:     {snapshot.sharpe_ratio:12.2f}")
        print("-" * 70)

        # Risk metrics
        print(f"Max Drawdown:     {snapshot.max_drawdown:12.2f}%")
        print(f"Current Drawdown: {snapshot.current_drawdown:12.2f}%")
        print(f"Avg Trade Duration: {snapshot.avg_trade_duration_minutes:10.1f} min")
        print("-" * 70)

        # Recent trades
        if self.trades:
            print("\n📈 RECENT TRADES (Last 5):")
            print("-" * 70)
            for trade in self.trades[-5:]:
                status = "✅" if trade.pnl > 0 else "❌"
                print(f"{status} {trade.symbol:10s} | {trade.side:5s} | "
                      f"P&L: ${trade.pnl:+8,.2f} ({trade.pnl_pct:+6.2f}%) | "
                      f"{trade.duration_minutes:4d}min | {trade.reason}")

        # Active positions
        if self.active_positions:
            print("\n📊 ACTIVE POSITIONS:")
            print("-" * 70)
            for trade in self.active_positions.values():
                print(f"🔄 {trade.symbol:10s} | {trade.side:5s} | "
                      f"Entry: ${trade.entry_price:,.2f} | "
                      f"Qty: {trade.quantity:.4f} | "
                      f"Duration: {int((datetime.now() - trade.entry_time).total_seconds() / 60)}min")

        # Alerts
        if self.alerts:
            print("\n⚠️  ALERTS:")
            print("-" * 70)
            for alert in self.alerts[-5:]:
                print(f"[{alert['severity']}] {alert['type']}: {alert['message']}")

        print("=" * 70 + "\n")

    def save_performance_data(self):
        """Save performance data to disk"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save trades
        if self.trades:
            trades_df = pd.DataFrame([asdict(t) for t in self.trades])
            trades_path = self.data_dir / f"trades_{timestamp}.csv"
            trades_df.to_csv(trades_path, index=False)
            logger.info(f"Trades saved to {trades_path}")

        # Save equity curve
        if self.equity_curve:
            equity_df = pd.DataFrame(self.equity_curve)
            equity_path = self.data_dir / f"equity_curve_{timestamp}.csv"
            equity_df.to_csv(equity_path, index=False)
            logger.info(f"Equity curve saved to {equity_path}")

        # Save snapshot
        if self.last_snapshot:
            snapshot_dict = asdict(self.last_snapshot)
            snapshot_dict['timestamp'] = str(snapshot_dict['timestamp'])
            snapshot_path = self.data_dir / f"snapshot_{timestamp}.json"
            with open(snapshot_path, 'w') as f:
                json.dump(snapshot_dict, f, indent=2)
            logger.info(f"Performance snapshot saved to {snapshot_path}")


async def monitor_loop():
    """Example monitoring loop"""
    monitor = PerformanceMonitor(initial_balance=10000.0)

    # Simulate some trades for demonstration
    trade1 = monitor.record_trade_entry("TRADE001", "BTCUSDT", 45000.0, 0.1, "LONG")
    await asyncio.sleep(1)
    monitor.record_trade_exit("TRADE001", 45500.0, "take_profit")  # +$50 profit

    trade2 = monitor.record_trade_entry("TRADE002", "ETHUSDT", 3000.0, 1.0, "LONG")
    await asyncio.sleep(1)
    monitor.record_trade_exit("TRADE002", 2950.0, "stop_loss")  # -$50 loss

    # Print report
    monitor.print_performance_report()

    # Save data
    monitor.save_performance_data()


if __name__ == "__main__":
    asyncio.run(monitor_loop())
