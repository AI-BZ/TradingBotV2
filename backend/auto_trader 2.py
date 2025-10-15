"""
Auto Trader - Automated trading execution system
"""
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

from binance_client import BinanceClient
from technical_indicators import TechnicalIndicators
from trading_strategy import TradingStrategy, RiskManager
from ml_engine import MLEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutoTrader:
    """Automated trading bot"""

    def __init__(self,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 testnet: bool = True,
                 use_futures: bool = True,
                 initial_balance: float = 10000.0,
                 leverage: int = 10):
        """Initialize auto trader

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet or mainnet
            use_futures: Use futures trading for LONG/SHORT (default: True)
            initial_balance: Initial balance in USDT
            leverage: Leverage for futures trading (1-125)
        """
        self.client = BinanceClient(api_key, api_secret, testnet, use_futures)
        self.use_futures = use_futures
        self.leverage = leverage
        self.strategy = TradingStrategy(ml_weight=0.6, technical_weight=0.4)
        self.risk_manager = RiskManager(
            max_position_size=0.2,
            stop_loss_pct=0.03,
            take_profit_pct=0.05
        )
        self.ml_engine = None

        # Trading state
        self.balance = initial_balance
        self.positions = {}  # symbol -> position info
        self.trade_history = []
        self.is_running = False

        # Trading symbols - will be auto-populated with top 10
        self.symbols = []

        logger.info(f"AutoTrader initialized with balance ${initial_balance:,.2f}")
        logger.info(f"Trading mode: {'FUTURES (LONG/SHORT)' if use_futures else 'SPOT (LONG only)'}")
        if use_futures:
            logger.info(f"Leverage: {leverage}x")

    def set_ml_engine(self, ml_engine: MLEngine):
        """Set ML engine for predictions"""
        self.ml_engine = ml_engine
        self.strategy.set_ml_engine(ml_engine)
        logger.info("ML engine configured")

    async def get_market_data(self, symbol: str, interval: str = '1h',
                              limit: int = 100) -> pd.DataFrame:
        """Fetch market data for symbol

        Args:
            symbol: Trading pair symbol
            interval: Candle interval
            limit: Number of candles

        Returns:
            DataFrame with OHLCV data
        """
        klines = await self.client.get_klines(symbol, interval, limit)
        data = pd.DataFrame(klines)
        data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
        return data

    async def analyze_symbol(self, symbol: str) -> Dict:
        """Analyze symbol and generate trading signal

        Args:
            symbol: Trading pair symbol

        Returns:
            Analysis dictionary with signal and indicators
        """
        # Get market data
        data = await self.get_market_data(symbol)

        # Calculate technical indicators
        indicators = TechnicalIndicators.calculate_all(
            data['high'].tolist(),
            data['low'].tolist(),
            data['close'].tolist(),
            data['volume'].tolist()
        )
        indicators['close'] = data['close'].iloc[-1]

        # Generate signal
        signal = self.strategy.generate_signal(data, indicators)
        signal['symbol'] = symbol
        signal['price'] = float(data['close'].iloc[-1])

        return signal

    async def execute_trade(self, signal: Dict) -> Optional[Dict]:
        """Execute trade based on signal

        Args:
            signal: Trading signal dictionary

        Returns:
            Trade execution result or None
        """
        symbol = signal['symbol']
        price = signal['price']
        action = signal['signal']

        # Check if we should trade
        if not self.strategy.should_trade(signal, min_confidence=0.5):
            logger.info(f"{symbol}: Signal {action} confidence too low, skipping")
            return None

        # Check risk limits
        if not self.risk_manager.can_open_position(self.balance):
            logger.warning(f"{symbol}: Risk limits reached, cannot open position")
            return None

        # Execute based on signal
        if action == 'BUY' and symbol not in self.positions:
            # Open long position
            position_size = self.risk_manager.calculate_position_size(
                self.balance, price, signal['confidence']
            )

            logger.info(f"{symbol}: Opening LONG position - Size: {position_size:.6f}, Price: ${price:.2f}")

            # Store position (in real trading, would call client.place_order)
            self.positions[symbol] = {
                'type': 'LONG',
                'entry_price': price,
                'size': position_size,
                'entry_time': datetime.now(),
                'signal': signal
            }

            # Update balance (simulated)
            cost = position_size * price
            self.balance -= cost

            trade = {
                'symbol': symbol,
                'action': 'BUY',
                'price': price,
                'size': position_size,
                'cost': cost,
                'timestamp': datetime.now(),
                'signal': signal
            }
            self.trade_history.append(trade)

            return trade

        elif action == 'SELL' and symbol in self.positions:
            # Close long position
            position = self.positions[symbol]
            if position['type'] == 'LONG':
                entry_price = position['entry_price']
                size = position['size']
                pnl = (price - entry_price) * size
                pnl_pct = (price - entry_price) / entry_price

                logger.info(f"{symbol}: Closing LONG position - P&L: ${pnl:.2f} ({pnl_pct:+.2%})")

                # Update balance (simulated)
                proceeds = size * price
                self.balance += proceeds

                # Update risk manager
                self.risk_manager.update_daily_pnl(pnl)

                trade = {
                    'symbol': symbol,
                    'action': 'SELL',
                    'price': price,
                    'size': size,
                    'proceeds': proceeds,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'timestamp': datetime.now(),
                    'signal': signal
                }
                self.trade_history.append(trade)

                # Remove position
                del self.positions[symbol]

                return trade

        return None

    async def check_stop_loss_take_profit(self):
        """Check all positions for stop loss and take profit triggers"""
        current_prices = {}

        # Get current prices for all positions
        for symbol in list(self.positions.keys()):
            try:
                price = await self.client.get_price(symbol)
                current_prices[symbol] = price
            except Exception as e:
                logger.error(f"Failed to get price for {symbol}: {e}")
                continue

        # Check each position
        for symbol, position in list(self.positions.items()):
            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            entry_price = position['entry_price']
            position_type = position['type']

            # Check stop loss
            if self.risk_manager.check_stop_loss(entry_price, current_price, position_type):
                logger.warning(f"{symbol}: STOP LOSS triggered at ${current_price:.2f}")

                # Close position
                signal = {
                    'symbol': symbol,
                    'signal': 'SELL',
                    'price': current_price,
                    'confidence': 1.0,
                    'source': 'stop_loss'
                }
                await self.execute_trade(signal)

            # Check take profit
            elif self.risk_manager.check_take_profit(entry_price, current_price, position_type):
                logger.info(f"{symbol}: TAKE PROFIT triggered at ${current_price:.2f}")

                # Close position
                signal = {
                    'symbol': symbol,
                    'signal': 'SELL',
                    'price': current_price,
                    'confidence': 1.0,
                    'source': 'take_profit'
                }
                await self.execute_trade(signal)

    async def trading_loop(self, interval: int = 300):
        """Main trading loop

        Args:
            interval: Time between iterations in seconds (default 5 minutes)
        """
        logger.info(f"Starting trading loop with {len(self.symbols)} symbols")
        logger.info(f"Symbols: {', '.join(self.symbols)}")

        iteration = 0

        while self.is_running:
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"Trading Iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Balance: ${self.balance:,.2f} | Open Positions: {len(self.positions)}")

            try:
                # Check stop loss and take profit for existing positions
                await self.check_stop_loss_take_profit()

                # Analyze each symbol
                for symbol in self.symbols:
                    try:
                        logger.info(f"\nAnalyzing {symbol}...")
                        signal = await self.analyze_symbol(symbol)

                        logger.info(f"  Signal: {signal['signal']} | Confidence: {signal['confidence']:.2%} | Price: ${signal['price']:.2f}")
                        logger.info(f"  Technical: {signal['technical']['signal']} ({signal['technical']['strength']:.2%})")
                        logger.info(f"  ML: {signal['ml']['signal']} ({signal['ml']['confidence']:.2%})")

                        # Execute trade if conditions met
                        trade = await self.execute_trade(signal)
                        if trade:
                            logger.info(f"  ✅ Trade executed: {trade['action']} {trade['size']:.6f} @ ${trade['price']:.2f}")

                    except Exception as e:
                        logger.error(f"Error analyzing {symbol}: {e}")

                # Print summary
                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration Summary:")
                logger.info(f"  Total Trades: {len(self.trade_history)}")
                logger.info(f"  Open Positions: {len(self.positions)}")
                logger.info(f"  Current Balance: ${self.balance:,.2f}")

                if self.trade_history:
                    closed_trades = [t for t in self.trade_history if 'pnl' in t]
                    if closed_trades:
                        total_pnl = sum(t['pnl'] for t in closed_trades)
                        logger.info(f"  Total P&L: ${total_pnl:,.2f}")

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")

            # Wait for next iteration
            logger.info(f"\nWaiting {interval}s until next iteration...")
            await asyncio.sleep(interval)

    async def start(self, duration_hours: int = 4):
        """Start automated trading

        Args:
            duration_hours: How long to run (hours)
        """
        logger.info(f"Starting AutoTrader for {duration_hours} hours")
        self.is_running = True

        # Start trading loop
        trading_task = asyncio.create_task(self.trading_loop())

        # Run for specified duration
        await asyncio.sleep(duration_hours * 3600)

        # Stop trading
        self.is_running = False
        await trading_task

        # Print final results
        await self.print_results()

    async def stop(self):
        """Stop automated trading"""
        logger.info("Stopping AutoTrader...")
        self.is_running = False

    async def print_results(self):
        """Print trading results summary"""
        print("\n" + "="*60)
        print("TRADING RESULTS")
        print("="*60)

        print(f"\nInitial Balance: ${10000.00:,.2f}")
        print(f"Final Balance: ${self.balance:,.2f}")

        # Calculate P&L from closed trades
        closed_trades = [t for t in self.trade_history if 'pnl' in t]
        if closed_trades:
            total_pnl = sum(t['pnl'] for t in closed_trades)
            total_return = (total_pnl / 10000.0) * 100

            wins = [t for t in closed_trades if t['pnl'] > 0]
            losses = [t for t in closed_trades if t['pnl'] <= 0]

            print(f"Total P&L: ${total_pnl:,.2f} ({total_return:+.2f}%)")
            print(f"\nTotal Trades: {len(closed_trades)}")
            print(f"  Wins: {len(wins)} ({len(wins)/len(closed_trades)*100:.1f}%)")
            print(f"  Losses: {len(losses)} ({len(losses)/len(closed_trades)*100:.1f}%)")

            if wins:
                avg_win = sum(t['pnl'] for t in wins) / len(wins)
                print(f"  Avg Win: ${avg_win:.2f}")
            if losses:
                avg_loss = sum(t['pnl'] for t in losses) / len(losses)
                print(f"  Avg Loss: ${avg_loss:.2f}")

        print(f"\nOpen Positions: {len(self.positions)}")
        for symbol, pos in self.positions.items():
            print(f"  {symbol}: {pos['type']} @ ${pos['entry_price']:.2f}")

        await self.client.close()


# Example usage
if __name__ == "__main__":
    async def run_trading_bot():
        # Initialize trader
        trader = AutoTrader(testnet=True, initial_balance=10000.0)

        # Run for 1 hour (for testing)
        await trader.start(duration_hours=1)

    # Run the bot
    asyncio.run(run_trading_bot())
