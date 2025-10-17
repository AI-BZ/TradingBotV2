"""
v5.0 Multi-Timeframe Validation - Dynamic Hard Stop Robustness Test
Tests v5.0 across 1m, 3m, 6m, 12m to validate dynamic stops prevent overfitting

v5.0 Changes:
- Dynamic Hard Stop: ATR-based adaptive stops (max(1%, ATR% × 2.0))
- Volume Filter: Disabled (avg_volume not implemented yet)

Expected vs v4.0:
- More stable performance across timeframes
- 3-month test should show improvement over v4.0's -5.3%
- Dynamic stops should reduce overfitting to recent conditions
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from backtester import Backtester
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_timeframe_test(months: int, weight: float):
    """Run backtest for specific timeframe"""

    end_date = datetime(2025, 10, 16)
    start_date = end_date - timedelta(days=months * 30)

    logger.info(f"\n{'='*80}")
    logger.info(f"📅 TIMEFRAME: {months} month{'s' if months > 1 else ''}")
    logger.info(f"Period: {start_date.date()} to {end_date.date()}")
    logger.info(f"Weight: {weight:.0%}")
    logger.info(f"{'='*80}\n")

    # All 10 coins
    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
        'DOGE/USDT', 'XPL/USDT', 'SUI/USDT', '1000PEPE/USDT', 'HYPE/USDT'
    ]

    # Initialize backtester with v5.0 config (dynamic hard stop enabled)
    backtester = Backtester(
        initial_balance=10000.0,
        leverage=10,
        symbols=symbols
    )

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

        active_coins = len([s for s in symbols if coin_stats.get(s, 0) > 0])

        # Display results
        logger.info(f"\n📊 {months}-Month Results:")
        logger.info(f"  Total Return:    {total_return:+.2f}%")
        logger.info(f"  Win Rate:        {win_rate:.2f}%")
        logger.info(f"  Total Trades:    {total_trades}")
        logger.info(f"  Profit Factor:   {profit_factor:.2f}")
        logger.info(f"  Sharpe Ratio:    {sharpe:.2f}")
        logger.info(f"  Max Drawdown:    {max_drawdown:.2f}%")
        logger.info(f"  Active Coins:    {active_coins}/10")

        return {
            'months': months,
            'weight': weight,
            'total_return': total_return,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe': sharpe,
            'active_coins': active_coins,
            'coin_stats': coin_stats
        }

    except Exception as e:
        logger.error(f"❌ {months}-month backtest failed: {e}", exc_info=True)
        return None


async def run_v5_multi_timeframe_validation():
    """Run comprehensive v5.0 multi-timeframe validation"""

    logger.info("\n" + "="*80)
    logger.info("🧪 v5.0 MULTI-TIMEFRAME VALIDATION")
    logger.info("="*80)
    logger.info("Testing Dynamic Hard Stop robustness across 1m, 3m, 6m, 12m")
    logger.info("\nv5.0 Configuration:")
    logger.info("  ✅ Dynamic Hard Stop: ENABLED (ATR × 2.0)")
    logger.info("  ❌ Volume Filter: DISABLED (avg_volume not implemented)")
    logger.info("\nv4.0 Baseline for Comparison:")
    logger.info("  1-month: +3.16%")
    logger.info("  3-month: -5.3% (60% complete, showing overfitting)")
    logger.info("="*80 + "\n")

    # Define timeframes with weights
    timeframes = [
        {'months': 1, 'weight': 0.40},   # 40% - Recent adaptation
        {'months': 3, 'weight': 0.30},   # 30% - Quarterly stability
        {'months': 6, 'weight': 0.20},   # 20% - Extended robustness
        {'months': 12, 'weight': 0.10}   # 10% - Full cycle validation
    ]

    # Run all timeframe tests
    results = []
    for tf in timeframes:
        result = await run_timeframe_test(tf['months'], tf['weight'])
        if result:
            results.append(result)

    if not results:
        logger.error("❌ All timeframe tests failed")
        return None

    # Calculate weighted metrics
    weighted_return = sum(r['total_return'] * r['weight'] for r in results)
    weighted_win_rate = sum(r['win_rate'] * r['weight'] for r in results)
    weighted_profit_factor = sum(r['profit_factor'] * r['weight'] for r in results)
    weighted_sharpe = sum(r['sharpe'] * r['weight'] for r in results)

    # Display summary
    logger.info("\n" + "="*80)
    logger.info("📊 v5.0 MULTI-TIMEFRAME SUMMARY")
    logger.info("="*80)

    logger.info("\n⏱️  Individual Timeframe Results:")
    for r in results:
        logger.info(f"\n  {r['months']}-Month (Weight: {r['weight']:.0%}):")
        logger.info(f"    Return:        {r['total_return']:+.2f}%")
        logger.info(f"    Win Rate:      {r['win_rate']:.2f}%")
        logger.info(f"    Trades:        {r['total_trades']}")
        logger.info(f"    Profit Factor: {r['profit_factor']:.2f}")
        logger.info(f"    Sharpe:        {r['sharpe']:.2f}")
        logger.info(f"    Max DD:        {r['max_drawdown']:.2f}%")

    logger.info(f"\n🎯 Weighted Composite Metrics:")
    logger.info(f"  Weighted Return:        {weighted_return:+.2f}%")
    logger.info(f"  Weighted Win Rate:      {weighted_win_rate:.2f}%")
    logger.info(f"  Weighted Profit Factor: {weighted_profit_factor:.2f}")
    logger.info(f"  Weighted Sharpe:        {weighted_sharpe:.2f}")

    # Compare with v4.0
    logger.info("\n📈 Comparison with v4.0:")
    logger.info("  Timeframe | v4.0 Result | v5.0 Result | Change")
    logger.info("  ----------|-------------|-------------|-------")

    v4_results = {
        1: 3.16,
        3: -5.3  # 60% complete estimate
    }

    for r in results:
        if r['months'] in v4_results:
            v4_val = v4_results[r['months']]
            v5_val = r['total_return']
            change = v5_val - v4_val
            status = "✅" if change > 0 else "❌"
            logger.info(f"  {r['months']}-month   | {v4_val:+6.2f}%    | {v5_val:+6.2f}%    | {change:+.2f}% {status}")
        else:
            logger.info(f"  {r['months']}-month   | N/A         | {r['total_return']:+6.2f}%    | NEW")

    # Validation checks
    logger.info("\n🧪 v5.0 Multi-Timeframe Validation:")

    checks = {
        'Weighted return positive': weighted_return > 0,
        'Weighted win rate > 35%': weighted_win_rate > 35,
        'Weighted profit factor > 1.0': weighted_profit_factor > 1.0,
        '1-month profitable': results[0]['total_return'] > 0 if len(results) > 0 else False,
        '3-month improved vs v4.0': results[1]['total_return'] > -5.3 if len(results) > 1 else False,
        'All timeframes have trades': all(r['total_trades'] > 0 for r in results),
        'Reduced overfitting': len([r for r in results if r['total_return'] > 0]) >= len(results) * 0.5
    }

    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        logger.info(f"  {status} {check}")

    passed_checks = sum(1 for v in checks.values() if v)
    total_checks = len(checks)

    logger.info("\n" + "="*80)

    if passed_checks >= 6:
        logger.info(f"🎉 v5.0 MULTI-TIMEFRAME VALIDATION PASSED ({passed_checks}/{total_checks})")
        logger.info("Dynamic hard stops successfully improve strategy robustness!")
    elif passed_checks >= 4:
        logger.info(f"⚠️  v5.0 PARTIAL SUCCESS ({passed_checks}/{total_checks})")
        logger.info("Some improvements visible, further analysis needed")
    else:
        logger.info(f"❌ v5.0 NEEDS IMPROVEMENT ({passed_checks}/{total_checks})")
        logger.info("Dynamic hard stops did not sufficiently address overfitting")

    logger.info("="*80 + "\n")

    # Key insights
    logger.info("💡 Key Insights:")

    # Check 3-month improvement
    if len(results) > 1 and results[1]['total_return'] > -5.3:
        improvement = results[1]['total_return'] - (-5.3)
        logger.info(f"  📈 3-month improved by {improvement:.2f}% vs v4.0")
        logger.info(f"     → Dynamic hard stops successfully reduce overfitting")
    elif len(results) > 1:
        degradation = abs(results[1]['total_return'] - (-5.3))
        logger.info(f"  📉 3-month degraded by {degradation:.2f}% vs v4.0")
        logger.info(f"     → Dynamic hard stops alone insufficient")

    # Check consistency across timeframes
    positive_timeframes = [r['months'] for r in results if r['total_return'] > 0]
    if len(positive_timeframes) >= 3:
        logger.info(f"  ✅ Consistent profitability across {len(positive_timeframes)}/{len(results)} timeframes")
        logger.info(f"     → Strategy shows robustness: {positive_timeframes}")
    else:
        logger.info(f"  ⚠️  Limited profitability: only {len(positive_timeframes)}/{len(results)} timeframes positive")
        logger.info(f"     → Further parameter tuning may be needed")

    # Win rate consistency
    win_rates = [r['win_rate'] for r in results]
    avg_win_rate = sum(win_rates) / len(win_rates)
    win_rate_std = (sum((wr - avg_win_rate)**2 for wr in win_rates) / len(win_rates))**0.5

    if win_rate_std < 5:
        logger.info(f"  🎯 Win rate very consistent: {avg_win_rate:.1f}% ± {win_rate_std:.1f}%")
        logger.info(f"     → Dynamic stops provide stable performance")
    elif win_rate_std < 10:
        logger.info(f"  📊 Win rate moderately consistent: {avg_win_rate:.1f}% ± {win_rate_std:.1f}%")
    else:
        logger.info(f"  ⚠️  Win rate highly variable: {avg_win_rate:.1f}% ± {win_rate_std:.1f}%")
        logger.info(f"     → Strategy sensitivity to market conditions")

    logger.info("")

    return {
        'timeframe_results': results,
        'weighted_return': weighted_return,
        'weighted_win_rate': weighted_win_rate,
        'weighted_profit_factor': weighted_profit_factor,
        'weighted_sharpe': weighted_sharpe,
        'validation_status': 'PASSED' if passed_checks >= 6 else ('PARTIAL' if passed_checks >= 4 else 'FAILED'),
        'passed_checks': passed_checks,
        'total_checks': total_checks
    }


if __name__ == "__main__":
    asyncio.run(run_v5_multi_timeframe_validation())
