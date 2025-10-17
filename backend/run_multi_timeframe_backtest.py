"""
Multi-timeframe backtesting for Two-Way strategy validation
Tests strategy robustness across different time periods to prevent overfitting

Validation Framework:
- 1 month (40% weight): Recent market adaptation
- 3 months (30% weight): Quarterly stability
- 6 months (20% weight): Extended robustness
- 1 year (10% weight): Full cycle validation
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


async def run_timeframe_backtest(months: int, weight: float):
    """Run backtest for specific timeframe

    Args:
        months: Number of months to backtest
        weight: Weight for composite score calculation

    Returns:
        dict: Backtest results with metrics
    """
    end_date = datetime(2025, 10, 16)
    start_date = end_date - timedelta(days=months * 30)

    logger.info("\n" + "="*80)
    logger.info(f"📅 BACKTEST: {months} MONTH{'S' if months > 1 else ''} ({start_date.date()} to {end_date.date()})")
    logger.info(f"⚖️  Weight: {weight*100:.0f}%")
    logger.info("="*80)

    # All 10 coins
    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
        'DOGE/USDT', 'XPL/USDT', 'SUI/USDT', '1000PEPE/USDT', 'HYPE/USDT'
    ]

    # Initialize backtester
    backtester = Backtester(
        initial_balance=10000.0,
        leverage=10,
        symbols=symbols
    )

    # Run backtest
    try:
        results = await backtester.run_backtest(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            interval='1h'
        )

        # Extract key metrics
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

        # Calculate XPL dominance
        xpl_trades = coin_stats.get('XPL/USDT', 0)
        xpl_pct = (xpl_trades / total_trades * 100) if total_trades > 0 else 0

        # Count active coins
        active_coins = len([s for s in symbols if coin_stats.get(s, 0) > 0])

        logger.info(f"\n📊 Results:")
        logger.info(f"  Total Return: {total_return:.2f}%")
        logger.info(f"  Win Rate: {win_rate:.2f}%")
        logger.info(f"  Total Trades: {total_trades}")
        logger.info(f"  Profit Factor: {profit_factor:.2f}")
        logger.info(f"  Max Drawdown: {max_drawdown:.2f}%")
        logger.info(f"  Sharpe Ratio: {sharpe:.2f}")
        logger.info(f"  Active Coins: {active_coins}/10")
        logger.info(f"  XPL Dominance: {xpl_pct:.1f}%")

        return {
            'months': months,
            'weight': weight,
            'total_return': total_return,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'active_coins': active_coins,
            'xpl_dominance': xpl_pct,
            'coin_stats': coin_stats
        }

    except Exception as e:
        logger.error(f"❌ Backtest failed for {months} months: {e}", exc_info=True)
        return None


async def run_multi_timeframe_validation():
    """Run comprehensive multi-timeframe validation"""

    logger.info("\n" + "="*80)
    logger.info("🧪 MULTI-TIMEFRAME VALIDATION - v4.0 PARAMETERS")
    logger.info("="*80)
    logger.info("\nValidation Framework:")
    logger.info("  📅 1 month  (40% weight) - Recent market adaptation")
    logger.info("  📅 3 months (30% weight) - Quarterly stability")
    logger.info("  📅 6 months (20% weight) - Extended robustness")
    logger.info("  📅 1 year   (10% weight) - Full cycle validation")
    logger.info("")

    # Define timeframes
    timeframes = [
        {'months': 1, 'weight': 0.40},
        {'months': 3, 'weight': 0.30},
        {'months': 6, 'weight': 0.20},
        {'months': 12, 'weight': 0.10}
    ]

    results = []

    # Run each timeframe
    for tf in timeframes:
        result = await run_timeframe_backtest(tf['months'], tf['weight'])
        if result:
            results.append(result)

    if not results:
        logger.error("❌ No successful backtests completed")
        return None

    # Calculate weighted composite score
    logger.info("\n" + "="*80)
    logger.info("📊 WEIGHTED COMPOSITE ANALYSIS")
    logger.info("="*80)

    weighted_return = sum(r['total_return'] * r['weight'] for r in results)
    weighted_win_rate = sum(r['win_rate'] * r['weight'] for r in results)
    weighted_profit_factor = sum(r['profit_factor'] * r['weight'] for r in results)
    weighted_sharpe = sum(r['sharpe_ratio'] * r['weight'] for r in results)
    avg_max_drawdown = sum(r['max_drawdown'] for r in results) / len(results)
    total_trades_all = sum(r['total_trades'] for r in results)

    logger.info(f"\n💰 Weighted Composite Metrics:")
    logger.info(f"  Return: {weighted_return:.2f}%")
    logger.info(f"  Win Rate: {weighted_win_rate:.2f}%")
    logger.info(f"  Profit Factor: {weighted_profit_factor:.2f}")
    logger.info(f"  Sharpe Ratio: {weighted_sharpe:.2f}")
    logger.info(f"  Avg Max Drawdown: {avg_max_drawdown:.2f}%")
    logger.info(f"  Total Trades (all periods): {total_trades_all}")

    # Consistency analysis
    logger.info(f"\n📈 Consistency Analysis:")
    profitable_periods = sum(1 for r in results if r['total_return'] > 0)
    logger.info(f"  Profitable Periods: {profitable_periods}/{len(results)} ({profitable_periods/len(results)*100:.0f}%)")

    all_coins_active = all(r['active_coins'] == 10 for r in results)
    logger.info(f"  All Coins Active: {'✅ Yes' if all_coins_active else '❌ No'}")

    xpl_balanced = all(r['xpl_dominance'] < 40 for r in results)
    logger.info(f"  XPL Balanced (<40%): {'✅ Yes' if xpl_balanced else '❌ No'}")

    # Validation criteria
    logger.info(f"\n🧪 Validation Criteria:")

    checks = {
        'Weighted Return > 0%': weighted_return > 0,
        'Weighted Win Rate > 30%': weighted_win_rate > 30,
        'Weighted Profit Factor > 1.0': weighted_profit_factor > 1.0,
        'All Periods Profitable': profitable_periods == len(results),
        'All Coins Active (all periods)': all_coins_active,
        'XPL Balanced (all periods)': xpl_balanced,
        'Avg Drawdown < 20%': avg_max_drawdown < 20
    }

    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        logger.info(f"  {status} {check}")

    # Overall assessment
    passed_checks = sum(1 for v in checks.values() if v)
    total_checks = len(checks)

    logger.info("\n" + "="*80)

    if passed_checks >= 6:
        logger.info(f"🎉 VALIDATION PASSED ({passed_checks}/{total_checks} checks)")
        logger.info("Strategy shows robust performance across multiple timeframes!")
        logger.info("✅ Ready for production deployment consideration")
    elif passed_checks >= 4:
        logger.info(f"⚠️  PARTIAL VALIDATION ({passed_checks}/{total_checks} checks)")
        logger.info("Strategy shows promise but needs further tuning")
        logger.info("🔧 Recommend parameter refinement before production")
    else:
        logger.info(f"❌ VALIDATION FAILED ({passed_checks}/{total_checks} checks)")
        logger.info("Strategy needs significant improvements")
        logger.info("🔄 Recommend revisiting parameters and strategy logic")

    logger.info("="*80 + "\n")

    # Detailed per-timeframe breakdown
    logger.info("="*80)
    logger.info("📋 DETAILED TIMEFRAME BREAKDOWN")
    logger.info("="*80)

    for r in results:
        logger.info(f"\n{r['months']} Month{'s' if r['months'] > 1 else ''} (Weight: {r['weight']*100:.0f}%):")
        logger.info(f"  Return: {r['total_return']:.2f}%, Win Rate: {r['win_rate']:.2f}%, Trades: {r['total_trades']}")
        logger.info(f"  Profit Factor: {r['profit_factor']:.2f}, Sharpe: {r['sharpe_ratio']:.2f}, Drawdown: {r['max_drawdown']:.2f}%")
        logger.info(f"  Active Coins: {r['active_coins']}/10, XPL: {r['xpl_dominance']:.1f}%")

    logger.info("\n" + "="*80 + "\n")

    return {
        'weighted_metrics': {
            'return': weighted_return,
            'win_rate': weighted_win_rate,
            'profit_factor': weighted_profit_factor,
            'sharpe_ratio': weighted_sharpe,
            'avg_drawdown': avg_max_drawdown
        },
        'timeframe_results': results,
        'validation_checks': checks,
        'passed_checks': passed_checks,
        'total_checks': total_checks
    }


if __name__ == "__main__":
    asyncio.run(run_multi_timeframe_validation())
