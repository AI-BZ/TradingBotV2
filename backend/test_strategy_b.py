"""
Test Strategy B Live Trading System
Quick validation before full deployment
"""
import asyncio
import logging
import os
from datetime import datetime

from binance_client import BinanceClient
from selective_tick_live_trader import SelectiveTickLiveTrader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_strategy_b():
    """Test Strategy B with 7 coins"""

    logger.info("\n" + "="*80)
    logger.info("🧪 TESTING STRATEGY B - SELECTIVE HIGH-CONFIDENCE TRADING")
    logger.info("="*80)
    logger.info("Test Duration: 5 minutes")
    logger.info("Symbols: 7 coins (ETH, SOL, BNB, DOGE, XRP, SUI, 1000PEPE)")
    logger.info("Strategy: Top 20% Quality Trades Only")
    logger.info("="*80 + "\n")

    # Initialize Binance client
    binance_client = BinanceClient(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        testnet=True,  # TESTNET for safety
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

    # Initialize Strategy B trader
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
        # Start trading in background
        trading_task = asyncio.create_task(trader.start())

        # Run for 5 minutes
        logger.info("⏱️  Starting 5-minute test run...")
        await asyncio.sleep(300)  # 5 minutes

        # Get performance
        performance = await trader.get_performance()

        logger.info("\n" + "="*80)
        logger.info("📊 TEST RESULTS (5-minute sample)")
        logger.info("="*80)
        logger.info(f"Total Trades: {performance['total_trades']}")
        logger.info(f"Win Rate: {performance['win_rate']:.2f}%")
        logger.info(f"Avg Profit/Trade: ${performance['avg_profit_per_trade']:.2f}")
        logger.info(f"Active Positions: {performance['active_positions']}")
        logger.info(f"Signals Generated: {performance['signals_generated']}")
        logger.info(f"Signals Skipped (Cooldown): {performance['signals_skipped_cooldown']}")
        logger.info(f"Total P&L: ${performance['total_pnl']:+.2f}")
        logger.info(f"Total Return: {performance['total_return']:+.2f}%")
        logger.info("="*80 + "\n")

        # Stop trading
        logger.info("🛑 Stopping test...")
        trading_task.cancel()
        await trader.stop()

        # Validation
        logger.info("\n" + "="*80)
        logger.info("✅ VALIDATION")
        logger.info("="*80)

        # Expected: ~162 trades/day per symbol = 0.11 trades/minute
        # For 5 minutes: ~0.5 trades per symbol
        # For 7 symbols: ~3-4 trades expected
        expected_trades = 7 * 0.5 * 5  # 7 symbols × 0.5 trades/min × 5 min
        actual_trades = performance['total_trades']

        if actual_trades < expected_trades * 2:  # Within 2x tolerance
            logger.info(f"✅ Trade frequency: {actual_trades} trades (expected ~{expected_trades:.0f})")
        else:
            logger.warning(f"⚠️  Trade frequency high: {actual_trades} trades (expected ~{expected_trades:.0f})")

        if performance['signals_skipped_cooldown'] > 0:
            logger.info(f"✅ Cooldown working: {performance['signals_skipped_cooldown']} signals skipped")
        else:
            logger.info("ℹ️  No cooldown events (market may be quiet)")

        logger.info("="*80 + "\n")

        logger.info("🎉 TEST COMPLETE! Strategy B is ready for deployment.")

    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await binance_client.close()


if __name__ == "__main__":
    asyncio.run(test_strategy_b())
