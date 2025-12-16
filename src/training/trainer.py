import json
import pandas as pd
import numpy as np
from sqlalchemy import text
from src.utils.database import SessionLocal
from src.utils.logger import get_logger
from src.data_collection.stock_collector import StockCollector
from src.feature_engineering.technical_indicators import TechnicalIndicators
from src.feature_engineering.preprocessing import DataPreprocessor
from src.models.lstm_model import LSTMModel
from src.models.xgboost_model import XGBoostModel
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from datetime import datetime, timedelta
import os

logger = get_logger()

from src.utils.config import get_settings
import redis

class ModelTrainer:
    def __init__(self, interval: str = '1d'):
        self.db = SessionLocal()
        self.collector = StockCollector(self.db)
        self.feature_engine = TechnicalIndicators(self.db) 
        self.interval = interval
        
        # Adaptive Sequence Length
        seq_config = {
            '1d': 60,
            '1h': 48,
            '15m': 96,
            '1m': 120
        }
        self.seq_len = seq_config.get(interval, 60)
        self.preprocessor = DataPreprocessor(sequence_length=self.seq_len)
        
        settings = get_settings()
        self.redis = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True)

    # Decorator for status tracking
    def track_status(func):
        def wrapper(self, *args, **kwargs):
            symbol = kwargs.get('symbol', args[0] if args else "Unknown")
            status_key = f"status:{symbol}"
            try:
                self.redis.set(status_key, "Running")
                self.redis.set("status:global", f"Training {symbol}")
                return func(self, *args, **kwargs)
            finally:
                self.redis.set(status_key, "Idle")
                # Only clear global if it was set by this process (simplification: just set to Idle or check)
                # For MVP, just setting to Idle is 'okay' but concurrency issues exist. 
                # Assuming single trainer worker:
                self.redis.set("status:global", "Idle")
        return wrapper

    @track_status
    def run_pipeline(self, symbol="BBCA.JK"):
        logger.info(f"Starting pipeline for {symbol} ({self.interval})")
        
        # 1. Collect Data
        # 1. Collect Data
        # Dynamic history limits based on YFinance constraints
        if self.interval == '1m':
            history_days = 7
        elif self.interval in ['5m', '15m']:
            history_days = 59
        elif self.interval == '1h':
            history_days = 720
        else:
            history_days = 3650
            
        self.collector.fetch_history(symbol, days=history_days, interval=self.interval)

        # Macro Data Handling
        MACRO_SYMBOLS = ['^JKSE', 'IDR=X']
        if symbol in MACRO_SYMBOLS:
            logger.info(f"Skipping training for Macro symbol {symbol} (Data collected only)")
            return

        # Ensure Macro Data is available
        for mac in MACRO_SYMBOLS:
            self.collector.fetch_history(mac, days=history_days, interval=self.interval)

        # Get stock_id
        stock_id = self.db.execute(text("SELECT id FROM stocks WHERE symbol=:s"), {"s": symbol}).fetchone()[0]
        
        # 3. Load Data for Training
        # We perform SQL join here to get main stock data
        # DB has 'timestamp' column, not 'date'
        query = text("""
            SELECT timestamp as date, open, high, low, close, volume 
            FROM stock_prices 
            WHERE stock_id = :stock_id 
            AND interval = :interval
            ORDER BY timestamp ASC
        """)
        data = self.db.execute(query, {"stock_id": stock_id, "interval": self.interval}).fetchall()
        
        if not data:
            logger.error(f"No training data available for {symbol}")
            return

        df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df.set_index('date', inplace=True)
        # Ensure index is datetime
        df.index = pd.to_datetime(df.index)
        df.dropna(inplace=True)
        # Force float to avoid Decimal issues
        df = df.astype(float)

        # --- A. FEATURE ENGINEERING: NEWS SENTIMENT ---
        try:
            sent_query = text("""
                SELECT date, sentiment_score 
                FROM news_sentiment 
                WHERE stock_id = :stock_id
            """)
            sent_res = self.db.execute(sent_query, {"stock_id": stock_id}).fetchall()
            if sent_res:
                sent_df = pd.DataFrame(sent_res, columns=['date', 'sentiment_score'])
                sent_df['date'] = pd.to_datetime(sent_df['date'])
                sent_df = sent_df.groupby('date')['sentiment_score'].mean().reset_index()
                sent_df.set_index('date', inplace=True)
                df = pd.merge(df, sent_df, left_index=True, right_index=True, how='left')
                df['sentiment_score'].fillna(0, inplace=True)
            else:
                df['sentiment_score'] = 0.0
        except Exception as e:
            logger.error(f"Failed to fetch sentiment: {e}")
            df['sentiment_score'] = 0.0

        # --- B. FEATURE ENGINEERING: MACRO CONTEXT ---
        try:
            # Fetch IHSG
            ihsg_id_res = self.db.execute(text("SELECT id FROM stocks WHERE symbol='^JKSE'")).fetchone()
            if ihsg_id_res:
                # Use timestamp column
                ihsg_query = text("""
                    SELECT timestamp as date, close as ihsg_close FROM stock_prices 
                    WHERE stock_id = :sid AND interval = :interval
                """)
                ihsg_data = self.db.execute(ihsg_query, {"sid": ihsg_id_res[0], "interval": self.interval}).fetchall()
                if ihsg_data:
                    ihsg_df = pd.DataFrame(ihsg_data, columns=['date', 'ihsg_close'])
                    ihsg_df['date'] = pd.to_datetime(ihsg_df['date'])
                    ihsg_df.set_index('date', inplace=True)
                    # Merge
                    df = pd.merge(df, ihsg_df, left_index=True, right_index=True, how='left')
                    df['ihsg_close'] = df['ihsg_close'].fillna(method='ffill')

            # Fetch USD
            usd_id_res = self.db.execute(text("SELECT id FROM stocks WHERE symbol='IDR=X'")).fetchone()
            if usd_id_res:
                usd_query = text("""
                    SELECT timestamp as date, close as usd_close FROM stock_prices 
                    WHERE stock_id = :sid AND interval = :interval
                """)
                usd_data = self.db.execute(usd_query, {"sid": usd_id_res[0], "interval": self.interval}).fetchall()
                if usd_data:
                    usd_df = pd.DataFrame(usd_data, columns=['date', 'usd_close'])
                    usd_df['date'] = pd.to_datetime(usd_df['date'])
                    usd_df.set_index('date', inplace=True)
                    # Merge
                    df = pd.merge(df, usd_df, left_index=True, right_index=True, how='left')
                    df['usd_close'] = df['usd_close'].fillna(method='ffill')

            # Fetch DJI (Dow Jones)
            dji_id_res = self.db.execute(text("SELECT id FROM stocks WHERE symbol='^DJI'")).fetchone()
            if dji_id_res:
                dji_query = text("""
                    SELECT timestamp as date, close as dji_close FROM stock_prices 
                    WHERE stock_id = :sid AND interval = :interval
                """)
                dji_data = self.db.execute(dji_query, {"sid": dji_id_res[0], "interval": self.interval}).fetchall()
                if dji_data:
                    dji_df = pd.DataFrame(dji_data, columns=['date', 'dji_close'])
                    dji_df['date'] = pd.to_datetime(dji_df['date'])
                    dji_df.set_index('date', inplace=True)
                    df = pd.merge(df, dji_df, left_index=True, right_index=True, how='left')
                    df['dji_close'] = df['dji_close'].fillna(method='ffill')

            # Fetch IXIC (Nasdaq)
            ixic_id_res = self.db.execute(text("SELECT id FROM stocks WHERE symbol='^IXIC'")).fetchone()
            if ixic_id_res:
                ixic_query = text("""
                    SELECT timestamp as date, close as ixic_close FROM stock_prices 
                    WHERE stock_id = :sid AND interval = :interval
                """)
                ixic_data = self.db.execute(ixic_query, {"sid": ixic_id_res[0], "interval": self.interval}).fetchall()
                if ixic_data:
                    ixic_df = pd.DataFrame(ixic_data, columns=['date', 'ixic_close'])
                    ixic_df['date'] = pd.to_datetime(ixic_df['date'])
                    ixic_df.set_index('date', inplace=True)
                    df = pd.merge(df, ixic_df, left_index=True, right_index=True, how='left')
                    df['ixic_close'] = df['ixic_close'].fillna(method='ffill')
            
            # Fill remaining macro NaNs with 0 or mean
            df.fillna(method='ffill', inplace=True)
            df.fillna(method='bfill', inplace=True)
            
            # CRITICAL: Re-cast to float because merged macro columns might be Decimal
            df = df.astype(float)
            if 'ihsg_close' in df.columns: df['ihsg_close'].fillna(method='bfill', inplace=True)
            if 'usd_close' in df.columns: df['usd_close'].fillna(method='bfill', inplace=True)
            if 'dji_close' in df.columns: df['dji_close'].fillna(method='bfill', inplace=True)
            if 'ixic_close' in df.columns: df['ixic_close'].fillna(method='bfill', inplace=True)

        except Exception as e:
             logger.error(f"Failed to merge macro features: {e}")

        # --- C. FEATURE ENGINEERING: TECHNICAL INDICATORS ---
        try:
            # Pass interval to calculation
            df = self.feature_engine.calculate_indicators(df, interval=self.interval)
        except Exception as e:
            logger.error(f"Failed to calculate indicators: {e}")

        # Define Expanded Features List
        features = ['close', 'volume', 'open', 'high', 'low', 
                   'rsi_14', 'macd', 'macd_signal', 
                   'bb_upper', 'bb_lower', 
                   'sentiment_score']
        
        # Add Macro if available
        if 'ihsg_close' in df.columns: features.append('ihsg_close')
        if 'usd_close' in df.columns: features.append('usd_close')
        if 'dji_close' in df.columns: features.append('dji_close')
        if 'ixic_close' in df.columns: features.append('ixic_close')

        # Add Timeframe-Specific Features
        if self.interval == '1d':
            features.extend(['relative_strength', 'volatility_regime', 'adx', 'volume_ma_ratio', 'ihsg_lag1', 'usd_idr_lag1'])
        elif self.interval == '1h':
            features.extend(['hour_sin', 'hour_cos', 'ema_5', 'ema_13', 'microtrend', 'sentiment_decay'])
        elif self.interval == '15m':
            features.extend(['vwap', 'distance_from_vwap', 'buy_pressure', 'sell_pressure', 'order_flow', 'high_low_ratio'])
        elif self.interval == '1m':
            features.extend(['tick_direction', 'momentum_1min', 'momentum_decay', 'realized_vol', 'volume_spike'])
        
        # Filter only existing columns (safety)
        features = [f for f in features if f in df.columns]

        # Create Target: Next Day Close (Shift -1)
        df['target'] = df['close'].shift(-1)
        
        # Capture the latest data for Future Prediction BEFORE dropping NaNs available for training
        # This ensures we can predict the 'next' step for the live/pending candle.
        future_X_df = None
        if len(df) >= self.preprocessor.sequence_length:
            future_X_df = df[features].iloc[-self.preprocessor.sequence_length:].copy()
            
        # Clean NaNs created by indicators (e.g. SMA-200 needs 200 rows)
        df.dropna(inplace=True)


        
        # 4. Preprocessing
        scaled_df = self.preprocessor.fit_transform(df, features)
        
        # Save Scaler for Inference
        scaler_path = f"data/models/{symbol}_{self.interval}_scaler.joblib"
        self.preprocessor.save(scaler_path)
        logger.info(f"Scaler saved to {scaler_path}")
        
        # Target scaler
        from sklearn.preprocessing import MinMaxScaler
        target_scaler = MinMaxScaler()
        y_scaled = target_scaler.fit_transform(df[['target']])
        
        X, y = self.preprocessor.create_sequences(scaled_df[features].values, y_scaled.flatten())

        # Split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        # 5. Train LSTM
        if len(X_train) > 0:
            lstm = LSTMModel(input_shape=(X_train.shape[1], X_train.shape[2]), timeframe=self.interval)
            lstm.train(X_train, y_train, epochs=10) # Increased epochs slightly
            
            # Evaluate
            preds = lstm.predict(X_test)
            
            # Inverse Transform to get real prices for logging
            # We need the scalers used.
            # Preprocessor fits on 'close' (index 0). 
            # We used a separate target_scaler for y.
            preds_unscaled = target_scaler.inverse_transform(preds)
            y_test_unscaled = target_scaler.inverse_transform(y_test.reshape(-1, 1))

            mse = mean_squared_error(y_test, preds)
            rmse = np.sqrt(mse)
            mae = np.mean(np.abs(y_test - preds))
            
            logger.info(f"LSTM Results - MSE: {mse}, RMSE: {rmse}, MAE: {mae}")
            
            # Save Model
            lstm.save(f"data/models/{symbol}_{self.interval}_lstm.h5")
            
            # --- LOGGING HISTORY (Backtest) ---
            try:
                # Recover dates for test set & previous close prices
                # X_test indices start at: len(X_train)
                # In df, X[0] is at index sequence_length (since it uses 0..59 to predict 60)
                # So X_train ends at train_size. X_test starts at train_size.
                # The "current time" T for X_test[i] is df.index[sequence_length + train_size + i]
                # The "target time" T+1 is conceptually the next index.
                
                    train_size = len(X_train)
                    start_idx = self.preprocessor.sequence_length + train_size
                    
                    logger.info(f"DEBUG: len(df)={len(df)}, len(X_train)={train_size}, seq_len={self.preprocessor.sequence_length}, start_idx={start_idx}")
                    
                    # Check bounds
                    if start_idx < len(df):
                        test_dates = df.index[start_idx : start_idx + len(X_test)]
                        logger.info(f"DEBUG: len(test_dates)={len(test_dates)}, len(preds)={len(preds_unscaled)}")
                        
                        # We need "Current Close" (at time T) to determine UP/DOWN direction
                        # We can fetch it from df based on test_dates
                        current_closes = df.loc[test_dates]['close'].values
                    
                    # Prepare batch insert
                    for i in range(len(preds_unscaled)):
                        if i >= len(test_dates): break
                        
                        pred_price = float(preds_unscaled[i][0])
                        actual_price = float(y_test_unscaled[i][0])
                        current_close = float(current_closes[i])
                        t_date = test_dates[i].to_pydatetime() # Prediction Date
                        
                        # Determine Directions
                        pred_dir = "UP" if pred_price > current_close else "DOWN"
                        actual_dir = "UP" if actual_price > current_close else "DOWN"
                        is_win = (pred_dir == actual_dir)
                        
                        # Insert Prediction
                        # We need target_date. For now use t_date (same day prediction) or next day?
                        # Schema has target_date as DATE.
                        
                        # For intraday, target_date might be same day.
                        
                        # Insert into predictions table
                        res = self.db.execute(text("""
                            INSERT INTO predictions (stock_id, prediction_date, target_date, predicted_direction, predicted_change_pct, predicted_price, confidence, model_version, interval, created_at)
                            VALUES (:sid, :pdate, :tdate, :pdir, :pct, :pprice, :conf, :ver, :intv, :cat)
                            ON CONFLICT (stock_id, prediction_date, interval) DO UPDATE 
                            SET predicted_price = EXCLUDED.predicted_price -- Dummy update to return ID
                            RETURNING id
                        """), {
                            "sid": stock_id,
                            "pdate": t_date,
                            "tdate": t_date.date(), # Approximate target date
                            "pdir": pred_dir,
                            "pct": (pred_price - current_close) / current_close * 100,
                            "pprice": pred_price,
                            "conf": 0.8, # Mock confidence for now
                            "ver": f"LSTM_v1",
                            "intv": self.interval,
                            "cat": t_date
                        })
                        
                        pred_id = res.fetchone()[0]
                        
                        # Insert Result (Upsert)
                        self.db.execute(text("""
                            INSERT INTO prediction_results (prediction_id, actual_direction, actual_change_pct, actual_price, is_correct, error_pct, evaluated_at)
                            VALUES (:pid, :adir, :apct, :aprice, :correct, :err, NOW())
                            ON CONFLICT (prediction_id) DO UPDATE
                            SET is_correct = EXCLUDED.is_correct, error_pct = EXCLUDED.error_pct, actual_price = EXCLUDED.actual_price
                        """), {
                            "pid": pred_id,
                            "adir": actual_dir,
                            "apct": (actual_price - current_close) / current_close * 100,
                            "aprice": actual_price,
                            "correct": is_win,
                            "err": abs(pred_price - actual_price) / actual_price * 100
                        })
                    
                    self.db.commit()

                    # --- LOGGING PERFORMANCE & METADATA ---
                    # Calculate aggregate metrics for this run
                    total_preds = len(preds_unscaled)
                    correct_preds = sum(1 for i in range(total_preds) 
                                      if (preds_unscaled[i][0] > current_closes[i] and y_test_unscaled[i][0] > current_closes[i]) or
                                         (preds_unscaled[i][0] <= current_closes[i] and y_test_unscaled[i][0] <= current_closes[i]))
                    accuracy = correct_preds / total_preds if total_preds > 0 else 0
                    
                    # Calculate REAL Price Error Metrics (not scaled)
                    y_test_real = y_test_unscaled[:, 0]
                    preds_real = preds_unscaled[:, 0]
                    mae_real = np.mean(np.abs(y_test_real - preds_real))
                    mse_real = mean_squared_error(y_test_real, preds_real)
                    rmse_real = np.sqrt(mse_real)

                    # Insert into model_performance
                    self.db.execute(text("""
                        INSERT INTO model_performance 
                        (model_name, model_version, accuracy, mae, rmse, training_date, total_predictions, correct_predictions, timeframe)
                        VALUES (:name, :ver, :acc, :mae, :rmse, NOW(), :total, :correct, :tf)
                    """), {
                        "name": f"{symbol}_LSTM",
                        "ver": "v1", # TODO: dynamic versioning
                        "acc": accuracy,
                        "mae": float(mae_real),
                        "rmse": float(rmse_real),
                        "total": total_preds,
                        "correct": correct_preds,
                        "tf": self.interval
                    })
                    
                    # Insert into model_metadata
                    
                    # Prevent duplicates: Delete old metadata for this version/model
                    self.db.execute(text("DELETE FROM model_metadata WHERE model_name=:name AND version=:ver"), {
                        "name": f"{symbol}_LSTM",
                        "ver": "v1"
                    })
                    
                    self.db.execute(text("""
                        INSERT INTO model_metadata
                        (model_name, version, training_samples, features_used, is_active)
                        VALUES (:name, :ver, :samples, :feats, :active)
                    """), {
                        "name": f"{symbol}_LSTM",
                        "ver": "v1",
                        "samples": len(X_train),
                        "feats": json.dumps(features),
                        "active": True
                    })
                    self.db.commit()
                    logger.info(f"LSTM Model performance & metadata saved. Accuracy: {accuracy:.2f}")

            except Exception as e:
                logger.error(f"Error logging history: {e}")
                self.db.rollback()

            # Save metrics to DB
            # (Duplicate block removed, logic merged above)

        # 6. Train XGBoost
        # Flatten for XGBoost: (N, T*F) or just use latest step features?
        # XGBoost doesn't take 3D input. Flatten:
        X_train_flat = X_train.reshape(X_train.shape[0], -1)
        X_test_flat = X_test.reshape(X_test.shape[0], -1)
        
        xgb = XGBoostModel()
        xgb.train(X_train_flat, y_train)
        preds_xgb = xgb.predict(X_test_flat)
        mse_xgb = mean_squared_error(y_test, preds_xgb)
        rmse_xgb = np.sqrt(mse_xgb)
        mae_xgb = np.mean(np.abs(y_test - preds_xgb))
        
        logger.info(f"XGBoost Results - MSE: {mse_xgb}, RMSE: {rmse_xgb}, MAE: {mae_xgb}")
        
        xgb.save(f"data/models/{symbol}_{self.interval}_xgb.joblib")
        
        # Calculate Real Price Metrics (Unscale)
        # We need to reconstruct the full shape (N, features) to use inverse_transform
        # y_test and preds_xgb are 1D arrays of Scaled Close Price.
        # Scaler expects (N, 13) or however many features.
        # We can cheat by creating a dummy array with 0s for other features.
        
        num_features = X_train.shape[2] # 3D shape (N, T, F)
        
        # Helper to unscale 1D array
        def unscale_array(target_array):
            dummy = np.zeros((len(target_array), num_features))
            dummy[:, 0] = target_array # Assuming 'close' is at index 0
            return self.preprocessor.scaler.inverse_transform(dummy)[:, 0]

        try:
            preds_xgb_real = unscale_array(preds_xgb)
            y_test_real_xgb = unscale_array(y_test)
            
            mae_xgb_real = np.mean(np.abs(y_test_real_xgb - preds_xgb_real))
            mse_xgb_real = mean_squared_error(y_test_real_xgb, preds_xgb_real)
            rmse_xgb_real = np.sqrt(mse_xgb_real)
        except Exception as e:
            logger.error(f"Failed to unscale XGBoost results: {e}")
            mae_xgb_real = mae_xgb # Fallback to scaled
            rmse_xgb_real = rmse_xgb

        logger.info(f"XGBoost Real Results - RMSE: {rmse_xgb_real:,.2f}, MAE: {mae_xgb_real:,.2f}")

        # Save metrics to DB
        try:
            self.db.execute(text("""
                INSERT INTO model_performance (model_name, model_version, accuracy, mae, rmse, timeframe, training_date, total_predictions, correct_predictions)
                VALUES (:name, :ver, :acc, :mae, :rmse, :tf, NOW(), 0, 0)
            """), {
                "name": f"{symbol}_XGBoost",
                "ver": "v1",
                "acc": 0.0, # XGBoost accuracy needs similar logic to LSTM if desired
                "mae": float(mae_xgb_real),
                "rmse": float(rmse_xgb_real),
                "tf": self.interval
            })
            
            # Insert into model_metadata for XGBoost too!
            self.db.execute(text("""
                INSERT INTO model_metadata
                (model_name, version, training_samples, features_used, is_active)
                VALUES (:name, :ver, :samples, :feats, :active)
            """), {
                "name": f"{symbol}_XGBoost",
                "ver": "v1",
                "samples": len(X_train_flat),
                "feats": json.dumps(features),
                "active": True
            })
            
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save XGBoost metrics: {e}")

        # --- 7. FUTURE PREDICTION (For Latest Candle) ---
        # To ensure DB History matches the newly trained model for the *current* pending signal.
        # Otherwise, the DB retains old 'v_live' predictions while Dashboard calc new ones.
        try:
            # We need the LAST sequence from the entire dataset (captured before dropna)
            # scaled using the FITTED scaler.
            
            if future_X_df is not None and not future_X_df.empty:
                # Scale using the scaler fitted on training data
                future_X_scaled = self.preprocessor.scaler.transform(future_X_df)
                last_sequence = future_X_scaled.reshape(1, self.preprocessor.sequence_length, len(features))
                
                # Predict
                future_pred_scaled = lstm.predict(last_sequence)
                future_pred_price = target_scaler.inverse_transform(future_pred_scaled)[0][0]
                
                # Get Current Close (Last row of future_X_df)
                current_close_price = future_X_df['close'].iloc[-1]
                current_date = future_X_df.index[-1].to_pydatetime()
                
                # Direction
                f_dir = "UP" if future_pred_price > current_close_price else "DOWN"
                f_pct = (future_pred_price - current_close_price) / current_close_price * 100
                
                logger.info(f"Future Prediction for {current_date}: {future_pred_price:.2f} ({f_dir})")
                
                # Insert Future Prediction (Overwrite existing)
                self.db.execute(text("""
                    INSERT INTO predictions (stock_id, prediction_date, target_date, predicted_direction, predicted_change_pct, predicted_price, confidence, model_version, interval, created_at)
                    VALUES (:sid, :pdate, :tdate, :pdir, :pct, :pprice, :conf, :ver, :intv, :cat)
                    ON CONFLICT (stock_id, prediction_date, interval) DO UPDATE 
                    SET 
                        predicted_price = EXCLUDED.predicted_price,
                        predicted_direction = EXCLUDED.predicted_direction,
                        predicted_change_pct = EXCLUDED.predicted_change_pct,
                        model_version = EXCLUDED.model_version,
                        created_at = EXCLUDED.created_at
                """), {
                    "sid": stock_id,
                    "pdate": current_date,
                    "tdate": (current_date + timedelta(days=1)).date(), # Approx target (FIXME for intraday)
                    "pdir": f_dir,
                    "pct": f_pct,
                    "pprice": float(future_pred_price),
                    "conf": 0.8,
                    "ver": f"LSTM_v1",
                    "intv": self.interval,
                    "cat": datetime.now()
                })
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to generate future prediction: {e}")

