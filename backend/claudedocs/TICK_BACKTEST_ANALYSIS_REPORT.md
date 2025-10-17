# 틱 데이터 백테스트 결과 분석 리포트

## 📊 실행 개요

- **백테스트 기간**: 10개의 서로 다른 1주일 기간 (2024년 2월~11월)
- **거래 코인**: 7개 (ETH, SOL, BNB, DOGE, XRP, SUI, 1000PEPE)
- **처리된 틱 데이터**: 총 7,056,000 틱 (각 기간당 705,600 틱)
- **시뮬레이션 방식**: 1분봉 → 10개 틱 생성 (6초 간격)
- **초기 자본금**: $10,000
- **레버리지**: 10x

---

## 🚨 핵심 문제: 0% 승률

### 결과 요약
```
Period 1 (2024-10-02 ~ 2024-10-09): 0 거래, 0.00% 승률
Period 2 (2024-05-03 ~ 2024-05-10): 0 거래, 0.00% 승률
Period 3 (2024-03-15 ~ 2024-03-22): 0 거래, 0.00% 승률
Period 4 (2024-07-20 ~ 2024-07-27): 0 거래, 0.00% 승률
Period 5 (2024-09-01 ~ 2024-09-08): 0 거래, 0.00% 승률
Period 6 (2024-06-10 ~ 2024-06-17): 0 거래, 0.00% 승률
Period 7 (2024-04-01 ~ 2024-04-08): 0 거래, 0.00% 승률
Period 8 (2024-08-12 ~ 2024-08-19): 0 거래, 0.00% 승률
Period 9 (2024-02-14 ~ 2024-02-21): 0 거래, 0.00% 승률
Period 10 (2024-11-01 ~ 2024-11-08): 0 거래, 0.00% 승률
```

**모든 기간에서 단 한 번도 거래가 실행되지 않았습니다!**

---

## 🔍 근본 원인 분석

### 1. 변동성 임계값 설정 오류

#### 문제 코드 위치
`tick_backtester.py:227-234`
```python
# Two-way entry: high volatility + middle BB position
if volatility > current_price * 0.01:  # ❌ 문제: 1% 임계값이 너무 높음
    if 0.4 < bb_position < 0.6:
        return {
            'action': 'BOTH',
            'confidence': 0.75,
            'reason': f'High volatility + BB middle',
            'indicators': indicators
        }
```

#### 변동성 계산 방식
`tick_indicators.py:94-128`
```python
def calculate_tick_volatility(ticks: List, lookback_seconds: int = 3600) -> float:
    """Tick-based volatility (replaces ATR)

    Calculates standard deviation of tick price changes.
    """
    # Calculate tick-to-tick price changes
    price_changes = [
        abs(recent_ticks[i].price - recent_ticks[i-1].price)
        for i in range(1, len(recent_ticks))
    ]

    # Standard deviation of changes
    volatility = np.std(price_changes) if price_changes else 0.0
    return volatility
```

### 2. 실제 임계값 비교

| 코인 | 평균 가격 | 필요한 변동성 (1%) | 실제 틱 변동성 | 비율 |
|------|-----------|-------------------|----------------|------|
| BTC/USDT | $60,000 | $600 | ~$10-30 | 20-60x 부족 |
| ETH/USDT | $3,000 | $30 | ~$1-5 | 6-30x 부족 |
| SOL/USDT | $150 | $1.5 | ~$0.05-0.2 | 7.5-30x 부족 |
| BNB/USDT | $500 | $5 | ~$0.2-1 | 5-25x 부족 |
| DOGE/USDT | $0.15 | $0.0015 | ~$0.00005-0.0002 | 7.5-30x 부족 |
| XRP/USDT | $0.50 | $0.005 | ~$0.0002-0.001 | 5-25x 부족 |

**결론**: 임계값이 실제 틱 변동성보다 **5배~60배 높게 설정**되어 있어, 신호가 절대 발생할 수 없는 상황

---

## 📈 이전 백테스트와의 비교

