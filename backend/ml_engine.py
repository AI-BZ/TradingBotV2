"""
ML Engine - Machine Learning models for trading predictions
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Optional, Tuple
import logging
import pickle
import os

logger = logging.getLogger(__name__)

class MLEngine:
    """Machine Learning engine for trading signal prediction"""

    def __init__(self, model_path: str = "models/"):
        """Initialize ML engine

        Args:
            model_path: Directory to save/load trained models
        """
        self.model_path = model_path
        self.rf_model = None
        self.scaler = StandardScaler()
        self.feature_names = []

        # Create models directory if it doesn't exist
        os.makedirs(model_path, exist_ok=True)

        logger.info(f"MLEngine initialized with model_path: {model_path}")

    def prepare_features(self, data: pd.DataFrame, indicators: Dict) -> pd.DataFrame:
        """Prepare features from technical indicators for ML model

        Args:
            data: OHLCV dataframe
            indicators: Dictionary of technical indicators

        Returns:
            DataFrame with ML features
        """
        features = pd.DataFrame()

        # Price features
        features['price_change'] = data['close'].pct_change()
        features['volume_change'] = data['volume'].pct_change()
        features['high_low_ratio'] = (data['high'] - data['low']) / data['close']

        # Technical indicator features
        if 'rsi' in indicators:
            features['rsi'] = indicators['rsi']
            features['rsi_oversold'] = (indicators['rsi'] < 30).astype(int)
            features['rsi_overbought'] = (indicators['rsi'] > 70).astype(int)

        if 'macd' in indicators:
            macd_data = indicators['macd']
            features['macd'] = macd_data.get('macd', 0)
            features['macd_signal'] = macd_data.get('signal', 0)
            features['macd_histogram'] = macd_data.get('histogram', 0)
            features['macd_crossover'] = (features['macd'] > features['macd_signal']).astype(int)

        if 'bb' in indicators:
            bb_data = indicators['bb']
            features['bb_position'] = (data['close'].iloc[-1] - bb_data.get('lower', 0)) / (bb_data.get('upper', 0) - bb_data.get('lower', 1))
            features['bb_width'] = bb_data.get('bandwidth', 0)

        if 'sma' in indicators:
            sma_data = indicators['sma']
            features['sma20'] = sma_data.get('sma_20', 0)
            features['sma50'] = sma_data.get('sma_50', 0)
            features['price_vs_sma20'] = (data['close'].iloc[-1] / sma_data.get('sma_20', 1)) - 1
            features['price_vs_sma50'] = (data['close'].iloc[-1] / sma_data.get('sma_50', 1)) - 1
            features['sma_crossover'] = (sma_data.get('sma_20', 0) > sma_data.get('sma_50', 0)).astype(int)

        if 'atr' in indicators:
            features['atr'] = indicators['atr']
            features['atr_ratio'] = indicators['atr'] / data['close'].iloc[-1]

        if 'stoch' in indicators:
            stoch_data = indicators['stoch']
            features['stoch_k'] = stoch_data.get('k', 0)
            features['stoch_d'] = stoch_data.get('d', 0)

        if 'adx' in indicators:
            features['adx'] = indicators['adx']

        # Forward fill and backward fill NaN values
        features = features.fillna(method='ffill').fillna(method='bfill').fillna(0)

        self.feature_names = features.columns.tolist()

        return features

    def create_labels(self, data: pd.DataFrame, lookahead: int = 5, threshold: float = 0.001) -> np.ndarray:
        """Create trading labels based on future price movement

        Args:
            data: OHLCV dataframe
            lookahead: Number of periods to look ahead
            threshold: Minimum price change threshold to trigger signal

        Returns:
            Array of labels: 1 (BUY), 0 (HOLD), -1 (SELL)
        """
        labels = []
        closes = data['close'].values

        for i in range(len(closes)):
            if i + lookahead >= len(closes):
                labels.append(0)  # HOLD for last few candles
                continue

            future_price = closes[i + lookahead]
            current_price = closes[i]
            price_change = (future_price - current_price) / current_price

            if price_change > threshold:
                labels.append(1)  # BUY signal
            elif price_change < -threshold:
                labels.append(-1)  # SELL signal
            else:
                labels.append(0)  # HOLD

        return np.array(labels)

    def train_model(self, data: pd.DataFrame, indicators_list: List[Dict],
                    lookahead: int = 5, threshold: float = 0.001) -> Dict:
        """Train Random Forest model on historical data

        Args:
            data: OHLCV dataframe
            indicators_list: List of indicator dictionaries for each time period
            lookahead: Periods to look ahead for labels
            threshold: Price change threshold

        Returns:
            Training metrics dictionary
        """
        logger.info(f"Training ML model with {len(data)} samples")

        # Prepare features for all time periods
        all_features = []
        for indicators in indicators_list:
            features = self.prepare_features(data, indicators)
            all_features.append(features.iloc[-1].values)

        X = pd.DataFrame(all_features, columns=self.feature_names)
        y = self.create_labels(data, lookahead, threshold)

        # Ensure X and y have same length
        min_len = min(len(X), len(y))
        X = X.iloc[:min_len]
        y = y[:min_len]

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train Random Forest
        self.rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1
        )

        self.rf_model.fit(X_scaled, y)

        # Calculate training metrics
        train_score = self.rf_model.score(X_scaled, y)

        # Feature importance
        feature_importance = dict(zip(self.feature_names, self.rf_model.feature_importances_))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]

        metrics = {
            'train_accuracy': train_score,
            'n_samples': len(X),
            'n_features': len(self.feature_names),
            'top_features': top_features,
            'label_distribution': {
                'buy': int(np.sum(y == 1)),
                'hold': int(np.sum(y == 0)),
                'sell': int(np.sum(y == -1))
            }
        }

        logger.info(f"Model trained with accuracy: {train_score:.4f}")
        logger.info(f"Label distribution: {metrics['label_distribution']}")

        return metrics

    def predict(self, data: pd.DataFrame, indicators: Dict) -> Tuple[int, float]:
        """Predict trading signal using trained model

        Args:
            data: Current OHLCV data
            indicators: Current technical indicators

        Returns:
            Tuple of (signal, confidence)
            signal: 1 (BUY), 0 (HOLD), -1 (SELL)
            confidence: Prediction probability
        """
        if self.rf_model is None:
            raise ValueError("Model not trained yet. Call train_model() first.")

        # Prepare features
        features = self.prepare_features(data, indicators)
        X = features.iloc[-1:].values

        # Scale features
        X_scaled = self.scaler.transform(X)

        # Predict
        prediction = self.rf_model.predict(X_scaled)[0]
        probabilities = self.rf_model.predict_proba(X_scaled)[0]
        confidence = probabilities.max()

        return int(prediction), float(confidence)

    def save_model(self, filename: str = "rf_model.pkl"):
        """Save trained model to disk

        Args:
            filename: Model filename
        """
        if self.rf_model is None:
            raise ValueError("No model to save. Train model first.")

        model_data = {
            'rf_model': self.rf_model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }

        filepath = os.path.join(self.model_path, filename)
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model saved to {filepath}")

    def load_model(self, filename: str = "rf_model.pkl"):
        """Load trained model from disk

        Args:
            filename: Model filename
        """
        filepath = os.path.join(self.model_path, filename)

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")

        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.rf_model = model_data['rf_model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']

        logger.info(f"Model loaded from {filepath}")


# Example usage and testing
if __name__ == "__main__":
    from technical_indicators import TechnicalIndicators

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=500, freq='1h')
    base_price = 43000

    # Random walk with trend
    price_changes = np.random.randn(500) * 100 + 5
    closes = base_price + np.cumsum(price_changes)

    data = pd.DataFrame({
        'timestamp': dates,
        'open': closes,
        'high': closes + np.random.rand(500) * 50,
        'low': closes - np.random.rand(500) * 50,
        'close': closes,
        'volume': np.random.rand(500) * 1000000
    })

    # Calculate indicators for all periods
    print("Calculating technical indicators...")
    indicators_list = []
    for i in range(50, len(data)):
        subset = data.iloc[:i+1]
        indicators = TechnicalIndicators.calculate_all(
            subset['high'].tolist(),
            subset['low'].tolist(),
            subset['close'].tolist(),
            subset['volume'].tolist()
        )
        indicators_list.append(indicators)

    # Train model
    print("\nTraining ML model...")
    ml_engine = MLEngine()
    metrics = ml_engine.train_model(data.iloc[50:], indicators_list)

    print("\n=== Training Results ===")
    print(f"Training Accuracy: {metrics['train_accuracy']:.4f}")
    print(f"Samples: {metrics['n_samples']}")
    print(f"Features: {metrics['n_features']}")
    print(f"\nLabel Distribution:")
    print(f"  BUY signals: {metrics['label_distribution']['buy']}")
    print(f"  HOLD signals: {metrics['label_distribution']['hold']}")
    print(f"  SELL signals: {metrics['label_distribution']['sell']}")
    print(f"\nTop 5 Features:")
    for feature, importance in metrics['top_features']:
        print(f"  {feature}: {importance:.4f}")

    # Test prediction
    print("\n=== Test Prediction ===")
    last_indicators = indicators_list[-1]
    signal, confidence = ml_engine.predict(data, last_indicators)
    signal_map = {1: 'BUY', 0: 'HOLD', -1: 'SELL'}
    print(f"Signal: {signal_map[signal]}")
    print(f"Confidence: {confidence:.2%}")

    # Save model
    ml_engine.save_model()
    print(f"\nModel saved to models/rf_model.pkl")
