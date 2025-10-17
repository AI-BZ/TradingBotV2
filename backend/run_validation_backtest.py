"""
Validation backtest for coin-specific parameter system
Tests that:
1. Coin-specific parameters are correctly loaded and applied
2. Position closing bug is fixed (trades are now recorded)
3. Entry frequency increased (target: 1-2 entries per day per coin)
4. All 10 coins generate Two-Way entry signals (not just XPL/SUI)
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from backtester import Backtester
from trading_strategy import TradingStrategy, RiskManager
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_validation_backtest():
    """Run validation backtest with coin-specific parameters"""

    logger.info("\n" + "="*80)
    logger.info("🧪 VALIDATION BACKTEST - COIN-SPECIFIC PARAMETERS")
    logger.info("="*80)

    # Test period: 30 days (2025-09-16 to 2025-10-16)
    end_date = datetime(2025, 10, 16)
    start_date = end_date - timedelta(days=30)

    logger.info(f"📅 Test Period: {start_date.date()} to {end_date.date()} (30 days)")
    logger.info(f"💰 Initial Balance: $10,000")
    logger.info(f"🎯 Target: 1-2 entries per day per coin (30-60 total per coin)")
    logger.info("")

    # All 10 coins
    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
        'DOGE/USDT', 'XPL/USDT', 'SUI/USDT', '1000PEPE/USDT', 'HYPE/USDT'
    ]

    # Initialize backtester (it creates strategy and risk_manager internally)
    backtester = Backtester(
        initial_balance=10000.0,
        leverage=10,
        symbols=symbols
    )

    # Access strategy for parameter info
    strategy = backtester.strategy

    logger.info("🪙 Testing coins:")
    for symbol in symbols:
        params = strategy.get_coin_parameters(symbol)
        logger.info(f"  • {symbol}: Tier={params.get('tier', 'N/A')}, "
                   f"BB={params.get('bb_compression', 0)*100:.1f}%, "
                   f"ATR={params.get('atr_expansion', 0)*100:.1f}%, "
                   f"Stop={params.get('hard_stop', 0)*100:.1f}%")

    logger.info("\n🔄 Starting backtest...")

    # Run backtest
    try:
        results = await backtester.run_backtest(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            interval='1h'
        )

        logger.info("\n" + "="*80)
        logger.info("✅ VALIDATION RESULTS")
        logger.info("="*80)

        # Overall metrics
        # Extract metrics from nested structure
        summary = results.get('backtest_summary', {})
        stats = results.get('trade_statistics', {})
        metrics = results.get('performance_metrics', {})

        logger.info(f"\n📊 Overall Performance:")
        logger.info(f"  Total Return: {summary.get('total_return_pct', 0):.2f}%")
        logger.info(f"  Win Rate: {stats.get('win_rate_pct', 0):.2f}%")
        logger.info(f"  Total Trades: {stats.get('total_trades', 0)}")
        logger.info(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        logger.info(f"  Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        logger.info(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")

        # Per-coin analysis
        logger.info(f"\n🪙 Per-Coin Entry Frequency:")
        coin_stats = {}

        for trade in backtester.trade_history:
            symbol = trade['symbol'].replace('_LONG', '').replace('_SHORT', '')
            if symbol not in coin_stats:
                coin_stats[symbol] = 0
            coin_stats[symbol] += 1

        all_coins_traded = True
        for symbol in symbols:
            count = coin_stats.get(symbol, 0)
            entries_per_day = count / 30
            status = "✅" if entries_per_day >= 1.0 else "⚠️"

            logger.info(f"  {status} {symbol}: {count} entries ({entries_per_day:.2f}/day)")

            if count == 0:
                all_coins_traded = False

        # Validation checks
        logger.info(f"\n🧪 Validation Checks:")

        total_trades = stats.get('total_trades', 0)
        total_return_pct = summary.get('total_return_pct', 0)

        # Check 1: Trades were recorded
        if total_trades > 0:
            logger.info(f"  ✅ Position closing works: {total_trades} trades recorded")
        else:
            logger.info(f"  ❌ Position closing failed: No trades recorded")

        # Check 2: All coins traded
        if all_coins_traded:
            logger.info(f"  ✅ All 10 coins generated entries")
        else:
            logger.info(f"  ⚠️  Only {len(coin_stats)} / 10 coins traded")

        # Check 3: Entry frequency improved
        avg_per_coin = total_trades / len(symbols) if symbols else 0
        avg_per_day_per_coin = avg_per_coin / 30

        if avg_per_day_per_coin >= 1.0:
            logger.info(f"  ✅ Entry frequency target met: {avg_per_day_per_coin:.2f} entries/day/coin")
        else:
            logger.info(f"  ⚠️  Entry frequency below target: {avg_per_day_per_coin:.2f} entries/day/coin")

        # Check 4: Strategy profitability
        if total_return_pct > 0:
            logger.info(f"  ✅ Strategy profitable: {total_return_pct:.2f}% return")
        else:
            logger.info(f"  ⚠️  Strategy unprofitable: {total_return_pct:.2f}% return")

        logger.info("\n" + "="*80)

        # Determine next steps
        if total_trades > 0 and total_return_pct > 0:
            logger.info("🎉 VALIDATION PASSED - Ready for multi-timeframe backtesting!")
        elif total_trades > 0:
            logger.info("⚠️  PARTIAL SUCCESS - Positions closing works, but strategy needs tuning")
        else:
            logger.info("❌ VALIDATION FAILED - Position closing still broken")

        logger.info("="*80 + "\n")

        return results

    except Exception as e:
        logger.error(f"❌ Backtest failed: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    asyncio.run(run_validation_backtest())
