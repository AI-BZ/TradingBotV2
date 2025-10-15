"""
5-Hour Comprehensive Trading System Test
Runs backtest + paper trading + generates comprehensive report
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
import logging

from backtester import Backtester
from paper_trader import PaperTrader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('5hour_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Run 5-hour comprehensive test"""

    start_time = datetime.now()
    logger.info("="*80)
    logger.info("5-HOUR COMPREHENSIVE TRADING SYSTEM TEST")
    logger.info("="*80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    results = {
        'test_info': {
            'start_time': start_time.isoformat(),
            'test_duration_hours': 5.0
        }
    }

    # ========================================================================
    # PHASE 1: 3-YEAR BACKTEST (약 2시간)
    # ========================================================================
    logger.info("\n" + "="*80)
    logger.info("PHASE 1: RUNNING 3-YEAR BACKTEST (2022-10 to 2025-10)")
    logger.info("="*80)
    logger.info("Expected Duration: ~2 hours")
    logger.info("")

    phase1_start = datetime.now()

    try:
        backtester = Backtester(initial_balance=10000.0, leverage=10)

        backtest_results = await backtester.run_backtest(
            start_date='2022-10-01',
            end_date='2025-10-16',
            interval='1h'
        )

        # Save backtest results
        backtester.save_results(backtest_results, 'backtest_3year_results.json')

        results['backtest'] = backtest_results

        phase1_duration = (datetime.now() - phase1_start).total_seconds() / 3600
        logger.info(f"\n✅ Phase 1 Complete - Duration: {phase1_duration:.2f} hours")

        # Print backtest summary
        if 'error' not in backtest_results:
            summary = backtest_results['backtest_summary']
            stats = backtest_results['trade_statistics']
            metrics = backtest_results['performance_metrics']

            logger.info("\n" + "="*80)
            logger.info("BACKTEST RESULTS SUMMARY")
            logger.info("="*80)
            logger.info(f"Initial Balance: ${summary['initial_balance']:,.2f}")
            logger.info(f"Final Balance:   ${summary['final_balance']:,.2f}")
            logger.info(f"Total Return:    {summary['total_return_pct']:+.2f}%")
            logger.info(f"Win Rate:        {stats['win_rate_pct']:.1f}%")
            logger.info(f"Profit Factor:   {metrics['profit_factor']:.2f}")
            logger.info(f"Max Drawdown:    {metrics['max_drawdown_pct']:.2f}%")
            logger.info(f"Sharpe Ratio:    {metrics['sharpe_ratio']:.2f}")

    except Exception as e:
        logger.error(f"❌ Phase 1 Failed: {e}")
        results['backtest'] = {'error': str(e)}

    # ========================================================================
    # PHASE 2: LIVE PAPER TRADING (2.5시간)
    # ========================================================================
    logger.info("\n" + "="*80)
    logger.info("PHASE 2: RUNNING LIVE PAPER TRADING")
    logger.info("="*80)
    logger.info("Duration: 2.5 hours")
    logger.info("")

    phase2_start = datetime.now()

    try:
        paper_trader = PaperTrader(initial_balance=10000.0, leverage=10)

        paper_results = await paper_trader.start(duration_hours=2.5)

        results['paper_trading'] = paper_results

        phase2_duration = (datetime.now() - phase2_start).total_seconds() / 3600
        logger.info(f"\n✅ Phase 2 Complete - Duration: {phase2_duration:.2f} hours")

        # Print paper trading summary
        if 'error' not in paper_results:
            summary = paper_results['paper_trading_summary']
            stats = paper_results['trade_statistics']
            metrics = paper_results['performance_metrics']

            logger.info("\n" + "="*80)
            logger.info("PAPER TRADING RESULTS SUMMARY")
            logger.info("="*80)
            logger.info(f"Duration:        {summary['duration_hours']:.2f} hours")
            logger.info(f"Initial Balance: ${summary['initial_balance']:,.2f}")
            logger.info(f"Final Balance:   ${summary['final_balance']:,.2f}")
            logger.info(f"Total Return:    {summary['total_return_pct']:+.2f}%")
            logger.info(f"Win Rate:        {stats['win_rate_pct']:.1f}%")
            logger.info(f"Profit Factor:   {metrics['profit_factor']:.2f}")

    except Exception as e:
        logger.error(f"❌ Phase 2 Failed: {e}")
        results['paper_trading'] = {'error': str(e)}

    # ========================================================================
    # PHASE 3: COMPREHENSIVE REPORT GENERATION
    # ========================================================================
    logger.info("\n" + "="*80)
    logger.info("PHASE 3: GENERATING COMPREHENSIVE REPORT")
    logger.info("="*80)

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds() / 3600

    results['test_info']['end_time'] = end_time.isoformat()
    results['test_info']['actual_duration_hours'] = total_duration

    # Save comprehensive results
    output_path = Path(__file__).parent / 'results' / '5hour_comprehensive_results.json'
    output_path.parent.mkdir(exist_ok=True)

    def convert_timestamps(obj):
        if isinstance(obj, dict):
            return {k: convert_timestamps(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_timestamps(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    results_serializable = convert_timestamps(results)

    with open(output_path, 'w') as f:
        json.dump(results_serializable, f, indent=2)

    logger.info(f"✅ Comprehensive results saved to {output_path}")

    # ========================================================================
    # FINAL REPORT
    # ========================================================================
    logger.info("\n" + "="*80)
    logger.info("5-HOUR TEST COMPLETE - FINAL REPORT")
    logger.info("="*80)
    logger.info(f"Start Time:      {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"End Time:        {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Total Duration:  {total_duration:.2f} hours")

    logger.info("\n📊 BACKTEST (3 YEARS: 2022-10 to 2025-10)")
    if 'backtest' in results and 'error' not in results['backtest']:
        bt = results['backtest']
        logger.info(f"  Return:        {bt['backtest_summary']['total_return_pct']:+.2f}%")
        logger.info(f"  Win Rate:      {bt['trade_statistics']['win_rate_pct']:.1f}%")
        logger.info(f"  Profit Factor: {bt['performance_metrics']['profit_factor']:.2f}")
        logger.info(f"  Max Drawdown:  {bt['performance_metrics']['max_drawdown_pct']:.2f}%")
        logger.info(f"  Sharpe Ratio:  {bt['performance_metrics']['sharpe_ratio']:.2f}")
    else:
        logger.info("  ❌ Backtest failed or incomplete")

    logger.info("\n💹 PAPER TRADING (2.5 HOURS LIVE)")
    if 'paper_trading' in results and 'error' not in results['paper_trading']:
        pt = results['paper_trading']
        logger.info(f"  Return:        {pt['paper_trading_summary']['total_return_pct']:+.2f}%")
        logger.info(f"  Win Rate:      {pt['trade_statistics']['win_rate_pct']:.1f}%")
        logger.info(f"  Profit Factor: {pt['performance_metrics']['profit_factor']:.2f}")
    else:
        logger.info("  ❌ Paper trading failed or incomplete")

    logger.info("\n" + "="*80)
    logger.info("All results saved to backend/results/ directory")
    logger.info("="*80)

    print("\n\n")
    print("="*80)
    print("🎉 5-HOUR COMPREHENSIVE TEST COMPLETED SUCCESSFULLY!")
    print("="*80)
    print(f"\nTest Duration: {total_duration:.2f} hours")
    print(f"\nResults Location:")
    print(f"  - Full Report:    results/5hour_comprehensive_results.json")
    print(f"  - Backtest:       results/backtest_3year_results.json")
    print(f"  - Paper Trading:  results/paper_trading_results.json")
    print(f"  - Log File:       5hour_test.log")
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(main())
