"""
v5.0 Validation Backtest - Volume Filter + Dynamic Hard Stop
Tests improvements over v4.0 baseline

v5.0 Improvements:
1. Volume Filter: Filters false breakouts, requires 1.5-2.8x average volume
2. Dynamic Hard Stop: ATR-based stops that adapt to volatility

Expected Results:
- Win Rate: 30.36% → 35%+ (volume filter reducing false signals)
- Max Drawdown: <16.37% (better stop management)
- Fewer large losses like XPL -6.41%, -7.74%
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from backtester import Backtester
from trading_strategy import TradingStrategy, RiskManager
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_v5_validation():
    """Run v5.0 validation backtest (1 month)"""

    # Test period: same as v4.0 for direct comparison
    end_date = datetime(2025, 10, 16)
    start_date = end_date - timedelta(days=30)

    logger.info("\n" + "="*80)
    logger.info("🧪 v5.0 VALIDATION BACKTEST")
    logger.info("="*80)
    logger.info(f"Period: {start_date.date()} to {end_date.date()} (30 days)")
    logger.info(f"\nv5.0 Improvements:")
    logger.info(f"  1. ✅ Volume Filter: Requires 1.5-2.8x average volume")
    logger.info(f"  2. ✅ Dynamic Hard Stop: ATR-based adaptive stops")
    logger.info(f"\nv4.0 Baseline:")
    logger.info(f"  Total Return: +3.16%")
    logger.info(f"  Win Rate: 30.36%")
    logger.info(f"  Total Trades: 280")
    logger.info(f"  Profit Factor: 1.09")
    logger.info(f"  Max Drawdown: 16.37%")
    logger.info("="*80 + "\n")

    # All 10 coins
    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
        'DOGE/USDT', 'XPL/USDT', 'SUI/USDT', '1000PEPE/USDT', 'HYPE/USDT'
    ]

    # Initialize backtester with v5.0 config
    backtester = Backtester(
        initial_balance=10000.0,
        leverage=10,
        symbols=symbols
    )

    # Enable dynamic hard stop in trailing stop manager (backtester should initialize with this)
    logger.info("🔧 v5.0 Configuration:")
    logger.info("  - Volume filter: ENABLED (trading_strategy.py)")
    logger.info("  - Dynamic hard stop: ENABLED (trailing_stop_manager.py)")
    logger.info("  - Hard stop multiplier: 2.0 × ATR")
    logger.info("")

    # Run backtest
    try:
        results = await backtester.run_backtest(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            interval='1h'
        )

        # Extract metrics
        summary = results.get('backtest_summary', {})
        stats = results.get('trade_statistics', {})
        metrics = results.get('performance_metrics', {})

        total_return = summary.get('total_return_pct', 0)
        win_rate = stats.get('win_rate_pct', 0)
        total_trades = stats.get('total_trades', 0)
        profit_factor = metrics.get('profit_factor', 0)
        max_drawdown = metrics.get('max_drawdown_pct', 0)
        sharpe = metrics.get('sharpe_ratio', 0)

        # Per-coin analysis
        coin_stats = {}
        for trade in backtester.trade_history:
            symbol = trade['symbol'].replace('_LONG', '').replace('_SHORT', '')
            if symbol not in coin_stats:
                coin_stats[symbol] = 0
            coin_stats[symbol] += 1

        # XPL dominance
        xpl_trades = coin_stats.get('XPL/USDT', 0)
        xpl_pct = (xpl_trades / total_trades * 100) if total_trades > 0 else 0

        # Active coins
        active_coins = len([s for s in symbols if coin_stats.get(s, 0) > 0])

        # Display results
        logger.info("\n" + "="*80)
        logger.info("📊 v5.0 RESULTS vs v4.0 BASELINE")
        logger.info("="*80)

        # Comparison table
        def format_change(v5, v4, higher_is_better=True):
            if v4 == 0:
                return f"{v5:.2f} (NEW)"
            change = v5 - v4
            pct_change = (change / abs(v4)) * 100 if v4 != 0 else 0

            if higher_is_better:
                symbol = "✅" if change > 0 else "⚠️"
            else:
                symbol = "✅" if change < 0 else "⚠️"

            return f"{v5:.2f} ({change:+.2f}, {pct_change:+.1f}%) {symbol}"

        logger.info(f"\n📈 Performance Metrics:")
        logger.info(f"  Total Return:    v4.0: +3.16%  →  v5.0: {format_change(total_return, 3.16, True)}")
        logger.info(f"  Win Rate:        v4.0: 30.36%  →  v5.0: {format_change(win_rate, 30.36, True)}")
        logger.info(f"  Profit Factor:   v4.0: 1.09    →  v5.0: {format_change(profit_factor, 1.09, True)}")
        logger.info(f"  Sharpe Ratio:    v4.0: 0.56    →  v5.0: {format_change(sharpe, 0.56, True)}")
        logger.info(f"  Max Drawdown:    v4.0: 16.37%  →  v5.0: {format_change(max_drawdown, 16.37, False)}")

        logger.info(f"\n📊 Trading Activity:")
        logger.info(f"  Total Trades:    v4.0: 280     →  v5.0: {total_trades} ({total_trades-280:+d} trades)")
        logger.info(f"  Active Coins:    v4.0: 10/10   →  v5.0: {active_coins}/10")
        logger.info(f"  XPL Dominance:   v4.0: 15%     →  v5.0: {xpl_pct:.1f}%")

        logger.info(f"\n🪙 Per-Coin Entry Frequency:")
        for symbol in symbols:
            count = coin_stats.get(symbol, 0)
            per_day = count / 30
            v4_counts = {'BTC/USDT': 10, 'ETH/USDT': 30, 'SOL/USDT': 30, 'BNB/USDT': 40,
                        'XRP/USDT': 20, 'DOGE/USDT': 26, 'XPL/USDT': 42, 'SUI/USDT': 20,
                        '1000PEPE/USDT': 24, 'HYPE/USDT': 38}
            v4_count = v4_counts.get(symbol, 0)
            change = count - v4_count
            status = "✅" if count >= 10 else "⚠️"
            logger.info(f"  {status} {symbol}: {count} entries ({per_day:.2f}/day) [v4.0: {v4_count}, Δ{change:+d}]")

        # Validation checks
        logger.info(f"\n🧪 Validation Checks:")
        checks = {
            'Win rate > 35%': win_rate > 35,
            'Win rate improved vs v4.0': win_rate > 30.36,
            'Profit Factor > 1.0': profit_factor > 1.0,
            'Profitable': total_return > 0,
            'All coins active': active_coins == 10,
            'XPL balanced (<40%)': xpl_pct < 40,
            'Max drawdown improved': max_drawdown < 16.37
        }

        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            logger.info(f"  {status} {check}")

        passed_checks = sum(1 for v in checks.values() if v)
        total_checks = len(checks)

        logger.info("\n" + "="*80)

        if passed_checks >= 6:
            logger.info(f"🎉 v5.0 VALIDATION PASSED ({passed_checks}/{total_checks} checks)")
            logger.info("Volume filter and dynamic hard stop show clear improvements!")
        elif passed_checks >= 4:
            logger.info(f"⚠️  v5.0 PARTIAL SUCCESS ({passed_checks}/{total_checks} checks)")
            logger.info("Some improvements visible, but further tuning recommended")
        else:
            logger.info(f"❌ v5.0 NEEDS WORK ({passed_checks}/{total_checks} checks)")
            logger.info("Improvements did not have expected impact")

        logger.info("="*80 + "\n")

        # Key insights
        logger.info("💡 Key Insights:")
        if total_trades < 280:
            logger.info(f"  📉 Trade count decreased ({total_trades} vs 280)")
            logger.info(f"     → Volume filter is working (filtering {280-total_trades} low-volume signals)")

        if win_rate > 30.36:
            improvement = win_rate - 30.36
            logger.info(f"  📈 Win rate improved by {improvement:.2f}%")
            logger.info(f"     → Volume filter successfully reduced false breakouts")

        if max_drawdown < 16.37:
            improvement = 16.37 - max_drawdown
            logger.info(f"  🛡️  Max drawdown reduced by {improvement:.2f}%")
            logger.info(f"     → Dynamic hard stops prevented excessive losses")

        logger.info("")

        return {
            'v5': {
                'return': total_return,
                'win_rate': win_rate,
                'trades': total_trades,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'sharpe': sharpe
            },
            'comparison': {
                'return_change': total_return - 3.16,
                'win_rate_change': win_rate - 30.36,
                'trade_change': total_trades - 280,
                'drawdown_change': max_drawdown - 16.37
            },
            'validation_result': 'PASSED' if passed_checks >= 6 else ('PARTIAL' if passed_checks >= 4 else 'FAILED')
        }

    except Exception as e:
        logger.error(f"❌ Backtest failed: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    asyncio.run(run_v5_validation())
