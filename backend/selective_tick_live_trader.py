"""
Selective Tick Live Trader - Strategy B Implementation
Real-time trading with high-confidence selective entry
7 coins: ETH, SOL, BNB, DOGE, XRP, SUI, 1000PEPE
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
import json

from binance_client import BinanceClient
from tick_indicators import TickIndicators
from trailing_stop_manager import TrailingStopManager
from tick_data_collector import Tick

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SelectiveTickLiveTrader:
    """Strategy B: Selective High-Confidence Live Trading

    Goals (from analysis):
    - Minimum trades (~162/day per symbol, not 809/day)
    - Maximum profit per trade (target $100+ vs $20)
    - Highest win rate (target >85% vs 42%)

    Key Features:
    - Stricter entry: 2x volatility thresholds
    - Cooldown period: 5 minutes between entries
    - Momentum confirmation required
    - Tight BB center (0.48-0.52)
    """

    def __init__(
        self,
        binance_client: BinanceClient,
        symbols: List[str],
        initial_balance: float = 10000.0,
        leverage: int = 10,
        position_size_pct: float = 0.1,
        taker_fee: float = 0.0005,
        slippage_pct: float = 0.0001,
        cooldown_seconds: int = 300  # 5 minutes
    ):
        """Initialize selective live trader

        Args:
            binance_client: Binance API client
            symbols: List of trading symbols (CCXT format: 'ETH/USDT')
            initial_balance: Starting balance
            leverage: Futures leverage
            position_size_pct: Position size per side (% of balance)
            taker_fee: Trading fee rate
            slippage_pct: Slippage percentage
            cooldown_seconds: Minimum seconds between entries per symbol
        """
        self.binance = binance_client
        self.symbols = symbols
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage
        self.position_size_pct = position_size_pct
        self.taker_fee = taker_fee
        self.slippage_pct = slippage_pct
        self.cooldown_seconds = cooldown_seconds

        # Tick data storage (per symbol)
        self.tick_buffers: Dict[str, List[Tick]] = {symbol: [] for symbol in symbols}

        # Trading state - INDEPENDENT POSITIONS
        self.positions: Dict[str, dict] = {}  # position_key -> position_data
        self.trades: List[dict] = []  # Completed trades
        self.total_fees_paid = 0.0

        # Pair tracking for 1 SET management
        self.pair_tracking: Dict[str, dict] = {}  # pair_id -> {long_key, short_key, entry_time, first_closed, first_closed_pnl}

        # Cooldown tracking (per symbol)
        self.last_entry_time: Dict[str, float] = {symbol: 0 for symbol in symbols}

        # Performance tracking
        self.max_balance = initial_balance
        self.min_balance = initial_balance

        # Components
        self.tick_indicators = TickIndicators()
        self.trailing_stop_manager = TrailingStopManager()

        # Stats
        self.signals_generated = 0
        self.signals_skipped_cooldown = 0
        self.signals_skipped_positions = 0

        logger.info(f"✅ SelectiveTickLiveTrader initialized (Strategy B)")
        logger.info(f"   Symbols: {', '.join(symbols)}")
        logger.info(f"   Balance: ${initial_balance:,.2f}")
        logger.info(f"   Leverage: {leverage}x")
        logger.info(f"   Cooldown: {cooldown_seconds}s")
        logger.info(f"   Strategy: SELECTIVE HIGH-CONFIDENCE")

    async def start(self):
        """Start live trading"""
        logger.info("\n" + "="*80)
        logger.info("🚀 STARTING SELECTIVE LIVE TRADING (Strategy B)")
        logger.info("="*80)
        logger.info(f"Strategy: Top 20% Quality Trades Only")
        logger.info(f"Expected: ~162 trades/day per symbol (vs 809 in Strategy A)")
        logger.info(f"Goal: Win Rate >85%, Avg Profit >$80/trade")
        logger.info("="*80 + "\n")

        # Start tick collection for all symbols
        tasks = []
        for symbol in self.symbols:
            task = asyncio.create_task(self._collect_and_trade(symbol))
            tasks.append(task)

        # Wait for all symbols
        await asyncio.gather(*tasks)

    async def _collect_and_trade(self, symbol: str):
        """Collect ticks and trade for a symbol"""
        logger.info(f"📡 Starting tick collection for {symbol}")

        while True:
            try:
                # Fetch current tick data
                tick = await self._fetch_tick(symbol)

                if tick:
                    # Add to buffer
                    self.tick_buffers[symbol].append(tick)

                    # Keep last 10,000 ticks (~16 minutes at 10 ticks/sec)
                    if len(self.tick_buffers[symbol]) > 10000:
                        self.tick_buffers[symbol].pop(0)

                    # Check trailing stops
                    await self._check_trailing_stops(symbol, tick.price, tick.timestamp)

                    # Generate signals (every 10 ticks = ~1 second)
                    tick_count = len(self.tick_buffers[symbol])
                    if tick_count >= 100 and tick_count % 10 == 0:
                        await self._generate_and_execute_signals(symbol, tick)

                # Sleep before next tick (simulate ~10 ticks/sec)
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Error in tick collection for {symbol}: {e}")
                await asyncio.sleep(1)

    async def _fetch_tick(self, symbol: str) -> Tick:
        """Fetch current tick data from Binance"""
        try:
            # Get current price and orderbook
            price = await self.binance.get_price(symbol)
            orderbook = await self.binance.get_orderbook(symbol, limit=5)

            # Get 24h stats
            ticker = await self.binance.get_ticker(symbol)

            tick = Tick(
                symbol=symbol,
                timestamp=datetime.now(),
                price=float(price),
                bid=float(orderbook['bids'][0][0]) if orderbook['bids'] else price,
                ask=float(orderbook['asks'][0][0]) if orderbook['asks'] else price,
                bid_qty=float(orderbook['bids'][0][1]) if orderbook['bids'] else 0,
                ask_qty=float(orderbook['asks'][0][1]) if orderbook['asks'] else 0,
                volume_24h=float(ticker.get('volume', 0)),
                quote_volume_24h=float(ticker.get('quoteVolume', 0)),
                price_change_pct=float(ticker.get('percentage', 0))
            )

            return tick

        except Exception as e:
            logger.error(f"Error fetching tick for {symbol}: {e}")
            return None

    async def _generate_and_execute_signals(self, symbol: str, tick: Tick):
        """Generate and execute SELECTIVE trading signals (Strategy B)"""

        # Get recent ticks
        recent_ticks = self.tick_buffers[symbol][-1000:]

        if len(recent_ticks) < 100:
            return

        # Calculate indicators
        std_vol, atr_vol, hybrid_vol = self.tick_indicators.calculate_hybrid_volatility(
            recent_ticks,
            lookback_seconds=600
        )

        indicators = self.tick_indicators.generate_tick_summary(
            recent_ticks,
            lookback_seconds=600
        )

        indicators['std_volatility'] = std_vol
        indicators['atr_volatility'] = atr_vol
        indicators['hybrid_volatility'] = hybrid_vol

        # Generate SELECTIVE signal (Strategy B)
        signal = self._get_selective_signal(symbol, indicators, tick.price)

        if signal['action'] == 'BOTH':
            self.signals_generated += 1
            await self._execute_two_way_entry(symbol, tick.price, signal, tick.timestamp)
        elif signal['action'] == 'CLOSE':
            await self._close_all_positions(symbol, tick.price, tick.timestamp, signal['reason'])

    def _get_selective_signal(self, symbol: str, indicators: dict, current_price: float) -> dict:
        """Strategy B: SELECTIVE HIGH-CONFIDENCE signal generation

        Key Differences from Strategy A:
        - 2x stricter volatility thresholds (0.08% vs 0.04%)
        - Tighter BB center (0.48-0.52 vs 0.40-0.60)
        - Momentum confirmation required
        - Cooldown period enforced
        """

        hybrid_vol = indicators.get('hybrid_volatility', 0)
        atr_vol = indicators.get('atr_volatility', 0)
        bb = indicators.get('bollinger_bands', {})
        bb_position = bb.get('position', 0.5)
        momentum = indicators.get('momentum', 0)

        # STRATEGY B: SELECTIVE ENTRY CONDITIONS
        if atr_vol > 0 and hybrid_vol > 0:
            # Calculate price-relative percentages
            hybrid_pct = (hybrid_vol / current_price) * 100
            atr_pct = (atr_vol / current_price) * 100

            # STRICTER THRESHOLDS (2x from Strategy A)
            # Strategy A: hybrid >= 0.04%, atr >= 0.15%
            # Strategy B: hybrid >= 0.08%, atr >= 0.30%
            if hybrid_pct >= 0.08 and atr_pct >= 0.30:

                # TIGHTER BB CENTER
                # Strategy A: 0.40-0.60 (wide range)
                # Strategy B: 0.48-0.52 (tight center)
                if 0.48 < bb_position < 0.52:

                    # MOMENTUM CONFIRMATION REQUIRED
                    if abs(momentum) > 0.0001:

                        # CHECK COOLDOWN
                        current_time = datetime.now().timestamp()
                        last_time = self.last_entry_time.get(symbol, 0)

                        if current_time - last_time >= self.cooldown_seconds:
                            # ALL CONDITIONS MET - ENTER
                            return {
                                'action': 'BOTH',
                                'confidence': 0.95,  # Very high confidence
                                'reason': f'HIGH CONFIDENCE: H:{hybrid_pct:.3f}% A:{atr_pct:.3f}% BB:{bb_position:.3f} M:{momentum:.6f}',
                                'indicators': indicators
                            }
                        else:
                            # Cooldown active
                            self.signals_skipped_cooldown += 1
                            remaining = self.cooldown_seconds - (current_time - last_time)
                            logger.debug(f"⏳ {symbol} Cooldown: {remaining:.0f}s remaining")

        # EXIT CONDITIONS (same as Strategy A)
        has_positions = any(p['symbol'] == symbol for p in self.positions.values())
        if has_positions:
            # Volatility collapsed
            if hybrid_vol < atr_vol * 0.05:
                return {
                    'action': 'CLOSE',
                    'confidence': 0.85,
                    'reason': f'Volatility collapsed ({hybrid_vol:.4f})'
                }

            # Extreme BB
            if bb_position < 0.15 or bb_position > 0.85:
                return {
                    'action': 'CLOSE',
                    'confidence': 0.80,
                    'reason': f'Extreme BB ({bb_position:.2%})'
                }
        else:
            self.signals_skipped_positions += 1

        return {'action': 'HOLD', 'confidence': 0.5, 'reason': 'No signal'}

    async def _execute_two_way_entry(
        self,
        symbol: str,
        price: float,
        signal: dict,
        timestamp: datetime
    ):
        """Execute two-way entry (LONG + SHORT as TWO INDEPENDENT positions)

        Strategy: Enter both sides simultaneously, manage independently
        - LONG position: Profits when price rises
        - SHORT position: Profits when price falls
        - Each has independent trailing stop
        - Losing side: Hard stop at -1.5%
        - Winning side: Trailing stop to maximize profit
        """

        # Check if already have positions for this symbol
        if any(p['symbol'] == symbol for p in self.positions.values()):
            return

        # Calculate position size (per side)
        position_size_usd = self.balance * self.position_size_pct
        position_size = position_size_usd / price

        # Create pair ID for tracking statistics
        pair_id = f"{symbol}_PAIR_{timestamp.timestamp()}"

        # Create LONG position key
        long_key = f"{symbol}_LONG_{timestamp.timestamp()}"

        # Create SHORT position key
        short_key = f"{symbol}_SHORT_{timestamp.timestamp()}"

        # Store LONG position
        self.positions[long_key] = {
            'symbol': symbol,
            'side': 'LONG',
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'confidence': signal['confidence'],
            'pair_id': pair_id,  # Link to pair for statistics
            'peak_price': price,  # For trailing stop
            'indicators': signal.get('indicators', {})
        }

        # Store SHORT position
        self.positions[short_key] = {
            'symbol': symbol,
            'side': 'SHORT',
            'entry_price': price,
            'size': position_size,
            'entry_time': timestamp,
            'confidence': signal['confidence'],
            'pair_id': pair_id,  # Link to pair for statistics
            'peak_price': price,  # For trailing stop
            'indicators': signal.get('indicators', {})
        }

        # Track pair for 1 SET management
        self.pair_tracking[pair_id] = {
            'long_key': long_key,
            'short_key': short_key,
            'entry_time': timestamp,
            'symbol': symbol,
            'first_closed': None,  # 'LONG' or 'SHORT' - which closed first
            'first_closed_pnl': 0.0,  # P&L of first closed position
            'first_closed_fee': 0.0  # Fee of first closed position
        }

        # Update last entry time
        self.last_entry_time[symbol] = timestamp.timestamp()

        logger.info(
            f"🎯 TWO-WAY ENTRY: {symbol} @ ${price:.2f} | "
            f"Size: ${position_size_usd:.0f}/side | "
            f"Conf: {signal['confidence']:.0%} | "
            f"{signal['reason']}"
        )

    async def _check_trailing_stops(self, symbol: str, current_price: float, timestamp: datetime):
        """Check trailing stops for EACH position INDEPENDENTLY

        Strategy: LONG and SHORT positions managed separately
        - Each position has independent trailing stop
        - Losing side: Hard stop at -1.5%
        - Winning side: Trailing stop to maximize profit
        - They close INDEPENDENTLY at different times
        """

        positions_to_close = []

        for pos_key, position in self.positions.items():
            if position['symbol'] != symbol:
                continue

            # Get volatility for trailing stop calculation
            recent_ticks = self.tick_buffers[symbol][-100:]
            if len(recent_ticks) < 10:
                continue

            volatility = self.tick_indicators.calculate_tick_volatility(
                recent_ticks,
                lookback_seconds=60
            )

            # Calculate P&L for THIS position
            entry_price = position['entry_price']
            size = position['size']
            side = position['side']

            if side == 'LONG':
                # LONG profits when price rises
                pnl = (current_price - entry_price) * size * self.leverage
                # Update peak price (highest price seen)
                position['peak_price'] = max(position['peak_price'], current_price)
            else:  # SHORT
                # SHORT profits when price falls
                pnl = (entry_price - current_price) * size * self.leverage
                # Update peak price (lowest price seen)
                position['peak_price'] = min(position['peak_price'], current_price)

            # Calculate P&L percentage
            position_value = entry_price * size * self.leverage
            pnl_pct = (pnl / position_value) * 100

            # Calculate max profit seen so far
            if side == 'LONG':
                max_pnl = (position['peak_price'] - entry_price) * size * self.leverage
            else:  # SHORT
                max_pnl = (entry_price - position['peak_price']) * size * self.leverage

            # Trailing stop distance (ATR-based)
            atr_multiplier = 1.8  # From trading_strategy.py
            trailing_distance = volatility * atr_multiplier

            # Hard stop-loss (adjustable based on 1 SET status)
            hard_stop_pct = -1.5  # Default: -1.5% (from trading_strategy.py)

            # Check if this is the REMAINING position after first close
            min_profit_needed = position.get('min_profit_to_breakeven', 0)
            is_remaining_position = min_profit_needed > 0

            # Check if should close
            should_close = False
            close_reason = ""

            if is_remaining_position:
                # REMAINING POSITION (after first close): Different logic
                # Goal: Recover first loss and maximize profit with trailing stop

                if pnl < -min_profit_needed:
                    # SET loss would be too large (double loss)
                    should_close = True
                    close_reason = f"SET Protection (Current: ${pnl:.2f}, First loss: ${-min_profit_needed:.2f})"

                elif pnl >= min_profit_needed:
                    # Reached break-even point, now use trailing stop to maximize
                    if max_pnl > min_profit_needed:  # Had profit beyond break-even
                        # Calculate pullback from peak
                        if side == 'LONG':
                            pullback = position['peak_price'] - current_price
                        else:  # SHORT
                            pullback = current_price - position['peak_price']

                        if pullback >= trailing_distance:
                            should_close = True
                            close_reason = f"Trailing Stop (Max: ${max_pnl:.2f}, Current: ${pnl:.2f})"
                    # else: Keep holding to reach minimum profit
                # else: Keep holding, not at break-even yet

            else:
                # NORMAL POSITION (both sides still active)
                # 1. Hard stop-loss hit (LOSING SIDE)
                if pnl_pct <= hard_stop_pct:
                    should_close = True
                    close_reason = f"Hard Stop Loss ({pnl_pct:.2f}%)"

                # 2. Trailing stop from peak (WINNING SIDE)
                elif max_pnl > 0:  # Only trail if we've been in profit
                    # Calculate how far price has pulled back from peak
                    if side == 'LONG':
                        pullback = position['peak_price'] - current_price
                    else:  # SHORT
                        pullback = current_price - position['peak_price']

                    if pullback >= trailing_distance:
                        should_close = True
                        close_reason = f"Trailing Stop (Max: ${max_pnl:.2f}, Current: ${pnl:.2f})"

            if should_close:
                positions_to_close.append((pos_key, close_reason))
                logger.debug(
                    f"  {symbol} {side} Close Signal | "
                    f"P&L: ${pnl:.2f} ({pnl_pct:.2f}%) | "
                    f"{close_reason}"
                )

        # Close positions INDEPENDENTLY
        for pos_key, reason in positions_to_close:
            await self._close_position(pos_key, current_price, reason, timestamp)

    async def _close_position(
        self,
        position_key: str,
        exit_price: float,
        reason: str,
        timestamp: datetime
    ):
        """Close position with 1 SET management

        Strategy:
        - First close: Record loss, adjust remaining position's stop-loss
        - Second close: Calculate 1 SET P&L (profit - first_loss - all fees)
        """

        position = self.positions.get(position_key)
        if not position:
            return

        entry_price = position['entry_price']
        size = position['size']
        side = position['side']
        pair_id = position.get('pair_id')

        # Calculate P&L with slippage
        if side == 'LONG':
            entry_with_slippage = entry_price * (1 + self.slippage_pct)
            exit_with_slippage = exit_price * (1 - self.slippage_pct)
            pnl_gross = (exit_with_slippage - entry_with_slippage) * size * self.leverage
        else:  # SHORT
            entry_with_slippage = entry_price * (1 - self.slippage_pct)
            exit_with_slippage = exit_price * (1 + self.slippage_pct)
            pnl_gross = (entry_with_slippage - exit_with_slippage) * size * self.leverage

        # Calculate fees (entry + exit)
        position_value = entry_price * size
        fee = position_value * self.taker_fee * 2  # Entry + Exit
        pnl_net = pnl_gross - fee

        # Check if this is FIRST or SECOND close
        pair_info = self.pair_tracking.get(pair_id)
        is_first_close = pair_info and pair_info['first_closed'] is None

        if is_first_close:
            # FIRST CLOSE (usually the losing side)
            logger.info(
                f"❌ FIRST CLOSE ({side}): {position['symbol']} | "
                f"P&L: ${pnl_net:+.2f} | Fee: ${fee:.2f} | {reason}"
            )

            # Update pair tracking
            pair_info['first_closed'] = side
            pair_info['first_closed_pnl'] = pnl_net
            pair_info['first_closed_fee'] = fee

            # Find remaining position and adjust its stop-loss
            if side == 'LONG':
                remaining_key = pair_info['short_key']
            else:
                remaining_key = pair_info['long_key']

            remaining_pos = self.positions.get(remaining_key)
            if remaining_pos:
                # Adjust remaining position's minimum profit target
                # Must recover first loss to break even
                remaining_pos['min_profit_to_breakeven'] = abs(pnl_net) + fee * 2  # Need to cover both fees

                logger.info(
                    f"📊 REMAINING ({remaining_pos['side']}): "
                    f"Must profit >${remaining_pos['min_profit_to_breakeven']:.2f} to break even on SET"
                )

            # Remove first position (don't record as trade yet)
            del self.positions[position_key]

        else:
            # SECOND CLOSE (usually the winning side with trailing stop)
            first_loss = pair_info['first_closed_pnl'] if pair_info else 0
            first_fee = pair_info['first_closed_fee'] if pair_info else 0

            # Calculate 1 SET P&L
            set_pnl = pnl_net + first_loss  # Second profit + first loss (negative)
            set_total_fees = fee + first_fee

            # Update balance (only once for the SET)
            self.balance += set_pnl
            self.total_fees_paid += set_total_fees
            self.max_balance = max(self.max_balance, self.balance)
            self.min_balance = min(self.min_balance, self.balance)

            # Record as 1 SET trade
            set_entry_time = pair_info['entry_time'] if pair_info else position['entry_time']
            trade = {
                'pair_id': pair_id,
                'symbol': position['symbol'],
                'type': '1-SET',
                'entry_price': entry_price,
                'exit_price': exit_price,
                'size': size,
                'first_closed': pair_info['first_closed'] if pair_info else None,
                'first_pnl': first_loss,
                'second_closed': side,
                'second_pnl': pnl_net,
                'set_pnl': set_pnl,
                'pnl': set_pnl,  # For compatibility with performance calculation
                'set_total_fees': set_total_fees,
                'fees': set_total_fees,  # For compatibility
                'entry_time': set_entry_time.isoformat() if hasattr(set_entry_time, 'isoformat') else set_entry_time,
                'exit_time': timestamp.isoformat(),
                'hold_time_seconds': (timestamp - set_entry_time).total_seconds() if hasattr(set_entry_time, 'total_seconds') else 0,
                'reason': reason,
                'balance_after': self.balance
            }
            self.trades.append(trade)

            # Remove second position
            del self.positions[position_key]

            # Clean up pair tracking
            if pair_id in self.pair_tracking:
                del self.pair_tracking[pair_id]

            logger.info(
                f"{'✅' if set_pnl > 0 else '❌'} SET COMPLETE: {position['symbol']} | "
                f"1st: ${first_loss:+.2f} | 2nd: ${pnl_net:+.2f} | "
                f"SET P&L: ${set_pnl:+.2f} | Fees: ${set_total_fees:.2f} | {reason}"
            )

    async def _close_all_positions(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        reason: str
    ):
        """Close all positions for a symbol (both LONG and SHORT)"""

        positions_to_close = [
            pos_key for pos_key, pos in self.positions.items()
            if pos['symbol'] == symbol
        ]

        for pos_key in positions_to_close:
            await self._close_position(pos_key, price, reason, timestamp)

    async def get_performance(self) -> dict:
        """Get current performance metrics with per-coin breakdown"""

        total_pnl = self.balance - self.initial_balance
        total_return = (total_pnl / self.initial_balance) * 100

        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['pnl'] > 0]
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        avg_profit = total_pnl / total_trades if total_trades > 0 else 0

        max_dd = ((self.max_balance - self.min_balance) / self.max_balance * 100) if self.max_balance > 0 else 0

        # Calculate trades per day
        if self.trades:
            first_trade = datetime.fromisoformat(self.trades[0]['entry_time'])
            last_trade = datetime.fromisoformat(self.trades[-1]['entry_time'])
            days = max(1, (last_trade - first_trade).total_seconds() / 86400)
            trades_per_day = total_trades / days
        else:
            trades_per_day = 0

        # Per-coin statistics
        per_coin_stats = {}
        for symbol in self.symbols:
            coin_trades = [t for t in self.trades if t['symbol'] == symbol]
            coin_winning = [t for t in coin_trades if t['pnl'] > 0]
            coin_pnl = sum(t['pnl'] for t in coin_trades)

            per_coin_stats[symbol] = {
                'total_trades': len(coin_trades),
                'winning_trades': len(coin_winning),
                'win_rate': (len(coin_winning) / len(coin_trades) * 100) if coin_trades else 0,
                'total_pnl': coin_pnl,
                'avg_profit_per_trade': coin_pnl / len(coin_trades) if coin_trades else 0,
                'trades_per_day': len(coin_trades) / days if self.trades and days > 0 else 0
            }

        # Active positions details (each position independently)
        active_positions_list = []
        for pos_key, position in self.positions.items():
            # Get current price from tick buffer
            current_price = 0
            if position['symbol'] in self.tick_buffers and self.tick_buffers[position['symbol']]:
                current_price = self.tick_buffers[position['symbol']][-1].price

            # Calculate unrealized P&L
            entry_price = position['entry_price']
            size = position['size']
            side = position['side']

            if current_price > 0:
                if side == 'LONG':
                    unrealized_pnl = (current_price - entry_price) * size * self.leverage
                else:  # SHORT
                    unrealized_pnl = (entry_price - current_price) * size * self.leverage

                # Percentage relative to position value
                position_value = entry_price * size * self.leverage
                unrealized_pnl_pct = (unrealized_pnl / position_value) * 100
            else:
                unrealized_pnl = 0
                unrealized_pnl_pct = 0

            # Calculate hold duration
            hold_duration = (datetime.now() - position['entry_time']).total_seconds()

            active_positions_list.append({
                'symbol': position['symbol'],
                'side': side,
                'pair_id': position.get('pair_id'),
                'entry_price': entry_price,
                'current_price': current_price,
                'size': size,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': unrealized_pnl_pct,
                'hold_duration_seconds': hold_duration,
                'confidence': position.get('confidence', 0)
            })

        return {
            'balance': self.balance,
            'total_pnl': total_pnl,
            'total_return': total_return,
            'total_trades': total_trades,
            'trades_per_day': trades_per_day,
            'winning_trades': len(winning_trades),
            'win_rate': win_rate,
            'avg_profit_per_trade': avg_profit,
            'max_drawdown': max_dd,
            'total_fees_paid': self.total_fees_paid,
            'active_positions': len(self.positions),  # Count of active positions
            'signals_generated': self.signals_generated,
            'signals_skipped_cooldown': self.signals_skipped_cooldown,
            'strategy': 'Strategy B - Selective High-Confidence (1-SET Management)',
            'per_coin_stats': per_coin_stats,
            'active_positions_list': active_positions_list
        }

    async def stop(self):
        """Stop trading and save results"""
        logger.info("\n" + "="*80)
        logger.info("🛑 STOPPING SELECTIVE LIVE TRADING")
        logger.info("="*80)

        # Close all remaining positions
        final_time = datetime.now()
        for symbol in self.symbols:
            if symbol in self.tick_buffers and self.tick_buffers[symbol]:
                final_price = self.tick_buffers[symbol][-1].price
                await self._close_all_positions(symbol, final_price, final_time, "Trading Stopped")

        # Get final performance
        performance = await self.get_performance()

        logger.info(f"\n📊 FINAL PERFORMANCE:")
        logger.info(f"   Total Return: {performance['total_return']:+.2f}%")
        logger.info(f"   Win Rate: {performance['win_rate']:.2f}%")
        logger.info(f"   Total Trades: {performance['total_trades']}")
        logger.info(f"   Trades/Day: {performance['trades_per_day']:.1f}")
        logger.info(f"   Avg Profit/Trade: ${performance['avg_profit_per_trade']:.2f}")
        logger.info(f"   Total Fees: ${performance['total_fees_paid']:.2f}")
        logger.info(f"   Max Drawdown: {performance['max_drawdown']:.2f}%")
        logger.info("="*80 + "\n")

        # Save results
        results = {
            'performance': performance,
            'trades': self.trades,
            'timestamp': datetime.now().isoformat()
        }

        output_file = Path('claudedocs/selective_live_trading_results.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"✅ Results saved to {output_file}")


async def main():
    """Main entry point for selective live trading"""

    # Initialize Binance client
    import os
    binance_client = BinanceClient(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_API_SECRET'),
        testnet=True,  # Use testnet for safety
        use_futures=True
    )

    # 7 target symbols
    symbols = [
        'ETH/USDT',
        'SOL/USDT',
        'BNB/USDT',
        'DOGE/USDT',
        'XRP/USDT',
        'SUI/USDT',
        '1000PEPE/USDT'
    ]

    # Initialize trader with Strategy B
    trader = SelectiveTickLiveTrader(
        binance_client=binance_client,
        symbols=symbols,
        initial_balance=10000.0,
        leverage=10,
        position_size_pct=0.1,
        taker_fee=0.0005,
        slippage_pct=0.0001,
        cooldown_seconds=300  # 5 minutes
    )

    try:
        # Start trading
        await trader.start()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Keyboard interrupt received")
    finally:
        # Stop and save results
        await trader.stop()
        await binance_client.close()


if __name__ == "__main__":
    asyncio.run(main())
