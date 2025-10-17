"""
Trading Strategy Engine - Combines technical indicators and ML predictions
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging
import json
from pathlib import Path

from technical_indicators import TechnicalIndicators
from tick_indicators import TickIndicators
from ml_engine import MLEngine

logger = logging.getLogger(__name__)

class TradingStrategy:
    """Hybrid trading strategy combining technical analysis and ML predictions"""

    def __init__(self,
                 ml_weight: float = 0.6,
                 technical_weight: float = 0.4,
                 confidence_threshold: float = 0.6):
        """Initialize trading strategy

        Args:
            ml_weight: Weight for ML predictions (0-1)
            technical_weight: Weight for technical indicators (0-1)
            confidence_threshold: Minimum confidence for ML predictions
        """
        self.ml_weight = ml_weight
        self.technical_weight = technical_weight
        self.confidence_threshold = confidence_threshold
        self.ml_engine = None
        self.tick_indicators = TickIndicators()

        # Load coin-specific parameters
        self.coin_params = self._load_coin_parameters()

        logger.info(f"TradingStrategy initialized: ML weight={ml_weight}, Technical weight={technical_weight}")
        logger.info(f"Loaded parameters for {len(self.coin_params.get('coin_parameters', {}))} coins")

    def _load_coin_parameters(self) -> Dict:
        """Load coin-specific parameters from JSON file"""
        params_file = Path(__file__).parent / 'coin_specific_params.json'

        try:
            with open(params_file, 'r') as f:
                params = json.load(f)
            logger.info(f"Loaded coin-specific parameters from {params_file}")
            return params
        except FileNotFoundError:
            logger.warning(f"Coin parameters file not found: {params_file}, using defaults")
            return {
                'coin_parameters': {},
                'fallback_parameters': {
                    'bb_compression': 0.055,
                    'atr_expansion': 0.025,
                    'hard_stop': 0.015,
                    'trailing_multiplier': 2.0
                }
            }
        except Exception as e:
            logger.error(f"Error loading coin parameters: {e}")
            return {
                'coin_parameters': {},
                'fallback_parameters': {
                    'bb_compression': 0.055,
                    'atr_expansion': 0.025,
                    'hard_stop': 0.015,
                    'trailing_multiplier': 2.0
                }
            }

    def get_coin_parameters(self, symbol: str) -> Dict:
        """Get parameters for specific coin

        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')

        Returns:
            Dictionary of parameters for the coin
        """
        coin_params = self.coin_params.get('coin_parameters', {})

        if symbol in coin_params:
            return coin_params[symbol]
        else:
            # Use fallback parameters
            fallback = self.coin_params.get('fallback_parameters', {
                'bb_compression': 0.055,
                'atr_expansion': 0.025,
                'hard_stop': 0.015,
                'trailing_multiplier': 2.0
            })
            logger.info(f"Using fallback parameters for {symbol}")
            return fallback

    def set_ml_engine(self, ml_engine: MLEngine):
        """Set ML engine for predictions"""
        self.ml_engine = ml_engine

    def analyze_technical_signals(self, indicators: Dict, symbol: str = None) -> Tuple[int, float]:
        """Analyze technical indicators using Two-Way Simultaneous Entry (Straddle) Strategy

        Strategy: Volatility-based market-neutral strategy with independent position management

        Entry Signal (Volatility Breakout):
        - Bollinger Bands Width < 50% of 20-day average (compression)
        - ATR 5-day average > ATR 20-day average × 1.2 (expansion)
        - Large candle body > ATR × 1.5 (breakout confirmation)
        → Signal: BOTH (enter LONG + SHORT simultaneously)

        Exit Strategy:
        - Losing side: Hard stop at -1.5% (ATR × 1.0)
        - Winning side: Trailing Stop (ATR × 1.8, acceleration 0.3)
        - Activate trailing when profit > +0.5%

        Args:
            indicators: Dictionary of technical indicators

        Returns:
            Tuple of (signal, strength)
            signal: 2 (BOTH - enter LONG+SHORT), 0 (HOLD)
            strength: Signal strength 0-1 based on volatility expansion
        """
        # Ensure we have required indicators
        if 'bb' not in indicators or 'atr' not in indicators or 'close' not in indicators:
            return 0, 0.0

        bb_data = indicators['bb']
        atr = indicators.get('atr', 0)
        close = indicators.get('close', 0)

        # Get historical data for BB width and ATR averages
        # Note: These should be calculated from historical data in real implementation
        # For now, we'll use approximations based on current values

        # Extract Bollinger Bands
        upper_band = bb_data.get('upper', 0)
        lower_band = bb_data.get('lower', 0)
        middle_band = bb_data.get('middle', 0)
        bb_bandwidth = bb_data.get('bandwidth', 0)

        if middle_band == 0:
            return 0, 0.0

        # Get coin-specific parameters
        if symbol:
            params = self.get_coin_parameters(symbol)
            bb_threshold = params.get('bb_compression', 0.055)
            atr_threshold = params.get('atr_expansion', 0.025)
        else:
            # Fallback to default
            bb_threshold = 0.055
            atr_threshold = 0.025

        # === VOLATILITY COMPRESSION DETECTION ===
        # BB Width calculation
        bb_width = (upper_band - lower_band) / middle_band

        # Coin-specific compression threshold
        is_compressed = bb_bandwidth < bb_threshold

        # === VOLATILITY EXPANSION DETECTION ===
        # Approximation: Use ATR relative to price
        atr_pct = atr / close if close > 0 else 0
        # Coin-specific expansion threshold
        is_expanding = atr_pct > atr_threshold

        # === VOLUME FILTER (v5.0 - DISABLED) ===
        # NOTE: avg_volume not calculated in technical_indicators.py yet
        # TODO: Implement avg_volume calculation before enabling
        # For now, bypass volume filter to test Dynamic Hard Stop alone
        has_volume = True  # Always pass volume filter for now

        # # Future implementation:
        # volume = indicators.get('volume', 0)
        # avg_volume = indicators.get('avg_volume', volume)  # 20-period average
        # volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
        # min_volume_ratio = params.get('min_volume_ratio', 1.5) if symbol else 1.5
        # has_volume = volume_ratio >= min_volume_ratio

        # === BREAKOUT CONFIRMATION ===
        # Approximation: Use ATR threshold
        # In real implementation, should check: |close - open| > ATR × 1.5
        # For now, check if we're in a volatile state
        candle_body_threshold = atr * 1.5
        # Note: Actual candle body check requires OHLC data
        # This is a simplified version - will need enhancement in backtester

        # === SIGNAL GENERATION ===
        signal = 0
        strength = 0.0

        # TWO-WAY ONLY STRATEGY: Only enter both sides simultaneously
        # Do NOT use traditional BUY/SELL signals

        # Entry signal: Volatility compression → expansion + volume confirmation (v5.0)
        if is_compressed and is_expanding and has_volume:
            signal = 2  # Special code: BOTH (LONG + SHORT simultaneously)

            # Calculate strength based on:
            # - Degree of compression (tighter = stronger)
            # - Degree of expansion (larger ATR = stronger)
            # - Combination confidence

            # Use coin-specific thresholds for strength calculation (v4.0 fix)
            # This ensures low-ATR coins (BTC, ETH) get proper strength scores
            compression_strength = max(0, (bb_threshold - bb_bandwidth) / bb_threshold) if bb_threshold > 0 else 0
            expansion_strength = min(atr_pct / atr_threshold, 1.0) if atr_threshold > 0 else 0

            # Combine signals (equal weight)
            strength = (compression_strength * 0.5 + expansion_strength * 0.5)

            # Boost strength if both conditions are very strong
            if compression_strength > 0.7 and expansion_strength > 0.7:
                strength = min(strength * 1.2, 1.0)

        # NOTE: signal = 0 (HOLD) if conditions not met
        # NO traditional BUY (1) or SELL (-1) signals in this strategy

        return signal, min(strength, 1.0)

    def generate_signal(self, data: pd.DataFrame, indicators: Dict, symbol: str = None) -> Dict:
        """Generate trading signal combining technical and ML analysis

        Args:
            data: OHLCV dataframe
            indicators: Technical indicators dictionary
            symbol: Trading symbol (e.g., 'BTC/USDT') for coin-specific parameters

        Returns:
            Signal dictionary with recommendation and details
        """
        # Get technical signals (with coin-specific parameters)
        tech_signal, tech_strength = self.analyze_technical_signals(indicators, symbol)

        # Get ML prediction if available
        ml_signal = 0
        ml_confidence = 0.0
        if self.ml_engine and self.ml_engine.rf_model is not None:
            try:
                ml_signal, ml_confidence = self.ml_engine.predict(data, indicators)
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}")
                ml_signal = 0
                ml_confidence = 0.0

        # Combine signals
        if ml_confidence < self.confidence_threshold:
            # Low ML confidence, rely on technical analysis
            final_signal = tech_signal  # Can be 2 (BOTH), 1 (BUY), 0 (HOLD), -1 (SELL)
            final_confidence = tech_strength
            signal_source = "technical"
        else:
            # For TWO-WAY strategy: if tech_signal = 2 (BOTH), always use it
            if tech_signal == 2:
                final_signal = 2  # BOTH - always execute two-way entry
                final_confidence = tech_strength
                signal_source = "technical"
            else:
                # Combine ML and technical signals with weights (traditional signals)
                combined_score = (ml_signal * ml_confidence * self.ml_weight +
                                tech_signal * tech_strength * self.technical_weight)

                if combined_score > 0.3:
                    final_signal = 1  # BUY
                elif combined_score < -0.3:
                    final_signal = -1  # SELL
                else:
                    final_signal = 0  # HOLD

                final_confidence = abs(combined_score)
                signal_source = "hybrid"

        # Signal interpretation
        signal_map = {2: 'BOTH', 1: 'BUY', 0: 'HOLD', -1: 'SELL'}

        return {
            'signal': signal_map[final_signal],
            'signal_value': final_signal,
            'confidence': final_confidence,
            'source': signal_source,
            'technical': {
                'signal': signal_map[tech_signal],
                'strength': tech_strength
            },
            'ml': {
                'signal': signal_map[ml_signal],
                'confidence': ml_confidence
            },
            'timestamp': datetime.now().isoformat(),
            'indicators': {
                'rsi': indicators.get('rsi', None),
                'macd_histogram': indicators.get('macd', {}).get('histogram', None),
                'bb_bandwidth': indicators.get('bb', {}).get('bandwidth', None),
                'atr': indicators.get('atr', None),
                'price': data['close'].iloc[-1] if not data.empty else None
            }
        }

    def should_trade(self, signal: Dict, min_confidence: float = 0.5) -> bool:
        """Determine if we should execute a trade based on signal

        Args:
            signal: Signal dictionary from generate_signal()
            min_confidence: Minimum confidence threshold

        Returns:
            True if should trade, False otherwise
        """
        if signal['signal'] == 'HOLD':
            return False

        if signal['confidence'] < min_confidence:
            return False

        return True

    def generate_tick_signal(self, ticks: list, symbol: str = None) -> Dict:
        """Generate trading signal from tick data (NO CANDLES!)

        This method uses ONLY tick data - no OHLCV assumptions.

        Args:
            ticks: List of Tick objects
            symbol: Trading symbol for coin-specific parameters

        Returns:
            Signal dictionary with recommendation and details
        """
        if len(ticks) < 100:
            return {
                'signal': 'HOLD',
                'signal_value': 0,
                'confidence': 0.0,
                'source': 'tick_insufficient_data',
                'timestamp': datetime.now().isoformat()
            }

        # Calculate tick-based indicators
        tick_summary = self.tick_indicators.generate_tick_summary(
            ticks,
            lookback_seconds=600  # 10 minutes
        )

        # Extract indicators
        volatility = tick_summary.get('volatility', 0)
        bb = tick_summary.get('bollinger_bands', {})
        bb_position = bb.get('position', 0.5)
        trend = tick_summary.get('trend', 'NEUTRAL')
        momentum = tick_summary.get('momentum', 0)
        current_price = tick_summary.get('current_price', 0)

        # Get coin-specific parameters
        params = self.get_coin_parameters(symbol) if symbol else {}
        volatility_threshold = params.get('atr_expansion', 0.01)  # 1% default

        # Generate signal using Two-Way Strategy
        signal = 0
        confidence = 0.0
        reason = "No signal"

        # TWO-WAY ENTRY: High volatility + middle BB position
        if current_price > 0:
            vol_pct = volatility / current_price

            if vol_pct > volatility_threshold:
                if 0.4 < bb_position < 0.6:  # Middle 20% of Bollinger Bands
                    signal = 2  # BOTH (LONG + SHORT simultaneously)
                    confidence = min(vol_pct / volatility_threshold, 1.0) * 0.75
                    reason = f"High volatility ({vol_pct:.3%}) + BB middle ({bb_position:.2%})"

        # Signal interpretation
        signal_map = {2: 'BOTH', 1: 'BUY', 0: 'HOLD', -1: 'SELL'}

        return {
            'signal': signal_map[signal],
            'signal_value': signal,
            'confidence': confidence,
            'source': 'tick_based',
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'tick_indicators': {
                'volatility': volatility,
                'volatility_pct': volatility / current_price if current_price > 0 else 0,
                'bb_position': bb_position,
                'trend': trend,
                'momentum': momentum,
                'price': current_price,
                'tick_count': len(ticks)
            }
        }


class RiskManager:
    """Risk management for trading operations"""

    def __init__(self,
                 max_position_size: float = 0.2,
                 stop_loss_pct: float = 0.03,
                 take_profit_pct: float = 0.05,
                 daily_loss_limit: float = 0.1,
                 max_drawdown: float = 0.25):
        """Initialize risk manager

        Args:
            max_position_size: Maximum position size as fraction of balance
            stop_loss_pct: Stop loss percentage
            take_profit_pct: Take profit percentage
            daily_loss_limit: Maximum daily loss as fraction of balance
            max_drawdown: Maximum drawdown tolerance
        """
        self.max_position_size = max_position_size
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_loss_limit = daily_loss_limit
        self.max_drawdown = max_drawdown

        self.daily_pnl = 0.0
        self.peak_balance = 0.0

        logger.info(f"RiskManager initialized with max_position={max_position_size}")

    def calculate_position_size(self, balance: float, price: float,
                                confidence: float) -> float:
        """Calculate position size based on balance and confidence

        Args:
            balance: Available balance
            price: Current price
            confidence: Signal confidence (0-1)

        Returns:
            Position size in base currency
        """
        # Base position size
        max_investment = balance * self.max_position_size

        # Adjust by confidence (50% to 100% of max position)
        confidence_factor = 0.5 + (confidence * 0.5)
        investment = max_investment * confidence_factor

        # Calculate position size
        position_size = investment / price

        return position_size

    def check_stop_loss(self, entry_price: float, current_price: float,
                       position_type: str) -> bool:
        """Check if stop loss should be triggered

        Args:
            entry_price: Entry price
            current_price: Current price
            position_type: 'LONG' or 'SHORT'

        Returns:
            True if stop loss triggered
        """
        if position_type == 'LONG':
            loss_pct = (entry_price - current_price) / entry_price
        else:  # SHORT
            loss_pct = (current_price - entry_price) / entry_price

        return loss_pct >= self.stop_loss_pct

    def check_take_profit(self, entry_price: float, current_price: float,
                         position_type: str) -> bool:
        """Check if take profit should be triggered

        Args:
            entry_price: Entry price
            current_price: Current price
            position_type: 'LONG' or 'SHORT'

        Returns:
            True if take profit triggered
        """
        if position_type == 'LONG':
            profit_pct = (current_price - entry_price) / entry_price
        else:  # SHORT
            profit_pct = (entry_price - current_price) / entry_price

        return profit_pct >= self.take_profit_pct

    def can_open_position(self, balance: float) -> bool:
        """Check if we can open new position based on risk limits

        Args:
            balance: Current balance

        Returns:
            True if can open position
        """
        # Update peak balance
        if balance > self.peak_balance:
            self.peak_balance = balance

        # Check daily loss limit
        if self.daily_pnl < -(balance * self.daily_loss_limit):
            logger.warning(f"Daily loss limit reached: {self.daily_pnl}")
            return False

        # Check max drawdown
        if self.peak_balance > 0:
            current_drawdown = (self.peak_balance - balance) / self.peak_balance
            if current_drawdown >= self.max_drawdown:
                logger.warning(f"Max drawdown reached: {current_drawdown:.2%}")
                return False

        return True

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L tracking

        Args:
            pnl: Profit/loss from closed position
        """
        self.daily_pnl += pnl

    def reset_daily_pnl(self):
        """Reset daily P&L counter (call at start of new day)"""
        self.daily_pnl = 0.0
        logger.info("Daily P&L reset")


