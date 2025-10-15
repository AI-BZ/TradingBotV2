"""
5-Hour Intelligent Trading System Test
AI-driven strategy optimization with parallel multi-coin adaptive testing
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List
import time

from binance_client import BinanceClient
from strategy_optimizer import AIStrategyOptimizer, StrategyConfig, MarketCondition
from backtester import Backtester
from paper_trader import PaperTrader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('5hour_intelligent_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def quick_backtest(symbol: str, strategy: StrategyConfig, period_months: int = 3) -> Dict:
    """Run quick backtest for a single coin with specific strategy

    Args:
        symbol: Trading symbol (e.g., 'BTC/USDT')
        strategy: Strategy configuration
        period_months: Backtest period in months

    Returns:
        Backtest results dictionary
    """
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_months * 30)

        logger.info(f"Quick backtest: {symbol} with {strategy.name} ({period_months}mo)")

        # Create backtester with strategy config
        backtester = Backtester(
            initial_balance=10000.0,
            leverage=10,
            symbols=[symbol]
        )

        # Apply strategy configuration
        backtester.strategy.ml_weight = strategy.ml_weight
        backtester.strategy.technical_weight = strategy.technical_weight
        backtester.risk_manager.max_position_size = strategy.max_position_size
        backtester.trailing_stop_manager.base_atr_multiplier = strategy.atr_multiplier
        backtester.trailing_stop_manager.min_profit_threshold = strategy.min_profit_threshold

        # Run backtest
        results = await backtester.run_backtest(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            interval='1h'
        )

        # Add metadata
        results['symbol'] = symbol
        results['strategy'] = strategy.name
        results['period_months'] = period_months

        return results

    except Exception as e:
        logger.error(f"Quick backtest failed for {symbol}: {e}")
        return {'error': str(e), 'symbol': symbol}


async def run_5hour_intelligent_test():
    """Run 5-hour AI-driven intelligent trading test"""

    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("5-HOUR INTELLIGENT TRADING SYSTEM TEST")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    results = {
        'test_info': {
            'start_time': start_time.isoformat(),
            'test_duration_hours': 5.0,
            'test_type': 'ai_driven_intelligent_adaptive'
        },
        'coin_results': {},
        'optimal_strategies': {},
        'paper_trading': None
    }

    # ========================================================================
    # PHASE 1: MARKET ANALYSIS & AI STRATEGY SELECTION (15 minutes)
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1: AI-DRIVEN STRATEGY SELECTION")
    logger.info("=" * 80)
    logger.info("Duration: ~15 minutes")
    logger.info("")

    phase1_start = datetime.now()

    try:
        # Initialize client and AI optimizer
        client = BinanceClient(testnet=True, use_futures=True)

        # Get top 10 coins
        logger.info("Loading Top 10 coins by volume...")
        raw_symbols = await client.get_top_coins(limit=10)

        # Clean symbols
        symbols = []
        for raw_symbol in raw_symbols:
            clean_symbol = raw_symbol.split(':')[0] if ':' in raw_symbol else raw_symbol
            symbols.append(clean_symbol)

        logger.info(f"Analyzing {len(symbols)} coins: {', '.join(symbols)}")

        # Initialize AI optimizer
        optimizer = AIStrategyOptimizer(client)

        # Analyze market conditions and select optimal strategies
        logger.info("\nAnalyzing market conditions for each coin...")
        optimal_strategies = await optimizer.optimize_all_coins(symbols)

        # Log results
        for symbol in symbols:
            long_strat = optimal_strategies[symbol]['LONG']['strategy']
            short_strat = optimal_strategies[symbol]['SHORT']['strategy']
            market_cond = optimal_strategies[symbol]['LONG']['market_condition']

            logger.info(f"\n{symbol}:")
            logger.info(f"  Market: {market_cond.regime}, Volatility: {market_cond.volatility:.3f}")
            logger.info(f"  LONG Strategy: {long_strat.name}")
            logger.info(f"  SHORT Strategy: {short_strat.name}")

        results['optimal_strategies'] = {
            symbol: {
                'LONG': {
                    'strategy': optimal_strategies[symbol]['LONG']['strategy'].to_dict(),
                    'market_condition': {
                        'regime': optimal_strategies[symbol]['LONG']['market_condition'].regime,
                        'volatility': optimal_strategies[symbol]['LONG']['market_condition'].volatility
                    }
                },
                'SHORT': {
                    'strategy': optimal_strategies[symbol]['SHORT']['strategy'].to_dict(),
                    'market_condition': {
                        'regime': optimal_strategies[symbol]['SHORT']['market_condition'].regime,
                        'volatility': optimal_strategies[symbol]['SHORT']['market_condition'].volatility
                    }
                }
            }
            for symbol in symbols
        }

        await client.close()

        phase1_duration = (datetime.now() - phase1_start).total_seconds() / 60
        logger.info(f"\n✅ Phase 1 Complete - Duration: {phase1_duration:.1f} minutes")

    except Exception as e:
        logger.error(f"❌ Phase 1 Failed: {e}")
        results['optimal_strategies'] = {'error': str(e)}
        return results

    # ========================================================================
    # PHASE 2: PARALLEL QUICK BACKTESTS (45 minutes)
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 2: PARALLEL MULTI-COIN QUICK BACKTESTS")
    logger.info("=" * 80)
    logger.info("Strategy: Test all coins with optimal strategies (3-month period)")
    logger.info("Duration: ~45 minutes")
    logger.info("")

    phase2_start = datetime.now()

    try:
        # Run quick backtests for all coins in parallel (batches of 3)
        all_backtest_tasks = []

        for symbol in symbols:
            # Use LONG strategy for initial test
            strategy = optimal_strategies[symbol]['LONG']['strategy']
            task = quick_backtest(symbol, strategy, period_months=3)
            all_backtest_tasks.append(task)

        # Run in batches of 3 to avoid overwhelming the system
        batch_size = 3
        quick_test_results = []

        for i in range(0, len(all_backtest_tasks), batch_size):
            batch = all_backtest_tasks[i:i+batch_size]
            logger.info(f"\nRunning backtest batch {i//batch_size + 1}/{(len(all_backtest_tasks) + batch_size - 1)//batch_size}")
            batch_results = await asyncio.gather(*batch)
            quick_test_results.extend(batch_results)

            # Small delay between batches
            if i + batch_size < len(all_backtest_tasks):
                await asyncio.sleep(5)

        # Analyze results
        successful_tests = [r for r in quick_test_results if 'error' not in r]

        for result in successful_tests:
            symbol = result['symbol']
            results['coin_results'][symbol] = {
                'quick_backtest_3mo': result
            }

            if 'backtest_summary' in result:
                summary = result['backtest_summary']
                stats = result['trade_statistics']
                logger.info(f"\n{symbol} Quick Backtest:")
                logger.info(f"  Return: {summary.get('total_return_pct', 0):+.2f}%")
                logger.info(f"  Win Rate: {stats.get('win_rate_pct', 0):.1f}%")
                logger.info(f"  Total Trades: {stats.get('total_trades', 0)}")

        phase2_duration = (datetime.now() - phase2_start).total_seconds() / 60
        logger.info(f"\n✅ Phase 2 Complete - Duration: {phase2_duration:.1f} minutes")

    except Exception as e:
        logger.error(f"❌ Phase 2 Failed: {e}")
        results['coin_results'] = {'error': str(e)}

    # ========================================================================
    # PHASE 3: ADAPTIVE TESTING (2 hours)
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 3: ADAPTIVE STRATEGY VALIDATION")
    logger.info("=" * 80)
    logger.info("Strategy: Test best performers with longer period, adjust poor performers")
    logger.info("Duration: ~2 hours")
    logger.info("")

    phase3_start = datetime.now()

    try:
        # Identify top performers and poor performers
        performance_scores = []

        for symbol in symbols:
            if symbol in results['coin_results']:
                result = results['coin_results'][symbol].get('quick_backtest_3mo', {})
                if 'backtest_summary' in result:
                    return_pct = result['backtest_summary'].get('total_return_pct', 0)
                    win_rate = result['trade_statistics'].get('win_rate_pct', 0)
                    score = (return_pct * 0.6) + (win_rate * 0.4)
                    performance_scores.append({'symbol': symbol, 'score': score, 'return': return_pct})

        performance_scores.sort(key=lambda x: x['score'], reverse=True)

        # Top 3 performers: Extended validation (6 months)
        top_performers = [p['symbol'] for p in performance_scores[:3]]
        logger.info(f"\n🏆 Top Performers for Extended Validation: {', '.join(top_performers)}")

        extended_tests = []
        for symbol in top_performers:
            strategy = optimal_strategies[symbol]['LONG']['strategy']
            task = quick_backtest(symbol, strategy, period_months=6)
            extended_tests.append(task)

        extended_results = await asyncio.gather(*extended_tests)

        for result in extended_results:
            if 'error' not in result:
                symbol = result['symbol']
                results['coin_results'][symbol]['extended_backtest_6mo'] = result

                if 'backtest_summary' in result:
                    summary = result['backtest_summary']
                    logger.info(f"\n{symbol} Extended Backtest (6mo):")
                    logger.info(f"  Return: {summary.get('total_return_pct', 0):+.2f}%")

        # Bottom 3 performers: Try different strategy
        poor_performers = [p['symbol'] for p in performance_scores[-3:]]
        logger.info(f"\n⚠️  Poor Performers - Testing Alternative Strategies: {', '.join(poor_performers)}")

        # Try alternative strategies for poor performers
        alternative_tests = []
        for symbol in poor_performers:
            # Try aggressive strategy
            from strategy_optimizer import StrategyDatabase
            alt_strategy = StrategyDatabase.STRATEGIES['aggressive_trend']
            task = quick_backtest(symbol, alt_strategy, period_months=3)
            alternative_tests.append(task)

        alternative_results = await asyncio.gather(*alternative_tests)

        for result in alternative_results:
            if 'error' not in result:
                symbol = result['symbol']
                results['coin_results'][symbol]['alternative_strategy_test'] = result

                if 'backtest_summary' in result:
                    summary = result['backtest_summary']
                    logger.info(f"\n{symbol} Alternative Strategy:")
                    logger.info(f"  Return: {summary.get('total_return_pct', 0):+.2f}%")

        phase3_duration = (datetime.now() - phase3_start).total_seconds() / 60
        logger.info(f"\n✅ Phase 3 Complete - Duration: {phase3_duration:.1f} minutes")

    except Exception as e:
        logger.error(f"❌ Phase 3 Failed: {e}")

    # ========================================================================
    # PHASE 4: LIVE PAPER TRADING (2 hours)
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 4: LIVE PAPER TRADING WITH OPTIMAL STRATEGIES")
    logger.info("=" * 80)
    logger.info("Duration: ~2 hours")
    logger.info("")

    phase4_start = datetime.now()

    try:
        # Use best overall strategy for paper trading
        paper_trader = PaperTrader(initial_balance=10000.0, leverage=10)

        # Run for 2 hours
        paper_results = await paper_trader.start(duration_hours=2.0)

        results['paper_trading'] = paper_results

        phase4_duration = (datetime.now() - phase4_start).total_seconds() / 60
        logger.info(f"\n✅ Phase 4 Complete - Duration: {phase4_duration:.1f} minutes")

        # Print paper trading summary
        if 'error' not in paper_results:
            summary = paper_results['paper_trading_summary']
            stats = paper_results['trade_statistics']

            logger.info("\n" + "=" * 80)
            logger.info("PAPER TRADING RESULTS")
            logger.info("=" * 80)
            logger.info(f"Duration:        {summary['duration_hours']:.2f} hours")
            logger.info(f"Initial Balance: ${summary['initial_balance']:,.2f}")
            logger.info(f"Final Balance:   ${summary['final_balance']:,.2f}")
            logger.info(f"Total Return:    {summary['total_return_pct']:+.2f}%")
            logger.info(f"Win Rate:        {stats['win_rate_pct']:.1f}%")

    except Exception as e:
        logger.error(f"❌ Phase 4 Failed: {e}")
        results['paper_trading'] = {'error': str(e)}

    # ========================================================================
    # FINAL REPORT
    # ========================================================================
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds() / 3600

    results['test_info']['end_time'] = end_time.isoformat()
    results['test_info']['actual_duration_hours'] = total_duration

    # Save comprehensive results
    output_path = Path(__file__).parent / 'results' / '5hour_intelligent_results.json'
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

    logger.info(f"\n✅ Comprehensive results saved to {output_path}")

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    logger.info("\n" + "=" * 80)
    logger.info("5-HOUR INTELLIGENT TEST COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Start Time:      {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"End Time:        {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Total Duration:  {total_duration:.2f} hours")

    logger.info("\n📊 TESTED COINS: {}".format(len(symbols)))
    logger.info(f"Symbols: {', '.join(symbols)}")

    logger.info("\n🧠 AI STRATEGY OPTIMIZATION:")
    logger.info("  ✅ Market condition analysis complete")
    logger.info("  ✅ Per-coin optimal strategies selected")
    logger.info("  ✅ LONG and SHORT strategies optimized separately")

    logger.info("\n📈 BACKTESTING RESULTS:")
    successful_backtests = len([s for s in symbols if s in results['coin_results']])
    logger.info(f"  Completed: {successful_backtests}/{len(symbols)} coins")

    if performance_scores:
        best = performance_scores[0]
        logger.info(f"  Best Performer: {best['symbol']} ({best['return']:+.2f}%)")

    logger.info("\n💹 PAPER TRADING:")
    if results['paper_trading'] and 'error' not in results['paper_trading']:
        pt = results['paper_trading']
        logger.info(f"  Return:        {pt['paper_trading_summary']['total_return_pct']:+.2f}%")
        logger.info(f"  Win Rate:      {pt['trade_statistics']['win_rate_pct']:.1f}%")
        logger.info(f"  Total Trades:  {pt['trade_statistics']['total_trades']}")
    else:
        logger.info("  ❌ Paper trading incomplete or failed")

    logger.info("\n" + "=" * 80)
    logger.info("📁 Results saved to backend/results/ directory")
    logger.info("=" * 80)

    print("\n\n")
    print("=" * 80)
    print("🎉 5-HOUR INTELLIGENT TEST COMPLETED!")
    print("=" * 80)
    print(f"\nTest Duration: {total_duration:.2f} hours")
    print(f"\nResults Location:")
    print(f"  - Full Report:    results/5hour_intelligent_results.json")
    print(f"  - Log File:       5hour_intelligent_test.log")
    print("\n" + "=" * 80)

    return results


if __name__ == "__main__":
    asyncio.run(run_5hour_intelligent_test())
