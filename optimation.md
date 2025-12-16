## 📊 **1. OPTIMASI FEATURE ENGINEERING (Per Timeframe)**

### A. Timeframe 1 Hari (Daily)
**Karakteristik**: Noise rendah, tren kuat, pengaruh fundamental besar

**Perbaikan Feature:**
```python
# Tambahkan ke feature_engineering/technical.py

def calculate_daily_features(df):
    # 1. Relative Strength vs Market
    df['relative_strength'] = (df['close'].pct_change(20) - 
                                df['ihsg'].pct_change(20))
    
    # 2. Volatility Regime Detection
    df['volatility_regime'] = df['close'].rolling(20).std() / df['close'].rolling(60).std()
    
    # 3. Trend Strength (ADX)
    df['adx'] = calculate_adx(df, period=14)
    
    # 4. Volume Profile
    df['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(30).mean()
    
    # 5. Macro Correlation Lag
    df['ihsg_lag1'] = df['ihsg'].shift(1)
    df['usd_idr_lag1'] = df['usd_idr'].shift(1)
    
    return df
```

**Why it works**: Daily trading sangat dipengaruhi sentimen institusi & makro. Feature tambahan ini menangkap "hidden correlation" yang LSTM butuhkan.

---

### B. Timeframe 1 Jam (Hourly)
**Karakteristik**: Noise sedang, sensitif terhadap breaking news

**Perbaikan Feature:**
```python
def calculate_hourly_features(df):
    # 1. Intraday Momentum
    df['morning_close'] = df['close'].where(df.index.hour == 11, np.nan).ffill()
    df['afternoon_bias'] = (df['close'] - df['morning_close']) / df['morning_close']
    
    # 2. Time-Based Features
    df['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
    
    # 3. Microtrend Detection (Fast EMA)
    df['ema_5'] = df['close'].ewm(span=5).mean()
    df['ema_13'] = df['close'].ewm(span=13).mean()
    df['microtrend'] = np.where(df['ema_5'] > df['ema_13'], 1, -1)
    
    # 4. News Impact Window
    df['sentiment_decay'] = df['sentiment_score'] * np.exp(-0.5 * df.index.hour)
    
    return df
```

**Why it works**: Hourly sangat dipengaruhi pola jam bursa (morning surge, lunch dip, closing rally).

---

### C. Timeframe 15 Menit
**Karakteristik**: Noise tinggi, butuh filter kuat

**Perbaikan Feature:**
```python
def calculate_15min_features(df):
    # 1. Scalping Indicators
    df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    df['distance_from_vwap'] = (df['close'] - df['vwap']) / df['vwap'] * 100
    
    # 2. Order Flow Proxy
    df['buy_pressure'] = np.where(df['close'] > df['open'], df['volume'], 0)
    df['sell_pressure'] = np.where(df['close'] < df['open'], df['volume'], 0)
    df['order_flow'] = (df['buy_pressure'].rolling(4).sum() - 
                        df['sell_pressure'].rolling(4).sum())
    
    # 3. Extreme Detection
    df['high_low_ratio'] = (df['high'] - df['low']) / df['close']
    
    # 4. Microstructure Noise Filter (Kalman-like)
    df['smooth_close'] = df['close'].ewm(alpha=0.3).mean()
    
    return df
```

**Why it works**: 15m membutuhkan "order book simulation" karena bid-ask spread & market maker behavior dominan.

---

### D. Timeframe 1 Menit (Ultra-Fast)
**Karakteristik**: Noise ekstrem, butuh regime switching

