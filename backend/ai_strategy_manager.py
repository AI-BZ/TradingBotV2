"""
Real-time AI Strategy Manager
Dynamically switches trading strategies based on market conditions and performance
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from binance_client import BinanceClient
from strategy_optimizer import AIStrategyOptimizer, StrategyConfig, MarketCondition, StrategyPerformance
from ml_engine import MLEngine
from technical_indicators import TechnicalIndicators
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StrategySwitch:
    """Record of strategy switch event"""
    timestamp: datetime
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    old_strategy: str
    new_strategy: str
    reason: str  # 'market_regime_change', 'poor_performance', 'ml_signal'
    market_condition: MarketCondition


@dataclass
class ActiveStrategy:
    """Currently active strategy for a symbol/direction"""
    symbol: str
    direction: str
    strategy: StrategyConfig
    activated_at: datetime
    market_condition: MarketCondition
    performance_score: float = 0.0
    trades_count: int = 0
    win_count: int = 0
    total_pnl: float = 0.0


class AIStrategyManager:
    """
    Real-time AI Strategy Manager

    Responsibilities:
    1. Monitor market conditions continuously
    2. Detect regime changes (trending → ranging, etc.)
    3. Switch strategies automatically when:
       - Market regime changes
       - Strategy performance degrades
       - ML model suggests better alternative
    4. Learn from performance and improve selection
    """

    def __init__(self, client: BinanceClient, ml_engine: Optional[MLEngine] = None):
        """Initialize AI Strategy Manager

        Args:
            client: Binance client for market data
            ml_engine: Optional ML engine for predictions
        """
        self.client = client
        self.ml_engine = ml_engine
        self.optimizer = AIStrategyOptimizer(client)

        # Active strategies per symbol/direction
        self.active_strategies: Dict[str, Dict[str, ActiveStrategy]] = {}

        # Strategy switch history
        self.switch_history: List[StrategySwitch] = []

        # Performance monitoring
        self.monitoring_interval = 300  # 5 minutes
        self.regime_check_interval = 600  # 10 minutes
        self.performance_check_interval = 900  # 15 minutes

        # Thresholds for strategy switching
        self.regime_change_threshold = 0.15  # 15% volatility change
        self.poor_performance_threshold = -0.02  # -2% return triggers review
        self.min_trades_before_switch = 5  # Minimum trades before evaluating performance

        logger.info("AIStrategyManager initialized")

    async def initialize_strategies(self, symbols: List[str]):
        """Initialize optimal strategies for all symbols

        Args:
            symbols: List of trading symbols
        """
        logger.info(f"Initializing AI strategies for {len(symbols)} symbols...")

        # Get optimal strategies from optimizer
        optimal_strategies = await self.optimizer.optimize_all_coins(symbols)

        # Activate strategies
        for symbol in symbols:
            self.active_strategies[symbol] = {}

            for direction in ['LONG', 'SHORT']:
                strategy = optimal_strategies[symbol][direction]['strategy']
                market_cond = optimal_strategies[symbol][direction]['market_condition']

                active_strat = ActiveStrategy(
                    symbol=symbol,
                    direction=direction,
                    strategy=strategy,
                    activated_at=datetime.now(),
                    market_condition=market_cond
                )

                self.active_strategies[symbol][direction] = active_strat

                logger.info(f"{symbol} {direction}: Activated {strategy.name} strategy "
                          f"(Market: {market_cond.regime}, Vol: {market_cond.volatility:.3f})")

    async def monitor_and_adapt(self, duration_hours: float = 24.0):
        """Continuously monitor market and adapt strategies

        Args:
            duration_hours: How long to monitor (hours)
        """
        logger.info(f"Starting AI strategy monitoring for {duration_hours} hours...")

        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)

        iteration = 0

        while datetime.now() < end_time:
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"AI Monitoring Iteration #{iteration}")
            logger.info(f"{'='*60}")

            # Check all active strategies
            for symbol in self.active_strategies.keys():
                await self.check_and_adapt_strategy(symbol)

            # Wait for next iteration
            logger.info(f"\nWaiting {self.monitoring_interval}s until next check...")
            await asyncio.sleep(self.monitoring_interval)

        logger.info(f"\nAI monitoring completed after {duration_hours} hours")
        self.save_switch_history()

    async def check_and_adapt_strategy(self, symbol: str):
        """Check if strategy should be switched for a symbol

        Args:
            symbol: Trading symbol to check
        """
        logger.info(f"\n🤖 AI Strategy Check: {symbol}")

        for direction in ['LONG', 'SHORT']:
            active = self.active_strategies[symbol][direction]

            # 1. Check market regime change
            current_market = await self.optimizer.analyze_market_condition(symbol)
            regime_changed = await self.detect_regime_change(active, current_market)

            if regime_changed:
                await self.switch_strategy(
                    symbol, direction,
                    reason='market_regime_change',
                    new_market_condition=current_market
                )
                continue

            # 2. Check strategy performance
            if active.trades_count >= self.min_trades_before_switch:
                poor_performance = self.check_poor_performance(active)

                if poor_performance:
                    await self.switch_strategy(
                        symbol, direction,
                        reason='poor_performance',
                        new_market_condition=current_market
                    )
                    continue

            # 3. ML-based recommendation (if ML engine available)
            if self.ml_engine and active.trades_count > 0:
                ml_recommends_change = await self.check_ml_recommendation(symbol, direction, active)

                if ml_recommends_change:
                    await self.switch_strategy(
                        symbol, direction,
                        reason='ml_signal',
                        new_market_condition=current_market
                    )
                    continue

            logger.info(f"  {direction}: {active.strategy.name} maintained "
                       f"(Score: {active.performance_score:.2f}, Trades: {active.trades_count})")

    async def detect_regime_change(self, active: ActiveStrategy,
                                   current_market: MarketCondition) -> bool:
        """Detect if market regime has changed significantly

        Args:
            active: Currently active strategy
            current_market: Current market conditions

        Returns:
            True if regime changed significantly
        """
        old_market = active.market_condition

        # Check regime type change
        regime_changed = old_market.regime != current_market.regime

        # Check volatility change
        vol_change = abs(current_market.volatility - old_market.volatility)
        vol_changed_significantly = vol_change > self.regime_change_threshold

        if regime_changed or vol_changed_significantly:
            logger.info(f"  🔄 Market Regime Change Detected:")
            logger.info(f"    Old: {old_market.regime} (Vol: {old_market.volatility:.3f})")
            logger.info(f"    New: {current_market.regime} (Vol: {current_market.volatility:.3f})")
            return True

        return False

    def check_poor_performance(self, active: ActiveStrategy) -> bool:
        """Check if strategy is performing poorly

        Args:
            active: Active strategy to evaluate

        Returns:
            True if performance is poor
        """
        if active.trades_count == 0:
            return False

        # Calculate average P&L per trade
        avg_pnl = active.total_pnl / active.trades_count

        # Calculate win rate
        win_rate = active.win_count / active.trades_count if active.trades_count > 0 else 0

        # Poor performance criteria
        poor_avg_pnl = avg_pnl < self.poor_performance_threshold
        poor_win_rate = win_rate < 0.4  # Less than 40% win rate

        if poor_avg_pnl or poor_win_rate:
            logger.info(f"  ⚠️  Poor Performance Detected:")
            logger.info(f"    Avg P&L: {avg_pnl:.4f}, Win Rate: {win_rate:.1%}")
            return True

        return False

    async def check_ml_recommendation(self, symbol: str, direction: str,
                                     active: ActiveStrategy) -> bool:
        """Check if ML model recommends strategy change

        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            active: Active strategy

        Returns:
            True if ML recommends change
        """
        try:
            # Get recent market data
            klines = await self.client.get_klines(symbol, interval='1h', limit=100)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

            # Calculate indicators
            indicators = TechnicalIndicators.calculate_all(
                df['high'].tolist(),
                df['low'].tolist(),
                df['close'].tolist(),
                df['volume'].tolist()
            )

            # Get ML prediction
            ml_signal, ml_confidence = self.ml_engine.predict(df, indicators)

            # ML recommends change if:
            # - High confidence (>0.7) signal conflicts with current strategy
            # - Current strategy is underperforming and ML has medium+ confidence (>0.6)

            if ml_confidence > 0.7:
                if direction == 'LONG' and ml_signal == -1:  # ML says SELL but we're LONG
                    logger.info(f"  🧠 ML Recommends Change: Strong SELL signal (conf: {ml_confidence:.2%})")
                    return True
                elif direction == 'SHORT' and ml_signal == 1:  # ML says BUY but we're SHORT
                    logger.info(f"  🧠 ML Recommends Change: Strong BUY signal (conf: {ml_confidence:.2%})")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error in ML recommendation check: {e}")
            return False

    async def switch_strategy(self, symbol: str, direction: str, reason: str,
                             new_market_condition: MarketCondition):
        """Switch to a new optimal strategy

        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            reason: Reason for switch
            new_market_condition: Current market conditions
        """
        old_active = self.active_strategies[symbol][direction]
        old_strategy_name = old_active.strategy.name

        # Get new optimal strategy based on current market conditions
        new_strategy = self.optimizer.strategy_db.get_best_strategy(
            symbol, direction, new_market_condition
        )

        # Update performance database with old strategy results
        if old_active.trades_count > 0:
            win_rate = (old_active.win_count / old_active.trades_count) * 100
            avg_return = (old_active.total_pnl / old_active.trades_count) if old_active.trades_count > 0 else 0

            # Simplified performance metrics for update
            self.optimizer.update_strategy_performance(
                symbol=symbol,
                direction=direction,
                strategy_name=old_strategy_name,
                win_rate=win_rate,
                profit_factor=1.0,  # Simplified
                avg_return=avg_return,
                sharpe_ratio=0.0,  # Simplified
                max_drawdown=0.0,  # Simplified
                total_trades=old_active.trades_count,
                market_condition=old_active.market_condition
            )

        # Create new active strategy
        new_active = ActiveStrategy(
            symbol=symbol,
            direction=direction,
            strategy=new_strategy,
            activated_at=datetime.now(),
            market_condition=new_market_condition
        )

        # Update active strategies
        self.active_strategies[symbol][direction] = new_active

        # Record switch
        switch = StrategySwitch(
            timestamp=datetime.now(),
            symbol=symbol,
            direction=direction,
            old_strategy=old_strategy_name,
            new_strategy=new_strategy.name,
            reason=reason,
            market_condition=new_market_condition
        )
        self.switch_history.append(switch)

        logger.info(f"  ✅ Strategy Switched:")
        logger.info(f"    {old_strategy_name} → {new_strategy.name}")
        logger.info(f"    Reason: {reason}")
        logger.info(f"    Old Performance: {old_active.trades_count} trades, "
                   f"Score: {old_active.performance_score:.2f}")

    def update_strategy_performance(self, symbol: str, direction: str,
                                   pnl: float, win: bool):
        """Update performance metrics for active strategy

        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            pnl: Profit/loss for the trade
            win: Whether trade was profitable
        """
        if symbol not in self.active_strategies:
            return

        active = self.active_strategies[symbol][direction]
        active.trades_count += 1
        active.total_pnl += pnl
        if win:
            active.win_count += 1

        # Update performance score (weighted average return)
        active.performance_score = active.total_pnl / active.trades_count if active.trades_count > 0 else 0

        logger.debug(f"{symbol} {direction} performance updated: "
                    f"{active.trades_count} trades, Score: {active.performance_score:.4f}")

    def get_current_strategy(self, symbol: str, direction: str) -> StrategyConfig:
        """Get currently active strategy for symbol/direction

        Args:
            symbol: Trading symbol
            direction: LONG or SHORT

        Returns:
            Active strategy configuration
        """
        if symbol not in self.active_strategies:
            raise ValueError(f"No active strategy for {symbol}")

        return self.active_strategies[symbol][direction].strategy

    def save_switch_history(self, filename: str = 'ai_strategy_switches.json'):
        """Save strategy switch history to file

        Args:
            filename: Output filename
        """
        output_path = Path(__file__).parent / 'results' / filename
        output_path.parent.mkdir(exist_ok=True)

        # Convert to serializable format
        history_data = []
        for switch in self.switch_history:
            switch_dict = asdict(switch)
            switch_dict['timestamp'] = switch.timestamp.isoformat()
            switch_dict['market_condition'] = asdict(switch.market_condition)
            history_data.append(switch_dict)

        with open(output_path, 'w') as f:
            json.dump(history_data, f, indent=2)

        logger.info(f"Strategy switch history saved to {output_path}")

    def generate_report(self) -> Dict:
        """Generate AI strategy management report

        Returns:
            Report dictionary with statistics
        """
        total_switches = len(self.switch_history)

        switches_by_reason = {}
        switches_by_symbol = {}

        for switch in self.switch_history:
            # By reason
            switches_by_reason[switch.reason] = switches_by_reason.get(switch.reason, 0) + 1

            # By symbol
            switches_by_symbol[switch.symbol] = switches_by_symbol.get(switch.symbol, 0) + 1

        # Current active strategies summary
        active_summary = {}
        for symbol, directions in self.active_strategies.items():
            active_summary[symbol] = {
                direction: {
                    'strategy': active.strategy.name,
                    'trades': active.trades_count,
                    'score': active.performance_score,
                    'win_rate': (active.win_count / active.trades_count * 100) if active.trades_count > 0 else 0
                }
                for direction, active in directions.items()
            }

        report = {
            'total_switches': total_switches,
            'switches_by_reason': switches_by_reason,
            'switches_by_symbol': switches_by_symbol,
            'current_active_strategies': active_summary,
            'switch_history': [
                {
                    'timestamp': s.timestamp.isoformat(),
                    'symbol': s.symbol,
                    'direction': s.direction,
                    'old_strategy': s.old_strategy,
                    'new_strategy': s.new_strategy,
                    'reason': s.reason
                }
                for s in self.switch_history[-10:]  # Last 10 switches
            ]
        }

        return report


# Test the AI Strategy Manager
async def test_ai_manager():
    """Test AI Strategy Manager"""
    client = BinanceClient(testnet=True, use_futures=True)

    try:
        # Initialize manager
        manager = AIStrategyManager(client)

        # Initialize strategies for BTC and ETH
        await manager.initialize_strategies(['BTC/USDT', 'ETH/USDT'])

        # Simulate some trades
        manager.update_strategy_performance('BTC/USDT', 'LONG', pnl=50.0, win=True)
        manager.update_strategy_performance('BTC/USDT', 'LONG', pnl=-30.0, win=False)
        manager.update_strategy_performance('BTC/USDT', 'LONG', pnl=40.0, win=True)

        # Check and adapt (would normally run in loop)
        await manager.check_and_adapt_strategy('BTC/USDT')

        # Generate report
        report = manager.generate_report()

        print("\n=== AI Strategy Manager Report ===")
        print(f"Total Switches: {report['total_switches']}")
        print(f"\nActive Strategies:")
        for symbol, strategies in report['current_active_strategies'].items():
            print(f"\n{symbol}:")
            for direction, info in strategies.items():
                print(f"  {direction}: {info['strategy']} "
                     f"(Trades: {info['trades']}, Score: {info['score']:.4f}, "
                     f"Win Rate: {info['win_rate']:.1f}%)")

    finally:
        await client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_ai_manager())
