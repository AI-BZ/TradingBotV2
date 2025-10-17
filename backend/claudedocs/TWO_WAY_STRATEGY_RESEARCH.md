# Two-Way Simultaneous Entry (Straddle) Strategy Research

## 전략 개요

**핵심 컨셉:** 변동성이 높을 때 같은 가격에서 LONG과 SHORT를 동시에 진입하여, 손실 나는 쪽은 빠르게 손절하고 수익 나는 쪽은 Trailing Stop으로 최대한 수익을 가져가는 전략

## 📊 리서치 결과 요약

### 1. Straddle/Hedging Strategy 기본 원리

**정의:**
- Market-neutral 전략
- 방향성 예측 불필요
- 변동성에 베팅하는 전략
- 어느 방향으로든 큰 움직임에서 수익

**작동 방식:**
1. 동일 가격에서 LONG + SHORT 동시 진입
2. 가격이 크게 움직이면 한쪽은 수익, 한쪽은 손실
3. 손실 쪽을 빠르게 손절 (1-2% 하드 스톱)
4. 수익 쪽을 Trailing Stop으로 계속 추적

### 2. 암호화폐 시장 적용 사례

**Volatility Breakout Strategy:**
- 변동성 압축 → 변동성 확장 전환점 포착
- ATR 기반 진입 신호
- 높은 변동성 기간 동안 효과적

**Dual-Regime Adaptive System:**
- 범위 시장 (ADX ≤ 25): Mean Reversion
- 트렌드 시장 (ADX > 25): Breakout
- 시장 상태에 따라 전략 전환

### 3. ATR 기반 포지션 관리

**암호화폐 ATR 설정:**
- 기간: 10-12 (암호화폐 변동성 특성)
- 진입 조건: 가격이 ATR × 1.5-2.0 이상 움직일 때

**포지션 크기 계산:**
```
Position Size = Risk per Trade ÷ (ATR × Multiplier)
```

**스톱 로스:**
- 손실 쪽: ATR × 1.0 (빠른 손절)
- 수익 쪽: Trailing Stop (ATR × 1.5-2.0)

---

## 🎯 암호화폐 최적화 전략 설계

### 진입 조건 (Entry Conditions)

**1. 변동성 압축 감지:**
- Bollinger Bands Width < 평균의 50% (변동성 압축)
- ATR < 최근 20일 평균 (낮은 변동성)
- 가격이 좁은 범위에서 횡보 (레인지)

**2. 변동성 확장 신호:**
- ATR이 급증 (최근 5일 평균 > 20일 평균)
- 볼린저 밴드 폭 확대
- 큰 캔들 발생 (Body > ATR × 1.5)

**3. 동시 진입:**
- LONG: 현재 가격에서 매수
- SHORT: 현재 가격에서 매도
- 동일 포지션 크기 (잔액의 10% 각각)

### 청산 조건 (Exit Conditions)

**손실 쪽 (Losing Side):**
- 하드 스톱: -1.5% (ATR × 1.0)
- 빠른 손절로 손실 최소화
- 한쪽이 손절되면 나머지 한쪽만 유지

**수익 쪽 (Winning Side):**
- Trailing Stop 활성화 (수익 +0.5% 이후)
- ATR × 1.8 기반 트레일링
- 가속도: 0.3 (수익 증가 시 스톱 간격 축소)
- 최대 수익 추적

### 리스크 관리

**포지션 크기:**
- 각 포지션: 잔액의 10% (LONG 10% + SHORT 10% = 총 20%)
- 최대 손실: 1.5% (한쪽만 손절 가정)
- 수수료: 0.02% × 4회 (진입 2회 + 청산 2회) = 0.08%

**일일 제한:**
- 최대 일일 손실: 10%
- 최대 동시 포지션: 1쌍 (LONG + SHORT)
- 손절 후 재진입 대기: 1시간

---

## 📈 예상 성과

### 시나리오 분석

