"""
Tick Data Migration Validation Script
절대 규칙: 틱데이터를 기본 베이스로 하는 시스템 검증

이 스크립트는 전체 시스템에서 캔들 데이터 사용이 0개임을 검증합니다.
"""
import subprocess
import json
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class TickSystemValidator:
    """틱 기반 시스템 검증기"""

    def __init__(self):
        self.backend_dir = Path(__file__).parent
        self.violations = []
        self.warnings = []
        self.passed_checks = []

    def check_no_candle_calls(self):
        """캔들 데이터 호출이 없는지 확인"""
        logger.info("\n" + "="*80)
        logger.info("🔍 검증 1: 캔들 데이터 호출 확인")
        logger.info("="*80)

        # 검색할 패턴들
        patterns = [
            ("get_klines", "Binance 캔들 데이터 호출"),
            ("fetch_ohlcv", "CCXT 캔들 데이터 호출"),
            ("interval.*['\"]1h", "1시간 캔들 인터벌"),
            ("interval.*['\"]5m", "5분 캔들 인터벌"),
            ("interval.*['\"]15m", "15분 캔들 인터벌"),
            ("interval.*['\"]1m", "1분 캔들 인터벌"),
        ]

        # 실시간 거래에서 캔들 사용하면 안되는 파일들
        critical_files = [
            "realtime_tick_trader.py",
            "tick_data_collector.py",
            "tick_indicators.py",
            "tick_backtester.py",
            "trading_strategy.py"  # generate_tick_signal 메서드에서
        ]

        for pattern, description in patterns:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", pattern, str(self.backend_dir)],
                capture_output=True,
                text=True
            )

            matches = [line for line in result.stdout.split('\n') if line]

            # 중요 파일에서 발견된 경우
            critical_violations = [
                m for m in matches
                if any(cf in m for cf in critical_files)
                and "# ❌" not in m  # 주석 제외
                and "# BEFORE" not in m  # 변경 전 코드 제외
            ]

            if critical_violations:
                self.violations.append({
                    'check': f"캔들 호출 금지 ({description})",
                    'pattern': pattern,
                    'matches': critical_violations,
                    'severity': 'CRITICAL'
                })
                logger.error(f"❌ CRITICAL: {description} 발견!")
                for match in critical_violations[:3]:  # 처음 3개만 표시
                    logger.error(f"   {match}")
            else:
                self.passed_checks.append(f"✅ {description} 없음")
                logger.info(f"✅ {description} 없음")

    def check_tick_infrastructure(self):
        """틱 인프라가 제대로 구축되었는지 확인"""
        logger.info("\n" + "="*80)
        logger.info("🔍 검증 2: 틱 인프라 구축 확인")
        logger.info("="*80)

        required_files = {
            "tick_data_collector.py": "틱 데이터 수집기",
            "tick_indicators.py": "틱 기반 지표",
            "tick_backtester.py": "틱 백테스터"
        }

        for filename, description in required_files.items():
            file_path = self.backend_dir / filename
            if file_path.exists():
                self.passed_checks.append(f"✅ {description} 존재")
                logger.info(f"✅ {description}: {filename}")
            else:
                self.violations.append({
                    'check': f"필수 파일 존재 ({description})",
                    'file': filename,
                    'severity': 'CRITICAL'
                })
                logger.error(f"❌ CRITICAL: {description} 파일 없음: {filename}")

    def check_imports(self):
        """틱 관련 import가 올바르게 되어있는지 확인"""
        logger.info("\n" + "="*80)
        logger.info("🔍 검증 3: 틱 모듈 import 확인")
        logger.info("="*80)

        files_to_check = {
            "realtime_tick_trader.py": [
                "from tick_data_collector import",
                "from tick_indicators import"
            ],
            "trading_strategy.py": [
                "from tick_indicators import"
            ]
        }

        for filename, required_imports in files_to_check.items():
            file_path = self.backend_dir / filename
            if not file_path.exists():
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            for import_statement in required_imports:
                if import_statement in content:
                    self.passed_checks.append(f"✅ {filename}: {import_statement}")
                    logger.info(f"✅ {filename}: {import_statement}")
                else:
                    self.violations.append({
                        'check': f"필수 import ({filename})",
                        'import': import_statement,
                        'severity': 'HIGH'
                    })
                    logger.error(f"❌ {filename}: {import_statement} 없음")

    def check_ohlcv_dependencies(self):
        """OHLCV 데이터 의존성 확인"""
        logger.info("\n" + "="*80)
        logger.info("🔍 검증 4: OHLCV 의존성 확인")
        logger.info("="*80)

        # OHLCV 관련 패턴
        ohlcv_patterns = [
            ("df\\['open'\\]", "DataFrame open 컬럼"),
            ("df\\['high'\\]", "DataFrame high 컬럼"),
            ("df\\['low'\\]", "DataFrame low 컬럼"),
            ("df\\['close'\\]", "DataFrame close 컬럼"),
            ("\\['open',.*'high',.*'low',.*'close'", "OHLCV 컬럼 리스트")
        ]

        critical_files = [
            "tick_data_collector.py",
            "tick_indicators.py",
            "tick_backtester.py"
        ]

        for pattern, description in ohlcv_patterns:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "-E", pattern, str(self.backend_dir)],
                capture_output=True,
                text=True
            )

            matches = [line for line in result.stdout.split('\n') if line]
            critical_matches = [
                m for m in matches
                if any(cf in m for cf in critical_files)
                and "# " not in m  # 주석 제외
            ]

            if critical_matches:
                self.warnings.append({
                    'check': f"OHLCV 의존성 ({description})",
                    'pattern': pattern,
                    'matches': critical_matches[:3],
                    'severity': 'WARNING'
                })
                logger.warning(f"⚠️  WARNING: {description} 발견")
                for match in critical_matches[:3]:
                    logger.warning(f"   {match}")

    def check_websocket_implementation(self):
        """WebSocket 틱 스트림이 구현되었는지 확인"""
        logger.info("\n" + "="*80)
        logger.info("🔍 검증 5: WebSocket 틱 스트림 구현 확인")
        logger.info("="*80)

        tick_collector = self.backend_dir / "tick_data_collector.py"
        if not tick_collector.exists():
            self.violations.append({
                'check': "WebSocket 구현",
                'severity': 'CRITICAL',
                'message': "tick_data_collector.py 없음"
            })
            return

        with open(tick_collector, 'r') as f:
            content = f.read()

        required_patterns = [
            ("wss://fstream.binance.com", "Binance Futures WebSocket URL"),
            ("@ticker", "Ticker 스트림"),
            ("async def subscribe_ticker_stream", "Ticker 구독 함수"),
            ("websockets.connect", "WebSocket 연결")
        ]

        for pattern, description in required_patterns:
            if pattern in content:
                self.passed_checks.append(f"✅ {description}")
                logger.info(f"✅ {description}")
            else:
                self.violations.append({
                    'check': f"WebSocket 구현 ({description})",
                    'pattern': pattern,
                    'severity': 'HIGH'
                })
                logger.error(f"❌ {description} 없음")

    def generate_report(self):
        """검증 리포트 생성"""
        logger.info("\n" + "="*80)
        logger.info("📊 검증 결과 요약")
        logger.info("="*80)

        total_checks = len(self.passed_checks) + len(self.violations) + len(self.warnings)
        passed_pct = (len(self.passed_checks) / total_checks * 100) if total_checks > 0 else 0

        logger.info(f"총 검사 항목: {total_checks}")
        logger.info(f"✅ 통과: {len(self.passed_checks)} ({passed_pct:.1f}%)")
        logger.info(f"❌ 실패: {len(self.violations)}")
        logger.info(f"⚠️  경고: {len(self.warnings)}")

        # 리포트 파일 생성
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_checks': total_checks,
                'passed': len(self.passed_checks),
                'violations': len(self.violations),
                'warnings': len(self.warnings),
                'pass_rate': passed_pct
            },
            'passed_checks': self.passed_checks,
            'violations': self.violations,
            'warnings': self.warnings,
            'overall_status': 'PASS' if len(self.violations) == 0 else 'FAIL'
        }

        report_file = self.backend_dir / 'claudedocs' / 'tick_validation_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"\n📄 상세 리포트 저장: {report_file}")

        # 최종 판정
        logger.info("\n" + "="*80)
        if len(self.violations) == 0:
            logger.info("🎉 검증 통과! 시스템이 100% 틱 데이터 기반입니다.")
            logger.info("="*80)
            return True
        else:
            logger.error("❌ 검증 실패! 아래 문제를 수정해주세요:")
            logger.error("="*80)
            for violation in self.violations:
                logger.error(f"  - {violation.get('check', 'Unknown check')}")
                if 'matches' in violation:
                    for match in violation['matches'][:2]:
                        logger.error(f"    {match}")
            return False

    def run_all_checks(self):
        """모든 검증 실행"""
        logger.info("\n" + "🚀 " + "="*76)
        logger.info("틱 데이터 시스템 검증 시작")
        logger.info("절대 규칙: 틱데이터가 거래 프로그램의 기본 베이스")
        logger.info("="*80)

        self.check_tick_infrastructure()
        self.check_no_candle_calls()
        self.check_imports()
        self.check_ohlcv_dependencies()
        self.check_websocket_implementation()

        return self.generate_report()


def main():
    """메인 실행"""
    validator = TickSystemValidator()
    success = validator.run_all_checks()

    # Exit code
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
