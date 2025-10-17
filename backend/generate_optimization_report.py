"""
Generate comprehensive optimization report after 2-hour run
"""
from pathlib import Path
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_report():
    """Generate comprehensive optimization report"""

    logger.info("\n" + "="*80)
    logger.info("📊 TWO-WAY STRATEGY OPTIMIZATION REPORT")
    logger.info("="*80)

    # Find latest optimization result
    results_dir = Path(__file__).parent / 'optimization_results'

    if not results_dir.exists():
        logger.error("No optimization results found!")
        return

    result_files = list(results_dir.glob('optimization_*.json'))
    if not result_files:
        logger.error("No optimization files found!")
        return

    latest_file = max(result_files, key=lambda x: x.stat().st_mtime)
    logger.info(f"Latest results: {latest_file.name}")

    with open(latest_file, 'r') as f:
        data = json.load(f)

    # Generate report
    report = []
    report.append("\n" + "="*80)
    report.append("📈 TWO-WAY SIMULTANEOUS ENTRY STRATEGY OPTIMIZATION REPORT")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Optimization Run: {data['timestamp']}")
    report.append(f"Duration: {data['duration_hours']:.2f} hours")
    report.append(f"Tests Completed: {data['tests_completed']}")
    report.append("")

    # Best strategy
    best = data['best_strategy']
    report.append("="*80)
    report.append("🏆 BEST STRATEGY FOUND")
    report.append("="*80)
    report.append(f"Name: {best['name']}")
    report.append(f"Composite Score: {best['score']:.2f}/100")
    report.append("")
    report.append("📋 Parameters:")
    params = best['parameters']
    report.append(f"  • BB Compression Threshold: {params['bb_compression']*100:.1f}%")
    report.append(f"  • ATR Expansion Threshold: {params['atr_expansion']*100:.1f}%")
    report.append(f"  • Hard Stop Loss: {params['hard_stop']*100:.1f}%")
    report.append(f"  • Trailing Stop Multiplier: {params['trailing_multiplier']:.1f}x ATR")
    report.append("")

    if 'results' in best and best['results']:
        results = best['results']
        report.append("📊 Performance Metrics:")
        report.append(f"  • Total Return: {results.get('total_return_pct', 0):.2f}%")
        report.append(f"  • Win Rate: {results.get('win_rate_pct', 0):.2f}%")
        report.append(f"  • Total Trades: {results.get('total_trades', 0)}")
        report.append(f"  • Profit Factor: {results.get('profit_factor', 0):.2f}")
        report.append(f"  • Max Drawdown: {results.get('max_drawdown_pct', 0):.2f}%")
        report.append(f"  • Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
        report.append("")

    # All results ranking
    report.append("="*80)
    report.append("📋 ALL STRATEGIES RANKED")
    report.append("="*80)

    all_results = data['all_results']
    for i, result in enumerate(all_results[:10], 1):  # Top 10
        report.append(f"{i}. {result['name']} | Score: {result['score']:.2f} | Return: {result['return']:.2f}%")

    report.append("")

    # Profitability assessment
    report.append("="*80)
    report.append("💰 PROFITABILITY ASSESSMENT")
    report.append("="*80)

    is_profitable = best['score'] > 50 and results.get('total_return_pct', 0) > 0
    if is_profitable:
        report.append("✅ PROFITABLE STRATEGY FOUND!")
        report.append("")
        report.append("Strategy meets criteria for ML training:")
        report.append(f"  ✓ Positive return: {results.get('total_return_pct', 0):.2f}% > 0%")
        report.append(f"  ✓ Decent win rate: {results.get('win_rate_pct', 0):.2f}% > 40%")
        report.append(f"  ✓ Profit factor: {results.get('profit_factor', 0):.2f} > 1.0")
        report.append("")
        report.append("✅ READY FOR ML TRAINING!")
        report.append("")
        report.append("Next Steps:")
        report.append("1. Best parameters have been applied to trading_strategy.py")
        report.append("2. Run generate_ml_training_data.py")
        report.append("3. Run train_ml_model.py")
        report.append("4. Deploy to paper trading")
    else:
        report.append("⚠️  NO PROFITABLE STRATEGY FOUND")
        report.append("")
        report.append("Best strategy does not meet profitability criteria:")
        report.append(f"  Return: {results.get('total_return_pct', 0):.2f}% (target: >0%)")
        report.append(f"  Win Rate: {results.get('win_rate_pct', 0):.2f}% (target: >40%)")
        report.append(f"  Profit Factor: {results.get('profit_factor', 0):.2f} (target: >1.0)")
        report.append("")
        report.append("Recommendations:")
        report.append("1. Test on different time periods (e.g., 60 days, 90 days)")
        report.append("2. Test on different coin selections")
        report.append("3. Adjust parameter ranges")
        report.append("4. Consider alternative strategies")

    report.append("")
    report.append("="*80)
    report.append("📄 REPORT COMPLETE")
    report.append("="*80)
    report.append("")

    # Print report
    report_text = "\n".join(report)
    print(report_text)

    # Save report
    report_file = results_dir / f"optimization_report_{data['timestamp']}.txt"
    with open(report_file, 'w') as f:
        f.write(report_text)

    logger.info(f"\n✅ Report saved to: {report_file}")

    return is_profitable


if __name__ == "__main__":
    generate_report()