**Perbaikan Feature:**
```python
def calculate_1min_features(df):
    # 1. Tick Direction
    df['tick_direction'] = np.sign(df['close'].diff())
    df['consecutive_ticks'] = (df['tick_direction'] != 
                                df['tick_direction'].shift()).cumsum()
    
    # 2. Momentum Decay
    df['momentum_1min'] = df['close'].diff()
    df['momentum_decay'] = df['momentum_1min'].ewm(alpha=0.1).mean()
    
    # 3. Volatility Clustering
    df['realized_vol'] = df['close'].pct_change().rolling(5).std()
    
    # 4. Quote Stuffing Detection
    df['volume_spike'] = df['volume'] / df['volume'].rolling(10).median()
    
    return df
```

**Why it works**: 1m adalah "high-frequency territory" — butuh deteksi manipulasi & false breakout.

---

## 🧠 **2. OPTIMASI ARSITEKTUR MODEL**

### A. LSTM Improvements

**Problem Current**: LSTM Anda pakai 60 steps — ini cocok untuk Daily, tapi terlalu panjang untuk 1m/15m.

**Solution**: Adaptive Sequence Length
```python
# training/lstm_trainer.py

SEQUENCE_LENGTH_CONFIG = {
    '1d': 60,   # 60 hari
    '1h': 48,   # 48 jam (2 hari bursa)
    '15m': 96,  # 24 jam bursa
    '1m': 120   # 2 jam
}

def build_adaptive_lstm(timeframe, n_features):
    seq_len = SEQUENCE_LENGTH_CONFIG[timeframe]
    
    model = Sequential([
        LSTM(units=100 if timeframe in ['1m', '15m'] else 50,
             return_sequences=True,
             input_shape=(seq_len, n_features)),
        Dropout(0.3),  # Naikkan dropout untuk fast timeframe
        
        LSTM(units=50 if timeframe in ['1m', '15m'] else 25),
        Dropout(0.3),
        
        Dense(25, activation='relu'),
        BatchNormalization(),  # Tambahkan ini
        
        Dense(1)
    ])
    
    # Adaptive Learning Rate
    lr = 0.0001 if timeframe in ['1m', '15m'] else 0.001
    model.compile(optimizer=Adam(learning_rate=lr), loss='mse')
    
    return model
```

---

### B. Ensemble Strategy Upgrade

**Current Problem**: XGBoost hanya "shadow model" — seharusnya dikombinasi!

**Solution**: Weighted Ensemble Voting
```python
# models/ensemble.py

def predict_ensemble(lstm_model, xgb_model, X, timeframe):
    # Get predictions
    lstm_pred = lstm_model.predict(X)
    xgb_pred = xgb_model.predict(X.reshape(X.shape[0], -1))
    
    # Adaptive Weighting (Fast timeframe = lebih percaya XGBoost)
    if timeframe in ['1m', '15m']:
        weight_lstm = 0.4
        weight_xgb = 0.6
    else:  # 1h, 1d
        weight_lstm = 0.7
        weight_xgb = 0.3
    
    final_pred = (weight_lstm * lstm_pred) + (weight_xgb * xgb_pred)
    return final_pred
```

---

## 🎯 **3. TRAINING STRATEGY (Critical!)**

### A. Walk-Forward Validation
**Current Issue**: Anda pakai train-test split biasa — ini overfitting di financial data!

**Solution**: Expanding Window
```python
# training/validation.py

def walk_forward_training(df, timeframe):
    results = []
    
    # Initial training: 80% data
    train_size = int(len(df) * 0.8)
    
    for i in range(train_size, len(df) - 60, 10):  # Step 10 candles
        # Train on expanding window
        train_data = df[:i]
        test_data = df[i:i+10]
        
        # Train model
        model = train_lstm(train_data)
        
        # Predict next period
        pred = model.predict(test_data)
        
        results.append({
            'actual': test_data['close'].values,
            'predicted': pred,
            'date': test_data.index
        })
    
    return calculate_metrics(results)
```

---

### B. Class Imbalance Handling
**Problem**: Pasar sering sideways (60% waktu) → model jadi "konservatif"

