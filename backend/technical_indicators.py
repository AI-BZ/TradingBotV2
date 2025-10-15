"""
Technical Indicators Engine
Calculate RSI, MACD, Bollinger Bands, Moving Averages, and more
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """Calculate technical indicators for trading strategies"""

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index (RSI)

        Args:
            prices: List of closing prices
            period: RSI period (default: 14)

        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0  # Neutral if not enough data

        df = pd.DataFrame({'close': prices})
        delta = df['close'].diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1])

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, float]:
        """Calculate MACD (Moving Average Convergence Divergence)

        Args:
            prices: List of closing prices
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period

        Returns:
            Dict with 'macd', 'signal', 'histogram'
        """
        if len(prices) < slow_period:
            return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}

        df = pd.DataFrame({'close': prices})

        # Calculate EMAs
        fast_ema = df['close'].ewm(span=fast_period, adjust=False).mean()
        slow_ema = df['close'].ewm(span=slow_period, adjust=False).mean()

        # MACD line
        macd = fast_ema - slow_ema

        # Signal line
        signal = macd.ewm(span=signal_period, adjust=False).mean()

        # Histogram
        histogram = macd - signal

        return {
            'macd': float(macd.iloc[-1]),
            'signal': float(signal.iloc[-1]),
            'histogram': float(histogram.iloc[-1])
        }

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: int = 2
    ) -> Dict[str, float]:
        """Calculate Bollinger Bands

        Args:
            prices: List of closing prices
            period: Moving average period
            std_dev: Standard deviation multiplier

        Returns:
            Dict with 'upper', 'middle', 'lower', 'bandwidth'
        """
        if len(prices) < period:
            return {'upper': 0.0, 'middle': 0.0, 'lower': 0.0, 'bandwidth': 0.0}

        df = pd.DataFrame({'close': prices})

        # Middle band (SMA)
        middle = df['close'].rolling(window=period).mean()

        # Standard deviation
        std = df['close'].rolling(window=period).std()

        # Upper and lower bands
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        # Bandwidth
        bandwidth = (upper - lower) / middle

        return {
            'upper': float(upper.iloc[-1]),
            'middle': float(middle.iloc[-1]),
            'lower': float(lower.iloc[-1]),
            'bandwidth': float(bandwidth.iloc[-1])
        }

    @staticmethod
    def calculate_moving_averages(
        prices: List[float],
        periods: List[int] = [20, 50, 200]
    ) -> Dict[int, float]:
        """Calculate Simple Moving Averages (SMA)

        Args:
            prices: List of closing prices
            periods: List of periods to calculate

        Returns:
            Dict of period: value
        """
        df = pd.DataFrame({'close': prices})
        result = {}

        for period in periods:
            if len(prices) >= period:
                sma = df['close'].rolling(window=period).mean()
                result[period] = float(sma.iloc[-1])
            else:
                result[period] = 0.0

        return result

    @staticmethod
    def calculate_ema(prices: List[float], period: int = 20) -> float:
        """Calculate Exponential Moving Average (EMA)

        Args:
            prices: List of closing prices
            period: EMA period

        Returns:
            EMA value
        """
        if len(prices) < period:
            return 0.0

        df = pd.DataFrame({'close': prices})
        ema = df['close'].ewm(span=period, adjust=False).mean()

        return float(ema.iloc[-1])

    @staticmethod
    def calculate_atr(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> float:
        """Calculate Average True Range (ATR)

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            period: ATR period

        Returns:
            ATR value
        """
        if len(highs) < period + 1:
            return 0.0

        df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})

        # True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # ATR
        atr = df['tr'].rolling(window=period).mean()

        return float(atr.iloc[-1])

    @staticmethod
    def calculate_stochastic(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        k_period: int = 14,
        d_period: int = 3
    ) -> Dict[str, float]:
        """Calculate Stochastic Oscillator

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            k_period: %K period
            d_period: %D period

        Returns:
            Dict with 'k' and 'd' values
        """
        if len(closes) < k_period:
            return {'k': 50.0, 'd': 50.0}

        df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})

        # %K
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()
        k = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))

        # %D (SMA of %K)
        d = k.rolling(window=d_period).mean()

        return {
            'k': float(k.iloc[-1]),
            'd': float(d.iloc[-1])
        }

    @staticmethod
    def calculate_adx(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> float:
        """Calculate Average Directional Index (ADX)

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            period: ADX period

        Returns:
            ADX value (0-100)
        """
        if len(closes) < period + 1:
            return 0.0

        df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})

        # True Range
        df['tr'] = df[['high', 'low', 'close']].apply(
            lambda row: max(
                row['high'] - row['low'],
                abs(row['high'] - df['close'].shift().iloc[row.name]),
                abs(row['low'] - df['close'].shift().iloc[row.name])
            ) if row.name > 0 else row['high'] - row['low'],
            axis=1
        )

        # Directional Movement
        df['up_move'] = df['high'] - df['high'].shift()
        df['down_move'] = df['low'].shift() - df['low']

        df['+dm'] = df.apply(
            lambda row: row['up_move'] if row['up_move'] > row['down_move'] and row['up_move'] > 0 else 0,
            axis=1
        )
        df['-dm'] = df.apply(
            lambda row: row['down_move'] if row['down_move'] > row['up_move'] and row['down_move'] > 0 else 0,
            axis=1
        )

        # Smoothed values
        atr = df['tr'].rolling(window=period).mean()
        plus_di = 100 * (df['+dm'].rolling(window=period).mean() / atr)
        minus_di = 100 * (df['-dm'].rolling(window=period).mean() / atr)

        # DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # ADX (smoothed DX)
        adx = dx.rolling(window=period).mean()

        return float(adx.iloc[-1])

    @classmethod
    def calculate_all(
        cls,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float] = None
    ) -> Dict:
        """Calculate all indicators at once

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            volumes: List of volumes (optional)

        Returns:
            Dictionary of all indicators
        """
        indicators = {}

        # RSI
        indicators['rsi'] = cls.calculate_rsi(closes)

        # MACD
        indicators['macd'] = cls.calculate_macd(closes)

        # Bollinger Bands
        indicators['bb'] = cls.calculate_bollinger_bands(closes)

        # Moving Averages
        indicators['sma'] = cls.calculate_moving_averages(closes)

        # EMA
        indicators['ema_20'] = cls.calculate_ema(closes, 20)
        indicators['ema_50'] = cls.calculate_ema(closes, 50)

        # ATR
        indicators['atr'] = cls.calculate_atr(highs, lows, closes)

        # Stochastic
        indicators['stoch'] = cls.calculate_stochastic(highs, lows, closes)

        # ADX
        indicators['adx'] = cls.calculate_adx(highs, lows, closes)

        return indicators


# Example usage
if __name__ == "__main__":
    # Sample data (100 candles)
    np.random.seed(42)
    base_price = 43000
    closes = base_price + np.cumsum(np.random.randn(100) * 100)
    highs = closes + np.random.rand(100) * 50
    lows = closes - np.random.rand(100) * 50

    closes = closes.tolist()
    highs = highs.tolist()
    lows = lows.tolist()

    # Calculate indicators
    ti = TechnicalIndicators()

    print("=== Technical Indicators ===")
    print(f"RSI: {ti.calculate_rsi(closes):.2f}")

    macd = ti.calculate_macd(closes)
    print(f"MACD: {macd['macd']:.2f}, Signal: {macd['signal']:.2f}, Histogram: {macd['histogram']:.2f}")

    bb = ti.calculate_bollinger_bands(closes)
    print(f"BB Upper: {bb['upper']:.2f}, Middle: {bb['middle']:.2f}, Lower: {bb['lower']:.2f}")

    sma = ti.calculate_moving_averages(closes)
    print(f"SMA20: {sma[20]:.2f}, SMA50: {sma[50]:.2f}")

    print(f"ATR: {ti.calculate_atr(highs, lows, closes):.2f}")

    # Calculate all at once
    all_indicators = ti.calculate_all(highs, lows, closes)
    print("\n=== All Indicators ===")
    print(json.dumps(all_indicators, indent=2, default=str))
