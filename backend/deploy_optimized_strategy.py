"""
Deploy Optimized Strategy - Post-06:00 Automation Script
Extracts best version from continuous optimization and deploys to production

Run this script AFTER 06:00 KST when continuous optimization completes
"""
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StrategyDeployer:
    """Deploy optimized strategy to production system"""

    def __init__(self, backend_dir: Path):
        self.backend_dir = backend_dir
        self.optimization_history_file = backend_dir / 'claudedocs' / 'continuous_optimization_history.json'
        self.coin_params_file = backend_dir / 'coin_specific_params.json'

    def load_optimization_results(self) -> dict:
        """Load continuous optimization results"""
        logger.info("📊 Loading optimization results...")

        if not self.optimization_history_file.exists():
            raise FileNotFoundError(
                f"Optimization history not found: {self.optimization_history_file}\n"
                "Make sure continuous optimization completed successfully."
            )

        with open(self.optimization_history_file, 'r') as f:
            history = json.load(f)

        logger.info(f"✅ Loaded optimization history")
        logger.info(f"   Total versions tested: {len(history.get('versions', []))}")
        logger.info(f"   Best version: v{history['best_version']['version']}")
        logger.info(f"   Best score: {history['best_version']['composite_score']:.2f}")

        return history

    def extract_best_strategy(self, history: dict) -> dict:
        """Extract best performing strategy configuration"""
        best = history['best_version']

        strategy_config = {
            'version': best['version'],
            'performance': {
                'total_return': best['total_return'],
                'win_rate': best['win_rate'],
                'composite_score': best['composite_score'],
                'total_trades': best['total_trades'],
                'profit_factor': best.get('profit_factor', 0),
                'sharpe': best.get('sharpe', 0),
                'max_drawdown': best.get('max_drawdown', 0)
            },
            'symbols': best['symbols'],
            'excluded_symbols': history.get('excluded_symbols', []),
            'parameters': best['params']
        }

        logger.info(f"\n{'='*80}")
        logger.info(f"🏆 BEST STRATEGY: v{strategy_config['version']}")
        logger.info(f"{'='*80}")
        logger.info(f"  Return:        {strategy_config['performance']['total_return']:+.2f}%")
        logger.info(f"  Win Rate:      {strategy_config['performance']['win_rate']:.2f}%")
        logger.info(f"  Total Trades:  {strategy_config['performance']['total_trades']}")
        logger.info(f"  Profit Factor: {strategy_config['performance']['profit_factor']:.2f}")
        logger.info(f"  Sharpe Ratio:  {strategy_config['performance']['sharpe']:.2f}")
        logger.info(f"  Max Drawdown:  {strategy_config['performance']['max_drawdown']:.2f}%")
        logger.info(f"\n📦 Active Symbols ({len(strategy_config['symbols'])}):")
        logger.info(f"  {', '.join(strategy_config['symbols'])}")

        if strategy_config['excluded_symbols']:
            logger.info(f"\n❌ Excluded Symbols ({len(strategy_config['excluded_symbols'])}):")
            logger.info(f"  {', '.join(strategy_config['excluded_symbols'])}")

        logger.info(f"\n🔧 Parameters:")
        for key, value in strategy_config['parameters'].items():
            logger.info(f"  {key}: {value}")
        logger.info(f"{'='*80}\n")

        return strategy_config

    def backup_current_config(self):
        """Backup current coin_specific_params.json"""
        if self.coin_params_file.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.coin_params_file.parent / f"coin_specific_params.json.backup_{timestamp}"
            shutil.copy(self.coin_params_file, backup_file)
            logger.info(f"💾 Backed up current config to: {backup_file.name}")

    def update_coin_parameters(self, strategy_config: dict):
        """Update coin_specific_params.json with optimized strategy"""
        logger.info("\n🔧 Updating coin_specific_params.json...")

        # Load current config
        with open(self.coin_params_file, 'r') as f:
            config = json.load(f)

        # Update version
        old_version = config.get('version', 'unknown')
        config['version'] = strategy_config['version']

        # Update parameters for active symbols only
        active_symbols = set(strategy_config['symbols'])

        # Mark excluded coins
        for symbol, params in config['coin_parameters'].items():
            if symbol not in active_symbols:
                params['excluded'] = True
                params['exclusion_reason'] = f"Excluded by continuous optimization (v{strategy_config['version']})"
            else:
                params['excluded'] = False
                if 'exclusion_reason' in params:
                    del params['exclusion_reason']

        # Update dynamic hard stop multiplier if present
        if 'hard_stop_atr_multiplier' in strategy_config['parameters']:
            multiplier = strategy_config['parameters']['hard_stop_atr_multiplier']
            for symbol in active_symbols:
                if symbol in config['coin_parameters']:
                    config['coin_parameters'][symbol]['hard_stop_atr_multiplier'] = multiplier

        # Update improvement history
        config[f'v{strategy_config["version"]}_deployment'] = {
            'deployed_at': datetime.now().isoformat(),
            'previous_version': old_version,
            'performance': strategy_config['performance'],
            'excluded_symbols': strategy_config['excluded_symbols'],
            'reason': 'Deployed best version from continuous optimization',
            'optimization_deadline': '2025-10-17T06:00:00'
        }

        # Save updated config
        with open(self.coin_params_file, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"✅ Updated coin_specific_params.json")
        logger.info(f"   Version: {old_version} → v{strategy_config['version']}")
        logger.info(f"   Active symbols: {len(active_symbols)}")
        logger.info(f"   Excluded symbols: {len(strategy_config['excluded_symbols'])}")

    def create_deployment_report(self, strategy_config: dict):
        """Create deployment report"""
        report_file = self.backend_dir / 'claudedocs' / f"deployment_v{strategy_config['version']}.md"

        report = f"""# Strategy Deployment Report - v{strategy_config['version']}

**Deployment Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}
**Optimization Period**: 2025-10-17 00:00 - 06:00 KST

---

## 🏆 Best Strategy Performance

| Metric | Value |
|--------|-------|
| Total Return | {strategy_config['performance']['total_return']:+.2f}% |
| Win Rate | {strategy_config['performance']['win_rate']:.2f}% |
| Total Trades | {strategy_config['performance']['total_trades']} |
| Profit Factor | {strategy_config['performance']['profit_factor']:.2f} |
| Sharpe Ratio | {strategy_config['performance']['sharpe']:.2f} |
| Max Drawdown | {strategy_config['performance']['max_drawdown']:.2f}% |
| Composite Score | {strategy_config['performance']['composite_score']:.2f} |

---

## 📦 Active Trading Symbols

{', '.join(strategy_config['symbols'])}

**Total**: {len(strategy_config['symbols'])} coins

---

## ❌ Excluded Symbols

"""
        if strategy_config['excluded_symbols']:
            report += '\n'.join([f"- {symbol}" for symbol in strategy_config['excluded_symbols']])
            report += f"\n\n**Total**: {len(strategy_config['excluded_symbols'])} coins excluded\n"
        else:
            report += "None - all 10 original coins remain active\n"

        report += f"""
---

## 🔧 Strategy Parameters

"""
        for key, value in strategy_config['parameters'].items():
            report += f"- **{key}**: {value}\n"

        report += f"""
---

## 📊 Deployment Actions

1. ✅ Backed up current coin_specific_params.json
2. ✅ Updated coin_specific_params.json with v{strategy_config['version']} parameters
3. ✅ Marked excluded symbols in configuration
4. ✅ Updated hard stop parameters
5. ✅ Created deployment report

---

## 🎯 Next Steps

1. **Backend**: Already updated with optimized parameters
2. **Frontend**: Run `update_frontend_for_production.py` to remove hardcoded data
3. **Testing**: Monitor real-time trading for 1-2 hours
4. **Production**: Deploy to VPS if paper trading shows stable performance

---

**Generated by**: Continuous Optimization System
**Strategy Version**: v{strategy_config['version']}
**Optimization Iterations**: See `continuous_optimization_history.json` for full details
"""

        with open(report_file, 'w') as f:
            f.write(report)

        logger.info(f"📄 Created deployment report: {report_file.name}")

    async def deploy(self):
        """Main deployment flow"""
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 DEPLOYING OPTIMIZED STRATEGY")
        logger.info(f"{'='*80}")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}\n")

        try:
            # 1. Load optimization results
            history = self.load_optimization_results()

            # 2. Extract best strategy
            strategy_config = self.extract_best_strategy(history)

            # 3. Backup current config
            self.backup_current_config()

            # 4. Update coin parameters
            self.update_coin_parameters(strategy_config)

            # 5. Create deployment report
            self.create_deployment_report(strategy_config)

            logger.info(f"\n{'='*80}")
            logger.info(f"✅ DEPLOYMENT COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"Strategy v{strategy_config['version']} is now ACTIVE")
            logger.info(f"\n📋 Next: Run update_frontend_for_production.py to update UI")
            logger.info(f"{'='*80}\n")

            return strategy_config

        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}", exc_info=True)
            raise


async def main():
    """Main entry point"""
    backend_dir = Path(__file__).parent
    deployer = StrategyDeployer(backend_dir)

    await deployer.deploy()


if __name__ == "__main__":
    asyncio.run(main())
