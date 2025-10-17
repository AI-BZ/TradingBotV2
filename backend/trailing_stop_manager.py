"""
Trailing Stop Manager - ATR-based dynamic trailing stop implementation
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TrailingStopManager:
    """ATR-based trailing stop manager with ML-driven parameter optimization"""

    def __init__(self,
                 base_atr_multiplier: float = 1.8,  # 2.5 → 1.8 (더 타이트하게)
                 min_profit_threshold: float = 0.005,  # 1% → 0.5% (더 빠른 익절 시작)
                 acceleration_step: float = 0.3,  # 0.1 → 0.3 (더 빠른 가속)
                 max_loss_pct: float = 0.01,  # 기본 최대 손실 1% 하드스톱
                 hard_stop_atr_multiplier: float = 2.0,  # v5.0 NEW: ATR 기반 동적 하드스톱
                 use_dynamic_hard_stop: bool = True):  # v5.0 NEW: 동적 하드스톱 사용 여부
        """Initialize trailing stop manager

        Args:
            base_atr_multiplier: Base ATR multiplier for stop distance (1.5-2.0)
            min_profit_threshold: Minimum profit % to activate trailing (0.5%)
            acceleration_step: How much to tighten stop as profit increases
            max_loss_pct: Fixed maximum loss percentage before hard stop (1%)
            hard_stop_atr_multiplier: ATR multiplier for dynamic hard stop (v5.0)
            use_dynamic_hard_stop: Use ATR-based dynamic hard stop instead of fixed (v5.0)
        """
        self.base_atr_multiplier = base_atr_multiplier
        self.min_profit_threshold = min_profit_threshold
        self.acceleration_step = acceleration_step
        self.max_loss_pct = max_loss_pct
        self.hard_stop_atr_multiplier = hard_stop_atr_multiplier  # v5.0 NEW
        self.use_dynamic_hard_stop = use_dynamic_hard_stop  # v5.0 NEW

        # Track highest/lowest prices for trailing
        self.position_peaks = {}  # symbol -> {'highest': float, 'lowest': float}

        logger.info(f"TrailingStopManager initialized: ATR={base_atr_multiplier}, "
                   f"Min profit={min_profit_threshold:.1%}, "
                   f"Hard stop={'Dynamic ATR×' + str(hard_stop_atr_multiplier) if use_dynamic_hard_stop else 'Fixed ' + str(max_loss_pct*100) + '%'}")

    def calculate_atr_multiplier(self,
                                 current_profit_pct: float,
                                 atr_value: float,
                                 price: float) -> float:
        """Calculate dynamic ATR multiplier based on profit and volatility

        Args:
            current_profit_pct: Current unrealized profit percentage
            atr_value: Current ATR value
            price: Current price

        Returns:
            Adjusted ATR multiplier
        """
        # Base multiplier (이미 1.8로 더 타이트함)
        multiplier = self.base_atr_multiplier

        # Calculate volatility percentage
        volatility_pct = atr_value / price

        # 변동성 기반 조정 (더 보수적으로)
        # High volatility (>3%) → 약간 넓힘
        if volatility_pct > 0.03:
            multiplier = 2.2  # 3.0 → 2.2
        # Medium volatility (1-3%) → 표준
        elif volatility_pct > 0.01:
            multiplier = 1.8  # 2.5 → 1.8
        # Low volatility (<1%) → 더 타이트
        else:
            multiplier = 1.5  # 2.0 → 1.5

        # 수익 발생 시 빠르게 스톱 조이기 (개선됨)
        if current_profit_pct > self.min_profit_threshold:
            # 0.5% 수익부터 스톱 조이기 시작
            profit_excess = current_profit_pct - self.min_profit_threshold
            # acceleration_step=0.3이므로 더 빠르게 조여짐
            tightening_factor = profit_excess * self.acceleration_step * 10  # 10배 더 빠르게
            multiplier = max(1.0, multiplier - tightening_factor)  # 최소 1.0까지

            # 2% 이상 수익 시 매우 타이트하게
            if current_profit_pct > 0.02:
                multiplier = max(0.8, multiplier - 0.5)  # 더욱 조임

        logger.debug(f"ATR multiplier adjusted to {multiplier:.2f} "
                    f"(profit: {current_profit_pct:.2%}, volatility: {volatility_pct:.2%})")

        return multiplier

    def initialize_position(self,
                           symbol: str,
                           entry_price: float,
                           position_type: str) -> None:
        """Initialize tracking for a new position

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            position_type: 'LONG' or 'SHORT'
        """
        self.position_peaks[symbol] = {
            'highest': entry_price,
            'lowest': entry_price,
            'entry_price': entry_price,
            'position_type': position_type,
            'initialized_at': datetime.now()
        }
        logger.info(f"{symbol}: Trailing stop initialized for {position_type} @ ${entry_price:.2f}")

    def update_trailing_stop(self,
                            symbol: str,
                            current_price: float,
                            atr_value: float) -> Tuple[float, bool]:
        """Update trailing stop for a position

        Args:
            symbol: Trading symbol
            current_price: Current market price
            atr_value: Current ATR value

        Returns:
            Tuple of (stop_price, should_close)
            stop_price: New trailing stop price
            should_close: True if stop was hit
        """
        if symbol not in self.position_peaks:
            logger.warning(f"{symbol}: Position not initialized in trailing stop manager")
            return current_price, False

        position_data = self.position_peaks[symbol]
        entry_price = position_data['entry_price']
        position_type = position_data['position_type']

        # Update peak prices
        if position_type == 'LONG':
            position_data['highest'] = max(position_data['highest'], current_price)
            peak_price = position_data['highest']
            current_profit_pct = (current_price - entry_price) / entry_price
        else:  # SHORT
            position_data['lowest'] = min(position_data['lowest'], current_price)
            peak_price = position_data['lowest']
            current_profit_pct = (entry_price - current_price) / entry_price

        # Calculate dynamic ATR multiplier
        atr_multiplier = self.calculate_atr_multiplier(
            current_profit_pct, atr_value, current_price
        )

        # v5.0: 동적 또는 고정 하드스톱 계산
        if self.use_dynamic_hard_stop:
            # 동적 하드스톱: ATR 기반으로 변동성에 맞춰 조정
            # 변동성이 높을 때는 더 넓은 스톱, 낮을 때는 더 좁은 스톱
            atr_pct = atr_value / current_price
            dynamic_stop_distance = max(self.max_loss_pct, atr_pct * self.hard_stop_atr_multiplier)

            # 하드스톱 체크
            hard_stop_hit = False
            if current_profit_pct < -dynamic_stop_distance:
                hard_stop_hit = True
                logger.warning(f"{symbol}: 🛑 DYNAMIC HARD STOP HIT! Loss {current_profit_pct:.2%} exceeds ATR-based stop {-dynamic_stop_distance:.2%} (ATR: {atr_pct:.2%})")
        else:
            # 고정 하드스톱: 기존 방식
            dynamic_stop_distance = self.max_loss_pct
            hard_stop_hit = False
            if current_profit_pct < -self.max_loss_pct:
                hard_stop_hit = True
                logger.warning(f"{symbol}: 🛑 HARD STOP HIT! Loss {current_profit_pct:.2%} exceeds max {-self.max_loss_pct:.2%}")

        # Calculate trailing stop price
        if position_type == 'LONG':
            # Stop trails below the highest price reached
            stop_price = peak_price - (atr_multiplier * atr_value)

            # 하드스톱 적용: 동적 또는 고정
            hard_stop_price = entry_price * (1 - dynamic_stop_distance)
            stop_price = max(stop_price, hard_stop_price)  # 둘 중 더 높은 스톱 사용

            should_close = current_price <= stop_price or hard_stop_hit

            if should_close:
                reason = "DYNAMIC HARD STOP" if (hard_stop_hit and self.use_dynamic_hard_stop) else ("HARD STOP" if hard_stop_hit else "trailing stop")
                logger.info(f"{symbol}: LONG {reason} hit! "
                           f"Price ${current_price:.2f} <= Stop ${stop_price:.2f} "
                           f"(Peak: ${peak_price:.2f}, Profit: {current_profit_pct:+.2%})")
        else:  # SHORT
            # Stop trails above the lowest price reached
            stop_price = peak_price + (atr_multiplier * atr_value)

            # 하드스톱 적용: 동적 또는 고정
            hard_stop_price = entry_price * (1 + dynamic_stop_distance)
            stop_price = min(stop_price, hard_stop_price)  # 둘 중 더 낮은 스톱 사용

            should_close = current_price >= stop_price or hard_stop_hit

            if should_close:
                reason = "DYNAMIC HARD STOP" if (hard_stop_hit and self.use_dynamic_hard_stop) else ("HARD STOP" if hard_stop_hit else "trailing stop")
                logger.info(f"{symbol}: SHORT {reason} hit! "
                           f"Price ${current_price:.2f} >= Stop ${stop_price:.2f} "
                           f"(Peak: ${peak_price:.2f}, Profit: {current_profit_pct:+.2%})")

        return stop_price, should_close

    def get_current_stop(self,
                        symbol: str,
                        current_price: float,
                        atr_value: float) -> Optional[float]:
        """Get current trailing stop price without triggering close

        Args:
            symbol: Trading symbol
            current_price: Current market price
            atr_value: Current ATR value

        Returns:
            Current stop price or None
        """
        if symbol not in self.position_peaks:
            return None

        position_data = self.position_peaks[symbol]
        entry_price = position_data['entry_price']
        position_type = position_data['position_type']

        # Calculate current profit
        if position_type == 'LONG':
            peak_price = position_data['highest']
            current_profit_pct = (current_price - entry_price) / entry_price
        else:
            peak_price = position_data['lowest']
            current_profit_pct = (entry_price - current_price) / entry_price

        # Calculate dynamic multiplier
        atr_multiplier = self.calculate_atr_multiplier(
            current_profit_pct, atr_value, current_price
        )

        # Calculate stop price
        if position_type == 'LONG':
            stop_price = peak_price - (atr_multiplier * atr_value)
        else:
            stop_price = peak_price + (atr_multiplier * atr_value)

        return stop_price

    def remove_position(self, symbol: str) -> None:
        """Remove position from tracking

        Args:
            symbol: Trading symbol
        """
        if symbol in self.position_peaks:
            del self.position_peaks[symbol]
            logger.info(f"{symbol}: Position removed from trailing stop manager")

    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """Get position tracking information

        Args:
            symbol: Trading symbol

        Returns:
            Position information dict or None
        """
        return self.position_peaks.get(symbol)


class MLTrailingStopOptimizer:
    """ML-based trailing stop parameter optimizer"""

    def __init__(self):
        """Initialize ML optimizer"""
        self.historical_trades = []
        self.optimal_params = {
            'atr_multiplier': 2.5,
            'acceleration_step': 0.1
        }

    def analyze_trade_outcome(self,
                             trade_data: Dict,
                             final_price: float,
                             atr_at_close: float) -> Dict:
        """Analyze completed trade to optimize parameters

        Args:
            trade_data: Trade information
            final_price: Exit price
            atr_at_close: ATR value at close

        Returns:
            Analysis results
        """
        self.historical_trades.append({
            'entry_price': trade_data['entry_price'],
            'exit_price': final_price,
            'peak_price': trade_data.get('peak_price'),
            'atr_at_entry': trade_data.get('atr_at_entry'),
            'atr_at_close': atr_at_close,
            'position_type': trade_data['position_type'],
            'pnl_pct': trade_data['pnl_pct']
        })

        # Analyze if we could have achieved better results
        analysis = self._calculate_optimal_exit(trade_data, final_price)

        return analysis

    def _calculate_optimal_exit(self, trade_data: Dict, actual_exit: float) -> Dict:
        """Calculate what would have been optimal exit point

        Args:
            trade_data: Trade data
            actual_exit: Actual exit price

        Returns:
            Optimization analysis
        """
        # TODO: Implement ML-based analysis
        # For now, return basic analysis
        return {
            'actual_pnl': trade_data['pnl_pct'],
            'could_improve': False,
            'suggested_multiplier': 2.5
        }

    def get_optimal_parameters(self,
                              market_volatility: float,
                              recent_performance: Dict) -> Dict:
        """Get ML-optimized parameters for current market conditions

        Args:
            market_volatility: Current market volatility measure
            recent_performance: Recent trading performance metrics

        Returns:
            Optimized parameters
        """
        # Base parameters
        params = self.optimal_params.copy()

        # Adjust based on recent performance
        if len(self.historical_trades) >= 10:
            recent_trades = self.historical_trades[-10:]
            avg_pnl = np.mean([t['pnl_pct'] for t in recent_trades])

            # If losing money, widen stops
            if avg_pnl < 0:
                params['atr_multiplier'] = min(3.0, params['atr_multiplier'] + 0.2)
            # If winning, can tighten stops
            elif avg_pnl > 0.02:
                params['atr_multiplier'] = max(2.0, params['atr_multiplier'] - 0.1)

        # Adjust for volatility
        if market_volatility > 0.03:
            params['atr_multiplier'] = min(3.0, params['atr_multiplier'] + 0.3)

        logger.info(f"ML-optimized parameters: {params}")
        return params


# Example usage
if __name__ == "__main__":
    # Initialize manager
    manager = TrailingStopManager(base_atr_multiplier=2.2)

    # Simulate LONG position
    symbol = "BTCUSDT"
    entry_price = 43000.0
    atr = 500.0  # $500 ATR

    # Initialize position
    manager.initialize_position(symbol, entry_price, 'LONG')

    # Simulate price movements
    prices = [43000, 43500, 44000, 44500, 44800, 44600, 44400]

    print("\n=== Trailing Stop Simulation ===")
    for i, price in enumerate(prices):
        stop_price, should_close = manager.update_trailing_stop(symbol, price, atr)

        profit_pct = (price - entry_price) / entry_price
        print(f"\nIteration {i+1}:")
        print(f"  Current Price: ${price:,.2f}")
        print(f"  Trailing Stop: ${stop_price:,.2f}")
        print(f"  Current Profit: {profit_pct:+.2%}")
        print(f"  Should Close: {'YES ✅' if should_close else 'NO'}")

        if should_close:
            final_profit = (price - entry_price) / entry_price
            print(f"\n🎯 Position closed with {final_profit:+.2%} profit")
            break
