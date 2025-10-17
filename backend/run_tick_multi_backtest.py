"""
Tick Data Multi-Period Backtest Runner
10개의 서로 다른 1주일 기간에 대해 틱 데이터 백테스트 실행
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import pandas as pd

from tick_backtester import TickBacktester
from tick_data_collector import TickDataCollector, Tick
from binance_client import BinanceClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 10개 백테스트 기간 정의
BACKTEST_PERIODS = [
    ("2024-10-02", "2024-10-09", "10월 첫째 주"),
    ("2024-05-03", "2024-05-10", "5월 첫째 주"),
    ("2024-03-15", "2024-03-22", "3월 중순"),
    ("2024-07-20", "2024-07-27", "7월 하순"),
    ("2024-09-01", "2024-09-08", "9월 첫째 주"),
    ("2024-06-10", "2024-06-17", "6월 중순"),
    ("2024-04-01", "2024-04-08", "4월 첫째 주"),
    ("2024-08-12", "2024-08-19", "8월 중순"),
    ("2024-02-14", "2024-02-21", "2월 중순 (밸런타인데이)"),
    ("2024-11-01", "2024-11-08", "11월 첫째 주"),
]


class TickMultiBacktester:
    """Multiple period tick-based backtest runner"""

    def __init__(self, symbols: List[str]):
        """
        Args:
            symbols: List of trading symbols (e.g., ['BTC/USDT', 'ETH/USDT'])
        """
        self.symbols = symbols
        self.binance = BinanceClient(testnet=True)
        self.results = []

        # Create results directory
        self.results_dir = Path(__file__).parent / 'claudedocs' / 'tick_backtest_results'
        self.results_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"TickMultiBacktester initialized for {len(symbols)} symbols")

    async def fetch_tick_data(self, symbol: str, start_date: str, end_date: str) -> List[Tick]:
        """
        Fetch historical tick data for a period

        NOTE: Binance doesn't provide direct tick data history API.
        We'll use 1-minute klines as proxy and simulate ticks from them.
        Real implementation should use saved tick data or different data source.

        Args:
            symbol: Trading symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of Tick objects
        """
        logger.info(f"Fetching tick data for {symbol}: {start_date} to {end_date}")

        # Convert to timestamps
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        # Calculate days and fetch in batches (max 1000 candles per request)
        days = (end_ts - start_ts) // (24 * 60 * 60 * 1000) + 1

        all_klines = []
        current_ts = start_ts

        # Fetch klines in batches
        while current_ts < end_ts:
            try:
                # Fetch up to 1000 1-minute candles at a time
                ohlcv = await self.binance.exchange.fetch_ohlcv(
                    symbol,
                    timeframe='1m',
                    since=current_ts,
                    limit=1000
                )

                if not ohlcv:
                    break

                # Convert to klines format
                for candle in ohlcv:
                    if candle[0] >= end_ts:
                        break
                    all_klines.append(candle)

                # Move to next batch
                if len(ohlcv) > 0:
                    current_ts = ohlcv[-1][0] + 60000  # Add 1 minute
                else:
                    break

            except Exception as e:
                logger.error(f"Error fetching klines batch: {e}")
                break

        klines = all_klines

        if not klines:
            logger.warning(f"No klines data for {symbol} in period {start_date} to {end_date}")
            return []

        # Simulate ticks from klines
        # For each 1-minute candle, create 10 ticks (6-second intervals)
        ticks = []
        for kline in klines:
            # CCXT ohlcv format: [timestamp, open, high, low, close, volume]
            open_time = kline[0]
            open_price = float(kline[1])
            high = float(kline[2])
            low = float(kline[3])
            close = float(kline[4])
            volume = float(kline[5])

            # Simulate 10 ticks per minute
            for i in range(10):
                tick_time = open_time + (i * 6000)  # 6-second intervals

                # Interpolate price (simple linear progression from open to close)
                progress = i / 9 if i < 9 else 1.0
                price = open_price + (close - open_price) * progress

                # Add some randomness for bid/ask spread (0.01% spread)
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
                    volume_24h=volume * 1440,  # Approximate 24h volume
                    quote_volume_24h=volume * price * 1440,
                    price_change_pct=((close - open_price) / open_price) * 100 if open_price > 0 else 0
                )
                ticks.append(tick)

        logger.info(f"Generated {len(ticks):,} ticks from {len(klines)} klines for {symbol}")
        return ticks

    async def run_single_backtest(
        self,
        period_index: int,
        start_date: str,
        end_date: str,
        description: str
    ) -> Dict:
        """
        Run backtest for a single period

        Args:
            period_index: Period number (1-10)
            start_date: Start date
            end_date: End date
            description: Period description

        Returns:
            Backtest results dictionary
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Period {period_index}: {description}")
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info(f"{'='*80}\n")

        # Fetch tick data for all symbols
        tick_data = {}
        for symbol in self.symbols:
            ticks = await self.fetch_tick_data(symbol, start_date, end_date)
            if ticks:
                tick_data[symbol] = ticks

        if not tick_data:
            logger.error(f"No tick data available for period {period_index}")
            return {
                'period': period_index,
                'start_date': start_date,
                'end_date': end_date,
                'description': description,
                'error': 'No tick data available'
            }

        # Run backtest
        backtester = TickBacktester(
            symbols=list(tick_data.keys()),
            initial_balance=10000.0
        )

        results = await backtester.run_backtest(tick_data)

        # Add period metadata
        results['period'] = period_index
        results['start_date'] = start_date
        results['end_date'] = end_date
        results['description'] = description

        # Save individual period results
        period_file = self.results_dir / f"period_{period_index}_{start_date}_{end_date}.json"
        with open(period_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Period {period_index} results saved to {period_file}")

        return results

    async def run_all_backtests(self) -> List[Dict]:
        """
        Run backtests for all 10 periods

        Returns:
            List of backtest results
        """
        logger.info(f"\n{'='*80}")
        logger.info("Starting Multi-Period Tick Backtest")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info(f"Periods: {len(BACKTEST_PERIODS)}")
        logger.info(f"{'='*80}\n")

        results = []

        for i, (start, end, desc) in enumerate(BACKTEST_PERIODS, 1):
            try:
                result = await self.run_single_backtest(i, start, end, desc)
                results.append(result)

                # Log summary
                if 'error' not in result:
                    logger.info(f"\nPeriod {i} Summary:")
                    logger.info(f"  Total Return: {result.get('total_return_pct', 0):.2f}%")
                    logger.info(f"  Win Rate: {result.get('win_rate', 0):.2f}%")
                    logger.info(f"  Total Trades: {result.get('total_trades', 0)}")
                    logger.info(f"  Profit Factor: {result.get('profit_factor', 0):.2f}")
                    logger.info(f"  Max Drawdown: {result.get('max_drawdown_pct', 0):.2f}%\n")

            except Exception as e:
                logger.error(f"Error in period {i}: {e}", exc_info=True)
                results.append({
                    'period': i,
                    'start_date': start,
                    'end_date': end,
                    'description': desc,
                    'error': str(e)
                })

        self.results = results
        return results

    def generate_summary_report(self) -> Dict:
        """
        Generate summary report across all periods

        Returns:
            Summary statistics dictionary
        """
        successful_results = [r for r in self.results if 'error' not in r]

        if not successful_results:
            return {'error': 'No successful backtests'}

        # Calculate aggregate statistics
        total_returns = [r['total_return_pct'] for r in successful_results]
        win_rates = [r['win_rate'] for r in successful_results]
        total_trades = [r['total_trades'] for r in successful_results]
        profit_factors = [r['profit_factor'] for r in successful_results]
        max_drawdowns = [r['max_drawdown_pct'] for r in successful_results]
        sharpe_ratios = [r.get('sharpe_ratio', 0) for r in successful_results]

        summary = {
            'total_periods': len(BACKTEST_PERIODS),
            'successful_periods': len(successful_results),
            'failed_periods': len(self.results) - len(successful_results),

            'average_return': sum(total_returns) / len(total_returns),
            'median_return': sorted(total_returns)[len(total_returns) // 2],
            'best_return': max(total_returns),
            'worst_return': min(total_returns),
            'positive_periods': sum(1 for r in total_returns if r > 0),
            'win_rate_periods': f"{sum(1 for r in total_returns if r > 0) / len(total_returns) * 100:.1f}%",

            'average_win_rate': sum(win_rates) / len(win_rates),
            'average_trades_per_period': sum(total_trades) / len(total_trades),
            'total_trades_all_periods': sum(total_trades),

            'average_profit_factor': sum(profit_factors) / len(profit_factors),
            'average_max_drawdown': sum(max_drawdowns) / len(max_drawdowns),
            'worst_drawdown': max(max_drawdowns),

            'average_sharpe': sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0,

            'consistency_score': (
                sum(1 for r in total_returns if r > 0) / len(total_returns) * 100
            ),

            'period_results': [
                {
                    'period': r['period'],
                    'dates': f"{r['start_date']} to {r['end_date']}",
                    'description': r['description'],
                    'return': r['total_return_pct'],
                    'win_rate': r['win_rate'],
                    'trades': r['total_trades'],
                    'profit_factor': r['profit_factor'],
                    'max_dd': r['max_drawdown_pct']
                }
                for r in successful_results
            ]
        }

        return summary

    def print_summary_report(self):
        """Print formatted summary report"""
        summary = self.generate_summary_report()

        if 'error' in summary:
            logger.error(f"Cannot generate summary: {summary['error']}")
            return

        logger.info(f"\n{'='*80}")
        logger.info("MULTI-PERIOD TICK BACKTEST SUMMARY")
        logger.info(f"{'='*80}\n")

        logger.info(f"Total Periods Tested: {summary['total_periods']}")
        logger.info(f"Successful: {summary['successful_periods']} | Failed: {summary['failed_periods']}\n")

        logger.info(f"📊 Return Statistics:")
        logger.info(f"  Average Return: {summary['average_return']:.2f}%")
        logger.info(f"  Median Return: {summary['median_return']:.2f}%")
        logger.info(f"  Best Period: {summary['best_return']:.2f}%")
        logger.info(f"  Worst Period: {summary['worst_return']:.2f}%")
        logger.info(f"  Positive Periods: {summary['positive_periods']}/{summary['successful_periods']} ({summary['win_rate_periods']})\n")

        logger.info(f"🎯 Performance Metrics:")
        logger.info(f"  Average Win Rate: {summary['average_win_rate']:.2f}%")
        logger.info(f"  Average Profit Factor: {summary['average_profit_factor']:.2f}")
        logger.info(f"  Average Sharpe Ratio: {summary['average_sharpe']:.2f}")
        logger.info(f"  Average Trades/Period: {summary['average_trades_per_period']:.0f}")
        logger.info(f"  Total Trades (All Periods): {summary['total_trades_all_periods']}\n")

        logger.info(f"⚠️  Risk Metrics:")
        logger.info(f"  Average Max Drawdown: {summary['average_max_drawdown']:.2f}%")
        logger.info(f"  Worst Drawdown: {summary['worst_drawdown']:.2f}%\n")

        logger.info(f"✅ Consistency Score: {summary['consistency_score']:.1f}%\n")

        logger.info(f"{'='*80}")
        logger.info("Individual Period Results:")
        logger.info(f"{'='*80}\n")

        for result in summary['period_results']:
            status = "✅" if result['return'] > 0 else "❌"
            logger.info(f"{status} Period {result['period']}: {result['description']}")
            logger.info(f"   Dates: {result['dates']}")
            logger.info(f"   Return: {result['return']:+.2f}% | Win Rate: {result['win_rate']:.1f}%")
            logger.info(f"   Trades: {result['trades']} | PF: {result['profit_factor']:.2f} | Max DD: {result['max_dd']:.2f}%\n")

        logger.info(f"{'='*80}\n")

        # Save summary report
        summary_file = self.results_dir / f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        logger.info(f"Summary report saved to {summary_file}\n")

    async def close(self):
        """Close connections"""
        await self.binance.close()


async def main():
    """Main execution function"""
    # Load active symbols from config
    config_file = Path(__file__).parent / 'coin_specific_params.json'
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Get active symbols (non-excluded)
    active_symbols = [
        symbol for symbol, params in config['coin_parameters'].items()
        if not params.get('excluded', False)
    ]

    logger.info(f"Using {len(active_symbols)} active symbols from v{config['version']}")
    logger.info(f"Symbols: {', '.join(active_symbols)}\n")

    # Create and run backtester
    backtester = TickMultiBacktester(symbols=active_symbols)

    try:
        # Run all backtests
        await backtester.run_all_backtests()

        # Print summary
        backtester.print_summary_report()

    finally:
        await backtester.close()


if __name__ == "__main__":
    asyncio.run(main())
