"""
Debug tick signal generation to understand why no trades are generated
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from test_hybrid_volatility_fix import fetch_test_data
from tick_indicators import TickIndicators
from tick_backtester import TickBacktester

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Debug signal generation"""

    # Get test data (1 day)
    logger.info("Fetching test data...")
    ticks = await fetch_test_data('ETH/USDT', '2024-10-05', '2024-10-06')
    logger.info(f"Loaded {len(ticks):,} ticks")

    # Sample every 1000 ticks to check signals throughout the day
    indicators_obj = TickIndicators()
    signal_count = 0

    for i in range(1000, len(ticks), 1000):
        recent = ticks[max(0, i-1000):i]

        if len(recent) < 100:
            continue

        # Calculate indicators
        std_vol, atr_vol, hybrid_vol = indicators_obj.calculate_hybrid_volatility(recent, 600)
        indicators = indicators_obj.generate_tick_summary(recent, 600)

        current_price = ticks[i-1].price
        hybrid_pct = (hybrid_vol / current_price) * 100 if current_price > 0 else 0
        atr_pct = (atr_vol / current_price) * 100 if current_price > 0 else 0

        bb = indicators.get('bollinger_bands', {})
        bb_position = bb.get('position', 0.5)
        upper_bb = bb.get('upper', 0)
        middle_bb = bb.get('middle', 0)
        lower_bb = bb.get('lower', 0)

        # Check signal conditions (updated thresholds)
        vol_ok = hybrid_pct >= 0.04 and atr_pct >= 0.15
        bb_ok = 0.40 < bb_position < 0.60
        would_signal = vol_ok and bb_ok

        if would_signal:
            signal_count += 1

        logger.info(f"\nTick {i:,} ({ticks[i-1].timestamp}):")
        logger.info(f"  Price: ${current_price:.2f}")
        logger.info(f"  Hybrid: ${hybrid_vol:.4f} ({hybrid_pct:.4f}%)")
        logger.info(f"  ATR: ${atr_vol:.4f} ({atr_pct:.4f}%)")
        logger.info(f"  BB: [{lower_bb:.2f}, {middle_bb:.2f}, {upper_bb:.2f}]")
        logger.info(f"  BB Position: {bb_position:.4f}")
        logger.info(f"  Vol OK: {vol_ok} (H>={0.04:.2f}%, ATR>={0.15:.2f}%)")
        logger.info(f"  BB OK: {bb_ok} (0.40 < {bb_position:.4f} < 0.60)")
        logger.info(f"  SIGNAL: {would_signal}")

    logger.info(f"\n{'='*80}")
    logger.info(f"Total signals that would be generated: {signal_count}")
    logger.info(f"Signal frequency: {signal_count / (len(ticks) / 1000):.2f} per 1000 ticks")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
