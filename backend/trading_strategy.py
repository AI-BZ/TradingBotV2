"""
Trading Strategy Engine - Combines technical indicators and ML predictions
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

from technical_indicators import TechnicalIndicators
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

        logger.info(f"TradingStrategy initialized: ML weight={ml_weight}, Technical weight={technical_weight}")

    def set_ml_engine(self, ml_engine: MLEngine):
        """Set ML engine for predictions"""
        self.ml_engine = ml_engine

    def analyze_technical_signals(self, indicators: Dict) -> Tuple[int, float]:
        """Analyze technical indicators for trading signals

        Args:
            indicators: Dictionary of technical indicators

        Returns:
            Tuple of (signal, strength)
            signal: 1 (BUY), 0 (HOLD), -1 (SELL)
            strength: Signal strength 0-1
        """
        buy_signals = 0
        sell_signals = 0
        total_signals = 0

        # RSI signals
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 30:
                buy_signals += 2  # Strong buy signal
                total_signals += 2
            elif rsi < 40:
                buy_signals += 1
                total_signals += 1
            elif rsi > 70:
                sell_signals += 2  # Strong sell signal
                total_signals += 2
            elif rsi > 60:
                sell_signals += 1
                total_signals += 1
            else:
                total_signals += 1  # Neutral

        # MACD signals
        if 'macd' in indicators:
            macd_data = indicators['macd']
            histogram = macd_data.get('histogram', 0)
            if histogram > 0:
                buy_signals += 1
            elif histogram < 0:
                sell_signals += 1
            total_signals += 1

        # Bollinger Bands signals
        if 'bb' in indicators and 'close' in indicators:
            bb_data = indicators['bb']
            close = indicators.get('close', 0)
            lower = bb_data.get('lower', 0)
            upper = bb_data.get('upper', 0)
            middle = bb_data.get('middle', 0)

            if close < lower:
                buy_signals += 2  # Price below lower band
                total_signals += 2
            elif close > upper:
                sell_signals += 2  # Price above upper band
                total_signals += 2
            else:
                total_signals += 1

        # SMA crossover signals
        if 'sma' in indicators:
            sma_data = indicators['sma']
            sma_20 = sma_data.get('sma_20', 0)
            sma_50 = sma_data.get('sma_50', 0)

            if sma_20 > sma_50:
                buy_signals += 1  # Bullish crossover
            elif sma_20 < sma_50:
                sell_signals += 1  # Bearish crossover
            total_signals += 1

        # Calculate signal and strength
        if total_signals == 0:
            return 0, 0.0

        net_signal = buy_signals - sell_signals
        strength = abs(net_signal) / total_signals

        if net_signal > 0:
            signal = 1  # BUY
        elif net_signal < 0:
            signal = -1  # SELL
        else:
            signal = 0  # HOLD

        return signal, min(strength, 1.0)

    def generate_signal(self, data: pd.DataFrame, indicators: Dict) -> Dict:
        """Generate trading signal combining technical and ML analysis

        Args:
            data: OHLCV dataframe
            indicators: Technical indicators dictionary

        Returns:
            Signal dictionary with recommendation and details
        """
        # Get technical signals
        tech_signal, tech_strength = self.analyze_technical_signals(indicators)

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
            final_signal = tech_signal
            final_confidence = tech_strength
            signal_source = "technical"
        else:
            # Combine ML and technical signals with weights
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
        signal_map = {1: 'BUY', 0: 'HOLD', -1: 'SELL'}

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


# Example usage
if __name__ == "__main__":
    from binance_client import BinanceClient
    import asyncio

    async def test_strategy():
        # Initialize components
        strategy = TradingStrategy(ml_weight=0.6, technical_weight=0.4)
        risk_manager = RiskManager()

        # Get market data
        client = BinanceClient(testnet=True)
        symbol = "BTCUSDT"

        print(f"Fetching data for {symbol}...")
        klines = await client.get_klines(symbol, interval='1h', limit=100)

        data = pd.DataFrame(klines)
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')

        # Calculate indicators
        print("Calculating technical indicators...")
        indicators = TechnicalIndicators.calculate_all(
            data['high'].tolist(),
            data['low'].tolist(),
            data['close'].tolist(),
            data['volume'].tolist()
        )
        indicators['close'] = data['close'].iloc[-1]

        # Generate signal
        print("\n=== Trading Signal ===")
        signal = strategy.generate_signal(data, indicators)

        print(f"Signal: {signal['signal']} ({signal['signal_value']})")
        print(f"Confidence: {signal['confidence']:.2%}")
        print(f"Source: {signal['source']}")
        print(f"\nTechnical Analysis:")
        print(f"  Signal: {signal['technical']['signal']}")
        print(f"  Strength: {signal['technical']['strength']:.2%}")
        print(f"\nML Prediction:")
        print(f"  Signal: {signal['ml']['signal']}")
        print(f"  Confidence: {signal['ml']['confidence']:.2%}")

        # Check if should trade
        should_trade = strategy.should_trade(signal, min_confidence=0.5)
        print(f"\nShould Trade: {'YES' if should_trade else 'NO'}")

        if should_trade:
            # Calculate position size
            balance = 10000.0
            price = data['close'].iloc[-1]
            position_size = risk_manager.calculate_position_size(
                balance, price, signal['confidence']
            )
            print(f"\nPosition Sizing:")
            print(f"  Balance: ${balance:,.2f}")
            print(f"  Price: ${price:,.2f}")
            print(f"  Position Size: {position_size:.6f} BTC")
            print(f"  Investment: ${position_size * price:,.2f}")

        await client.close()

    # Run test
    asyncio.run(test_strategy())
