"""
Continuous Optimization Loop - Auto-improve strategy until deadline
Runs: v5.0 → analyze → v6.0 → analyze → v7.0 → ... until 2025-10-17 06:00 KST

Improvement strategies per iteration:
- Analyze per-coin performance (win rate, P&L, drawdown)
- Identify weak performers (XPL, etc.)
- Test exclusion/adjustment strategies
- Fine-tune hard stops, ATR multipliers
- Optimize confidence thresholds
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from backtester import Backtester
from trailing_stop_manager import TrailingStopManager
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContinuousOptimizer:
    """Continuous strategy optimization until deadline"""

    def __init__(self, deadline_kst: datetime):
        """Initialize optimizer

        Args:
            deadline_kst: Deadline in KST (2025-10-17 06:00)
        """
        self.deadline_kst = deadline_kst
        self.current_version = "5.0"
        self.version_history = []
        self.best_version = None
        self.best_score = -float('inf')

        # Optimization parameters
        self.symbols = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
            'DOGE/USDT', 'XPL/USDT', 'SUI/USDT', '1000PEPE/USDT', 'HYPE/USDT'
        ]

        self.excluded_symbols = set()  # Track excluded coins

        logger.info(f"🚀 Continuous Optimizer initialized")
        logger.info(f"⏰ Deadline: {deadline_kst.strftime('%Y-%m-%d %H:%M KST')}")

    def time_remaining(self) -> float:
        """Calculate remaining time in hours"""
        now_kst = datetime.now()  # Assuming system is in KST
        remaining = (self.deadline_kst - now_kst).total_seconds() / 3600
        return max(0, remaining)

    def should_continue(self) -> bool:
        """Check if we should continue optimization"""
        remaining = self.time_remaining()

        if remaining <= 0:
            logger.info(f"⏰ Deadline reached! Stopping optimization.")
            return False

        # Need at least 2.5 hours for a full multi-timeframe backtest
        if remaining < 2.5:
            logger.warning(f"⚠️  Only {remaining:.1f}h remaining - not enough for full backtest")
            return False

        return True

    async def run_quick_validation(self, version: str, symbols: list, params: dict) -> dict:
        """Run quick 1-month validation (faster iteration)

        Args:
            version: Version string (e.g., "6.0")
            symbols: List of trading symbols
            params: Strategy parameters

        Returns:
            Results dictionary
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🧪 Quick Validation: v{version}")
        logger.info(f"{'='*80}")
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Parameters: {json.dumps(params, indent=2)}")

        # 1-month test only for speed
        end_date = datetime(2025, 10, 16)
        start_date = end_date - timedelta(days=30)

        backtester = Backtester(
            initial_balance=10000.0,
            leverage=10,
            symbols=symbols
        )

        # Apply custom parameters if provided
        if params.get('hard_stop_atr_multiplier'):
            backtester.trailing_stop_manager.hard_stop_atr_multiplier = params['hard_stop_atr_multiplier']

        try:
            results = await backtester.run_backtest(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                interval='1h'
            )

            # Extract metrics
            summary = results.get('backtest_summary', {})
            stats = results.get('trade_statistics', {})
            metrics = results.get('performance_metrics', {})

            total_return = summary.get('total_return_pct', 0)
            win_rate = stats.get('win_rate_pct', 0)
            total_trades = stats.get('total_trades', 0)
            profit_factor = metrics.get('profit_factor', 0)
            sharpe = metrics.get('sharpe_ratio', 0)
            max_drawdown = metrics.get('max_drawdown_pct', 0)

            # Per-coin analysis
            coin_stats = {}
            coin_pnl = {}
            for trade in backtester.trade_history:
                symbol = trade['symbol'].replace('_LONG', '').replace('_SHORT', '')
                if symbol not in coin_stats:
                    coin_stats[symbol] = {'trades': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0}

                coin_stats[symbol]['trades'] += 1
                coin_stats[symbol]['total_pnl'] += trade['pnl']

                if trade['pnl'] > 0:
                    coin_stats[symbol]['wins'] += 1
                else:
                    coin_stats[symbol]['losses'] += 1

            # Calculate composite score
            # Weighted: 40% return, 30% win_rate, 20% sharpe, 10% profit_factor
            composite_score = (
                total_return * 0.4 +
                (win_rate - 30) * 0.3 +  # Normalize win rate (30% baseline)
                sharpe * 10 * 0.2 +  # Normalize sharpe (scale by 10)
                (profit_factor - 1) * 20 * 0.1  # Normalize profit factor
            )

            logger.info(f"\n📊 v{version} Results:")
            logger.info(f"  Total Return:    {total_return:+.2f}%")
            logger.info(f"  Win Rate:        {win_rate:.2f}%")
            logger.info(f"  Total Trades:    {total_trades}")
            logger.info(f"  Profit Factor:   {profit_factor:.2f}")
            logger.info(f"  Sharpe Ratio:    {sharpe:.2f}")
            logger.info(f"  Max Drawdown:    {max_drawdown:.2f}%")
            logger.info(f"  Composite Score: {composite_score:.2f}")

            # Display per-coin performance
            logger.info(f"\n🪙 Per-Coin Performance:")
            for symbol in sorted(coin_stats.keys()):
                stats_data = coin_stats[symbol]
                coin_win_rate = (stats_data['wins'] / stats_data['trades'] * 100) if stats_data['trades'] > 0 else 0
                avg_pnl = stats_data['total_pnl'] / stats_data['trades'] if stats_data['trades'] > 0 else 0

                status = "✅" if stats_data['total_pnl'] > 0 else "❌"
                logger.info(f"  {status} {symbol}: {stats_data['trades']} trades, "
                          f"{coin_win_rate:.1f}% WR, ${stats_data['total_pnl']:.2f} P&L, "
                          f"${avg_pnl:.2f} avg")

            return {
                'version': version,
                'total_return': total_return,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'profit_factor': profit_factor,
                'sharpe': sharpe,
                'max_drawdown': max_drawdown,
                'composite_score': composite_score,
                'coin_stats': coin_stats,
                'symbols': symbols,
                'params': params
            }

        except Exception as e:
            logger.error(f"❌ v{version} backtest failed: {e}", exc_info=True)
            return None

    def analyze_and_improve(self, results: dict) -> dict:
        """Analyze results and suggest improvements

        Args:
            results: Backtest results

        Returns:
            Improvement suggestions
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 ANALYZING v{results['version']} FOR IMPROVEMENTS")
        logger.info(f"{'='*80}")

        improvements = {
            'version': self.increment_version(results['version']),
            'changes': [],
            'symbols': results['symbols'].copy(),
            'params': results['params'].copy()
        }

        coin_stats = results.get('coin_stats', {})

        # 1. Identify losing coins
        losing_coins = []
        for symbol, stats in coin_stats.items():
            if stats['total_pnl'] < 0:
                losing_coins.append((symbol, stats['total_pnl']))

        losing_coins.sort(key=lambda x: x[1])  # Sort by worst P&L

        if losing_coins:
            logger.info(f"\n❌ Losing Coins ({len(losing_coins)}):")
            for symbol, pnl in losing_coins:
                logger.info(f"  {symbol}: ${pnl:.2f}")

            # Exclude worst performing coin (if not already excluded)
            if losing_coins:
                worst_coin = losing_coins[0][0]
                if worst_coin not in self.excluded_symbols:
                    improvements['symbols'].remove(worst_coin)
                    self.excluded_symbols.add(worst_coin)
                    improvements['changes'].append(f"EXCLUDE {worst_coin} (P&L: ${losing_coins[0][1]:.2f})")
                    logger.info(f"  ⚠️  Excluding {worst_coin} from next version")

        # 2. Low win rate coins (< 30%)
        low_wr_coins = []
        for symbol, stats in coin_stats.items():
            if stats['trades'] > 0:
                win_rate = (stats['wins'] / stats['trades']) * 100
                if win_rate < 30 and symbol in improvements['symbols']:
                    low_wr_coins.append((symbol, win_rate))

        if low_wr_coins:
            logger.info(f"\n⚠️  Low Win Rate Coins (<30%):")
            for symbol, wr in low_wr_coins:
                logger.info(f"  {symbol}: {wr:.1f}%")

        # 3. Adjust hard stop multiplier based on drawdown
        current_multiplier = results['params'].get('hard_stop_atr_multiplier', 2.0)
        max_drawdown = results.get('max_drawdown', 0)

        if max_drawdown > 20:
            # Too much drawdown - tighten stops
            new_multiplier = max(1.5, current_multiplier - 0.2)
            improvements['params']['hard_stop_atr_multiplier'] = new_multiplier
            improvements['changes'].append(f"TIGHTEN hard stop: {current_multiplier:.1f} → {new_multiplier:.1f} (drawdown {max_drawdown:.1f}%)")
            logger.info(f"  🛡️  Tightening hard stop multiplier: {current_multiplier:.1f} → {new_multiplier:.1f}")
        elif max_drawdown < 10 and results['win_rate'] < 35:
            # Low drawdown but low win rate - widen stops
            new_multiplier = min(3.0, current_multiplier + 0.2)
            improvements['params']['hard_stop_atr_multiplier'] = new_multiplier
            improvements['changes'].append(f"WIDEN hard stop: {current_multiplier:.1f} → {new_multiplier:.1f} (low WR, safe DD)")
            logger.info(f"  📈 Widening hard stop multiplier: {current_multiplier:.1f} → {new_multiplier:.1f}")

        # 4. Adjust confidence threshold based on trade count
        total_trades = results.get('total_trades', 0)
        if total_trades < 150:
            # Too few trades - lower confidence threshold
            improvements['changes'].append(f"RECOMMENDATION: Lower confidence threshold (only {total_trades} trades)")
            logger.info(f"  💡 Recommendation: Lower confidence threshold to generate more trades")
        elif total_trades > 400:
            # Too many trades - raise confidence threshold
            improvements['changes'].append(f"RECOMMENDATION: Raise confidence threshold (too many {total_trades} trades)")
            logger.info(f"  💡 Recommendation: Raise confidence threshold to filter signals")

        logger.info(f"\n✨ Improvements for v{improvements['version']}:")
        for change in improvements['changes']:
            logger.info(f"  • {change}")

        return improvements

    def increment_version(self, version: str) -> str:
        """Increment version number"""
        major, minor = version.split('.')
        new_minor = int(minor) + 1
        return f"{major}.{new_minor}"

    def save_version_history(self):
        """Save optimization history to file"""
        output_path = Path(__file__).parent / 'claudedocs' / 'continuous_optimization_history.json'

        history_data = {
            'deadline_kst': self.deadline_kst.isoformat(),
            'best_version': self.best_version,
            'best_score': self.best_score,
            'excluded_symbols': list(self.excluded_symbols),
            'versions': self.version_history
        }

        with open(output_path, 'w') as f:
            json.dump(history_data, f, indent=2)

        logger.info(f"💾 Optimization history saved to {output_path}")

    async def run_continuous_loop(self):
        """Main continuous optimization loop"""
        logger.info(f"\n{'='*80}")
        logger.info(f"🔄 STARTING CONTINUOUS OPTIMIZATION LOOP")
        logger.info(f"{'='*80}")
        logger.info(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}")
        logger.info(f"Deadline: {self.deadline_kst.strftime('%Y-%m-%d %H:%M:%S KST')}")
        logger.info(f"Time available: {self.time_remaining():.1f} hours")

        iteration = 0

        # Start with current v5.0 parameters
        current_params = {
            'hard_stop_atr_multiplier': 2.0,
            'use_dynamic_hard_stop': True
        }

        current_symbols = self.symbols.copy()

        while self.should_continue():
            iteration += 1
            remaining = self.time_remaining()

            logger.info(f"\n{'#'*80}")
            logger.info(f"🔄 ITERATION {iteration} - v{self.current_version}")
            logger.info(f"⏰ Time remaining: {remaining:.1f} hours")
            logger.info(f"{'#'*80}")

            # Run quick validation
            results = await self.run_quick_validation(
                self.current_version,
                current_symbols,
                current_params
            )

            if not results:
                logger.error(f"❌ Iteration {iteration} failed - skipping")
                break

            # Track in history
            self.version_history.append(results)

            # Check if this is the best version
            if results['composite_score'] > self.best_score:
                self.best_score = results['composite_score']
                self.best_version = results
                logger.info(f"🏆 NEW BEST VERSION: v{self.current_version} (score: {self.best_score:.2f})")

            # Save progress
            self.save_version_history()

            # Check if we have time for another iteration
            if not self.should_continue():
                logger.info(f"⏰ No time for another iteration - stopping")
                break

            # Analyze and get improvements
            improvements = self.analyze_and_improve(results)

            # Update for next iteration
            self.current_version = improvements['version']
            current_symbols = improvements['symbols']
            current_params = improvements['params']

            logger.info(f"\n⏭️  Next iteration: v{self.current_version}")
            logger.info(f"  Symbols: {len(current_symbols)}/10")
            logger.info(f"  Excluded: {', '.join(self.excluded_symbols) if self.excluded_symbols else 'None'}")

        # Final summary
        logger.info(f"\n{'='*80}")
        logger.info(f"🏁 OPTIMIZATION COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Total iterations: {iteration}")
        logger.info(f"Versions tested: {len(self.version_history)}")
        logger.info(f"\n🏆 BEST VERSION: v{self.best_version['version']}")
        logger.info(f"  Total Return:    {self.best_version['total_return']:+.2f}%")
        logger.info(f"  Win Rate:        {self.best_version['win_rate']:.2f}%")
        logger.info(f"  Composite Score: {self.best_version['composite_score']:.2f}")
        logger.info(f"  Symbols:         {', '.join(self.best_version['symbols'])}")
        logger.info(f"  Excluded:        {', '.join(self.excluded_symbols) if self.excluded_symbols else 'None'}")
        logger.info(f"\n💾 Full history saved to claudedocs/continuous_optimization_history.json")


async def main():
    """Main entry point"""
    # Deadline: 2025-10-17 06:00 KST
    deadline = datetime(2025, 10, 17, 6, 0, 0)

    optimizer = ContinuousOptimizer(deadline_kst=deadline)
    await optimizer.run_continuous_loop()


if __name__ == "__main__":
    asyncio.run(main())
