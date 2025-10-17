"""
Tick-Based Technical Indicators
Complete rewrite of all indicators to work ONLY with tick data

CRITICAL RULE: NO OHLCV assumptions. NO candle data.
All calculations use tick-by-tick price updates only.

Traditional indicators like SMA, ATR, RSI assume OHLCV candles.
Tick-based indicators use time-weighted and volume-weighted calculations instead.
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)


class TickIndicators:
    """Technical indicators calculated from tick data only

    NO candle data (open, high, low, close) is used.
    All calculations are based on:
    - Tick prices (last traded price)
    - Bid/ask spreads
    - Time-weighted averages
    - Volume-weighted averages
    """

    @staticmethod
    def calculate_vwap(ticks: List, lookback_seconds: int = 3600) -> float:
        """Volume-Weighted Average Price (VWAP)

        Replaces SMA for tick data.
        Uses 24h volume as weight since tick-level volume not available.

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds (default: 1 hour)

        Returns:
            VWAP value
        """
        if not ticks:
            return 0.0

        # Filter ticks within lookback window
        cutoff_time = ticks[-1].timestamp - timedelta(seconds=lookback_seconds)
        recent_ticks = [t for t in ticks if t.timestamp >= cutoff_time]

        if not recent_ticks:
            return ticks[-1].price

        # Volume-weighted calculation
        total_volume = sum(t.volume_24h for t in recent_ticks)
        if total_volume == 0:
            # Fallback to simple average if no volume data
            return sum(t.price for t in recent_ticks) / len(recent_ticks)

        vwap = sum(t.price * t.volume_24h for t in recent_ticks) / total_volume
        return vwap

    @staticmethod
    def calculate_time_weighted_average(
        ticks: List,
        lookback_seconds: int = 3600
    ) -> float:
        """Time-Weighted Average Price (TWAP)

        Alternative to VWAP when volume data unreliable.
        Gives equal weight to all ticks within time window.

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds

        Returns:
            TWAP value
        """
        if not ticks:
            return 0.0

        cutoff_time = ticks[-1].timestamp - timedelta(seconds=lookback_seconds)
        recent_ticks = [t for t in ticks if t.timestamp >= cutoff_time]

        if not recent_ticks:
            return ticks[-1].price

        return sum(t.price for t in recent_ticks) / len(recent_ticks)

    @staticmethod
    def calculate_tick_volatility(
        ticks: List,
        lookback_seconds: int = 3600
    ) -> float:
        """Tick-based volatility (replaces ATR)

        Calculates standard deviation of tick price changes.
        NO high/low/close assumption - uses tick-to-tick changes only.

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds

        Returns:
            Volatility value (standard deviation of price changes)
        """
        if len(ticks) < 2:
            return 0.0

        # Filter ticks within lookback window
        cutoff_time = ticks[-1].timestamp - timedelta(seconds=lookback_seconds)
        recent_ticks = [t for t in ticks if t.timestamp >= cutoff_time]

        if len(recent_ticks) < 2:
            return 0.0

        # Calculate tick-to-tick price changes
        price_changes = [
            abs(recent_ticks[i].price - recent_ticks[i-1].price)
            for i in range(1, len(recent_ticks))
        ]

        # Standard deviation of changes
        volatility = np.std(price_changes) if price_changes else 0.0
        return volatility

    @staticmethod
    def calculate_tick_momentum(
        ticks: List,
        lookback_seconds: int = 3600
    ) -> float:
        """Tick-based momentum (replaces RSI/MACD)

        Measures rate of price change over time window.
        Positive = upward momentum, Negative = downward momentum.

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds

        Returns:
            Momentum value (percentage change per second)
        """
        if len(ticks) < 2:
            return 0.0

        cutoff_time = ticks[-1].timestamp - timedelta(seconds=lookback_seconds)
        recent_ticks = [t for t in ticks if t.timestamp >= cutoff_time]

        if len(recent_ticks) < 2:
            return 0.0

        # Price change over time window
        start_price = recent_ticks[0].price
        end_price = recent_ticks[-1].price

        if start_price == 0:
            return 0.0

        # Percentage change
        pct_change = ((end_price - start_price) / start_price) * 100

        # Normalize by time (momentum per second)
        time_elapsed = (recent_ticks[-1].timestamp - recent_ticks[0].timestamp).total_seconds()
        if time_elapsed == 0:
            return 0.0

        momentum = pct_change / time_elapsed
        return momentum

    @staticmethod
    def calculate_tick_bollinger_bands(
        ticks: List,
        lookback_seconds: int = 3600,
        num_std: float = 2.0
    ) -> Tuple[float, float, float]:
        """Tick-based Bollinger Bands

        Uses VWAP as middle band, volatility for upper/lower bands.
        NO assumption of OHLCV candles.

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds
            num_std: Number of standard deviations for bands

        Returns:
            (upper_band, middle_band, lower_band)
        """
        if not ticks:
            return 0.0, 0.0, 0.0

        # Middle band = VWAP
        middle = TickIndicators.calculate_vwap(ticks, lookback_seconds)

        # Band width = volatility
        volatility = TickIndicators.calculate_tick_volatility(ticks, lookback_seconds)

        # Upper/lower bands
        upper = middle + (num_std * volatility)
        lower = middle - (num_std * volatility)

        return upper, middle, lower

    @staticmethod
    def calculate_bid_ask_spread(ticks: List) -> float:
        """Average bid-ask spread

        Tick data advantage: can measure true market liquidity.
        Candle data doesn't have this information.

        Args:
            ticks: List of Tick objects

        Returns:
            Average spread as percentage of price
        """
        if not ticks:
            return 0.0

        spreads = [
            ((t.ask - t.bid) / t.price) * 100
            for t in ticks
            if t.price > 0
        ]

        return np.mean(spreads) if spreads else 0.0

    @staticmethod
    def calculate_tick_trend(
        ticks: List,
        short_window: int = 300,   # 5 minutes
        long_window: int = 1800    # 30 minutes
    ) -> str:
        """Tick-based trend detection

        Compares short-term vs long-term VWAP to determine trend.
        Replaces MACD crossover logic.

        Args:
            ticks: List of Tick objects
            short_window: Short-term window in seconds
            long_window: Long-term window in seconds

        Returns:
            'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        if len(ticks) < 2:
            return 'NEUTRAL'

        # Calculate VWAPs
        short_vwap = TickIndicators.calculate_vwap(ticks, short_window)
        long_vwap = TickIndicators.calculate_vwap(ticks, long_window)

        if short_vwap == 0 or long_vwap == 0:
            return 'NEUTRAL'

        # Crossover detection
        diff_pct = ((short_vwap - long_vwap) / long_vwap) * 100

        if diff_pct > 0.5:
            return 'BULLISH'
        elif diff_pct < -0.5:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    @staticmethod
    def calculate_tick_support_resistance(
        ticks: List,
        lookback_seconds: int = 3600,
        tolerance: float = 0.002  # 0.2% tolerance
    ) -> Tuple[float, float]:
        """Tick-based support and resistance levels

        Identifies price levels where ticks cluster.
        Uses tick density, not candle high/low.

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds
            tolerance: Price clustering tolerance (fraction)

        Returns:
            (support_level, resistance_level)
        """
        if len(ticks) < 10:
            current_price = ticks[-1].price if ticks else 0
            return current_price, current_price

        # Filter recent ticks
        cutoff_time = ticks[-1].timestamp - timedelta(seconds=lookback_seconds)
        recent_ticks = [t for t in ticks if t.timestamp >= cutoff_time]

        if not recent_ticks:
            current_price = ticks[-1].price
            return current_price, current_price

        # Get price range
        prices = [t.price for t in recent_ticks]
        current_price = recent_ticks[-1].price

        # Find support (price below current where ticks cluster)
        support_candidates = [p for p in prices if p < current_price]
        if support_candidates:
            # Most common price below current (with tolerance)
            support = np.percentile(support_candidates, 25)  # 25th percentile
        else:
            support = current_price * 0.99

        # Find resistance (price above current where ticks cluster)
        resistance_candidates = [p for p in prices if p > current_price]
        if resistance_candidates:
            # Most common price above current (with tolerance)
            resistance = np.percentile(resistance_candidates, 75)  # 75th percentile
        else:
            resistance = current_price * 1.01

        return support, resistance

    @staticmethod
    def calculate_tick_volume_profile(
        ticks: List,
        lookback_seconds: int = 3600,
        num_bins: int = 20
    ) -> dict:
        """Volume profile from tick data

        Shows which price levels have most trading activity.
        Tick data advantage: can see true volume distribution.

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds
            num_bins: Number of price bins

        Returns:
            Dictionary with volume distribution
        """
        if not ticks:
            return {}

        # Filter recent ticks
        cutoff_time = ticks[-1].timestamp - timedelta(seconds=lookback_seconds)
        recent_ticks = [t for t in ticks if t.timestamp >= cutoff_time]

        if not recent_ticks:
            return {}

        # Create price bins
        prices = [t.price for t in recent_ticks]
        volumes = [t.volume_24h for t in recent_ticks]

        min_price = min(prices)
        max_price = max(prices)

        if min_price == max_price:
            return {
                'poc': recent_ticks[-1].price,  # Point of Control
                'value_area_high': recent_ticks[-1].price,
                'value_area_low': recent_ticks[-1].price
            }

        # Histogram of volume by price
        hist, bin_edges = np.histogram(prices, bins=num_bins, weights=volumes)

        # Point of Control (price with highest volume)
        poc_idx = np.argmax(hist)
        poc = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2

        # Value Area (70% of volume)
        total_volume = sum(hist)
        target_volume = total_volume * 0.70

        # Find value area around POC
        cumsum = 0
        low_idx = poc_idx
        high_idx = poc_idx

        while cumsum < target_volume and (low_idx > 0 or high_idx < len(hist) - 1):
            if low_idx > 0:
                cumsum += hist[low_idx - 1]
                low_idx -= 1
            if high_idx < len(hist) - 1 and cumsum < target_volume:
                cumsum += hist[high_idx + 1]
                high_idx += 1

        value_area_low = bin_edges[low_idx]
        value_area_high = bin_edges[high_idx + 1]

        return {
            'poc': poc,
            'value_area_high': value_area_high,
            'value_area_low': value_area_low,
            'volume_distribution': list(hist),
            'price_bins': list(bin_edges)
        }

    @staticmethod
    def generate_tick_summary(ticks: List, lookback_seconds: int = 3600) -> dict:
        """Generate comprehensive tick-based indicator summary

        Args:
            ticks: List of Tick objects
            lookback_seconds: Time window in seconds

        Returns:
            Dictionary with all indicators
        """
        if not ticks:
            return {}

        # Calculate all indicators
        vwap = TickIndicators.calculate_vwap(ticks, lookback_seconds)
        volatility = TickIndicators.calculate_tick_volatility(ticks, lookback_seconds)
        momentum = TickIndicators.calculate_tick_momentum(ticks, lookback_seconds)
        upper_bb, middle_bb, lower_bb = TickIndicators.calculate_tick_bollinger_bands(ticks, lookback_seconds)
        spread = TickIndicators.calculate_bid_ask_spread(ticks[-100:])  # Recent spread
        trend = TickIndicators.calculate_tick_trend(ticks)
        support, resistance = TickIndicators.calculate_tick_support_resistance(ticks, lookback_seconds)
        volume_profile = TickIndicators.calculate_tick_volume_profile(ticks, lookback_seconds)

        current_price = ticks[-1].price
        current_time = ticks[-1].timestamp

        # Bollinger Band position
        if upper_bb != lower_bb:
            bb_position = (current_price - lower_bb) / (upper_bb - lower_bb)
        else:
            bb_position = 0.5

        return {
            'timestamp': current_time.isoformat(),
            'current_price': current_price,
            'vwap': vwap,
            'volatility': volatility,
            'momentum': momentum,
            'bollinger_bands': {
                'upper': upper_bb,
                'middle': middle_bb,
                'lower': lower_bb,
                'position': bb_position  # 0 = lower band, 1 = upper band
            },
            'bid_ask_spread': spread,
            'trend': trend,
            'support': support,
            'resistance': resistance,
            'volume_profile': volume_profile,
            'tick_count': len(ticks)
        }


