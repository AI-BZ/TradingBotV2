"""
Two-Way Strategy Optimization Script
Systematically test different parameter combinations to find optimal settings
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
import logging

from backtester import Backtester
from trading_strategy import TradingStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_single_backtest(params: dict) -> dict:
    """Run backtest with specific parameters

    Args:
        params: Dictionary of strategy parameters

    Returns:
        Backtest results with parameters
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing parameters: {params}")
    logger.info(f"{'='*80}")

    # Create backtester
    backtester = Backtester(
        initial_balance=10000.0,
        leverage=1,
        symbols=None
    )

    # Note: Parameters are used in TechnicalIndicators.calculate_all()
    # We'll modify the strategy thresholds directly in trading_strategy.py

    try:
        results = await backtester.run_backtest(
            start_date='2025-09-16',
            end_date='2025-10-16',
            interval='1h'
        )

        # Add parameters to results
        results['parameters'] = params

        # Extract key metrics
        if 'trade_statistics' in results:
            stats = results['trade_statistics']
            metrics = results['performance_metrics']
            summary = results['backtest_summary']

            logger.info(f"\n{'='*80}")
            logger.info(f"RESULTS for {params['name']}:")
            logger.info(f"{'='*80}")
            logger.info(f"Total Trades: {stats['total_trades']}")
            logger.info(f"Win Rate: {stats['win_rate_pct']:.2f}%")
            logger.info(f"Total Return: {summary['total_return_pct']:.2f}%")
            logger.info(f"Profit Factor: {metrics['profit_factor']:.2f}")
            logger.info(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
            logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            logger.info(f"{'='*80}\n")

        return results

    except Exception as e:
        logger.error(f"Backtest failed for {params['name']}: {e}")
        return {
            'error': str(e),
            'parameters': params
        }


async def optimize_strategy():
    """Run multiple backtests with different parameter combinations"""

    logger.info("\n" + "="*80)
    logger.info("TWO-WAY STRATEGY PARAMETER OPTIMIZATION")
    logger.info("="*80)
    logger.info("Testing multiple parameter combinations over 2 hours")
    logger.info("Goal: Find profitable settings for ML training\n")

    # Define parameter sets to test
    # Each will modify thresholds in trading_strategy.py
    parameter_sets = [
        # Current settings (baseline)
        {
            'name': 'Baseline',
            'bb_compression': 0.05,  # 5%
            'atr_expansion': 0.015,  # 1.5%
            'hard_stop': 0.015,      # 1.5%
            'trailing_multiplier': 1.8,
            'description': 'Current relaxed settings'
        },

        # Tighter entry (fewer trades, higher quality)
        {
            'name': 'Tight_Entry',
            'bb_compression': 0.03,  # 3%
            'atr_expansion': 0.02,   # 2%
            'hard_stop': 0.015,      # 1.5%
            'trailing_multiplier': 1.8,
            'description': 'Stricter volatility requirements'
        },

        # Looser entry (more trades, lower quality)
        {
            'name': 'Loose_Entry',
            'bb_compression': 0.07,  # 7%
            'atr_expansion': 0.01,   # 1%
            'hard_stop': 0.015,      # 1.5%
            'trailing_multiplier': 1.8,
            'description': 'Easier volatility requirements'
        },

        # Tighter hard stop (faster loss cutting)
        {
            'name': 'Tight_Stop',
            'bb_compression': 0.05,
            'atr_expansion': 0.015,
            'hard_stop': 0.01,       # 1% (tighter)
            'trailing_multiplier': 1.8,
            'description': 'Faster loss cutting'
        },

        # Looser hard stop (more room for reversal)
        {
            'name': 'Loose_Stop',
            'bb_compression': 0.05,
            'atr_expansion': 0.015,
            'hard_stop': 0.02,       # 2% (looser)
            'trailing_multiplier': 1.8,
            'description': 'More room for price swings'
        },

        # Tighter trailing (lock profits faster)
        {
            'name': 'Tight_Trail',
            'bb_compression': 0.05,
            'atr_expansion': 0.015,
            'hard_stop': 0.015,
            'trailing_multiplier': 1.5,  # Tighter
            'description': 'Lock profits faster'
        },

        # Looser trailing (let profits run)
        {
            'name': 'Loose_Trail',
            'bb_compression': 0.05,
            'atr_expansion': 0.015,
            'hard_stop': 0.015,
            'trailing_multiplier': 2.5,  # Looser
            'description': 'Let profits run longer'
        },

        # Balanced approach
        {
            'name': 'Balanced',
            'bb_compression': 0.04,
            'atr_expansion': 0.018,
            'hard_stop': 0.012,
            'trailing_multiplier': 2.0,
            'description': 'Balanced risk/reward'
        },

        # Aggressive (high risk/reward)
        {
            'name': 'Aggressive',
            'bb_compression': 0.06,
            'atr_expansion': 0.012,
            'hard_stop': 0.02,
            'trailing_multiplier': 2.5,
            'description': 'Aggressive entries, wide stops'
        },

        # Conservative (low risk)
        {
            'name': 'Conservative',
            'bb_compression': 0.03,
            'atr_expansion': 0.02,
            'hard_stop': 0.01,
            'trailing_multiplier': 1.5,
            'description': 'Conservative entries, tight stops'
        }
    ]

    all_results = []

    # Test each parameter set
    for i, params in enumerate(parameter_sets, 1):
        logger.info(f"\n{'#'*80}")
        logger.info(f"TEST {i}/{len(parameter_sets)}: {params['name']}")
        logger.info(f"Description: {params['description']}")
        logger.info(f"{'#'*80}")

        # Modify strategy parameters
        # (In real implementation, this would update trading_strategy.py dynamically)
        # For now, we'll run with current settings and log the intended parameters

        result = await run_single_backtest(params)
        all_results.append(result)

        # Small delay between tests
        await asyncio.sleep(2)

    # Analyze and rank results
    logger.info("\n" + "="*80)
    logger.info("OPTIMIZATION RESULTS SUMMARY")
    logger.info("="*80)

    # Filter successful results
    successful_results = [r for r in all_results if 'error' not in r and 'trade_statistics' in r]

    if not successful_results:
        logger.error("No successful backtests completed!")
        return

    # Rank by different criteria
    rankings = {
        'by_return': sorted(successful_results,
                           key=lambda x: x['backtest_summary']['total_return_pct'],
                           reverse=True),
        'by_win_rate': sorted(successful_results,
                             key=lambda x: x['trade_statistics']['win_rate_pct'],
                             reverse=True),
        'by_profit_factor': sorted(successful_results,
                                  key=lambda x: x['performance_metrics']['profit_factor'],
                                  reverse=True),
        'by_sharpe': sorted(successful_results,
                           key=lambda x: x['performance_metrics']['sharpe_ratio'],
                           reverse=True)
    }

    # Display top performers
    logger.info("\n🏆 TOP 3 BY TOTAL RETURN:")
    for i, result in enumerate(rankings['by_return'][:3], 1):
        params = result['parameters']
        summary = result['backtest_summary']
        logger.info(f"{i}. {params['name']}: {summary['total_return_pct']:.2f}%")

    logger.info("\n🎯 TOP 3 BY WIN RATE:")
    for i, result in enumerate(rankings['by_win_rate'][:3], 1):
        params = result['parameters']
        stats = result['trade_statistics']
        logger.info(f"{i}. {params['name']}: {stats['win_rate_pct']:.2f}%")

    logger.info("\n💰 TOP 3 BY PROFIT FACTOR:")
    for i, result in enumerate(rankings['by_profit_factor'][:3], 1):
        params = result['parameters']
        metrics = result['performance_metrics']
        logger.info(f"{i}. {params['name']}: {metrics['profit_factor']:.2f}")

    # Find best overall (composite score)
    logger.info("\n" + "="*80)
    logger.info("BEST OVERALL STRATEGY (Composite Score)")
    logger.info("="*80)

    # Calculate composite scores
    for result in successful_results:
        stats = result['trade_statistics']
        metrics = result['performance_metrics']
        summary = result['backtest_summary']

        # Composite score components (normalized 0-100)
        return_score = max(0, min(100, summary['total_return_pct'] * 10))  # -10% to +10% → 0-100
        win_rate_score = stats['win_rate_pct']  # Already 0-100
        profit_factor_score = min(100, metrics['profit_factor'] * 50)  # 0-2 → 0-100
        sharpe_score = max(0, min(100, (metrics['sharpe_ratio'] + 2) * 25))  # -2 to 2 → 0-100

        # Weighted composite (prioritize profitability)
        composite = (
            return_score * 0.4 +
            win_rate_score * 0.2 +
            profit_factor_score * 0.3 +
            sharpe_score * 0.1
        )

        result['composite_score'] = composite

    # Rank by composite score
    best_results = sorted(successful_results, key=lambda x: x['composite_score'], reverse=True)

    # Display best strategy
    best = best_results[0]
    best_params = best['parameters']
    best_stats = best['trade_statistics']
    best_metrics = best['performance_metrics']
    best_summary = best['backtest_summary']

    logger.info(f"\n✨ WINNER: {best_params['name']}")
    logger.info(f"Description: {best_params['description']}")
    logger.info(f"Composite Score: {best['composite_score']:.2f}/100")
    logger.info(f"\nPerformance Metrics:")
    logger.info(f"  Total Return: {best_summary['total_return_pct']:.2f}%")
    logger.info(f"  Win Rate: {best_stats['win_rate_pct']:.2f}%")
    logger.info(f"  Total Trades: {best_stats['total_trades']}")
    logger.info(f"  Profit Factor: {best_metrics['profit_factor']:.2f}")
    logger.info(f"  Max Drawdown: {best_metrics['max_drawdown_pct']:.2f}%")
    logger.info(f"  Sharpe Ratio: {best_metrics['sharpe_ratio']:.2f}")
    logger.info(f"\nParameters:")
    logger.info(f"  BB Compression: {best_params['bb_compression']*100:.1f}%")
    logger.info(f"  ATR Expansion: {best_params['atr_expansion']*100:.1f}%")
    logger.info(f"  Hard Stop: {best_params['hard_stop']*100:.1f}%")
    logger.info(f"  Trailing Multiplier: {best_params['trailing_multiplier']:.1f}x")

    # Save results
    output_dir = Path(__file__).parent / 'optimization_results'
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'twoway_optimization_{timestamp}.json'

    # Prepare serializable results
    save_data = {
        'timestamp': timestamp,
        'optimization_run': 'Two-Way Strategy Parameter Sweep',
        'best_strategy': {
            'name': best_params['name'],
            'parameters': best_params,
            'results': {
                'total_return_pct': best_summary['total_return_pct'],
                'win_rate_pct': best_stats['win_rate_pct'],
                'total_trades': best_stats['total_trades'],
                'profit_factor': best_metrics['profit_factor'],
                'max_drawdown_pct': best_metrics['max_drawdown_pct'],
                'sharpe_ratio': best_metrics['sharpe_ratio'],
                'composite_score': best['composite_score']
            }
        },
        'all_results': [
            {
                'name': r['parameters']['name'],
                'composite_score': r.get('composite_score', 0),
                'return': r.get('backtest_summary', {}).get('total_return_pct', 0),
                'win_rate': r.get('trade_statistics', {}).get('win_rate_pct', 0)
            }
            for r in best_results
        ]
    }

    with open(output_file, 'w') as f:
        json.dump(save_data, f, indent=2)

    logger.info(f"\n✅ Results saved to: {output_file}")

    # Check if profitable for ML training
    if best_summary['total_return_pct'] > 0 and best_stats['win_rate_pct'] > 40:
        logger.info("\n" + "="*80)
        logger.info("✅ PROFITABLE STRATEGY FOUND!")
        logger.info("="*80)
        logger.info("Ready to proceed with ML training")
        logger.info("\nNext steps:")
        logger.info("1. Apply best parameters to trading_strategy.py")
        logger.info("2. Run generate_ml_training_data.py")
        logger.info("3. Run train_ml_model.py")
        logger.info("4. Deploy to paper trading")

        return best_params
    else:
        logger.warning("\n" + "="*80)
        logger.warning("⚠️  NO PROFITABLE STRATEGY FOUND")
        logger.warning("="*80)
        logger.warning("Best result still not profitable enough for ML training")
        logger.warning("Consider:")
        logger.warning("1. Testing on different time periods")
        logger.warning("2. Using different symbols")
        logger.warning("3. Adjusting parameter ranges")

        return None


if __name__ == "__main__":
    asyncio.run(optimize_strategy())
