import sys
import os
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

# Add src to path
# Robustly add /app to path since we run inside Docker
sys.path.append("/app")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.feature_engineering.technical_indicators import TechnicalIndicators
from src.models.lstm_model import LSTMModel

def test_features():
    print("Testing Feature Engineering...")
    # Mock DB
    db = MagicMock()
    ti = TechnicalIndicators(db)
    
    # Create Dummy Data
    dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
    df = pd.DataFrame({
        'open': np.random.rand(100) * 100,
        'high': np.random.rand(100) * 105,
        'low': np.random.rand(100) * 95,
        'close': np.random.rand(100) * 100,
        'volume': np.random.randint(1000, 10000, 100),
        'ihsg_close': np.random.rand(100) * 7000, # Mock macro
        'usd_close': np.random.rand(100) * 15000,
        'sentiment_score': np.random.rand(100) # Mock sentiment
    }, index=dates)

    # Test Daily
    df_d = ti.calculate_indicators(df.copy(), interval='1d')
    assert 'relative_strength' in df_d.columns, "relative_strength missing in Daily"
    print("✅ Daily Features OK")

    # Test Hourly
    df_h = ti.calculate_indicators(df.copy(), interval='1h')
    assert 'hour_sin' in df_h.columns, "hour_sin missing in Hourly"
    assert 'sentiment_decay' in df_h.columns, "sentiment_decay missing in Hourly"
    print("✅ Hourly Features OK")
    
    # Test 15m
    df_15 = ti.calculate_indicators(df.copy(), interval='15m')
    assert 'distance_from_vwap' in df_15.columns, "distance_from_vwap missing in 15m"
    print("✅ 15m Features OK")

    # Test 1m
    df_1m = ti.calculate_indicators(df.copy(), interval='1m')
    assert 'momentum_decay' in df_1m.columns, "momentum_decay missing in 1m"
    print("✅ 1m Features OK")

def test_lstm_adaptive():
    print("\nTesting LSTM Adaptive Architecture...")
    
    # Test Slow (1d)
    model_slow = LSTMModel(input_shape=(60, 18), timeframe='1d', units=50)
    # Check config if possible, or just build
    # layer 0 is Input, layer 1 is LSTM
    l1_config = model_slow.model.layers[0].get_config()
    # Note: Keras model layers start from index 0 (if Input is a layer? In Sequential it usually isn't separate if passed to add, but here we used Input layer)
    # Actually explicit Input layer is not counted in layers list usually in old keras, but in new it might.
    # Let's inspect layers.
    
    # layer 0: LSTM
    # layer 1: Dropout
    # layer 2: LSTM
    
    units_l1 = model_slow.model.layers[0].units
    print(f"1d Model Units L1: {units_l1} (Expected 50)")
    assert units_l1 == 50
    
    # Test Fast (1m)
    model_fast = LSTMModel(input_shape=(120, 18), timeframe='1m', units=50)
    units_l1_fast = model_fast.model.layers[0].units
    print(f"1m Model Units L1: {units_l1_fast} (Expected 100)")
    assert units_l1_fast == 100
    
    print("✅ LSTM Adaptive OK")

if __name__ == "__main__":
    try:
        test_features()
        test_lstm_adaptive()
        print("\n🎉 ALL TESTS PASSED")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
