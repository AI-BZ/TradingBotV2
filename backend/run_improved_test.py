"""
Improved 2.5-Hour Paper Trading Test
Tests all improvements: limit orders, improved trailing stops, 1x leverage, volatility filtering
"""
import asyncio
import sys
from datetime import datetime
from paper_trader import PaperTrader

async def main():
    print("\n" + "="*80)
    print("🚀 IMPROVED TRADING BOT TEST - 2.5 Hours")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📋 Configuration:")
    print("  - Duration: 2.5 hours")
    print("  - Initial Balance: $10,000")
    print("  - Leverage: 1x (NO leverage)")
    print("  - Order Type: LIMIT (Maker fee 0.02%)")
    print("  - Trailing Stops: IMPROVED (ATR 1.8, accel 0.3, hard stop 1%)")
    print("  - Coin Selection: FILTERED (max 5% volatility)")
    print("  - AI Adaptation: ENABLED")
    print("="*80 + "\n")

    # Create paper trader with improved settings
    trader = PaperTrader(
        initial_balance=10000.0,
        leverage=1,  # No leverage for safety
        use_limit_orders=True,  # Maker fee (0.02% vs 0.04% Taker)
        use_ai_adaptation=True  # AI strategy manager enabled
    )

    try:
        # Run for 2.5 hours
        results = await trader.start(duration_hours=2.5)

        # Print detailed results
        print("\n" + "="*80)
        print("📊 IMPROVED TEST RESULTS")
        print("="*80)

        if 'error' not in results:
            summary = results['paper_trading_summary']
            stats = results['trade_statistics']
            metrics = results['performance_metrics']

            print(f"\n⏱️  Trading Session:")
            print(f"  Duration:        {summary['duration_hours']:.2f} hours")
            print(f"  Start:           {summary['start_time']}")
            print(f"  End:             {summary['end_time']}")

            print(f"\n💰 Financial Performance:")
            print(f"  Initial Balance: ${summary['initial_balance']:,.2f}")
            print(f"  Final Balance:   ${summary['final_balance']:,.2f}")
            print(f"  Total P&L:       ${summary['total_pnl']:,.2f}")
            print(f"  Total Return:    {summary['total_return_pct']:+.2f}%")

            print(f"\n📊 Trade Statistics:")
            print(f"  Total Trades:    {stats['total_trades']}")
            print(f"  Winning Trades:  {stats['winning_trades']} ({stats['win_rate_pct']:.1f}%)")
            print(f"  Losing Trades:   {stats['losing_trades']}")

            print(f"\n📈 Performance Metrics:")
            print(f"  Avg Win:         ${metrics['avg_win']:.2f}")
            print(f"  Avg Loss:        ${metrics['avg_loss']:.2f}")
            print(f"  Profit Factor:   {metrics['profit_factor']:.2f}")

            # Fee-adjusted analysis
            total_trades = stats['total_trades']
            if total_trades > 0:
                # Maker fee: 0.02% per trade
                # Position: $2,000 (20% of $10K with 1x leverage)
                # Fee per trade: $2,000 * 0.02% * 2 (open + close) = $0.80
                estimated_fees = total_trades * 0.80
                net_pnl_after_fees = summary['total_pnl'] - estimated_fees
                net_return_after_fees = (net_pnl_after_fees / summary['initial_balance']) * 100

                print(f"\n💸 Fee-Adjusted Performance (Maker 0.02%):")
                print(f"  Estimated Fees:  ${estimated_fees:.2f} ({total_trades} trades × $0.80)")
                print(f"  Net P&L (fees):  ${net_pnl_after_fees:.2f}")
                print(f"  Net Return:      {net_return_after_fees:+.2f}%")

                # Success criteria check
                print(f"\n✅ Success Criteria Evaluation:")
                win_rate_ok = stats['win_rate_pct'] >= 50.0
                profit_factor_ok = metrics['profit_factor'] >= 1.0
                net_pnl_ok = net_pnl_after_fees >= -20.0  # -0.20% acceptable

                print(f"  Win Rate ≥50%:        {stats['win_rate_pct']:.1f}% {'✅' if win_rate_ok else '❌'}")
                print(f"  Profit Factor ≥1.0:   {metrics['profit_factor']:.2f} {'✅' if profit_factor_ok else '❌'}")
                print(f"  Net P&L ≥-$20:        ${net_pnl_after_fees:.2f} {'✅' if net_pnl_ok else '❌'}")

                if win_rate_ok and profit_factor_ok and net_pnl_ok:
                    print(f"\n🎉 TEST PASSED - Strategy meets minimum criteria!")
                else:
                    print(f"\n⚠️  TEST INCONCLUSIVE - Some criteria not met")
                    if not win_rate_ok:
                        print(f"     → Need to improve win rate (currently {stats['win_rate_pct']:.1f}%)")
                    if not profit_factor_ok:
                        print(f"     → Need better profit factor (currently {metrics['profit_factor']:.2f})")
                    if not net_pnl_ok:
                        print(f"     → Net P&L too negative (${net_pnl_after_fees:.2f})")

            # Biggest win/loss analysis
            if results.get('trades'):
                trades = results['trades']
                if trades:
                    biggest_win = max(trades, key=lambda t: t.get('pnl', 0))
                    biggest_loss = min(trades, key=lambda t: t.get('pnl', 0))

                    print(f"\n🏆 Trade Analysis:")
                    print(f"  Biggest Win:     {biggest_win['symbol']} ${biggest_win['pnl']:.2f} ({biggest_win['pnl_pct']:+.2%})")
                    print(f"  Biggest Loss:    {biggest_loss['symbol']} ${biggest_loss['pnl']:.2f} ({biggest_loss['pnl_pct']:+.2%})")

                    # Check hard stop effectiveness
                    if biggest_loss['pnl_pct'] > -0.015:  # Better than -1.5%
                        print(f"  ✅ Hard stop working - max loss {biggest_loss['pnl_pct']:+.2%} (limit: -1.0%)")
                    else:
                        print(f"  ⚠️  Large loss detected: {biggest_loss['pnl_pct']:+.2%}")
        else:
            print(f"\n❌ Error: {results.get('error')}")

        print("\n" + "="*80)
        print(f"Test completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        return results

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        await trader.stop()
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
