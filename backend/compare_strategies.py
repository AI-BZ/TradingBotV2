"""
Compare Two Trading Strategies:
Strategy A: High Frequency (current approach) - Many trades
Strategy B: Selective High-Confidence - Few high-quality trades

Same test period, same data, different entry logic
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from tick_data_collector import Tick
from tick_backtester import TickBacktester
from tick_indicators import TickIndicators

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SelectiveTickBacktester(TickBacktester):
    """Strategy B: Selective High-Confidence Trades Only

    Only enter when:
    1. Volatility is VERY high (top 20% of range)
    2. BB position is perfect center (0.48-0.52)
    3. Momentum confirms direction
    4. Minimum time between trades (cooldown)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_entry_time = {}
        self.cooldown_seconds = 300  # 5 minutes between trades

    def _get_tick_signal(self, symbol: str, indicators: dict, current_price: float) -> dict:
        """SELECTIVE STRATEGY: Only very high confidence signals"""

        hybrid_vol = indicators.get('hybrid_volatility', 0)
        atr_vol = indicators.get('atr_volatility', 0)
        bb = indicators.get('bollinger_bands', {})
        bb_position = bb.get('position', 0.5)
        momentum = indicators.get('momentum', 0)

        # Calculate percentages
        if atr_vol > 0 and hybrid_vol > 0:
            hybrid_pct = (hybrid_vol / current_price) * 100
            atr_pct = (atr_vol / current_price) * 100

            # MUCH STRICTER ENTRY CONDITIONS
            # 1. VERY HIGH volatility (2x the normal threshold)
            # 2. Perfect BB center position
            # 3. Strong momentum confirmation
            if hybrid_pct >= 0.08 and atr_pct >= 0.30:  # 2x stricter
                if 0.48 < bb_position < 0.52:  # Very tight center
                    if abs(momentum) > 0.0001:  # Must have momentum
                        # Check cooldown
                        current_time = datetime.now().timestamp()
                        last_time = self.last_entry_time.get(symbol, 0)

                        if current_time - last_time >= self.cooldown_seconds:
                            self.last_entry_time[symbol] = current_time

                            return {
                                'action': 'BOTH',
                                'confidence': 0.95,  # Very high confidence
                                'reason': f'HIGH VOL (H:{hybrid_pct:.2f}% A:{atr_pct:.2f}%) + Perfect BB + Momentum',
                                'indicators': indicators
                            }

        # Exit logic (same as Strategy A)
        has_positions = any(p['symbol'] == symbol for p in self.positions.values())
        if has_positions:
            if hybrid_vol < atr_vol * 0.05:
                return {
                    'action': 'CLOSE',
                    'confidence': 0.85,
                    'reason': f'Volatility collapsed ({hybrid_vol:.4f})'
                }

            if bb_position < 0.15 or bb_position > 0.85:
                return {
                    'action': 'CLOSE',
                    'confidence': 0.80,
                    'reason': f'Extreme BB ({bb_position:.2%})'
                }

        return {'action': 'HOLD', 'confidence': 0.5, 'reason': 'No signal'}


