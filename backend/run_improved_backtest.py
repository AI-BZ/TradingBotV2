"""
Improved Backtest Script
Validates improvements using historical data with same parameters as paper trading
"""
import asyncio
from datetime import datetime, timedelta
from backtester import Backtester

async def main():
    print("\n" + "="*80)
    print("📊 IMPROVED STRATEGY BACKTEST")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📋 Configuration:")
    print("  - Historical Period: 30 days")
    print("  - Initial Balance: $10,000")
    print("  - Leverage: 1x (NO leverage)")
    print("  - Order Type: LIMIT (Maker fee 0.02%)")
    print("  - Trailing Stops: IMPROVED (ATR 1.8, accel 0.3, hard stop 1%)")
    print("  - Coin Selection: Top 10 by volume (filtered)")
    print("="*80 + "\n")

    # Create backtester with improved settings
    backtester = Backtester(
        initial_balance=10000.0,
        leverage=1,  # No leverage
        symbols=None  # Auto-select top 10
    )

    # Update trailing stop parameters to match improvements
    backtester.trailing_stop_manager.base_atr_multiplier = 1.8
    backtester.trailing_stop_manager.min_profit_threshold = 0.005
    backtester.trailing_stop_manager.acceleration_step = 0.3
    backtester.trailing_stop_manager.max_loss_pct = 0.01

    try:
        # Run backtest on last 30 days
        print("🔄 Running backtest on last 30 days (may take 5-10 minutes)...\n")

        # Calculate dates
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        results = await backtester.run_backtest(
            start_date=start_date,
            end_date=end_date,
            interval='1h'
        )

        # Save results
        if results and 'error' not in results:
            backtester.save_results(results, 'improved_backtest_results.json')

        # Print results
        print("\n" + "="*80)
        print("📊 BACKTEST RESULTS")
        print("="*80)

        if results and 'error' not in results:
            summary = results['backtest_summary']
            stats = results['trade_statistics']
            metrics = results['performance_metrics']

            print(f"\n⏱️  Backtest Period:")
            print(f"  Start Date:      {start_date}")
            print(f"  End Date:        {end_date}")
            print(f"  Duration:        30 days")

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
            print(f"  Max Drawdown:    {metrics.get('max_drawdown_pct', 0):.2f}%")
            print(f"  Sharpe Ratio:    {metrics.get('sharpe_ratio', 0):.2f}")

            # Fee-adjusted analysis
            total_trades = stats['total_trades']
            if total_trades > 0:
                # Maker fee: 0.02% per trade, position: $2,000
                estimated_fees = total_trades * 0.80
                net_pnl_after_fees = summary['total_pnl'] - estimated_fees
                net_return_after_fees = (net_pnl_after_fees / summary['initial_balance']) * 100

                print(f"\n💸 Fee-Adjusted Performance:")
                print(f"  Estimated Fees:  ${estimated_fees:.2f} ({total_trades} trades × $0.80)")
                print(f"  Net P&L (fees):  ${net_pnl_after_fees:.2f}")
                print(f"  Net Return:      {net_return_after_fees:+.2f}%")

            # Biggest trades
            if results.get('trades'):
                trades = results['trades']
                if trades:
                    best = max(trades, key=lambda t: t.get('pnl', 0))
                    worst = min(trades, key=lambda t: t.get('pnl', 0))

                    print(f"\n🏆 Notable Trades:")
                    print(f"  Best Trade:      {best.get('symbol', 'N/A')} ${best.get('pnl', 0):.2f} ({best.get('pnl_pct', 0):+.2%})")
                    print(f"  Worst Trade:     {worst.get('symbol', 'N/A')} ${worst.get('pnl', 0):.2f} ({worst.get('pnl_pct', 0):+.2%})")

            # Success criteria
            print(f"\n✅ Backtest Validation:")
            win_rate_ok = stats['win_rate_pct'] >= 50.0
            profit_factor_ok = metrics['profit_factor'] >= 1.0
            max_dd_ok = metrics.get('max_drawdown_pct', 100) <= 10.0

            print(f"  Win Rate ≥50%:        {stats['win_rate_pct']:.1f}% {'✅' if win_rate_ok else '❌'}")
            print(f"  Profit Factor ≥1.0:   {metrics['profit_factor']:.2f} {'✅' if profit_factor_ok else '❌'}")
            print(f"  Max Drawdown ≤10%:    {metrics.get('max_drawdown_pct', 0):.2f}% {'✅' if max_dd_ok else '❌'}")

            if win_rate_ok and profit_factor_ok and max_dd_ok:
                print(f"\n🎉 BACKTEST PASSED - Strategy validated on historical data!")
            else:
                print(f"\n⚠️  BACKTEST SHOWS CONCERNS - Review strategy parameters")

        else:
            print(f"\n❌ Backtest failed or no results")
            if results:
                print(f"Error: {results.get('error', 'Unknown error')}")

        print("\n" + "="*80)
        print(f"Backtest completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Results saved to: backend/results/improved_backtest_results.json")
        print("="*80 + "\n")

        return results

    except Exception as e:
        print(f"\n\n❌ Error during backtest: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(main())
