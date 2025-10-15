"""
AI-Driven Strategy Optimization System
Selects optimal trading strategies per coin based on market conditions
"""
import asyncio
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pandas as pd

from binance_client import BinanceClient
from technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Trading strategy configuration"""
    name: str
    ml_weight: float
    technical_weight: float
    rsi_oversold: int
    rsi_overbought: int
    atr_multiplier: float
    min_profit_threshold: float
    max_position_size: float
    volatility_threshold: float

    def to_dict(self):
        return asdict(self)


@dataclass
class MarketCondition:
    """Current market condition analysis"""
    symbol: str
    volatility: float  # ATR as % of price
    trend_strength: float  # ADX or similar
    momentum: float  # RSI deviation from 50
    liquidity: float  # Volume ratio
    regime: str  # 'trending', 'ranging', 'volatile', 'quiet'


@dataclass
class StrategyPerformance:
    """Historical strategy performance"""
    strategy_name: str
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    win_rate: float
    profit_factor: float
    avg_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    last_tested: datetime
    market_conditions: MarketCondition


class StrategyDatabase:
    """Database of strategy configurations and performance"""

    # Pre-defined strategy configurations
    STRATEGIES = {
        'aggressive_trend': StrategyConfig(
            name='aggressive_trend',
            ml_weight=0.7,
            technical_weight=0.3,
            rsi_oversold=35,
            rsi_overbought=65,
            atr_multiplier=3.0,
            min_profit_threshold=0.015,
            max_position_size=0.25,
            volatility_threshold=0.03
        ),
        'conservative_trend': StrategyConfig(
            name='conservative_trend',
            ml_weight=0.5,
            technical_weight=0.5,
            rsi_oversold=30,
            rsi_overbought=70,
            atr_multiplier=2.5,
            min_profit_threshold=0.01,
            max_position_size=0.15,
            volatility_threshold=0.02
        ),
        'range_bound': StrategyConfig(
            name='range_bound',
            ml_weight=0.4,
            technical_weight=0.6,
            rsi_oversold=25,
            rsi_overbought=75,
            atr_multiplier=2.0,
            min_profit_threshold=0.008,
            max_position_size=0.20,
            volatility_threshold=0.015
        ),
        'high_volatility': StrategyConfig(
            name='high_volatility',
            ml_weight=0.6,
            technical_weight=0.4,
            rsi_oversold=40,
            rsi_overbought=60,
            atr_multiplier=3.5,
            min_profit_threshold=0.02,
            max_position_size=0.15,
            volatility_threshold=0.04
        ),
        'scalping': StrategyConfig(
            name='scalping',
            ml_weight=0.8,
            technical_weight=0.2,
            rsi_oversold=35,
            rsi_overbought=65,
            atr_multiplier=1.5,
            min_profit_threshold=0.005,
            max_position_size=0.30,
            volatility_threshold=0.01
        )
    }

    def __init__(self, data_dir: str = 'strategy_performance'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.performance_db: Dict[str, List[StrategyPerformance]] = {}
        self.load_performance_db()

    def load_performance_db(self):
        """Load historical performance data"""
        db_file = self.data_dir / 'performance_db.json'
        if db_file.exists():
            try:
                with open(db_file, 'r') as f:
                    data = json.load(f)
                    # Convert to StrategyPerformance objects
                    for key, perf_list in data.items():
                        self.performance_db[key] = []
                        for p in perf_list:
                            # Reconstruct objects
                            market_cond = MarketCondition(**p['market_conditions'])
                            p['market_conditions'] = market_cond
                            p['last_tested'] = datetime.fromisoformat(p['last_tested'])
                            self.performance_db[key].append(StrategyPerformance(**p))
                logger.info(f"Loaded performance database with {len(self.performance_db)} entries")
            except Exception as e:
                logger.error(f"Error loading performance DB: {e}")
                self.performance_db = {}

    def save_performance_db(self):
        """Save performance database"""
        db_file = self.data_dir / 'performance_db.json'
        try:
            # Convert to JSON-serializable format
            data = {}
            for key, perf_list in self.performance_db.items():
                data[key] = []
                for p in perf_list:
                    p_dict = asdict(p)
                    p_dict['market_conditions'] = asdict(p.market_conditions)
                    p_dict['last_tested'] = p.last_tested.isoformat()
                    data[key].append(p_dict)

            with open(db_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved performance database to {db_file}")
        except Exception as e:
            logger.error(f"Error saving performance DB: {e}")

    def update_performance(self, perf: StrategyPerformance):
        """Update strategy performance"""
        key = f"{perf.symbol}_{perf.direction}_{perf.strategy_name}"
        if key not in self.performance_db:
            self.performance_db[key] = []
        self.performance_db[key].append(perf)
        self.save_performance_db()

    def get_best_strategy(self, symbol: str, direction: str, market_cond: MarketCondition) -> StrategyConfig:
        """Get best strategy for symbol/direction based on market conditions"""
        # Get historical performance for this symbol/direction
        matching_perfs = []
        for key, perf_list in self.performance_db.items():
            if key.startswith(f"{symbol}_{direction}_"):
                matching_perfs.extend(perf_list)

        if matching_perfs:
            # Filter by similar market conditions
            similar_perfs = [
                p for p in matching_perfs
                if abs(p.market_conditions.volatility - market_cond.volatility) < 0.01
                and p.market_conditions.regime == market_cond.regime
            ]

            if similar_perfs:
                # Select best performing
                best = max(similar_perfs, key=lambda p: p.profit_factor * p.win_rate)
                logger.info(f"Selected {best.strategy_name} for {symbol} {direction} based on historical performance")
                return self.STRATEGIES[best.strategy_name]

        # No historical data, use regime-based selection
        return self._select_by_regime(market_cond)

    def _select_by_regime(self, market_cond: MarketCondition) -> StrategyConfig:
        """Select strategy based on market regime"""
        if market_cond.regime == 'volatile':
            return self.STRATEGIES['high_volatility']
        elif market_cond.regime == 'trending':
            if market_cond.volatility > 0.025:
                return self.STRATEGIES['aggressive_trend']
            else:
                return self.STRATEGIES['conservative_trend']
        elif market_cond.regime == 'ranging':
            return self.STRATEGIES['range_bound']
        elif market_cond.regime == 'quiet':
            return self.STRATEGIES['scalping']
        else:
            return self.STRATEGIES['conservative_trend']


class AIStrategyOptimizer:
    """AI-driven strategy optimizer"""

    def __init__(self, client: BinanceClient):
        self.client = client
        self.strategy_db = StrategyDatabase()

    async def analyze_market_condition(self, symbol: str) -> MarketCondition:
        """Analyze current market conditions for a symbol"""
        try:
            # Get recent data
            klines = await self.client.get_klines(symbol, interval='1h', limit=100)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

            # Calculate indicators
            indicators = TechnicalIndicators.calculate_all(df)

            current_price = float(df['close'].iloc[-1])
            atr = indicators.get('atr', current_price * 0.02)
            rsi = indicators.get('rsi', 50.0)

            # Calculate volatility
            volatility = atr / current_price

            # Calculate trend strength (simple momentum)
            close_prices = df['close'].values
            sma_20 = close_prices[-20:].mean()
            trend_strength = abs(current_price - sma_20) / sma_20

            # Calculate momentum
            momentum = abs(rsi - 50) / 50

            # Calculate liquidity (volume ratio)
            avg_volume = df['volume'].mean()
            current_volume = float(df['volume'].iloc[-1])
            liquidity = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Determine regime
            if volatility > 0.03:
                regime = 'volatile'
            elif trend_strength > 0.02 and momentum > 0.3:
                regime = 'trending'
            elif volatility < 0.015 and trend_strength < 0.01:
                regime = 'quiet'
            else:
                regime = 'ranging'

            return MarketCondition(
                symbol=symbol,
                volatility=volatility,
                trend_strength=trend_strength,
                momentum=momentum,
                liquidity=liquidity,
                regime=regime
            )

        except Exception as e:
            logger.error(f"Error analyzing market condition for {symbol}: {e}")
            # Return default
            return MarketCondition(
                symbol=symbol,
                volatility=0.02,
                trend_strength=0.01,
                momentum=0.0,
                liquidity=1.0,
                regime='ranging'
            )

    async def get_optimal_strategy(self, symbol: str, direction: str) -> Tuple[StrategyConfig, MarketCondition]:
        """Get optimal strategy for symbol and direction"""
        market_cond = await self.analyze_market_condition(symbol)
        strategy = self.strategy_db.get_best_strategy(symbol, direction, market_cond)

        logger.info(f"{symbol} {direction}: Market={market_cond.regime}, "
                   f"Volatility={market_cond.volatility:.3f}, Strategy={strategy.name}")

        return strategy, market_cond

    async def optimize_all_coins(self, symbols: List[str]) -> Dict[str, Dict[str, StrategyConfig]]:
        """Optimize strategies for all coins and both directions"""
        results = {}

        for symbol in symbols:
            results[symbol] = {}

            # Get optimal strategy for LONG
            long_strategy, long_cond = await self.get_optimal_strategy(symbol, 'LONG')
            results[symbol]['LONG'] = {
                'strategy': long_strategy,
                'market_condition': long_cond
            }

            # Get optimal strategy for SHORT
            short_strategy, short_cond = await self.get_optimal_strategy(symbol, 'SHORT')
            results[symbol]['SHORT'] = {
                'strategy': short_strategy,
                'market_condition': short_cond
            }

            await asyncio.sleep(0.1)  # Rate limiting

        return results

    def update_strategy_performance(self, symbol: str, direction: str, strategy_name: str,
                                   win_rate: float, profit_factor: float, avg_return: float,
                                   sharpe_ratio: float, max_drawdown: float, total_trades: int,
                                   market_condition: MarketCondition):
        """Update performance database with test results"""
        perf = StrategyPerformance(
            strategy_name=strategy_name,
            symbol=symbol,
            direction=direction,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_return=avg_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            total_trades=total_trades,
            last_tested=datetime.now(),
            market_conditions=market_condition
        )

        self.strategy_db.update_performance(perf)
        logger.info(f"Updated performance for {symbol} {direction} {strategy_name}: "
                   f"WR={win_rate:.1f}%, PF={profit_factor:.2f}")


# Test the optimizer
async def test_optimizer():
    """Test the AI strategy optimizer"""
    client = BinanceClient(testnet=True, use_futures=True)

    try:
        optimizer = AIStrategyOptimizer(client)

        # Test with BTC
        symbol = 'BTC/USDT'

        # Analyze market
        market_cond = await optimizer.analyze_market_condition(symbol)
        print(f"\n{symbol} Market Condition:")
        print(f"  Regime: {market_cond.regime}")
        print(f"  Volatility: {market_cond.volatility:.3f}")
        print(f"  Trend Strength: {market_cond.trend_strength:.3f}")
        print(f"  Momentum: {market_cond.momentum:.3f}")

        # Get optimal strategies
        long_strategy, _ = await optimizer.get_optimal_strategy(symbol, 'LONG')
        short_strategy, _ = await optimizer.get_optimal_strategy(symbol, 'SHORT')

        print(f"\nOptimal LONG Strategy: {long_strategy.name}")
        print(f"  ML Weight: {long_strategy.ml_weight}")
        print(f"  ATR Multiplier: {long_strategy.atr_multiplier}")

        print(f"\nOptimal SHORT Strategy: {short_strategy.name}")
        print(f"  ML Weight: {short_strategy.ml_weight}")
        print(f"  ATR Multiplier: {short_strategy.atr_multiplier}")

    finally:
        await client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_optimizer())
