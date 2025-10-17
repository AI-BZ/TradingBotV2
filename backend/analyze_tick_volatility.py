"""
틱 데이터 변동성 특성 분석
실제 데이터를 기반으로 최적의 임계값 범위를 찾습니다.
"""
import asyncio
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import logging

from binance_client import BinanceClient
from tick_data_collector import Tick
from tick_indicators import TickIndicators

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TickVolatilityAnalyzer:
    """틱 데이터의 변동성 특성을 분석"""

    def __init__(self):
        self.binance = BinanceClient(testnet=True)
        self.tick_indicators = TickIndicators()

    async def fetch_sample_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> List[Tick]:
        """샘플 틱 데이터 가져오기 (1일치)"""
        logger.info(f"Fetching data for {symbol}: {start_date}")

        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)

        # 1분봉 가져오기
        ohlcv = await self.binance.exchange.fetch_ohlcv(
            symbol,
            timeframe='1m',
            since=start_ts,
            limit=1000
        )

        if not ohlcv:
            return []

        # 틱 시뮬레이션
        ticks = []
        for kline in ohlcv:
            open_time = kline[0]
            open_price = float(kline[1])
            high = float(kline[2])
            low = float(kline[3])
            close = float(kline[4])
            volume = float(kline[5])

            # 10 ticks per minute
            for i in range(10):
                tick_time = open_time + (i * 6000)
                progress = i / 9 if i < 9 else 1.0
                price = open_price + (close - open_price) * progress

                spread_pct = 0.0001
                bid = price * (1 - spread_pct)
                ask = price * (1 + spread_pct)

                tick = Tick(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(tick_time / 1000),
                    price=price,
                    bid=bid,
                    ask=ask,
                    bid_qty=volume / 10,
                    ask_qty=volume / 10,
                    volume_24h=volume * 1440,
                    quote_volume_24h=volume * price * 1440,
                    price_change_pct=((close - open_price) / open_price) * 100 if open_price > 0 else 0
                )
                ticks.append(tick)

        logger.info(f"Generated {len(ticks):,} ticks for {symbol}")
        return ticks

    def analyze_volatility_characteristics(
        self,
        ticks: List[Tick],
        symbol: str
    ) -> Dict:
        """변동성 특성 분석"""
        logger.info(f"\n{'='*80}")
        logger.info(f"Analyzing {symbol} volatility characteristics")
        logger.info(f"{'='*80}")

        if len(ticks) < 100:
            return {}

        prices = [t.price for t in ticks]
        avg_price = np.mean(prices)

        # 1. 표준편차 기반 변동성 (현재 방식)
        price_changes = [
            abs(ticks[i].price - ticks[i-1].price)
            for i in range(1, len(ticks))
        ]
        std_volatility = np.std(price_changes)
        std_volatility_pct = (std_volatility / avg_price) * 100

        # 2. ATR-like 변동성 (high-low 범위)
        # 각 10분 윈도우의 고가-저가
        window_size = 100  # 10분 = 100 ticks
        atr_like_values = []
        for i in range(0, len(ticks) - window_size, window_size):
            window = ticks[i:i+window_size]
            high = max(t.price for t in window)
            low = min(t.price for t in window)
            atr_like_values.append(high - low)

        atr_volatility = np.mean(atr_like_values) if atr_like_values else 0
        atr_volatility_pct = (atr_volatility / avg_price) * 100

        # 3. 백분위수 기반 변동성
        percentile_90 = np.percentile(price_changes, 90)
        percentile_90_pct = (percentile_90 / avg_price) * 100

        # 4. 롤링 표준편차 (다양한 윈도우)
        rolling_std_60s = []  # 1분
        rolling_std_300s = []  # 5분
        rolling_std_600s = []  # 10분

        for lookback in [60, 300, 600]:
            for i in range(len(ticks)):
                cutoff_time = ticks[i].timestamp - timedelta(seconds=lookback)
                recent = [t for t in ticks[:i+1] if t.timestamp >= cutoff_time]
                if len(recent) >= 10:
                    changes = [abs(recent[j].price - recent[j-1].price) for j in range(1, len(recent))]
                    std = np.std(changes)
                    if lookback == 60:
                        rolling_std_60s.append(std)
                    elif lookback == 300:
                        rolling_std_300s.append(std)
                    else:
                        rolling_std_600s.append(std)

        # 통계 요약
        results = {
            'symbol': symbol,
            'avg_price': avg_price,
            'total_ticks': len(ticks),

            # 표준편차 방식
            'std_volatility': std_volatility,
            'std_volatility_pct': std_volatility_pct,
            'std_volatility_range': {
                'min': min(price_changes),
                'max': max(price_changes),
                'median': np.median(price_changes)
            },

            # ATR-like 방식
            'atr_volatility': atr_volatility,
            'atr_volatility_pct': atr_volatility_pct,
            'atr_range': {
                'min': min(atr_like_values) if atr_like_values else 0,
                'max': max(atr_like_values) if atr_like_values else 0,
                'median': np.median(atr_like_values) if atr_like_values else 0
            },

            # 백분위수
            'percentile_90': percentile_90,
            'percentile_90_pct': percentile_90_pct,

            # 롤링 표준편차
            'rolling_std': {
                '60s_avg': np.mean(rolling_std_60s) if rolling_std_60s else 0,
                '300s_avg': np.mean(rolling_std_300s) if rolling_std_300s else 0,
                '600s_avg': np.mean(rolling_std_600s) if rolling_std_600s else 0,
            },

            # 추천 임계값
            'recommended_thresholds': {
                'std_based': {
                    'conservative': std_volatility * 2,  # 평균의 2배
                    'moderate': std_volatility * 1.5,
                    'aggressive': std_volatility * 1.0
                },
                'atr_based': {
                    'conservative': atr_volatility * 0.5,
                    'moderate': atr_volatility * 0.3,
                    'aggressive': atr_volatility * 0.2
                },
                'percentile_based': {
                    'conservative': percentile_90 * 1.5,
                    'moderate': percentile_90 * 1.0,
                    'aggressive': percentile_90 * 0.7
                }
            }
        }

        # 로그 출력
        logger.info(f"\n📊 {symbol} Volatility Analysis:")
        logger.info(f"Average Price: ${avg_price:,.2f}")
        logger.info(f"\n1. 표준편차 기반 (현재 방식):")
        logger.info(f"   Volatility: ${std_volatility:.4f} ({std_volatility_pct:.4f}%)")
        logger.info(f"   Range: ${results['std_volatility_range']['min']:.4f} - ${results['std_volatility_range']['max']:.4f}")

        logger.info(f"\n2. ATR-like 기반 (고가-저가):")
        logger.info(f"   Volatility: ${atr_volatility:.4f} ({atr_volatility_pct:.4f}%)")
        logger.info(f"   Range: ${results['atr_range']['min']:.4f} - ${results['atr_range']['max']:.4f}")

        logger.info(f"\n3. 백분위수 기반:")
        logger.info(f"   90th Percentile: ${percentile_90:.4f} ({percentile_90_pct:.4f}%)")

        logger.info(f"\n4. 롤링 표준편차:")
        logger.info(f"   60s: ${results['rolling_std']['60s_avg']:.4f}")
        logger.info(f"   300s: ${results['rolling_std']['300s_avg']:.4f}")
        logger.info(f"   600s: ${results['rolling_std']['600s_avg']:.4f}")

        logger.info(f"\n🎯 추천 임계값:")
        logger.info(f"\n표준편차 기반:")
        logger.info(f"   Conservative: ${results['recommended_thresholds']['std_based']['conservative']:.4f}")
        logger.info(f"   Moderate: ${results['recommended_thresholds']['std_based']['moderate']:.4f}")
        logger.info(f"   Aggressive: ${results['recommended_thresholds']['std_based']['aggressive']:.4f}")

        logger.info(f"\nATR 기반:")
        logger.info(f"   Conservative: ${results['recommended_thresholds']['atr_based']['conservative']:.4f}")
        logger.info(f"   Moderate: ${results['recommended_thresholds']['atr_based']['moderate']:.4f}")
        logger.info(f"   Aggressive: ${results['recommended_thresholds']['atr_based']['aggressive']:.4f}")

        # 현재 임계값과 비교
        current_threshold = avg_price * 0.01  # 1%
        logger.info(f"\n⚠️  현재 설정된 임계값: ${current_threshold:,.2f} (1%)")
        logger.info(f"   → 표준편차의 {current_threshold / std_volatility:.1f}배")
        logger.info(f"   → ATR의 {current_threshold / atr_volatility:.1f}배")
        logger.info(f"   → 신호 발생 불가능!")

        return results

    async def analyze_multiple_coins(self, date: str = "2024-10-02") -> Dict:
        """여러 코인 동시 분석"""
        # Load active symbols
        config_file = Path(__file__).parent / 'coin_specific_params.json'
        with open(config_file, 'r') as f:
            config = json.load(f)

        symbols = [
            s for s, p in config['coin_parameters'].items()
            if not p.get('excluded', False)
        ]

        logger.info(f"Analyzing {len(symbols)} symbols")

        all_results = {}
        next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        for symbol in symbols:
            try:
                ticks = await self.fetch_sample_data(symbol, date, next_date)
                if ticks:
                    results = self.analyze_volatility_characteristics(ticks, symbol)
                    all_results[symbol] = results
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")

        return all_results

    def generate_comparison_report(self, all_results: Dict):
        """비교 리포트 생성"""
        logger.info(f"\n{'='*80}")
        logger.info("CROSS-COIN VOLATILITY COMPARISON")
        logger.info(f"{'='*80}\n")

        # 표로 정리
        comparison_data = []
        for symbol, results in all_results.items():
            if results:
                comparison_data.append({
                    'Symbol': symbol,
                    'Price': f"${results['avg_price']:,.2f}",
                    'Std Vol': f"{results['std_volatility_pct']:.4f}%",
                    'ATR Vol': f"{results['atr_volatility_pct']:.4f}%",
                    'Std ($)': f"${results['std_volatility']:.4f}",
                    'ATR ($)': f"${results['atr_volatility']:.4f}",
                    'Current Thresh': f"${results['avg_price'] * 0.01:,.2f}",
                    'Std Multiple': f"{(results['avg_price'] * 0.01) / results['std_volatility']:.1f}x",
                    'ATR Multiple': f"{(results['avg_price'] * 0.01) / results['atr_volatility']:.1f}x"
                })

        df = pd.DataFrame(comparison_data)
        logger.info("\n" + df.to_string(index=False))

        # 통합 추천
        logger.info(f"\n{'='*80}")
        logger.info("RECOMMENDED STRATEGY PARAMETERS")
        logger.info(f"{'='*80}\n")

        avg_std_pct = np.mean([r['std_volatility_pct'] for r in all_results.values() if r])
        avg_atr_pct = np.mean([r['atr_volatility_pct'] for r in all_results.values() if r])

        logger.info(f"평균 표준편차 변동성: {avg_std_pct:.4f}%")
        logger.info(f"평균 ATR 변동성: {avg_atr_pct:.4f}%")

        logger.info(f"\n🎯 최종 추천 임계값:")
        logger.info(f"\n방법 1: 표준편차 기반 (단순, 빠름)")
        logger.info(f"   Conservative: current_price * {avg_std_pct * 0.02:.6f}  # 평균 std의 2배")
        logger.info(f"   Moderate: current_price * {avg_std_pct * 0.015:.6f}  # 평균 std의 1.5배")
        logger.info(f"   Aggressive: current_price * {avg_std_pct * 0.01:.6f}  # 평균 std의 1배")

        logger.info(f"\n방법 2: ATR 기반 (정확, 권장)")
        logger.info(f"   Conservative: atr * 0.5  # ATR의 50%")
        logger.info(f"   Moderate: atr * 0.3  # ATR의 30%")
        logger.info(f"   Aggressive: atr * 0.2  # ATR의 20%")

        logger.info(f"\n방법 3: 하이브리드 (가장 안정적)")
        logger.info(f"   std_vol = calculate_tick_volatility()")
        logger.info(f"   atr_vol = calculate_atr_like()  # high-low range")
        logger.info(f"   threshold = min(std_vol * 2, atr_vol * 0.3)")

        # 저장
        output_file = Path(__file__).parent / 'claudedocs' / 'tick_volatility_analysis.json'
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        logger.info(f"\n✅ Analysis saved to {output_file}")

    async def close(self):
        await self.binance.close()


async def main():
    """메인 실행"""
    analyzer = TickVolatilityAnalyzer()

    try:
        # 여러 코인 분석
        results = await analyzer.analyze_multiple_coins("2024-10-02")

        # 비교 리포트 생성
        analyzer.generate_comparison_report(results)

    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(main())
