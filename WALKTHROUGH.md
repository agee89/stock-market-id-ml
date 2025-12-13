# Stock Market Prediction System - Walkthrough

## Overview
This project implements a full-stack machine learning system for predicting Indonesian stock market (IDX) prices.

## Components Implemented

### 1. Infrastructure
- directory structure (`src/`, `data/`, `docker/`).
- `docker-compose.yml` defining 5 services:
    - **postgres**: Database for stocks, prices, news, and predictions.
    - **redis**: Caching (prepared for future use).
    - **data_collector**: Fetches data from Yahoo Finance.
    - **ml_trainer**: Trains LSTM/XGBoost models.
    - **api**: Exposes data and predictions via REST.
    - **dashboard**: Streamlit UI for interaction.
- `init_db.sql`: Database schema with tables for stocks, indicators, sentiment, predictions.

### 2. Core Modules
- **Data Collection**: `StockCollector` fetches history from Yahoo Finance.
- **Feature Engineering**: `TechnicalIndicators` calculates RSI, MACD, BB, SMA/EMA using `ta`.
- **Preprocessing**: `DataPreprocessor` scales data and creates sequences for LSTM.
- **Models**:
    - `LSTMModel`: Deep learning model for sequence prediction (TensorFlow).
    - `XGBoostModel`: Gradient boosting for regression.
- **Training**: `ModelTrainer` orchestrates the pipeline.

### 3. Application
- **API**: FastAPI service at `http://localhost:8005`.
- **Dashboard**: Streamlit app at `http://localhost:8505`.

## How to Run

1.  **Build and Start**:
    ```bash
    docker-compose up --build -d
    ```
    *Note: The first build may take 10-15 minutes due to large ML dependencies.*

2.  **Access Dashboard**:
    Open [http://localhost:8505](http://localhost:8505) in your browser.

3.  **Check API Health**:
    [http://localhost:8005/health](http://localhost:8005/health)

4.  **Database Inspection**:
    Connect to `localhost:5435` (User: `stockml`, Pass: `your_secure_password_here`, DB: `stock_ml`).

## Automated Workflows
- The `data_collector` service automatically fetches data on startup.
- The `ml_trainer` service runs the training pipeline on startup.
- You can trigger retraining manually from the Dashboard.
