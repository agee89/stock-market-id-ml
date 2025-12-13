import xgboost as xgb
import joblib
import os
from src.utils.logger import get_logger

logger = get_logger()

class XGBoostModel:
    def __init__(self, n_estimators=100, learning_rate=0.1, max_depth=5, seed=42):
        self.model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            objective='reg:squarederror',
            random_state=seed
        )

    def train(self, X_train, y_train):
        logger.info(f"Training XGBoost model with {len(X_train)} samples")
        self.model.fit(X_train, y_train)

    def predict(self, X):
        return self.model.predict(X)

    def save(self, path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            joblib.dump(self.model, path)
            logger.info(f"XGBoost model saved to {path}")
        except Exception as e:
            logger.error(f"Error saving XGBoost model: {e}")

    @staticmethod
    def load(path):
        try:
            model = joblib.load(path)
            return model
        except Exception as e:
            logger.error(f"Error loading XGBoost model: {e}")
            return None
