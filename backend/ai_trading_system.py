"""
AI-Powered Unified Trading System
Integrates ML predictions, strategy optimization, and real-time adaptation
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
from pathlib import Path

from binance_client import BinanceClient
from ml_engine import MLEngine
from ai_strategy_manager import AIStrategyManager
from trading_strategy import TradingStrategy, RiskManager
from technical_indicators import TechnicalIndicators
from trailing_stop_manager import TrailingStopManager
import pandas as pd

logger = logging.getLogger(__name__)


class AITradingSystem:
    """
    Complete AI-Powered Trading System

    Features:
    1. ML-based signal prediction (ml_engine)
    2. AI strategy optimization (strategy_optimizer)
    3. Real-time strategy adaptation (ai_strategy_manager)
    4. Intelligent trailing stops
    5. Continuous learning and improvement
    """

    def __init__(self,
                 initial_balance: float = 10000.0,
                 leverage: int = 10,
                 mode: str = 'paper',  # 'paper' or 'live'
                 use_ml: bool = True,
                 use_ai_adaptation: bool = True):
        """Initialize AI Trading System

        Args:
            initial_balance: Starting balance in USDT
            leverage: Trading leverage
            mode: 'paper' for simulation, 'live' for real trading
            use_ml: Enable ML predictions
            use_ai_adaptation: Enable real-time AI strategy adaptation
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.mode = mode
        self.use_ml = use_ml
        self.use_ai_adaptation = use_ai_adaptation

        # Initialize components
        self.client = BinanceClient(
            testnet=(mode == 'paper'),
            use_futures=True
        )

        # ML Engine
        self.ml_engine = MLEngine() if use_ml else None

        # AI Strategy Manager
        self.ai_manager: Optional[AIStrategyManager] = None
        if use_ai_adaptation:
            self.ai_manager = AIStrategyManager(self.client, self.ml_engine)

        # Trading components (will be configured per strategy)
        self.strategy = TradingStrategy()
        self.risk_manager = RiskManager()
        self.trailing_stop_manager = TrailingStopManager()

        # State
        self.positions = {}
        self.trade_history = []
        self.symbols = []
        self.is_running = False
        self.start_time = None

        logger.info(f"🤖 AI Trading System initialized:")
        logger.info(f"  Mode: {mode}")
        logger.info(f"  ML Enabled: {use_ml}")
        logger.info(f"  AI Adaptation: {use_ai_adaptation}")
        logger.info(f"  Initial Balance: ${initial_balance:,.2f}")

    async def initialize(self, symbols: List[str]):
        """Initialize trading system with symbols

        Args:
            symbols: List of trading symbols
        """
        self.symbols = symbols
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 INITIALIZING AI TRADING SYSTEM")
        logger.info(f"{'='*80}")

        # Set leverage for all symbols
        for symbol in symbols:
            try:
                await self.client.set_leverage(symbol, self.leverage)
                logger.info(f"✅ {symbol}: Leverage set to {self.leverage}x")
            except Exception as e:
                logger.warning(f"⚠️  {symbol}: Could not set leverage - {e}")

        # Train or load ML model if enabled
        if self.ml_engine:
            await self.initialize_ml_model()

        # Initialize AI strategies if enabled
        if self.ai_manager:
            await self.ai_manager.initialize_strategies(symbols)
            logger.info(f"✅ AI strategies initialized for {len(symbols)} symbols")

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ AI TRADING SYSTEM READY")
        logger.info(f"{'='*80}\n")

    async def initialize_ml_model(self):
        """Initialize or train ML model"""
        logger.info("\n🧠 Initializing ML Model...")

        # Try to load existing model
        try:
            self.ml_engine.load_model()
            logger.info("✅ ML model loaded from disk")
            return
        except FileNotFoundError:
            logger.info("📚 No existing model found, training new model...")

        # Train on recent data for BTC (as example)
        try:
            klines = await self.client.get_klines('BTC/USDT', interval='1h', limit=500)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

            # Calculate indicators for training
            indicators_list = []
            for i in range(50, len(df)):
                subset = df.iloc[:i+1]
                indicators = TechnicalIndicators.calculate_all(
                    subset['high'].tolist(),
                    subset['low'].tolist(),
                    subset['close'].tolist(),
                    subset['volume'].tolist()
                )
                indicators_list.append(indicators)

            # Train model
            metrics = self.ml_engine.train_model(df.iloc[50:], indicators_list)

            logger.info(f"✅ ML Model Trained:")
            logger.info(f"  Accuracy: {metrics['train_accuracy']:.2%}")
            logger.info(f"  Samples: {metrics['n_samples']}")
            logger.info(f"  Buy: {metrics['label_distribution']['buy']}, "
                       f"Hold: {metrics['label_distribution']['hold']}, "
                       f"Sell: {metrics['label_distribution']['sell']}")

            # Save model
            self.ml_engine.save_model()

        except Exception as e:
            logger.error(f"❌ ML model training failed: {e}")
            self.ml_engine = None

    async def analyze_and_trade(self, symbol: str) -> Optional[Dict]:
        """Analyze symbol and execute trade if signal generated

        Args:
            symbol: Trading symbol

        Returns:
            Trade execution result or None
        """
        try:
            # Get market data
            klines = await self.client.get_klines(symbol, interval='1h', limit=100)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

            # Calculate indicators
            indicators = TechnicalIndicators.calculate_all(
                df['high'].tolist(),
                df['low'].tolist(),
                df['close'].tolist(),
                df['volume'].tolist()
            )
            indicators['close'] = float(df['close'].iloc[-1])

            # Get ML prediction if available
            ml_signal = 0
            ml_confidence = 0.5

            if self.ml_engine:
                try:
                    ml_signal, ml_confidence = self.ml_engine.predict(df, indicators)
                except Exception as e:
                    logger.debug(f"ML prediction skipped: {e}")

            # Apply active strategy configuration if AI manager enabled
            if self.ai_manager:
                # Determine direction based on ML or technical
                direction = 'LONG' if ml_signal >= 0 else 'SHORT'

                # Get current optimal strategy
                active_strategy = self.ai_manager.get_current_strategy(symbol, direction)

                # Apply strategy configuration
                self.strategy.ml_weight = active_strategy.ml_weight
                self.strategy.technical_weight = active_strategy.technical_weight
                self.risk_manager.max_position_size = active_strategy.max_position_size
                self.trailing_stop_manager.base_atr_multiplier = active_strategy.atr_multiplier
                self.trailing_stop_manager.min_profit_threshold = active_strategy.min_profit_threshold

            # Generate hybrid signal (ML + Technical)
            signal = self.strategy.generate_signal(df, indicators)
            signal['symbol'] = symbol
            signal['price'] = float(df['close'].iloc[-1])
            signal['atr'] = indicators.get('atr', signal['price'] * 0.02)

            # Enhance with ML if available
            if self.ml_engine and ml_confidence > 0.6:
                signal['ml_signal'] = ml_signal
                signal['ml_confidence'] = ml_confidence
                # Adjust confidence based on ML
                signal['confidence'] = (signal['confidence'] * 0.4) + (ml_confidence * 0.6)

            logger.info(f"  {symbol}: {signal['signal']} "
                       f"(Conf: {signal['confidence']:.2%}, "
                       f"ML: {ml_signal} @ {ml_confidence:.2%})")

            # Execute trade if conditions met
            if self.strategy.should_trade(signal, min_confidence=0.5):
                return await self.execute_trade(signal)

            return None

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None

    async def execute_trade(self, signal: Dict) -> Optional[Dict]:
        """Execute trade based on signal

        Args:
            signal: Trading signal

        Returns:
            Trade result or None
        """
        symbol = signal['symbol']
        price = signal['price']
        action = signal['signal']

        # Check risk limits
        if not self.risk_manager.can_open_position(self.balance):
            logger.info(f"  ⚠️  Risk limits reached, cannot open {symbol}")
            return None

        # Execute based on action
        if action == 'BUY' and symbol not in self.positions:
            # Open LONG
            size = self.risk_manager.calculate_position_size(
                self.balance, price, signal['confidence']
            )

            logger.info(f"  📈 {symbol}: Opening LONG @ ${price:,.2f} "
                       f"(Size: {size:.6f})")

            self.trailing_stop_manager.initialize_position(symbol, price, 'LONG')

            self.positions[symbol] = {
                'type': 'LONG',
                'entry_price': price,
                'size': size,
                'entry_time': datetime.now(),
                'signal': signal
            }

            # Update balance
            cost = size * price / self.leverage
            self.balance -= cost

            trade = {
                'symbol': symbol,
                'action': 'OPEN_LONG',
                'price': price,
                'size': size,
                'timestamp': datetime.now()
            }
            self.trade_history.append(trade)

            return trade

        elif action == 'SELL' and symbol not in self.positions:
            # Open SHORT
            size = self.risk_manager.calculate_position_size(
                self.balance, price, signal['confidence']
            )

            logger.info(f"  📉 {symbol}: Opening SHORT @ ${price:,.2f} "
                       f"(Size: {size:.6f})")

            self.trailing_stop_manager.initialize_position(symbol, price, 'SHORT')

            self.positions[symbol] = {
                'type': 'SHORT',
                'entry_price': price,
                'size': size,
                'entry_time': datetime.now(),
                'signal': signal
            }

            # Update balance
            cost = size * price / self.leverage
            self.balance -= cost

            trade = {
                'symbol': symbol,
                'action': 'OPEN_SHORT',
                'price': price,
                'size': size,
                'timestamp': datetime.now()
            }
            self.trade_history.append(trade)

            return trade

        return None

    async def check_trailing_stops(self):
        """Check all positions for trailing stop triggers"""
        for symbol in list(self.positions.keys()):
            try:
                current_price = await self.client.get_price(symbol)

                # Get ATR for stop calculation
                klines = await self.client.get_klines(symbol, interval='1h', limit=20)
                df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

                indicators = TechnicalIndicators.calculate_all(
                    df['high'].tolist(),
                    df['low'].tolist(),
                    df['close'].tolist(),
                    df['volume'].tolist()
                )
                atr = indicators.get('atr', current_price * 0.02)

                # Check trailing stop
                stop_price, should_close = self.trailing_stop_manager.update_trailing_stop(
                    symbol, current_price, atr
                )

                if should_close:
                    await self.close_position(symbol, current_price, 'trailing_stop')

            except Exception as e:
                logger.error(f"Error checking trailing stop for {symbol}: {e}")

    async def close_position(self, symbol: str, price: float, reason: str):
        """Close an open position

        Args:
            symbol: Trading symbol
            price: Close price
            reason: Reason for closing
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        entry_price = position['entry_price']
        size = position['size']
        position_type = position['type']

        # Calculate P&L
        if position_type == 'LONG':
            pnl = (price - entry_price) * size
            pnl_pct = (price - entry_price) / entry_price
        else:  # SHORT
            pnl = (entry_price - price) * size
            pnl_pct = (entry_price - price) / entry_price

        logger.info(f"  💰 {symbol}: Closing {position_type} @ ${price:,.2f} "
                   f"(P&L: ${pnl:,.2f}, {pnl_pct:+.2%}) - {reason}")

        # Update balance
        proceeds = (size * entry_price / self.leverage) + pnl
        self.balance += proceeds

        # Update AI manager performance if enabled
        if self.ai_manager:
            self.ai_manager.update_strategy_performance(
                symbol, position_type, pnl, win=(pnl > 0)
            )

        # Update risk manager
        self.risk_manager.update_daily_pnl(pnl)

        # Remove position
        del self.positions[symbol]
        self.trailing_stop_manager.remove_position(symbol)

        # Record trade
        trade = {
            'symbol': symbol,
            'action': f'CLOSE_{position_type}',
            'price': price,
            'size': size,
            'entry_price': entry_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'timestamp': datetime.now()
        }
        self.trade_history.append(trade)

    async def trading_loop(self, interval: int = 300):
        """Main trading loop

        Args:
            interval: Time between iterations (seconds)
        """
        iteration = 0

        while self.is_running:
            iteration += 1
            logger.info(f"\n{'='*80}")
            logger.info(f"🤖 AI Trading Iteration #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"{'='*80}")
            logger.info(f"Balance: ${self.balance:,.2f} | Positions: {len(self.positions)}")

            try:
                # Check trailing stops
                await self.check_trailing_stops()

                # Analyze each symbol
                for symbol in self.symbols:
                    await self.analyze_and_trade(symbol)

                # AI strategy adaptation check (every 10 iterations = ~50 minutes)
                if self.ai_manager and iteration % 10 == 0:
                    logger.info("\n🔄 Running AI strategy adaptation check...")
                    for symbol in self.symbols:
                        await self.ai_manager.check_and_adapt_strategy(symbol)

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")

            # Wait for next iteration
            logger.info(f"\n⏳ Waiting {interval}s until next iteration...")
            await asyncio.sleep(interval)

    async def start(self, duration_hours: float = 24.0):
        """Start AI trading system

        Args:
            duration_hours: How long to run (hours)
        """
        self.start_time = datetime.now()
        self.is_running = True

        logger.info(f"\n🚀 Starting AI Trading System for {duration_hours} hours...")

        # Start trading loop
        trading_task = asyncio.create_task(self.trading_loop())

        # Run for specified duration
        await asyncio.sleep(duration_hours * 3600)

        # Stop trading
        self.is_running = False
        await trading_task

        # Generate report
        report = self.generate_report()
        self.save_results(report)

        # Save AI manager data if enabled
        if self.ai_manager:
            self.ai_manager.save_switch_history()
            ai_report = self.ai_manager.generate_report()
            logger.info(f"\n📊 AI Strategy Switches: {ai_report['total_switches']}")

        await self.client.close()

        return report

    def generate_report(self) -> Dict:
        """Generate trading performance report"""
        closed_trades = [t for t in self.trade_history if 'pnl' in t]
        wins = [t for t in closed_trades if t['pnl'] > 0]
        losses = [t for t in closed_trades if t['pnl'] <= 0]

        total_pnl = sum(t['pnl'] for t in closed_trades)
        total_return = (total_pnl / self.initial_balance) * 100

        win_rate = (len(wins) / len(closed_trades)) * 100 if closed_trades else 0

        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0

        profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) \
            if losses and sum(t['pnl'] for t in losses) != 0 else 0

        duration = datetime.now() - self.start_time if self.start_time else timedelta(0)

        return {
            'summary': {
                'mode': self.mode,
                'ml_enabled': self.use_ml,
                'ai_adaptation_enabled': self.use_ai_adaptation,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': datetime.now().isoformat(),
                'duration_hours': duration.total_seconds() / 3600,
                'initial_balance': self.initial_balance,
                'final_balance': self.balance,
                'total_pnl': total_pnl,
                'total_return_pct': total_return
            },
            'statistics': {
                'total_trades': len(closed_trades),
                'winning_trades': len(wins),
                'losing_trades': len(losses),
                'win_rate_pct': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor
            },
            'trades': closed_trades
        }

    def save_results(self, report: Dict, filename: str = 'ai_trading_results.json'):
        """Save trading results to file"""
        output_path = Path(__file__).parent / 'results' / filename
        output_path.parent.mkdir(exist_ok=True)

        # Convert timestamps
        def convert_timestamps(obj):
            if isinstance(obj, dict):
                return {k: convert_timestamps(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_timestamps(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj

        results_serializable = convert_timestamps(report)

        with open(output_path, 'w') as f:
            json.dump(results_serializable, f, indent=2)

        logger.info(f"✅ Results saved to {output_path}")


# Test the AI Trading System
async def test_ai_system():
    """Test AI Trading System"""
    logging.basicConfig(level=logging.INFO)

    # Create AI Trading System
    ai_system = AITradingSystem(
        initial_balance=10000.0,
        leverage=10,
        mode='paper',
        use_ml=True,
        use_ai_adaptation=True
    )

    # Initialize with top coins
    await ai_system.initialize(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])

    # Run for 1 hour (test)
    results = await ai_system.start(duration_hours=1.0)

    print("\n" + "="*80)
    print("AI TRADING SYSTEM TEST RESULTS")
    print("="*80)
    print(f"\nFinal Balance: ${results['summary']['final_balance']:,.2f}")
    print(f"Total Return: {results['summary']['total_return_pct']:+.2f}%")
    print(f"Total Trades: {results['statistics']['total_trades']}")
    print(f"Win Rate: {results['statistics']['win_rate_pct']:.1f}%")
    print(f"Profit Factor: {results['statistics']['profit_factor']:.2f}")


if __name__ == "__main__":
    asyncio.run(test_ai_system())
