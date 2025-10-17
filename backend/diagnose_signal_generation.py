"""
Diagnostic script to analyze why Two-Way entry signals are not generating
Analyzes actual BB bandwidth and ATR values from market data
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from binance_client import BinanceClient
from technical_indicators import TechnicalIndicators
from trading_strategy import TradingStrategy
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def diagnose_volatility_patterns():
    """Analyze actual volatility patterns in market data"""

    logger.info("\n" + "="*80)
    logger.info("🔍 TWO-WAY SIGNAL GENERATION DIAGNOSTIC")
    logger.info("="*80)

    # Initialize
    client = BinanceClient(testnet=True, use_futures=True)
    strategy = TradingStrategy()

    # Test all 10 coins
    symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
        'DOGE/USDT', 'XPL/USDT', 'SUI/USDT', '1000PEPE/USDT', 'HYPE/USDT'
    ]

    # Test period: last 30 days
    end_date = datetime(2025, 10, 16)
    start_date = end_date - timedelta(days=30)

    logger.info(f"📅 Analysis Period: {start_date.date()} to {end_date.date()}\n")

    try:
        all_stats = {}

        for symbol in symbols:
            logger.info(f"\n{'='*80}")
            logger.info(f"📊 Analyzing {symbol}")
            logger.info(f"{'='*80}")

            # Load data
            logger.info(f"Loading {symbol} data...")
            klines = []

            # Fetch data in batches
            start_ts = int(start_date.timestamp() * 1000)
            end_ts = int(end_date.timestamp() * 1000)

            current_ts = start_ts
            while current_ts < end_ts:
                batch = await client.get_klines(symbol, interval='1h', limit=1000)
                if not batch:
                    break

                valid_batch = [k for k in batch if start_ts <= k['timestamp'] <= end_ts]
                klines.extend(valid_batch)

                if len(batch) < 1000:
                    break

                current_ts = batch[-1]['timestamp'] + 3600000
                await asyncio.sleep(0.2)

            if not klines:
                logger.warning(f"No data for {symbol}")
                continue

            data = pd.DataFrame(klines)
            data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
            data = data.sort_values('timestamp').reset_index(drop=True)

            logger.info(f"Loaded {len(data)} candles")

            # Get coin-specific parameters
            params = strategy.get_coin_parameters(symbol)
            bb_threshold = params.get('bb_compression', 0.055)
            atr_threshold = params.get('atr_expansion', 0.025)

            logger.info(f"\n📋 Coin Parameters:")
            logger.info(f"  BB Compression Threshold: {bb_threshold*100:.1f}%")
            logger.info(f"  ATR Expansion Threshold: {atr_threshold*100:.1f}%")

            # Analyze volatility metrics
            bb_widths = []
            atr_pcts = []
            signals_met = {'compression': 0, 'expansion': 0, 'both': 0}

            for idx in range(100, len(data)):
                history = data.iloc[:idx + 1]

                # Calculate indicators
                indicators = TechnicalIndicators.calculate_all(
                    history['high'].tolist()[-100:],
                    history['low'].tolist()[-100:],
                    history['close'].tolist()[-100:],
                    history['volume'].tolist()[-100:]
                )

                # BB bandwidth
                bb_data = indicators.get('bb', {})
                bb_bandwidth = bb_data.get('bandwidth', 0)
                bb_widths.append(bb_bandwidth)

                # ATR percentage
                atr = indicators.get('atr', 0)
                close = float(history['close'].iloc[-1])
                atr_pct = atr / close if close > 0 else 0
                atr_pcts.append(atr_pct)

                # Check conditions
                is_compressed = bb_bandwidth < bb_threshold
                is_expanding = atr_pct > atr_threshold

                if is_compressed:
                    signals_met['compression'] += 1
                if is_expanding:
                    signals_met['expansion'] += 1
                if is_compressed and is_expanding:
                    signals_met['both'] += 1

            # Statistics
            bb_widths = np.array(bb_widths)
            atr_pcts = np.array(atr_pcts)

            total_bars = len(bb_widths)

            logger.info(f"\n📊 Volatility Statistics:")
            logger.info(f"\n  BB Bandwidth:")
            logger.info(f"    Min:     {np.min(bb_widths)*100:.2f}%")
            logger.info(f"    Max:     {np.max(bb_widths)*100:.2f}%")
            logger.info(f"    Mean:    {np.mean(bb_widths)*100:.2f}%")
            logger.info(f"    Median:  {np.median(bb_widths)*100:.2f}%")
            logger.info(f"    Threshold: {bb_threshold*100:.1f}%")
            logger.info(f"    Below threshold: {(bb_widths < bb_threshold).sum()} bars ({(bb_widths < bb_threshold).sum()/total_bars*100:.1f}%)")

            logger.info(f"\n  ATR Percentage:")
            logger.info(f"    Min:     {np.min(atr_pcts)*100:.2f}%")
            logger.info(f"    Max:     {np.max(atr_pcts)*100:.2f}%")
            logger.info(f"    Mean:    {np.mean(atr_pcts)*100:.2f}%")
            logger.info(f"    Median:  {np.median(atr_pcts)*100:.2f}%")
            logger.info(f"    Threshold: {atr_threshold*100:.1f}%")
            logger.info(f"    Above threshold: {(atr_pcts > atr_threshold).sum()} bars ({(atr_pcts > atr_threshold).sum()/total_bars*100:.1f}%)")

            logger.info(f"\n  Signal Conditions Met:")
            logger.info(f"    Compression only: {signals_met['compression']} bars ({signals_met['compression']/total_bars*100:.1f}%)")
            logger.info(f"    Expansion only:   {signals_met['expansion']} bars ({signals_met['expansion']/total_bars*100:.1f}%)")
            logger.info(f"    BOTH (entry):     {signals_met['both']} bars ({signals_met['both']/total_bars*100:.1f}%)")

            # Calculate suggested thresholds (percentiles)
            bb_50pct = np.percentile(bb_widths, 50)
            bb_75pct = np.percentile(bb_widths, 75)
            atr_25pct = np.percentile(atr_pcts, 25)
            atr_50pct = np.percentile(atr_pcts, 50)

            logger.info(f"\n  💡 Suggested Threshold Adjustments:")
            logger.info(f"    BB Compression (50th percentile): {bb_50pct*100:.2f}%")
            logger.info(f"    BB Compression (75th percentile): {bb_75pct*100:.2f}%")
            logger.info(f"    ATR Expansion (25th percentile):  {atr_25pct*100:.2f}%")
            logger.info(f"    ATR Expansion (50th percentile):  {atr_50pct*100:.2f}%")

            # Store stats
            all_stats[symbol] = {
                'bb_mean': np.mean(bb_widths),
                'bb_median': np.median(bb_widths),
                'bb_threshold': bb_threshold,
                'bb_below_threshold_pct': (bb_widths < bb_threshold).sum()/total_bars*100,
                'atr_mean': np.mean(atr_pcts),
                'atr_median': np.median(atr_pcts),
                'atr_threshold': atr_threshold,
                'atr_above_threshold_pct': (atr_pcts > atr_threshold).sum()/total_bars*100,
                'both_conditions_pct': signals_met['both']/total_bars*100,
                'suggested_bb': bb_75pct,
                'suggested_atr': atr_25pct
            }

        # Summary
        logger.info(f"\n" + "="*80)
        logger.info("📋 DIAGNOSTIC SUMMARY")
        logger.info("="*80)

        for symbol, stats in all_stats.items():
            logger.info(f"\n{symbol}:")
            logger.info(f"  Current thresholds: BB < {stats['bb_threshold']*100:.1f}%, ATR > {stats['atr_threshold']*100:.1f}%")
            logger.info(f"  Actual averages: BB = {stats['bb_mean']*100:.2f}%, ATR = {stats['atr_mean']*100:.2f}%")
            logger.info(f"  BOTH conditions met: {stats['both_conditions_pct']:.2f}% of time")
            logger.info(f"  Suggested: BB < {stats['suggested_bb']*100:.2f}%, ATR > {stats['suggested_atr']*100:.2f}%")

        logger.info(f"\n" + "="*80)
        logger.info("🎯 RECOMMENDATIONS")
        logger.info("="*80)

        avg_both_pct = np.mean([stats['both_conditions_pct'] for stats in all_stats.values()])

        if avg_both_pct < 1.0:
            logger.info(f"\n❌ Problem: BOTH conditions met only {avg_both_pct:.2f}% of time (target: 5-10%)")
            logger.info(f"\n✅ Solution: Relax thresholds to increase signal frequency")
            logger.info(f"\nProposed adjustments:")
            for symbol, stats in all_stats.items():
                logger.info(f"  {symbol}:")
                logger.info(f"    bb_compression: {stats['bb_threshold']*100:.1f}% → {stats['suggested_bb']*100:.2f}%")
                logger.info(f"    atr_expansion: {stats['atr_threshold']*100:.1f}% → {stats['suggested_atr']*100:.2f}%")
        else:
            logger.info(f"\n✅ Thresholds are reasonable ({avg_both_pct:.2f}% signal frequency)")

        logger.info(f"\n" + "="*80 + "\n")

        return all_stats

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(diagnose_volatility_patterns())
