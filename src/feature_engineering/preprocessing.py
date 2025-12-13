import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from typing import Tuple, List

class DataPreprocessor:
    def __init__(self, sequence_length: int = 60):
        self.sequence_length = sequence_length
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.feature_columns = []

    def fit_transform(self, df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
        """
        Normalize specific columns in the dataframe.
        """
        self.feature_columns = feature_cols
        scaled_data = self.scaler.fit_transform(df[feature_cols])
        df_scaled = pd.DataFrame(scaled_data, columns=feature_cols, index=df.index)
        
        # Keep other columns if needed, or just return scaled
        return df_scaled

    def create_sequences(self, data: np.ndarray, target: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequences for LSTM training.
        data: (N, n_features)
        target: (N,)
        """
        X, y = [], []
        for i in range(self.sequence_length, len(data)):
            X.append(data[i-self.sequence_length:i])
            y.append(target[i])
        
        return np.array(X), np.array(y)

    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        """Inverse transform scaled data."""
        return self.scaler.inverse_transform(data)