async def load_test_data(symbol: str, start_date: str, end_date: str) -> List[Tick]:
    """Load tick data from saved files"""
    ticks = []

    # Try to load from file
    file_path = Path(f"tick_data/{symbol.replace('/', '_')}_{start_date}_to_{end_date}.jsonl")

    if not file_path.exists():
        logger.error(f"Data file not found: {file_path}")
        return ticks

    try:
        with open(file_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                tick = Tick(
                    symbol=data['symbol'],
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    price=float(data['price']),
                    bid=float(data['bid']),
                    ask=float(data['ask']),
                    bid_qty=float(data.get('bid_qty', 0)),
                    ask_qty=float(data.get('ask_qty', 0)),
                    volume_24h=float(data['volume_24h']),
                    quote_volume_24h=float(data.get('quote_volume_24h', 0)),
                    price_change_pct=float(data.get('price_change_pct', 0))
                )
                ticks.append(tick)

        logger.info(f"✅ Loaded {len(ticks):,} ticks for {symbol}")
    except Exception as e:
        logger.error(f"❌ Error loading data: {e}")

    return ticks


async def main():
    """Compare Strategy A vs Strategy B"""

    symbol = 'ETH/USDT'
    start_date = '2024-10-02'
    end_date = '2024-10-09'

    logger.info("\n" + "="*80)
    logger.info("🔬 STRATEGY COMPARISON TEST")
    logger.info("="*80)
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"")
    logger.info(f"Strategy A: High Frequency - Many trades, more fees")
    logger.info(f"Strategy B: Selective - Few high-confidence trades")
    logger.info("="*80 + "\n")

    # Load test data
    ticks = await load_test_data(symbol, start_date, end_date)

    if not ticks:
        logger.error("❌ No test data available!")
        return

    tick_data = {symbol: ticks}

    # === STRATEGY A: High Frequency ===
    logger.info("\n📊 STRATEGY A: HIGH FREQUENCY")
    logger.info("="*80)

    strategy_a = TickBacktester(
        symbols=[symbol],
        initial_balance=10000.0,
        leverage=10,
        position_size_pct=0.1,
        taker_fee=0.0005,
        slippage_pct=0.0001
    )

    results_a = await strategy_a.run_backtest(tick_data, progress_interval=20000)

    # === STRATEGY B: Selective ===
    logger.info("\n📊 STRATEGY B: SELECTIVE HIGH-CONFIDENCE")
    logger.info("="*80)

    strategy_b = SelectiveTickBacktester(
        symbols=[symbol],
        initial_balance=10000.0,
        leverage=10,
        position_size_pct=0.1,
        taker_fee=0.0005,
        slippage_pct=0.0001
    )

    results_b = await strategy_b.run_backtest(tick_data, progress_interval=20000)

    # === COMPARISON ===
    logger.info("\n" + "="*80)
    logger.info("⚖️  STRATEGY COMPARISON")
    logger.info("="*80)

    comparison = {
        'test_period': f"{start_date} to {end_date}",
        'symbol': symbol,
        'strategy_a': {
            'name': 'High Frequency',
            'description': 'Many trades, moderate thresholds',
            'total_trades': results_a['total_trades'],
            'trades_per_day': results_a['total_trades'] / 7,
            'win_rate': results_a['win_rate'],
            'total_return': results_a['total_return'],
            'final_balance': results_a['final_balance'],
            'total_fees_paid': results_a['total_fees_paid'],
            'fee_percentage': results_a['fee_percentage'],
            'avg_profit_per_trade': results_a['total_pnl'] / results_a['total_trades'] if results_a['total_trades'] > 0 else 0,
            'sharpe_ratio': results_a['sharpe_ratio'],
            'max_drawdown': results_a['max_drawdown']
        },
        'strategy_b': {
            'name': 'Selective High-Confidence',
            'description': 'Few high-quality trades, strict thresholds',
            'total_trades': results_b['total_trades'],
            'trades_per_day': results_b['total_trades'] / 7,
            'win_rate': results_b['win_rate'],
            'total_return': results_b['total_return'],
            'final_balance': results_b['final_balance'],
            'total_fees_paid': results_b['total_fees_paid'],
            'fee_percentage': results_b['fee_percentage'],
            'avg_profit_per_trade': results_b['total_pnl'] / results_b['total_trades'] if results_b['total_trades'] > 0 else 0,
            'sharpe_ratio': results_b['sharpe_ratio'],
            'max_drawdown': results_b['max_drawdown']
        }
    }

    # Print comparison
    print("\n" + "="*80)
    print("📊 DETAILED COMPARISON")
    print("="*80)
    print(f"\n{'Metric':<30} {'Strategy A (High Freq)':<25} {'Strategy B (Selective)':<25}")
    print("-"*80)
    print(f"{'Total Trades':<30} {comparison['strategy_a']['total_trades']:<25,} {comparison['strategy_b']['total_trades']:<25,}")
    print(f"{'Trades/Day':<30} {comparison['strategy_a']['trades_per_day']:<25.1f} {comparison['strategy_b']['trades_per_day']:<25.1f}")
    print(f"{'Win Rate':<30} {comparison['strategy_a']['win_rate']:<25.2f}% {comparison['strategy_b']['win_rate']:<25.2f}%")
    print(f"{'Total Return':<30} {comparison['strategy_a']['total_return']:<25.2f}% {comparison['strategy_b']['total_return']:<25.2f}%")
    print(f"{'Final Balance':<30} ${comparison['strategy_a']['final_balance']:<24,.2f} ${comparison['strategy_b']['final_balance']:<24,.2f}")
    print(f"{'Total Fees Paid':<30} ${comparison['strategy_a']['total_fees_paid']:<24,.2f} ${comparison['strategy_b']['total_fees_paid']:<24,.2f}")
    print(f"{'Fee % of PnL':<30} {comparison['strategy_a']['fee_percentage']:<25.2f}% {comparison['strategy_b']['fee_percentage']:<25.2f}%")
    print(f"{'Avg Profit/Trade':<30} ${comparison['strategy_a']['avg_profit_per_trade']:<24.2f} ${comparison['strategy_b']['avg_profit_per_trade']:<24.2f}")
    print(f"{'Sharpe Ratio':<30} {comparison['strategy_a']['sharpe_ratio']:<25.2f} {comparison['strategy_b']['sharpe_ratio']:<25.2f}")
    print(f"{'Max Drawdown':<30} {comparison['strategy_a']['max_drawdown']:<25.2f}% {comparison['strategy_b']['max_drawdown']:<25.2f}%")
    print("="*80)

    # Determine winner
    print("\n🏆 WINNER ANALYSIS:")
    print("-"*80)

    if comparison['strategy_b']['final_balance'] > comparison['strategy_a']['final_balance']:
        winner = "Strategy B (Selective)"
        advantage = comparison['strategy_b']['final_balance'] - comparison['strategy_a']['final_balance']
        print(f"✅ {winner} wins by ${advantage:,.2f}")
    else:
        winner = "Strategy A (High Frequency)"
        advantage = comparison['strategy_a']['final_balance'] - comparison['strategy_b']['final_balance']
        print(f"✅ {winner} wins by ${advantage:,.2f}")

    print("\n📝 Key Insights:")
    fee_savings = comparison['strategy_a']['total_fees_paid'] - comparison['strategy_b']['total_fees_paid']
    print(f"- Strategy B saves ${fee_savings:,.2f} in fees")
    print(f"- Strategy B makes {comparison['strategy_b']['trades_per_day']:.1f} trades/day vs {comparison['strategy_a']['trades_per_day']:.1f}")
    print(f"- Strategy B avg profit: ${comparison['strategy_b']['avg_profit_per_trade']:.2f} vs ${comparison['strategy_a']['avg_profit_per_trade']:.2f}")

    print("="*80 + "\n")

    # Save results
    output_file = Path('claudedocs/strategy_comparison_results.json')
    with open(output_file, 'w') as f:
        json.dump(comparison, f, indent=2)

    logger.info(f"✅ Comparison results saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