**Solution**: SMOTE + Class Weights
```python
from imblearn.over_sampling import SMOTE

def prepare_classification_data(X, y, threshold=0.01):
    # Convert regression to classification
    y_direction = np.where(y > threshold, 1,   # UP
                           np.where(y < -threshold, -1,  # DOWN
                                    0))  # SIDEWAYS
    
    # Filter out sideways (optional)
    mask = y_direction != 0
    X_filtered = X[mask]
    y_filtered = y_direction[mask]
    
    # Oversample minority class
    smote = SMOTE(random_state=42)
    X_resampled, y_resampled = smote.fit_resample(
        X_filtered.reshape(X_filtered.shape[0], -1),
        y_filtered
    )
    
    return X_resampled, y_resampled
```

---

## 📈 **4. SIGNAL GENERATION (Execution Logic)**

### A. Confidence Threshold
**Problem**: Sistem Anda eksekusi semua sinyal → false positive tinggi

**Solution**: Dynamic Confidence Filter
```python
# api/prediction.py

def generate_signal_with_confidence(pred, current_price, features):
    # Calculate confidence score
    volatility = features['atr'] / current_price
    trend_strength = abs(features['macd'] - features['macd_signal'])
    volume_confirmation = features['volume_ma_ratio']
    
    confidence = (
        (1 - volatility) * 0.4 +  # Low volatility = high confidence
        trend_strength * 0.3 +
        volume_confirmation * 0.3
    )
    
    # Threshold by timeframe
    CONFIDENCE_THRESHOLD = {
        '1m': 0.75,   # Strict
        '15m': 0.70,
        '1h': 0.65,
        '1d': 0.60    # Lenient
    }
    
    if confidence < CONFIDENCE_THRESHOLD[timeframe]:
        return "WAIT"  # No signal
    
    # Generate directional signal
    if pred > current_price * 1.005:  # 0.5% threshold
        return "BUY", confidence
    elif pred < current_price * 0.995:
        return "SELL", confidence
    else:
        return "HOLD", confidence
```

---

### B. Multi-Timeframe Confirmation
**Problem**: 1m bisa bullish tapi 1h bearish → conflict

**Solution**: Hierarchical Voting
```python
def multi_timeframe_decision(signals_dict):
    """
    signals_dict = {
        '1d': ('BUY', 0.85),
        '1h': ('BUY', 0.70),
        '15m': ('SELL', 0.65),
        '1m': ('BUY', 0.80)
    }
    """
    # Weight by timeframe
    weights = {'1d': 0.4, '1h': 0.3, '15m': 0.2, '1m': 0.1}
    
    score = 0
    for tf, (signal, conf) in signals_dict.items():
        direction = 1 if signal == 'BUY' else (-1 if signal == 'SELL' else 0)
        score += direction * conf * weights[tf]
    
    # Final decision
    if score > 0.3:
        return "STRONG_BUY"
    elif score > 0.1:
        return "BUY"
    elif score < -0.3:
        return "STRONG_SELL"
    elif score < -0.1:
        return "SELL"
    else:
        return "NEUTRAL"
```

---

## 🔧 **5. HYPERPARAMETER TUNING (Automated)**

### A. Optuna Integration
```python
# training/hyperparameter_tuning.py
import optuna

def objective(trial, X_train, y_train, timeframe):
    # Suggest parameters
    units_1 = trial.suggest_int('units_1', 50, 200)
    units_2 = trial.suggest_int('units_2', 25, 100)
    dropout = trial.suggest_float('dropout', 0.1, 0.5)
    lr = trial.suggest_loguniform('lr', 1e-5, 1e-2)
    
    # Build model
    model = Sequential([
        LSTM(units_1, return_sequences=True, 
             input_shape=(X_train.shape[1], X_train.shape[2])),
        Dropout(dropout),
        LSTM(units_2),
        Dropout(dropout),
        Dense(1)
    ])
    
    model.compile(optimizer=Adam(learning_rate=lr), loss='mse')
    
    # Train
    history = model.fit(X_train, y_train, epochs=20, 
                        validation_split=0.2, verbose=0)
    
    # Return validation loss
    return min(history.history['val_loss'])

# Run optimization
study = optuna.create_study(direction='minimize')
study.optimize(lambda trial: objective(trial, X_train, y_train, '1h'), 
               n_trials=50)

print(f"Best parameters: {study.best_params}")
```