# Example usage - TICK-BASED TEST
if __name__ == "__main__":
    """
    틱 데이터 기반 전략 테스트
    ❌ 캔들 데이터 사용 금지!
    """
    from tick_data_collector import TickDataCollector
    import asyncio

    async def test_tick_strategy():
        # Initialize components
        strategy = TradingStrategy(ml_weight=0.6, technical_weight=0.4)
        risk_manager = RiskManager()

        symbol = "BTC/USDT"
        print(f"✅ 틱 데이터 기반 테스트: {symbol}")

        # Collect tick data (5 minutes)
        collector = TickDataCollector(symbols=[symbol], buffer_size=10000)
        print("📡 틱 데이터 수집 중 (5분)...")

        collection_task = asyncio.create_task(collector.start())
        await asyncio.sleep(300)  # 5 minutes
        await collector.stop()
        collection_task.cancel()

        # Get collected ticks
        ticks = list(collector.tick_buffers[symbol])
        print(f"✅ 수집된 틱: {len(ticks):,}개")

        if len(ticks) < 100:
            print("⚠️  틱 데이터 부족 (최소 100개 필요)")
            return

        # Generate tick-based signal
        print("\n=== 틱 기반 트레이딩 신호 ===")
        signal = strategy.generate_tick_signal(ticks, symbol)

        print(f"신호: {signal['signal']}")
        print(f"신뢰도: {signal['confidence']:.2%}")
        print(f"소스: {signal['source']}")
        print(f"이유: {signal.get('reason', 'N/A')}")

        # Tick indicators
        tick_ind = signal.get('tick_indicators', {})
        print(f"\n틱 지표:")
        print(f"  변동성: {tick_ind.get('volatility', 0):.4f}")
        print(f"  변동성 %: {tick_ind.get('volatility_pct', 0):.3%}")
        print(f"  BB 포지션: {tick_ind.get('bb_position', 0):.2%}")
        print(f"  트렌드: {tick_ind.get('trend', 'N/A')}")
        print(f"  모멘텀: {tick_ind.get('momentum', 0):.6f}")
        print(f"  현재 가격: ${tick_ind.get('price', 0):,.2f}")

        # Check if should trade
        should_trade = strategy.should_trade(signal, min_confidence=0.5)
        print(f"\n거래 실행: {'예' if should_trade else '아니오'}")

        if should_trade:
            balance = 10000.0
            price = tick_ind.get('price', 0)
            if price > 0:
                position_size = risk_manager.calculate_position_size(
                    balance, price, signal['confidence']
                )
                print(f"\n포지션 크기:")
                print(f"  잔고: ${balance:,.2f}")
                print(f"  가격: ${price:,.2f}")
                print(f"  포지션: {position_size:.6f} BTC")
                print(f"  투자액: ${position_size * price:,.2f}")

    # Run test
    asyncio.run(test_tick_strategy())
