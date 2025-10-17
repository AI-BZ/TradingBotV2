"""
Train ML Model for Trading Strategy
Uses backtest-generated data to train a Random Forest classifier
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import joblib

def main():
    print("\n" + "="*80)
    print("🤖 ML MODEL TRAINING")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📋 Configuration:")
    print("  - Model: Random Forest Classifier")
    print("  - Features: Technical indicators + Market conditions")
    print("  - Target: Win/Loss binary classification")
    print("  - Train/Val/Test Split: 80/10/10")
    print("="*80 + "\n")

    # Load training data
    results_dir = Path(__file__).parent / 'results'

    print("📁 Loading datasets...")
    try:
        train_df = pd.read_csv(results_dir / 'ml_train.csv')
        val_df = pd.read_csv(results_dir / 'ml_val.csv')
        test_df = pd.read_csv(results_dir / 'ml_test.csv')

        print(f"   ✅ Training set:   {len(train_df)} samples")
        print(f"   ✅ Validation set: {len(val_df)} samples")
        print(f"   ✅ Test set:       {len(test_df)} samples")

    except FileNotFoundError:
        print("\n❌ Error: ML training data not found!")
        print("   Please run 'python generate_ml_training_data.py' first")
        return None

    # Prepare features and labels
    feature_columns = [
        'signal_confidence', 'technical_score', 'ml_score',
        'rsi', 'macd', 'macd_signal', 'bb_position', 'atr', 'volume_ratio',
        'volatility', 'trend_strength', 'position_type', 'entry_price', 'position_size'
    ]

    # Check which features are available
    available_features = [col for col in feature_columns if col in train_df.columns]
    print(f"\n🔧 Feature Engineering:")
    print(f"   Available features: {len(available_features)}")
    print(f"   Features: {', '.join(available_features)}")

    # Prepare datasets
    X_train = train_df[available_features]
    y_train = train_df['label']

    X_val = val_df[available_features]
    y_val = val_df['label']

    X_test = test_df[available_features]
    y_test = test_df['label']

    # Check class balance
    print(f"\n📊 Class Distribution:")
    print(f"   Training:   Wins: {y_train.sum()} ({y_train.mean():.1%}) | Losses: {len(y_train) - y_train.sum()} ({1-y_train.mean():.1%})")
    print(f"   Validation: Wins: {y_val.sum()} ({y_val.mean():.1%}) | Losses: {len(y_val) - y_val.sum()} ({1-y_val.mean():.1%})")
    print(f"   Test:       Wins: {y_test.sum()} ({y_test.mean():.1%}) | Losses: {len(y_test) - y_test.sum()} ({1-y_test.mean():.1%})")

    # Train Random Forest model
    print(f"\n🌲 Training Random Forest Model...")
    print(f"   Hyperparameters:")
    print(f"     - n_estimators: 100")
    print(f"     - max_depth: 10")
    print(f"     - min_samples_split: 20")
    print(f"     - min_samples_leaf: 10")
    print(f"     - class_weight: balanced (handle imbalance)")

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        class_weight='balanced',  # Handle class imbalance
        random_state=42,
        n_jobs=-1,  # Use all CPU cores
        verbose=1
    )

    model.fit(X_train, y_train)
    print("   ✅ Training completed!")

    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': available_features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print(f"\n🎯 Top 5 Important Features:")
    for idx, row in feature_importance.head(5).iterrows():
        print(f"   {row['feature']:20s}: {row['importance']:.4f}")

    # Evaluate on validation set
    print(f"\n📈 Validation Set Performance:")
    val_predictions = model.predict(X_val)
    val_proba = model.predict_proba(X_val)[:, 1]

    val_accuracy = (val_predictions == y_val).mean()
    val_auc = roc_auc_score(y_val, val_proba)

    print(f"   Accuracy: {val_accuracy:.2%}")
    print(f"   ROC-AUC:  {val_auc:.4f}")

    print(f"\n   Classification Report:")
    print(classification_report(y_val, val_predictions, target_names=['Loss', 'Win']))

    # Evaluate on test set
    print(f"\n🎯 Test Set Performance (Final Evaluation):")
    test_predictions = model.predict(X_test)
    test_proba = model.predict_proba(X_test)[:, 1]

    test_accuracy = (test_predictions == y_test).mean()
    test_auc = roc_auc_score(y_test, test_proba)

    print(f"   Accuracy: {test_accuracy:.2%}")
    print(f"   ROC-AUC:  {test_auc:.4f}")

    print(f"\n   Classification Report:")
    print(classification_report(y_test, test_predictions, target_names=['Loss', 'Win']))

    print(f"\n   Confusion Matrix:")
    cm = confusion_matrix(y_test, test_predictions)
    print(f"   [[TN={cm[0,0]:3d}  FP={cm[0,1]:3d}]")
    print(f"    [FN={cm[1,0]:3d}  TP={cm[1,1]:3d}]]")

    # Save model
    model_path = results_dir / 'trading_ml_model.pkl'
    joblib.dump(model, model_path)
    print(f"\n💾 Model saved to: {model_path}")

    # Save feature list
    feature_list_path = results_dir / 'ml_features.json'
    with open(feature_list_path, 'w') as f:
        json.dump(available_features, f, indent=2)
    print(f"💾 Feature list saved to: {feature_list_path}")

    # Save model metadata
    metadata = {
        'trained_at': datetime.now().isoformat(),
        'model_type': 'RandomForestClassifier',
        'n_features': len(available_features),
        'features': available_features,
        'training_samples': len(X_train),
        'validation_samples': len(X_val),
        'test_samples': len(X_test),
        'validation_accuracy': float(val_accuracy),
        'validation_auc': float(val_auc),
        'test_accuracy': float(test_accuracy),
        'test_auc': float(test_auc),
        'feature_importance': {
            feat: float(imp)
            for feat, imp in zip(feature_importance['feature'], feature_importance['importance'])
        }
    }

    metadata_path = results_dir / 'ml_model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"💾 Metadata saved to: {metadata_path}")

    # Success criteria
    print(f"\n✅ Model Training Assessment:")
    accuracy_ok = test_accuracy >= 0.50
    auc_ok = test_auc >= 0.55

    print(f"   Test Accuracy ≥50%:  {test_accuracy:.1%} {'✅' if accuracy_ok else '❌'}")
    print(f"   Test ROC-AUC ≥0.55:  {test_auc:.4f} {'✅' if auc_ok else '❌'}")

    if accuracy_ok and auc_ok:
        print(f"\n🎉 MODEL TRAINING SUCCESSFUL!")
        print(f"   The model is ready for paper trading integration.")
    else:
        print(f"\n⚠️  MODEL PERFORMANCE BELOW TARGET")
        print(f"   Consider: More data, feature engineering, or hyperparameter tuning")

    print("\n" + "="*80)
    print(f"Training completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    return model, metadata


if __name__ == "__main__":
    main()
