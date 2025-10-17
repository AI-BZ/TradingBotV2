"""
Test the hybrid volatility fix on a single period
Verifies trades are now generated with the fixed signal logic
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging

from binance_client import BinanceClient
from tick_backtester import TickBacktester
from tick_data_collector import Tick

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_test_data(symbol: str, start_date: str, end_date: str):
    """Fetch 1 week of tick data (simulated from 1-min candles)"""
    logger.info(f"Fetching test data for {symbol}: {start_date} to {end_date}")

    binance = BinanceClient(testnet=True)

    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

    # Fetch 1-minute candles
    all_klines = []
    current_ts = start_ts

    while current_ts < end_ts:
        klines = await binance.exchange.fetch_ohlcv(
            symbol,
            timeframe='1m',
            since=current_ts,
            limit=1000
        )

        if not klines:
            break

        all_klines.extend(klines)
        current_ts = klines[-1][0] + 60000

        if current_ts >= end_ts:
            break

    await binance.close()

    # Simulate ticks from candles
    logger.info(f"Simulating ticks from {len(all_klines)} 1-minute candles")
    ticks = []

    for kline in all_klines:
        open_time = kline[0]
        open_price = float(kline[1])
        high = float(kline[2])
        low = float(kline[3])
        close = float(kline[4])
        volume = float(kline[5])

        # Create 10 ticks per minute (6-second intervals)
        for i in range(10):
            tick_time = open_time + (i * 6000)
            progress = i / 9 if i < 9 else 1.0
            price = open_price + (close - open_price) * progress

            spread_pct = 0.0001
            bid = price * (1 - spread_pct)
            ask = price * (1 + spread_pct)

            tick = Tick(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(tick_time / 1000),
                price=price,
                bid=bid,
                ask=ask,
                bid_qty=volume / 10,
                ask_qty=volume / 10,
                volume_24h=volume * 1440,
                quote_volume_24h=volume * price * 1440,
                price_change_pct=((close - open_price) / open_price) * 100 if open_price > 0 else 0
            )
            ticks.append(tick)

    logger.info(f"Generated {len(ticks):,} ticks for {symbol}")
    return ticks


async def main():
    """Run test backtest with hybrid volatility fix"""

    logger.info("\n" + "="*80)
    logger.info("Testing Hybrid Volatility Fix")
    logger.info("="*80 + "\n")

    # Test with a single symbol and short period first
    symbols = ['ETH/USDT']
    start_date = "2024-10-02"
    end_date = "2024-10-09"

    # Fetch test data
    tick_data = {}
    for symbol in symbols:
        ticks = await fetch_test_data(symbol, start_date, end_date)
        tick_data[symbol] = ticks

    # Run backtest
    backtester = TickBacktester(
        symbols=symbols,
        initial_balance=10000.0,
        leverage=10,
        position_size_pct=0.1
    )

    results = await backtester.run_backtest(tick_data, progress_interval=10000)

    # Save results
    output_file = Path('claudedocs/hybrid_volatility_test_results.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    logger.info("\n" + "="*80)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("="*80)
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"\nPerformance:")
    logger.info(f"  Total Trades: {results['total_trades']}")
    logger.info(f"  Win Rate: {results['win_rate']:.2f}%")
    logger.info(f"  Total Return: {results['total_return']:+.2f}%")
    logger.info(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    logger.info(f"  Max Drawdown: {results['max_drawdown']:.2f}%")

    if results['total_trades'] == 0:
        logger.error("\n❌ STILL NO TRADES! The fix didn't work.")
        logger.error("   Debug: Check if hybrid_volatility is being calculated correctly")
    else:
        logger.info(f"\n✅ SUCCESS! Generated {results['total_trades']} trades")
        logger.info("   The hybrid volatility fix is working!")
        logger.info(f"\n   First 3 trades:")
        for i, trade in enumerate(results['trades'][:3], 1):
            logger.info(f"     {i}. {trade['symbol']} {trade['type']}: "
                       f"${trade['pnl']:+.2f} ({trade['pnl_pct']:+.2f}%) - {trade['reason']}")

    logger.info("="*80 + "\n")
    logger.info(f"Full results saved to: {output_file}")

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