---

## 🎓 **6. MONITORING & FEEDBACK LOOP**

### A. Track Prediction Quality
```python
# utils/metrics.py

def calculate_winning_rate(predictions_df):
    """
    predictions_df columns: ['date', 'predicted', 'actual', 'signal']
    """
    # Direction accuracy
    pred_direction = np.sign(predictions_df['predicted'] - 
                             predictions_df['actual'].shift(1))
    actual_direction = np.sign(predictions_df['actual'] - 
                               predictions_df['actual'].shift(1))
    
    direction_correct = (pred_direction == actual_direction).sum()
    win_rate = direction_correct / len(predictions_df) * 100
    
    # Price accuracy (MAPE)
    mape = np.mean(np.abs((predictions_df['actual'] - 
                           predictions_df['predicted']) / 
                          predictions_df['actual'])) * 100
    
    return {
        'win_rate': win_rate,
        'mape': mape,
        'sharpe_ratio': calculate_sharpe(predictions_df)
    }
```

---

## 📋 **IMPLEMENTASI ROADMAP**

### Phase 1 (Week 1-2): Foundation
- [ ] Implementasi **Adaptive Sequence Length**
- [ ] Tambahkan **Feature Engineering** per timeframe
- [ ] Setup **Walk-Forward Validation**

### Phase 2 (Week 3-4): Model Upgrade
- [ ] Integrate **Ensemble Voting** (LSTM + XGBoost)
- [ ] Implementasi **Confidence Threshold**
- [ ] Add **BatchNormalization** ke LSTM

### Phase 3 (Week 5-6): Optimization
- [ ] Run **Optuna Hyperparameter Tuning**
- [ ] Implement **Multi-Timeframe Confirmation**
- [ ] Setup **Class Imbalance Handling**

### Phase 4 (Week 7-8): Monitoring
- [ ] Build **Real-time Win Rate Dashboard**
- [ ] Implement **A/B Testing** (Old vs New Model)
- [ ] Setup **Alert System** untuk anomali

---

## 🎯 **EXPECTED IMPROVEMENTS**

| Timeframe | Current Win Rate | Target Win Rate | Strategy Focus |
|-----------|------------------|-----------------|----------------|
| **1 Hari** | ~55% | **70%+** | Fundamental + Macro |
| **1 Jam** | ~50% | **65%+** | News + Intraday Pattern |
| **15 Menit** | ~48% | **60%+** | VWAP + Order Flow |
| **1 Menit** | ~45% | **58%+** | Momentum + Noise Filter |

---

## ⚠️ **CRITICAL NOTES**

1. **Data Quality > Model Complexity**
   - Pastikan data tidak ada missing values
   - Validasi timestamp alignment antar ticker
   - Handle stock splits & dividends

2. **Overfitting Prevention**
   - JANGAN train terlalu lama (max 50 epochs)
   - Gunakan Early Stopping
   - Monitor validation loss

3. **Slippage & Fees**
   - Prediksi 0.5% profit → real profit mungkin hanya 0.2%
   - Tambahkan trading cost ke backtesting

4. **Market Regime Changes**
   - Model perlu retrain setiap 3-6 bulan
   - Deteksi bull/bear/sideways market
   - Adjust strategy per regime

---

**Kesimpulan**: Winning rate bukan hanya soal model, tapi **Feature Quality + Training Strategy + Execution Logic**. Fokus pada 3 pilar ini dan Anda bisa meningkatkan akurasi 10-20% dalam 2-3 bulan! 🚀