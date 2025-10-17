"""
Two-Way Strategy Optimization Loop
Dynamically modifies strategy parameters and runs backtests
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
import logging
import re

from backtester import Backtester

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_strategy_parameters(bb_compression, atr_expansion, hard_stop):
    """Update trading_strategy.py with new parameters"""

    strategy_file = Path(__file__).parent / 'trading_strategy.py'
    content = strategy_file.read_text()

    # Update BB compression threshold
    content = re.sub(
        r'is_compressed = bb_bandwidth < [\d.]+',
        f'is_compressed = bb_bandwidth < {bb_compression}',
        content
    )

    # Update ATR expansion threshold
    content = re.sub(
        r'is_expanding = atr_pct > [\d.]+',
        f'is_expanding = atr_pct > {atr_expansion}',
        content
    )

    strategy_file.write_text(content)
    logger.info(f"✓ Updated strategy: BB={bb_compression}, ATR={atr_expansion}, Hard Stop={hard_stop}")


def update_backtester_hard_stop(hard_stop):
    """Update backtester.py with new hard stop"""

    backtester_file = Path(__file__).parent / 'backtester.py'
    content = backtester_file.read_text()

    # Update hard stop percentage
    content = re.sub(
        r"'hard_stop_pct': [\d.]+",
        f"'hard_stop_pct': {hard_stop}",
        content
    )

    backtester_file.write_text(content)


def update_trailing_stop(trailing_multiplier):
    """Update TrailingStopManager with new multiplier"""

    tsm_file = Path(__file__).parent / 'trailing_stop_manager.py'
    if tsm_file.exists():
        content = tsm_file.read_text()

        # Update base_atr_multiplier in __init__
        content = re.sub(
            r'base_atr_multiplier=[\d.]+',
            f'base_atr_multiplier={trailing_multiplier}',
            content
        )

        tsm_file.write_text(content)


async def run_single_test(params):
    """Run backtest with specific parameters"""

    logger.info(f"\n{'='*80}")
    logger.info(f"Testing: {params['name']}")
    logger.info(f"BB Compression: {params['bb_compression']*100:.1f}%")
    logger.info(f"ATR Expansion: {params['atr_expansion']*100:.1f}%")
    logger.info(f"Hard Stop: {params['hard_stop']*100:.1f}%")
    logger.info(f"Trailing: {params['trailing_multiplier']:.1f}x ATR")
    logger.info(f"{'='*80}")

    # Update parameters
    update_strategy_parameters(
        params['bb_compression'],
        params['atr_expansion'],
        params['hard_stop']
    )
    update_backtester_hard_stop(params['hard_stop'])
    update_trailing_stop(params['trailing_multiplier'])

    # Small delay for file system
    await asyncio.sleep(1)

    # Run backtest
    backtester = Backtester(initial_balance=10000.0, leverage=1, symbols=None)

    try:
        results = await backtester.run_backtest(
            start_date='2025-09-16',
            end_date='2025-10-16',
            interval='1h'
        )

        if 'trade_statistics' in results:
            stats = results['trade_statistics']
            metrics = results['performance_metrics']
            summary = results['backtest_summary']

            # Calculate composite score
            return_score = max(0, min(100, summary['total_return_pct'] * 10))
            win_rate_score = stats['win_rate_pct']
            profit_factor_score = min(100, metrics['profit_factor'] * 50)
            sharpe_score = max(0, min(100, (metrics['sharpe_ratio'] + 2) * 25))

            composite = (
                return_score * 0.4 +
                win_rate_score * 0.2 +
                profit_factor_score * 0.3 +
                sharpe_score * 0.1
            )

            logger.info(f"\n✅ Results for {params['name']}:")
            logger.info(f"  Trades: {stats['total_trades']}")
            logger.info(f"  Win Rate: {stats['win_rate_pct']:.2f}%")
            logger.info(f"  Return: {summary['total_return_pct']:.2f}%")
            logger.info(f"  Profit Factor: {metrics['profit_factor']:.2f}")
            logger.info(f"  Composite Score: {composite:.2f}/100")

            return {
                'params': params,
                'stats': stats,
                'metrics': metrics,
                'summary': summary,
                'composite_score': composite
            }
        else:
            logger.warning(f"⚠️  No trades for {params['name']}")
            return {
                'params': params,
                'error': 'No trades executed',
                'composite_score': 0
            }

    except Exception as e:
        logger.error(f"❌ Error for {params['name']}: {e}")
        return {
            'params': params,
            'error': str(e),
            'composite_score': 0
        }


async def run_optimization():
    """Run optimization loop for 2 hours"""

    start_time = datetime.now()
    logger.info("\n" + "="*80)
    logger.info("🚀 TWO-WAY STRATEGY OPTIMIZATION - 2 HOUR RUN")
    logger.info("="*80)
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("Goal: Find profitable parameters for ML training\n")

    # Parameter sets to test
    parameter_sets = [
        {'name': 'Baseline', 'bb_compression': 0.05, 'atr_expansion': 0.015, 'hard_stop': 0.015, 'trailing_multiplier': 1.8},
        {'name': 'Tight_Entry', 'bb_compression': 0.03, 'atr_expansion': 0.02, 'hard_stop': 0.015, 'trailing_multiplier': 1.8},
        {'name': 'Loose_Entry', 'bb_compression': 0.07, 'atr_expansion': 0.01, 'hard_stop': 0.015, 'trailing_multiplier': 1.8},
        {'name': 'Tight_Stop', 'bb_compression': 0.05, 'atr_expansion': 0.015, 'hard_stop': 0.01, 'trailing_multiplier': 1.8},
        {'name': 'Loose_Stop', 'bb_compression': 0.05, 'atr_expansion': 0.015, 'hard_stop': 0.02, 'trailing_multiplier': 1.8},
        {'name': 'Tight_Trail', 'bb_compression': 0.05, 'atr_expansion': 0.015, 'hard_stop': 0.015, 'trailing_multiplier': 1.5},
        {'name': 'Loose_Trail', 'bb_compression': 0.05, 'atr_expansion': 0.015, 'hard_stop': 0.015, 'trailing_multiplier': 2.5},
        {'name': 'Balanced', 'bb_compression': 0.04, 'atr_expansion': 0.018, 'hard_stop': 0.012, 'trailing_multiplier': 2.0},
        {'name': 'Aggressive', 'bb_compression': 0.06, 'atr_expansion': 0.012, 'hard_stop': 0.02, 'trailing_multiplier': 2.5},
        {'name': 'Conservative', 'bb_compression': 0.03, 'atr_expansion': 0.02, 'hard_stop': 0.01, 'trailing_multiplier': 1.5},
        # Additional parameter sweeps
        {'name': 'VeryTight', 'bb_compression': 0.025, 'atr_expansion': 0.025, 'hard_stop': 0.008, 'trailing_multiplier': 1.3},
        {'name': 'VeryLoose', 'bb_compression': 0.08, 'atr_expansion': 0.008, 'hard_stop': 0.025, 'trailing_multiplier': 3.0},
        {'name': 'MediumTight', 'bb_compression': 0.035, 'atr_expansion': 0.016, 'hard_stop': 0.011, 'trailing_multiplier': 1.6},
        {'name': 'MediumLoose', 'bb_compression': 0.06, 'atr_expansion': 0.013, 'hard_stop': 0.018, 'trailing_multiplier': 2.2},
    ]

    all_results = []

    # Run all tests
    for i, params in enumerate(parameter_sets, 1):
        logger.info(f"\n{'#'*80}")
        logger.info(f"Test {i}/{len(parameter_sets)}: {params['name']}")
        logger.info(f"{'#'*80}")

        result = await run_single_test(params)
        all_results.append(result)

        # Check time limit (2 hours)
        elapsed = (datetime.now() - start_time).total_seconds() / 3600
        if elapsed > 2.0:
            logger.warning("\n⏰ 2 hour time limit reached!")
            break

    # Analyze results
    logger.info("\n" + "="*80)
    logger.info("📊 OPTIMIZATION SUMMARY")
    logger.info("="*80)

    # Sort by composite score
    all_results.sort(key=lambda x: x['composite_score'], reverse=True)

    logger.info("\n🏆 TOP 5 STRATEGIES:")
    for i, result in enumerate(all_results[:5], 1):
        params = result['params']
        score = result['composite_score']

        if 'stats' in result:
            logger.info(f"\n{i}. {params['name']} (Score: {score:.2f}/100)")
            logger.info(f"   Return: {result['summary']['total_return_pct']:.2f}%")
            logger.info(f"   Win Rate: {result['stats']['win_rate_pct']:.2f}%")
            logger.info(f"   Trades: {result['stats']['total_trades']}")
            logger.info(f"   PF: {result['metrics']['profit_factor']:.2f}")
        else:
            logger.info(f"\n{i}. {params['name']} (Score: {score:.2f}/100) - {result.get('error', 'No data')}")

    # Best strategy
    best = all_results[0]
    if 'stats' in best:
        logger.info("\n" + "="*80)
        logger.info("✨ BEST STRATEGY FOUND")
        logger.info("="*80)
        logger.info(f"Name: {best['params']['name']}")
        logger.info(f"Composite Score: {best['composite_score']:.2f}/100")
        logger.info(f"\nParameters:")
        logger.info(f"  BB Compression: {best['params']['bb_compression']*100:.1f}%")
        logger.info(f"  ATR Expansion: {best['params']['atr_expansion']*100:.1f}%")
        logger.info(f"  Hard Stop: {best['params']['hard_stop']*100:.1f}%")
        logger.info(f"  Trailing Multiplier: {best['params']['trailing_multiplier']:.1f}x")
        logger.info(f"\nPerformance:")
        logger.info(f"  Total Return: {best['summary']['total_return_pct']:.2f}%")
        logger.info(f"  Win Rate: {best['stats']['win_rate_pct']:.2f}%")
        logger.info(f"  Total Trades: {best['stats']['total_trades']}")
        logger.info(f"  Profit Factor: {best['metrics']['profit_factor']:.2f}")
        logger.info(f"  Max Drawdown: {best['metrics']['max_drawdown_pct']:.2f}%")
        logger.info(f"  Sharpe Ratio: {best['metrics']['sharpe_ratio']:.2f}")

        # Apply best parameters
        logger.info("\n🔧 Applying best parameters to trading_strategy.py...")
        update_strategy_parameters(
            best['params']['bb_compression'],
            best['params']['atr_expansion'],
            best['params']['hard_stop']
        )
        update_backtester_hard_stop(best['params']['hard_stop'])
        update_trailing_stop(best['params']['trailing_multiplier'])
        logger.info("✅ Best parameters applied!")

        # Check profitability
        if best['summary']['total_return_pct'] > 0 and best['stats']['win_rate_pct'] > 40:
            logger.info("\n" + "="*80)
            logger.info("✅✅✅ PROFITABLE STRATEGY CONFIRMED! ✅✅✅")
            logger.info("="*80)
            logger.info("Ready for ML training!")
            logger.info("\nRunning ML training pipeline...")

            # Run ML training
            await asyncio.sleep(2)
            import subprocess
            subprocess.run(['python', 'generate_ml_training_data.py'])
            subprocess.run(['python', 'train_ml_model.py'])

            logger.info("\n✅ ML TRAINING COMPLETE!")
        else:
            logger.warning("\n⚠️  Best strategy still not profitable enough")
            logger.warning("Consider testing different time periods or coins")

    # Save results
    output_dir = Path(__file__).parent / 'optimization_results'
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'optimization_{timestamp}.json'

    save_data = {
        'timestamp': timestamp,
        'duration_hours': (datetime.now() - start_time).total_seconds() / 3600,
        'tests_completed': len(all_results),
        'best_strategy': {
            'name': best['params']['name'],
            'score': best['composite_score'],
            'parameters': best['params'],
            'results': best.get('summary', {})
        },
        'all_results': [
            {
                'name': r['params']['name'],
                'score': r['composite_score'],
                'return': r.get('summary', {}).get('total_return_pct', 0)
            }
            for r in all_results
        ]
    }

    with open(output_file, 'w') as f:
        json.dump(save_data, f, indent=2)

    logger.info(f"\n📄 Results saved: {output_file}")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60
    logger.info(f"\n⏱️  Total runtime: {duration:.1f} minutes")
    logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(run_optimization())