def compare_with_candle_based(tick_summary: dict):
    """Log comparison between tick-based and traditional candle-based indicators

    This helps understand the difference between real-time tick data
    and delayed candle data.
    """
    logger.info("\n" + "="*80)
    logger.info("📊 TICK-BASED vs CANDLE-BASED INDICATOR COMPARISON")
    logger.info("="*80)
    logger.info(f"Tick Data:")
    logger.info(f"  - VWAP (replaces SMA): ${tick_summary['vwap']:.2f}")
    logger.info(f"  - Volatility (replaces ATR): {tick_summary['volatility']:.4f}")
    logger.info(f"  - Momentum (replaces RSI): {tick_summary['momentum']:.6f}")
    logger.info(f"  - Trend (replaces MACD): {tick_summary['trend']}")
    logger.info(f"  - Bollinger Position: {tick_summary['bollinger_bands']['position']:.2%}")
    logger.info(f"  - Bid-Ask Spread: {tick_summary['bid_ask_spread']:.3f}%")
    logger.info("\nCandle Data Limitations:")
    logger.info("  - SMA: Uses OHLC, ignores intra-candle movement")
    logger.info("  - ATR: Based on High-Low range, misses tick volatility")
    logger.info("  - RSI: Requires close prices, can't see real-time momentum")
    logger.info("  - MACD: Lagging indicator, tick trend is immediate")
    logger.info("  - Bollinger: Uses SMA, tick version uses VWAP")
    logger.info("  - Spread: NOT available in candle data at all!")
    logger.info("="*80 + "\n")