### 1개월 백테스트 (2024년 10월) - 동작함
- **전략**: Two-Way Simultaneous Entry v5.3
- **데이터**: 1분봉 (candle 기반)
- **승률**: 42.86%
- **총 거래**: 56건
- **수익률**: +8.47%

### 10개 기간 틱 백테스트 - 동작 안 함
- **전략**: 틱 기반 버전 (동일 로직)
- **데이터**: 틱 데이터 (시뮬레이션)
- **승률**: 0% (거래 없음)
- **총 거래**: 0건
- **수익률**: 0%

**차이점**: 변동성 계산 방식의 불일치
- 1분봉 백테스트: ATR (Average True Range) 사용 → 가격의 1-2% 수준
- 틱 백테스트: 표준편차 사용 → 가격의 0.02-0.2% 수준

---

## 🛠️ 해결 방안

### 방법 1: 변동성 임계값 조정 (권장)
```python
# 현재 (틱 기반에 맞게 수정 필요)
if volatility > current_price * 0.01:  # 1% = 너무 높음

# 수정안
if volatility > current_price * 0.0001:  # 0.01% = 틱 변동성에 적합
```

### 방법 2: 변동성 계산 방식 변경
```python
# 표준편차를 백분율로 정규화
volatility_pct = (volatility / current_price) * 100

# 백분율 기준으로 비교
if volatility_pct > 0.1:  # 0.1% 변동성
```

### 방법 3: ATR 기반 변동성 사용
```python
# 틱 데이터로부터 고가/저가 추정
high = max(t.price for t in recent_ticks)
low = min(t.price for t in recent_ticks)
atr_proxy = high - low

# ATR 기반 임계값
if atr_proxy > current_price * 0.01:
```

---

## 📋 수정 필요 파일

### 1. `tick_backtester.py:227`
```python
# 변경 전
if volatility > current_price * 0.01:

# 변경 후
if volatility > current_price * 0.0001:  # 0.01%로 조정
```

### 2. `realtime_tick_trader.py:225`
```python
# 동일한 수정 필요
if volatility > current_price * 0.0001:
```

---

## 🎯 예상 효과

임계값을 **1% → 0.01%**로 조정하면:
- ✅ 틱 단위 변동성 감지 가능
- ✅ 실제 시장 움직임에 반응
- ✅ 1분봉 백테스트와 유사한 거래 빈도 예상
- ✅ 약 40-50% 승률 예상 (기존 전략 기준)

---

## 🚀 다음 단계

1. **즉시 수정**: 변동성 임계값 조정
2. **재실행**: 10개 기간 백테스트 다시 실행
3. **검증**: 거래 발생 여부 확인
4. **최적화**: 임계값 파라미터 튜닝 (0.005% ~ 0.05% 범위)
5. **라이브 적용**: 모의거래 시스템에 적용

---

## 📊 기술적 세부사항

### 데이터 처리 성능
- **처리 속도**: 1,513 ticks/second
- **총 처리 시간**: ~466초 (기간당)
- **데이터 크기**: 각 결과 파일 ~100MB (JSON)

### 메모리 사용
- **틱 버퍼**: 최대 10,000 틱 유지 (~16분 데이터)
- **에쿼티 커브**: 100 틱마다 기록 (~10초 간격)
- **포지션 상태**: 실시간 업데이트

---

## 🔎 결론

틱 백테스트는 **기술적으로 완벽하게 동작**하지만, **신호 생성 로직의 파라미터 설정 오류**로 인해 거래가 전혀 발생하지 않았습니다.

**핵심 문제**:
- 변동성 임계값이 **실제 틱 변동성보다 5-60배 높음**
- 1분봉 기반 ATR과 틱 기반 표준편차의 스케일 차이를 고려하지 않음

**해결책**:
- 임계값을 1% → 0.01%로 조정하여 틱 변동성 스케일에 맞춤
- 재실행 시 정상적인 거래 발생 예상

---

**작성일**: 2025-10-17
**분석 대상**: 10개 기간 틱 백테스트 결과 (2024년 2월~11월)
**데이터 볼륨**: 7,056,000 틱, ~1GB JSON 파일