if __name__ == "__main__":
    import time
    import argparse
    import sys

    # Parse Arguments
    parser = argparse.ArgumentParser(description="Stock Market ID AI Trainer")
    parser.add_argument("--all", action="store_true", help="Run once for all stocks and exit")
    parser.add_argument("--interval", type=str, default="1d", help="Timeframe (1d, 1h, 15m, 1m)")
    args = parser.parse_args()

    # Configuration
    if args.interval:
        intervals = [args.interval]
    else:
        intervals = ['1d', '1h', '15m', '1m']

    logger.info(f"Starting Trainer... Mode: {'ONE-OFF' if args.all else 'CONTINUOUS'}, Intervals: {intervals}")

    def get_all_symbols():
        db = SessionLocal()
        try:
            res = db.execute(text("SELECT symbol FROM stocks"))
            syms = [row[0] for row in res.fetchall()]
            # Filter bad symbols if any
            syms = [s for s in syms if s.upper() not in ['^JKSE', 'IDR=X', 'USDIDR=X', '^DJI', '^IXIC', 'ALL', 'all']] 
            return syms
        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            return ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK", "UNVR.JK"]
        finally:
            db.close()

    if args.all:
        # --- ONE-OFF MODE (Mass Retrain) ---
        symbols = get_all_symbols()
        logger.info(f"Found {len(symbols)} stocks to train.")
        
        for symbol in symbols:
            for interval in intervals:
                try:
                    logger.info(f"--- Training {symbol} [{interval}] ---")
                    
                    # Hardcoded history settings matching previous logic
                    # Ideally this logic matches fetch_history defaults
                    
                    trainer = ModelTrainer(interval=interval)
                    trainer.run_pipeline(symbol)
                except Exception as e:
                    logger.error(f"Training failed for {symbol} {interval}: {e}")
        
        logger.info("Mass Retraining Completed Successfully.")
        sys.exit(0)

    else:
        # --- CONTINUOUS MODE (Daemon) ---
        while True:
            try:
                symbols = get_all_symbols()
                
                for symbol in symbols:
                    for interval in intervals:
                        try:
                            logger.info(f"--- Training {symbol} [{interval}] ---")
                            trainer = ModelTrainer(interval=interval)
                            trainer.run_pipeline(symbol)
                        except Exception as e:
                            logger.error(f"Training failed for {symbol} {interval}: {e}")
                            
                logger.info("Cycle completed. Sleeping for 1 hour...")
                time.sleep(3600) 
                
            except KeyboardInterrupt:
                logger.info("Trainer stopped by user.")
                break
            except Exception as e:
                logger.critical(f"Trainer loop crashed: {e}")
                time.sleep(60)
