import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
import os
import numpy as np
import random
from src.utils.logger import get_logger

logger = get_logger()

class LSTMModel:
    def __init__(self, input_shape, units=50, seed=42):
        self.input_shape = input_shape
        self.units = units
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
            
            # LSTM Layer 1
            model.add(LSTM(units=self.units, return_sequences=True))
            model.add(Dropout(0.2))

            # LSTM Layer 2
            model.add(LSTM(units=self.units, return_sequences=False))
            model.add(Dropout(0.2))

            # Output Layer
            model.add(Dense(units=25))
            model.add(Dense(units=1)) # Predicting Close price or change

            model.compile(optimizer='adam', loss='mean_squared_error')
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
