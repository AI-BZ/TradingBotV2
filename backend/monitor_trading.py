#!/usr/bin/env python3
"""
Trading Monitor - 1시간 후 거래 현황 체크 및 자동 문제 진단
"""
import asyncio
import time
import requests
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_BASE = "http://167.179.108.246:8000"
CHECK_INTERVAL = 3600  # 1시간 (초)
EXPECTED_SIGNALS_PER_HOUR = 7  # 7개 코인 × 약 7건/시간 = 최소 기대값

async def check_trading_status():
    """거래 상태 체크"""
    try:
        response = requests.get(f"{API_BASE}/api/v1/trading/performance", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"API 요청 실패: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"API 연결 실패: {e}")
        return None


async def diagnose_issue():
    """문제 진단 및 자동 수정 시도"""
    logger.warning("🚨 거래 신호가 없음 - 시스템 진단 시작")

    issues_found = []

    # 1. API 상태 체크
    try:
        health = requests.get(f"{API_BASE}/health", timeout=5)
        if health.status_code != 200:
            issues_found.append("API 응답 없음")
    except:
        issues_found.append("백엔드 연결 실패")

    # 2. 거래 상태 체크
    status = await check_trading_status()
    if not status:
        issues_found.append("거래 성과 API 응답 없음")
        return issues_found

    if status.get("status") != "running":
        issues_found.append(f"거래 상태: {status.get('status')} (running 아님)")

        # 자동 재시작 시도
        logger.info("거래 자동 재시작 시도...")
        try:
            restart = requests.post(f"{API_BASE}/api/v1/trading/start", timeout=10)
            if restart.status_code == 200:
                logger.info("✅ 거래 재시작 성공")
            else:
                issues_found.append(f"거래 재시작 실패: {restart.status_code}")
        except Exception as e:
            issues_found.append(f"거래 재시작 오류: {e}")

    # 3. 신호 생성 체크
    signals_generated = status.get("signals_generated", 0)
    if signals_generated == 0:
        logger.warning("⚠️ 생성된 신호가 0개 - 조건이 너무 엄격하거나 시장 변동성 부족")
        issues_found.append("신호 생성 0개 (1시간 경과)")

    return issues_found


async def monitor_loop():
    """메인 모니터링 루프"""
    start_time = datetime.now()
    logger.info(f"🔍 거래 모니터링 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"⏰ {CHECK_INTERVAL // 60}분 후 체크 예정...")

    # 1시간 대기
    await asyncio.sleep(CHECK_INTERVAL)

    # 거래 상태 체크
    check_time = datetime.now()
    logger.info(f"⏰ 체크 시간: {check_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"⏱️ 경과 시간: {(check_time - start_time).total_seconds() / 60:.1f}분")

    status = await check_trading_status()

    if not status:
        logger.error("❌ API 응답 없음 - 백엔드 문제 가능성")
        await diagnose_issue()
        return

    # 거래 현황 출력
    logger.info("=" * 60)
    logger.info("📊 거래 현황:")
    logger.info(f"  상태: {status.get('status')}")
    logger.info(f"  생성된 신호: {status.get('signals_generated')}")
    logger.info(f"  총 거래: {status.get('total_trades')}")
    logger.info(f"  활성 포지션: {status.get('active_positions')}")
    logger.info(f"  쿨다운 스킵: {status.get('signals_skipped_cooldown')}")
    logger.info(f"  총 PnL: {status.get('total_pnl', 0):.2f}")
    logger.info("=" * 60)

    # 문제 진단
    signals_generated = status.get("signals_generated", 0)
    total_trades = status.get("total_trades", 0)

    if signals_generated == 0 and total_trades == 0:
        logger.warning("⚠️ 1시간 동안 신호 및 거래 없음 - 문제 진단 시작")
        issues = await diagnose_issue()

        if issues:
            logger.error("🚨 발견된 문제:")
            for i, issue in enumerate(issues, 1):
                logger.error(f"  {i}. {issue}")

        # 추가 진단 정보
        logger.info("\n📋 추가 진단 정보:")
        logger.info(f"  전략: {status.get('strategy')}")
        logger.info(f"  위험 상태: {status.get('risk_status')}")
        logger.info(f"  최대 손실: {status.get('max_drawdown', 0):.2f}%")

        # 코인별 상태
        per_coin = status.get('per_coin_stats', {})
        logger.info("\n💰 코인별 상태:")
        for symbol, stats in per_coin.items():
            logger.info(f"  {symbol}: 거래 {stats.get('total_trades')}건")
    else:
        logger.info("✅ 거래 정상 작동 중")
        logger.info(f"  생성된 신호: {signals_generated}개")
        logger.info(f"  완료된 거래: {total_trades}건")


async def main():
    """메인 함수"""
    try:
        await monitor_loop()
    except KeyboardInterrupt:
        logger.info("\n👋 모니터링 중단")
    except Exception as e:
        logger.error(f"❌ 오류 발생: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