if __name__ == "__main__":
    """Test tick indicators with sample data"""
    from tick_data_collector import Tick
    from datetime import datetime, timedelta

    # Create sample ticks
    base_time = datetime.now()
    sample_ticks = []

    # Simulate 1000 ticks over 100 seconds (10 ticks/second)
    for i in range(1000):
        price = 50000 + np.random.randn() * 100  # Random walk around $50k
        tick = Tick(
            symbol='BTC/USDT',
            timestamp=base_time + timedelta(seconds=i*0.1),
            price=price,
            bid=price - 0.5,
            ask=price + 0.5,
            bid_qty=1.5,
            ask_qty=1.5,
            volume_24h=1000.0,
            quote_volume_24h=50000000.0,
            price_change_pct=0.05
        )
        sample_ticks.append(tick)

    # Generate tick summary
    summary = TickIndicators.generate_tick_summary(sample_ticks, lookback_seconds=60)

    # Display results
    print("\n📊 Tick Indicator Test Results:")
    print(f"Current Price: ${summary['current_price']:.2f}")
    print(f"VWAP: ${summary['vwap']:.2f}")
    print(f"Volatility: {summary['volatility']:.4f}")
    print(f"Momentum: {summary['momentum']:.6f}")
    print(f"Trend: {summary['trend']}")
    print(f"Bollinger Bands: ${summary['bollinger_bands']['lower']:.2f} - ${summary['bollinger_bands']['upper']:.2f}")
    print(f"Support: ${summary['support']:.2f}")
    print(f"Resistance: ${summary['resistance']:.2f}")
    print(f"Bid-Ask Spread: {summary['bid_ask_spread']:.3f}%")

    # Compare with candle-based
    compare_with_candle_based(summary)