**Scenario 1: 강한 상승 (50% 확률)**
- LONG: +8% (Trailing Stop으로 대부분 확보)
- SHORT: -1.5% (하드 스톱)
- 순수익: +6.5% - 0.08% 수수료 = **+6.42%**

**Scenario 2: 강한 하락 (50% 확률)**
- LONG: -1.5% (하드 스톱)
- SHORT: +8% (Trailing Stop으로 대부분 확보)
- 순수익: +6.5% - 0.08% 수수료 = **+6.42%**

**Scenario 3: 횡보 (변동성 없음)**
- 진입하지 않음 (변동성 조건 미충족)

**Scenario 4: 작은 움직임 (양쪽 손절)**
- LONG: -1.5%
- SHORT: -1.5%
- 순손실: -3% - 0.08% 수수료 = **-3.08%**
- 확률: 20% 미만 (변동성 확장 시그널로 필터링)

### 기대 수익률

```
Expected Return = (0.5 × 6.42%) + (0.5 × 6.42%) + (0.2 × -3.08%)
                = 3.21% + 3.21% - 0.62%
                = 5.8% per trade
```

**월간 예상:**
- 거래 빈도: 주 2-3회 = 월 10회
- 월간 수익률: 5.8% × 10 = **58%** (매우 낙관적)
- 현실적 목표: **월 10-20%** (일부 손실 고려)

---

## ⚙️ 구현 세부사항

### Volatility Detection (변동성 감지)

```python
# Bollinger Bands Width
bb_width = (bb_upper - bb_lower) / bb_middle
bb_width_avg = bb_width의 20일 평균
is_compressed = bb_width < bb_width_avg * 0.5

# ATR Expansion
atr_short_avg = ATR의 5일 평균
atr_long_avg = ATR의 20일 평균
is_expanding = atr_short_avg > atr_long_avg * 1.2
```

### Entry Signal

```python
# 변동성 압축 후 확장
if is_compressed and is_expanding:
    # 큰 캔들 발생 확인
    candle_body = abs(close - open)
    if candle_body > atr * 1.5:
        # LONG + SHORT 동시 진입
        open_long_position(price, size=balance * 0.1)
        open_short_position(price, size=balance * 0.1)
```

### Exit Logic

```python
# 각 포지션 독립적으로 관리
for position in active_positions:
    pnl_pct = calculate_pnl_percent(position)

    # 손실 쪽 하드 스톱
    if pnl_pct <= -1.5:
        close_position(position, reason="hard_stop")

    # 수익 쪽 트레일링 스톱
    elif pnl_pct > 0.5:
        trailing_stop_manager.update(position)
```

---

## 🔍 백테스트 검증 계획

### 테스트 조건

**기간:** 30일 (2025-09-16 ~ 2025-10-16)
**코인:** Top 10 변동성 코인
**초기 자본:** $10,000
**레버리지:** 1x (레버리지 없음)
**수수료:** 0.02% (Maker)

### 성공 기준

- ✅ **승률:** ≥ 40% (최소 목표)
- ✅ **수익 팩터:** ≥ 1.5
- ✅ **월간 수익률:** ≥ 5%
- ✅ **최대 낙폭:** ≤ 15%
- ✅ **평균 수익:** > 평균 손실 × 1.5

### 실패 시 조정 사항

1. 변동성 임계값 조정
2. 하드 스톱 간격 조정 (-1.5% → -2.0%)
3. 포지션 크기 축소 (10% → 5%)
4. 진입 빈도 제한 (과도한 거래 방지)

---

## 📚 참고 문헌

1. **OKX Learn** - Long Straddle Option Strategy
2. **BingX Blog** - Crypto Futures Straddles and Strangles
3. **Medium (FMZQuant)** - Dual-Regime Adaptive Trading System
4. **Cornix** - Trailing Stop-Loss Guide
5. **LuxAlgo** - ATR-Based Stop-Loss for Breakouts

---

**생성일:** 2025-10-16
**다음 단계:** 전략 구현 → 백테스트 실행 → 성과 검증
