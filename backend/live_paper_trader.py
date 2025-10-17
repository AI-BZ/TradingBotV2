"""
Live Paper Trading Engine
실시간 모의거래 엔진 - Testnet 실시간 데이터로 전략 실행
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from binance_client import BinanceClient
from trading_strategy import TradingStrategy
from trailing_stop_manager import TrailingStopManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class LiveTrade:
    """실시간 거래 기록"""
    trade_id: str
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_time: datetime
    entry_price: float
    quantity: float
    leverage: int
    stop_loss: float
    take_profit: float
    status: str  # 'OPEN', 'CLOSED'
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: Optional[str] = None


class LivePaperTrader:
    """실시간 모의거래 엔진"""

    def __init__(
        self,
        symbols: List[str],
        initial_balance: float = 10000.0,
        leverage: int = 10,
        position_size_pct: float = 0.1
    ):
        """
        Args:
            symbols: 거래할 심볼 리스트
            initial_balance: 초기 자본금
            leverage: 레버리지
            position_size_pct: 포지션 크기 (자본금의 %)
        """
        self.symbols = symbols
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.leverage = leverage
        self.position_size_pct = position_size_pct

        # Components
        self.binance = BinanceClient(testnet=True)
        self.strategy = TradingStrategy()
        self.stop_manager = TrailingStopManager()

        # State
        self.open_positions: Dict[str, List[LiveTrade]] = {symbol: [] for symbol in symbols}
        self.closed_trades: List[LiveTrade] = []
        self.trade_counter = 0

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_balance = initial_balance
        self.max_drawdown = 0.0

        # Save directory
        self.trades_dir = Path(__file__).parent / 'live_trades'
        self.trades_dir.mkdir(exist_ok=True)

        logger.info(f"LivePaperTrader initialized: {len(symbols)} symbols, ${initial_balance} balance")

    def _generate_trade_id(self) -> str:
        """거래 ID 생성"""
        self.trade_counter += 1
        return f"LIVE_{datetime.now().strftime('%Y%m%d')}_{self.trade_counter:06d}"

    async def check_signals(self, symbol: str) -> Optional[str]:
        """
        거래 신호 확인
        Returns: 'BOTH', 'LONG', 'SHORT', None
        """
        try:
            # 최근 데이터 가져오기
            ohlcv = await self.binance.exchange.fetch_ohlcv(symbol, '1m', limit=100)

            if not ohlcv or len(ohlcv) < 100:
                return None

            # DataFrame 변환
            import pandas as pd
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # 전략 신호 생성
            signal = self.strategy.generate_signal(df, symbol)

            return signal if signal in ['BOTH', 'LONG', 'SHORT'] else None

        except Exception as e:
            logger.error(f"Error checking signals for {symbol}: {e}")
            return None

    async def open_position(self, symbol: str, side: str, current_price: float):
        """포지션 오픈"""
        try:
            # 포지션 크기 계산
            position_value = self.current_balance * self.position_size_pct
            quantity = (position_value * self.leverage) / current_price

            # 손절/익절 계산
            params = self.strategy.get_coin_params(symbol)
            stop_loss_pct = params.get('hard_stop_pct', 0.02)
            take_profit_multiplier = params.get('trailing_stop_multiplier', 2.0)

            if side == 'LONG':
                stop_loss = current_price * (1 - stop_loss_pct)
                take_profit = current_price * (1 + stop_loss_pct * take_profit_multiplier)
            else:  # SHORT
                stop_loss = current_price * (1 + stop_loss_pct)
                take_profit = current_price * (1 - stop_loss_pct * take_profit_multiplier)

            # 거래 생성
            trade = LiveTrade(
                trade_id=self._generate_trade_id(),
                symbol=symbol,
                side=side,
                entry_time=datetime.now(),
                entry_price=current_price,
                quantity=quantity,
                leverage=self.leverage,
                stop_loss=stop_loss,
                take_profit=take_profit,
                status='OPEN'
            )

            self.open_positions[symbol].append(trade)
            logger.info(f"✅ Opened {side} position: {symbol} @ ${current_price:.4f} | Qty: {quantity:.4f}")

            self._save_state()

        except Exception as e:
            logger.error(f"Error opening position for {symbol}: {e}")

    async def check_and_close_positions(self, symbol: str, current_price: float):
        """포지션 청산 체크"""
        if not self.open_positions[symbol]:
            return

        for trade in self.open_positions[symbol][:]:  # Copy list to modify during iteration
            should_close = False
            exit_reason = None

            if trade.side == 'LONG':
                # 손절 체크
                if current_price <= trade.stop_loss:
                    should_close = True
                    exit_reason = 'STOP_LOSS'
                # 익절 체크
                elif current_price >= trade.take_profit:
                    should_close = True
                    exit_reason = 'TAKE_PROFIT'

            else:  # SHORT
                # 손절 체크
                if current_price >= trade.stop_loss:
                    should_close = True
                    exit_reason = 'STOP_LOSS'
                # 익절 체크
                elif current_price <= trade.take_profit:
                    should_close = True
                    exit_reason = 'TAKE_PROFIT'

            if should_close:
                await self.close_position(trade, current_price, exit_reason)

    async def close_position(self, trade: LiveTrade, exit_price: float, reason: str):
        """포지션 청산"""
        # PnL 계산
        if trade.side == 'LONG':
            pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100 * trade.leverage
        else:  # SHORT
            pnl_pct = ((trade.entry_price - exit_price) / trade.entry_price) * 100 * trade.leverage

        pnl = (self.current_balance * self.position_size_pct) * (pnl_pct / 100)

        # 거래 업데이트
        trade.exit_time = datetime.now()
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
        trade.status = 'CLOSED'
        trade.exit_reason = reason

        # 잔고 업데이트
        self.current_balance += pnl

        # 통계 업데이트
        self.total_trades += 1
        self.total_pnl += pnl

        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Drawdown 업데이트
        if self.current_balance > self.max_balance:
            self.max_balance = self.current_balance
        drawdown_pct = ((self.max_balance - self.current_balance) / self.max_balance) * 100
        if drawdown_pct > self.max_drawdown:
            self.max_drawdown = drawdown_pct

        # 포지션 리스트에서 제거
        self.open_positions[trade.symbol].remove(trade)
        self.closed_trades.append(trade)

        emoji = "💰" if pnl > 0 else "📉"
        logger.info(
            f"{emoji} Closed {trade.side} {trade.symbol}: "
            f"Entry: ${trade.entry_price:.4f} → Exit: ${exit_price:.4f} | "
            f"PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%) | Reason: {reason}"
        )

        self._save_state()

    def _save_state(self):
        """거래 상태 저장"""
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'balance': {
                    'initial': self.initial_balance,
                    'current': self.current_balance,
                    'pnl': self.total_pnl,
                    'pnl_pct': ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
                },
                'performance': {
                    'total_trades': self.total_trades,
                    'winning_trades': self.winning_trades,
                    'losing_trades': self.losing_trades,
                    'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
                    'max_drawdown': self.max_drawdown
                },
                'open_positions': {
                    symbol: [asdict(trade) for trade in trades]
                    for symbol, trades in self.open_positions.items() if trades
                },
                'recent_trades': [asdict(trade) for trade in self.closed_trades[-10:]]  # Last 10 trades
            }

            # Save to file
            state_file = self.trades_dir / 'current_state.json'
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def get_performance_summary(self) -> Dict:
        """성과 요약 반환"""
        return {
            'balance': {
                'initial': self.initial_balance,
                'current': self.current_balance,
                'pnl': self.total_pnl,
                'pnl_pct': ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
            },
            'trades': {
                'total': self.total_trades,
                'winning': self.winning_trades,
                'losing': self.losing_trades,
                'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
            },
            'risk': {
                'max_drawdown': self.max_drawdown,
                'open_positions': sum(len(trades) for trades in self.open_positions.values())
            },
            'timestamp': datetime.now().isoformat()
        }

    async def trading_loop(self):
        """메인 거래 루프"""
        logger.info("🚀 Starting live paper trading...")

        while True:
            try:
                for symbol in self.symbols:
                    # 현재 가격 조회
                    ticker = await self.binance.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']

                    # 기존 포지션 체크
                    await self.check_and_close_positions(symbol, current_price)

                    # 신규 신호 체크 (포지션이 없을 때만)
                    if len(self.open_positions[symbol]) == 0:
                        signal = await self.check_signals(symbol)

                        if signal == 'BOTH':
                            # TWO-WAY 진입
                            await self.open_position(symbol, 'LONG', current_price)
                            await self.open_position(symbol, 'SHORT', current_price)
                        elif signal in ['LONG', 'SHORT']:
                            await self.open_position(symbol, signal, current_price)

                # 5초마다 체크
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    async def start(self):
        """거래 시작"""
        try:
            await self.trading_loop()
        finally:
            await self.binance.close()


async def main():
    """메인 실행 함수"""
    # Load active symbols
    config_file = Path(__file__).parent / 'coin_specific_params.json'
    with open(config_file, 'r') as f:
        config = json.load(f)

    active_symbols = [
        symbol for symbol, params in config['coin_parameters'].items()
        if not params.get('excluded', False)
    ]

    logger.info(f"Starting live paper trading with {len(active_symbols)} symbols")

    trader = LivePaperTrader(
        symbols=active_symbols,
        initial_balance=10000.0,
        leverage=10,
        position_size_pct=0.1
    )

    await trader.start()


if __name__ == "__main__":
    asyncio.run(main())
