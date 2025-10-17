"""
Generate ML Training Data from Backtest
Runs backtest on 6 months of historical data and saves trade features for ML training
"""
import asyncio
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
from backtester import Backtester
from technical_indicators import TechnicalIndicators

async def main():
    print("\n" + "="*80)
    print("📊 ML TRAINING DATA GENERATION")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📋 Configuration:")
    print("  - Historical Period: 6 months (Apr-Oct 2024)")
    print("  - Initial Balance: $10,000")
    print("  - Leverage: 1x (NO leverage)")
    print("  - Order Type: LIMIT (Maker fee 0.02%)")
    print("  - Trailing Stops: IMPROVED (ATR 1.8, accel 0.3, hard stop 1%)")
    print("  - Coin Selection: Top 10 by volume (filtered)")
    print("  - Output: ML training dataset (features + labels)")
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
        # Run backtest on last 6 months
        print("🔄 Running backtest on last 6 months (may take 10-20 minutes)...\n")

        # Calculate dates (6 months)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

        print(f"Period: {start_date} to {end_date}")
        print("Loading historical data...\n")

        results = await backtester.run_backtest(
            start_date=start_date,
            end_date=end_date,
            interval='1h'
        )

        # Extract ML training features from trades
        if results and 'error' not in results and results.get('trades'):
            print(f"\n✅ Backtest completed successfully!")
            print(f"Total trades: {len(results['trades'])}")

            # Generate ML training dataset
            ml_dataset = generate_ml_features(results['trades'])

            # Save to file
            output_path = Path(__file__).parent / 'results' / 'ml_training_data.csv'
            output_path.parent.mkdir(exist_ok=True)

            ml_dataset.to_csv(output_path, index=False)
            print(f"\n📁 ML training data saved to: {output_path}")
            print(f"   Total samples: {len(ml_dataset)}")
            print(f"   Features: {len(ml_dataset.columns) - 1}")  # -1 for label column

            # Print feature summary
            print(f"\n📊 Feature Summary:")
            print(f"   Winning trades: {ml_dataset['label'].sum()}")
            print(f"   Losing trades: {len(ml_dataset) - ml_dataset['label'].sum()}")
            print(f"   Win rate: {ml_dataset['label'].mean():.2%}")

            # Split into train/val/test
            train_size = int(len(ml_dataset) * 0.8)
            val_size = int(len(ml_dataset) * 0.1)

            train_df = ml_dataset[:train_size]
            val_df = ml_dataset[train_size:train_size + val_size]
            test_df = ml_dataset[train_size + val_size:]

            # Save splits
            train_df.to_csv(Path(__file__).parent / 'results' / 'ml_train.csv', index=False)
            val_df.to_csv(Path(__file__).parent / 'results' / 'ml_val.csv', index=False)
            test_df.to_csv(Path(__file__).parent / 'results' / 'ml_test.csv', index=False)

            print(f"\n📦 Dataset splits saved:")
            print(f"   Training:   {len(train_df)} samples (80%)")
            print(f"   Validation: {len(val_df)} samples (10%)")
            print(f"   Test:       {len(test_df)} samples (10%)")

            # Print backtest performance
            summary = results['backtest_summary']
            stats = results['trade_statistics']

            print(f"\n💰 Backtest Performance:")
            print(f"   Total Return: {summary['total_return_pct']:+.2f}%")
            print(f"   Win Rate:     {stats['win_rate_pct']:.1f}%")
            print(f"   Profit Factor: {results['performance_metrics']['profit_factor']:.2f}")

        else:
            print(f"\n❌ Backtest failed or no trades")
            if results:
                print(f"Error: {results.get('error', 'Unknown error')}")

        print("\n" + "="*80)
        print(f"Data generation completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        return ml_dataset if results and 'error' not in results else None

    except Exception as e:
        print(f"\n\n❌ Error during data generation: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_ml_features(trades):
    """Generate ML features from trade history

    Args:
        trades: List of trade dictionaries from backtest

    Returns:
        DataFrame with features and labels
    """
    print("\n🔧 Generating ML features from trades...")

    features_list = []

    for trade in trades:
        if 'pnl' not in trade:  # Skip open positions
            continue

        # Extract signal features (with fallback for backtest trades without signal field)
        signal = trade.get('signal', {})

        # Extract features from trade
        features = {
            # Signal features (using defaults for backtest trades)
            'signal_confidence': signal.get('confidence', 0.5),  # Default 50% for backtest
            'technical_score': signal.get('technical_score', 0.5),
            'ml_score': signal.get('ml_score', 0.0),  # No ML yet

            # Technical indicators (from signal or defaults)
            'rsi': signal.get('rsi', 50),
            'macd': signal.get('macd', 0),
            'macd_signal': signal.get('macd_signal', 0),
            'bb_position': signal.get('bb_position', 0.5),
            'atr': signal.get('atr', 0),
            'volume_ratio': signal.get('volume_ratio', 1.0),

            # Market conditions
            'volatility': signal.get('volatility', 0.02),  # Default 2%
            'trend_strength': signal.get('trend_strength', 0.5),

            # Trade metadata
            'position_type': 1 if trade['type'] == 'LONG' else 0,
            'entry_price': trade['entry_price'],
            'position_size': trade['size'],
            'duration_hours': trade.get('duration_hours', 0),
            'exit_reason': 1 if trade.get('exit_reason') == 'trailing_stop' else 0,

            # Label (1 = win, 0 = loss)
            'label': 1 if trade['pnl'] > 0 else 0,

            # Additional metrics (for analysis, not training)
            'pnl': trade['pnl'],
            'pnl_pct': trade['pnl_pct']
        }

        features_list.append(features)

    df = pd.DataFrame(features_list)

    print(f"   ✅ Generated {len(df)} feature samples")
    print(f"   ✅ Features: {list(df.columns[:-3])}")  # Exclude label, pnl, pnl_pct

    return df


if __name__ == "__main__":
    asyncio.run(main())
