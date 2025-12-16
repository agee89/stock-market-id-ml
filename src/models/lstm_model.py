import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input, BatchNormalization
from tensorflow.keras.optimizers import Adam
import os
import numpy as np
import random
from src.utils.logger import get_logger

logger = get_logger()

class LSTMModel:
    def __init__(self, input_shape, units=50, dropout=0.2, timeframe='1d', seed=42):
        self.input_shape = input_shape
        self.units = units
        self.dropout = dropout
        self.timeframe = timeframe
        self.seed = seed
        self._set_seed()
        self.model = self._build_model()
        
    def _set_seed(self):
        os.environ['PYTHONHASHSEED'] = str(self.seed)
        random.seed(self.seed)
        np.random.seed(self.seed)
        tf.random.set_seed(self.seed)

    def _build_model(self):
        try:
            model = Sequential()
            # Input layer handled by first LSTM layer with input_shape
            model.add(Input(shape=self.input_shape))
            
            # Adaptive Hyperparameters
            is_fast = self.timeframe in ['1m', '15m']
            layer1_units = 100 if is_fast else self.units
            layer2_units = 50 if is_fast else self.units // 2
            dropout_rate = 0.3 if is_fast else self.dropout
            learning_rate = 0.0001 if is_fast else 0.001

            # LSTM Layer 1
            model.add(LSTM(units=layer1_units, return_sequences=True))
            model.add(Dropout(dropout_rate))

            # LSTM Layer 2
            model.add(LSTM(units=layer2_units, return_sequences=False))
            model.add(Dropout(dropout_rate))

            # Output Block
            model.add(Dense(units=25, activation='relu'))
            model.add(BatchNormalization()) # Added for stability
            model.add(Dense(units=1)) # Predicting Close price

            model.compile(optimizer=Adam(learning_rate=learning_rate), loss='mean_squared_error')
            return model
        except Exception as e:
            logger.error(f"Error building model: {e}")
            raise

    def train(self, X_train, y_train, epochs=25, batch_size=32, validation_data=None):
        logger.info(f"Training LSTM model with {len(X_train)} samples")
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=validation_data,
            verbose=1
        )
        return history

    def predict(self, X):
        return self.model.predict(X)

    def save(self, path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            self.model.save(path)
            logger.info(f"Model saved to {path}")
        except Exception as e:
            logger.error(f"Error saving model: {e}")

    @staticmethod
    def load(path):
        try:
            model = load_model(path)
            # Create instance wrapper? Or just return raw model.
            # Returning raw model for now or simple wrapper if needed.
            return model
        except Exception as e:
            logger.error(f"Error loading model from {path}: {e}")
            return None
