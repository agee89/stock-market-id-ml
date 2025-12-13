# 📈 Indonesian Stock Market Prediction with Machine Learning

## 🎯 Project Overview

Sistem machine learning berbasis Docker untuk memprediksi pergerakan harga saham di Bursa Efek Indonesia (IDX). Sistem ini menggunakan pendekatan continuous learning dengan feedback loop untuk meningkatkan akurasi prediksi secara bertahap.

### Key Features
- ✅ Prediksi arah pergerakan harga (naik/turun)
- ✅ Estimasi persentase perubahan harga
- ✅ Continuous learning dari hasil prediksi
- ✅ Multi-factor analysis (technical, sentiment, market)
- ✅ Containerized dengan Docker
- ✅ Real-time data collection
- ✅ Performance monitoring & metrics

---

## 🏗️ Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Environment                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  Data Collector  │──────▶│  PostgreSQL DB   │            │
│  │  - Yahoo Finance │      │  - Historical    │            │
│  │  - News API      │      │  - Predictions   │            │
│  │  - IDX Data      │      │  - Performance   │            │
│  └──────────────────┘      └──────────────────┘            │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ Feature Engineer │      │   ML Pipeline    │            │
│  │ - Indicators     │──────▶│  - LSTM Model    │            │
│  │ - Sentiment      │      │  - XGBoost       │            │
│  │ - Normalization  │      │  - Ensemble      │            │
│  └──────────────────┘      └──────────────────┘            │
│                                     │                        │
│                                     ▼                        │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  API Service     │◀─────│  Predictor       │            │
│  │  - REST API      │      │  - Inference     │            │
│  │  - WebSocket     │      │  - Evaluation    │            │
│  └──────────────────┘      └──────────────────┘            │
│           │                         │                        │
│           ▼                         ▼                        │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  Web Dashboard   │      │ Retraining Job   │            │
│  │  - Streamlit/    │      │ - Scheduled      │            │
│  │    React         │      │ - Auto-improve   │            │
│  └──────────────────┘      └──────────────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Project

```
stock-ml-predictor/
├── docker-compose.yml
├── .env.example
├── README.md
├── requirements.txt
├── CLAUDE.md
│
├── data/
│   ├── raw/                    # Data mentah
│   ├── processed/              # Data terproses
│   └── models/                 # Saved models
│
├── src/
│   ├── data_collection/
│   │   ├── __init__.py
│   │   ├── stock_collector.py      # Scrape harga saham (Yahoo & Macro)
│   │   └── news_collector.py       # Scrape berita
│   │
│   ├── feature_engineering/
│   │   ├── __init__.py
│   │   ├── technical_indicators.py # RSI, MACD, Bollinger
│   │   ├── sentiment_analysis.py   # NLP untuk berita
│   │   └── preprocessing.py        # Normalisasi, scaling
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── lstm_model.py           # Time series LSTM
│   │   └── xgboost_model.py        # Gradient boosting
│   │
│   ├── training/
│   │   ├── __init__.py
│   │   └── trainer.py              # Training pipeline & logic
│   │
│   ├── prediction/
│   │   └── __init__.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py                 # FastAPI endpoints
│   │
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── app.py                  # Streamlit dashboard
│   │
│   └── utils/
│       ├── __init__.py
│       ├── database.py             # DB connections
│       ├── logger.py               # Logging setup
│       └── config.py               # Configuration
│
├── tests/
│   └── test_collectors.py
│
├── scripts/
│   └── init_db.sql
│
└── docker/
    ├── Dockerfile.ml
    ├── Dockerfile.api
    └── Dockerfile.dashboard
```

---

## 🐳 Docker Setup

### docker-compose.yml

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    container_name: stock_ml_db
    environment:
      POSTGRES_DB: stock_ml
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - stock_ml_network

  # Redis for caching
  redis:
    image: redis:7-alpine
    container_name: stock_ml_redis
    ports:
      - "6379:6379"
    networks:
      - stock_ml_network

  # ML Training Service
  ml_trainer:
    build:
      context: .
      dockerfile: docker/Dockerfile.ml
    container_name: stock_ml_trainer
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=stock_ml
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_HOST=redis
    volumes:
      - ./data:/app/data
      - ./src:/app/src
      - ./models:/app/models
    depends_on:
      - postgres
      - redis
    networks:
      - stock_ml_network
    command: python -m src.training.trainer

  # Data Collection Service
  data_collector:
    build:
      context: .
      dockerfile: docker/Dockerfile.ml
    container_name: stock_ml_collector
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=stock_ml
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - YAHOO_API_KEY=${YAHOO_API_KEY}
      - NEWS_API_KEY=${NEWS_API_KEY}
    volumes:
      - ./data:/app/data
      - ./src:/app/src
    depends_on:
      - postgres
    networks:
      - stock_ml_network
    command: python -m src.data_collection.stock_collector

  # FastAPI Service
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    container_name: stock_ml_api
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=stock_ml
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_HOST=redis
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./models:/app/models
    depends_on:
      - postgres
      - redis
      - ml_trainer
    networks:
      - stock_ml_network
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

  # Streamlit Dashboard
  dashboard:
    build:
      context: .
      dockerfile: docker/Dockerfile.dashboard
    container_name: stock_ml_dashboard
    environment:
      - API_URL=http://api:8000
    ports:
      - "8501:8501"
    volumes:
      - ./src/dashboard:/app/dashboard
    depends_on:
      - api
    networks:
      - stock_ml_network
    command: streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0

volumes:
  postgres_data:

networks:
  stock_ml_network:
    driver: bridge
```

### .env.example

```bash
# Database
DB_USER=stockml
DB_PASSWORD=your_secure_password_here
DB_NAME=stock_ml
DB_HOST=postgres
DB_PORT=5432

# API Keys
YAHOO_API_KEY=your_yahoo_finance_key
NEWS_API_KEY=your_news_api_key
ALPHA_VANTAGE_KEY=your_alpha_vantage_key

# Model Configuration
MODEL_RETRAIN_INTERVAL=7  # days
PREDICTION_CONFIDENCE_THRESHOLD=0.6
LEARNING_RATE=0.001

# Stock Configuration
DEFAULT_STOCKS=BBCA.JK,BBRI.JK,TLKM.JK,ASII.JK,UNVR.JK
TIMEFRAME=1d  # 1m, 5m, 15m, 1h, 1d
LOOKBACK_DAYS=365

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Logging
LOG_LEVEL=INFO
```

---

## 🛠️ Dockerfiles

### docker/Dockerfile.ml

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY data/ ./data/

# Set Python path
ENV PYTHONPATH=/app

CMD ["python", "-m", "src.training.trainer"]
```

### docker/Dockerfile.api

```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY models/ ./models/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker/Dockerfile.dashboard

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt streamlit plotly

COPY src/dashboard/ ./dashboard/

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

---

## 📦 Requirements.txt

```txt
# Core ML Libraries
tensorflow==2.15.0
torch==2.1.0
scikit-learn==1.3.2
xgboost==2.0.2
lightgbm==4.1.0

# Data Processing
pandas==2.1.3
numpy==1.26.2
scipy==1.11.4

# Data Collection
yfinance==0.2.32
requests==2.31.0
beautifulsoup4==4.12.2
selenium==4.15.2

# NLP & Sentiment Analysis
transformers==4.35.2
nltk==3.8.1
textblob==0.17.1
newspaper3k==0.2.8

# Technical Indicators
ta==0.11.0
ta-lib==0.4.28

# Database
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
redis==5.0.1

# API & Web
fastapi==0.104.1
uvicorn==0.24.0
websockets==12.0
pydantic==2.5.2

# Dashboard
streamlit==1.28.2
plotly==5.18.0
matplotlib==3.8.2
seaborn==0.13.0

# Utilities
python-dotenv==1.0.0
schedule==1.2.0
loguru==0.7.2
joblib==1.3.2
tqdm==4.66.1

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
```

---

## 🗄️ Database Schema (init_db.sql)

```sql
-- Table: stocks
CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(200),
    sector VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: stock_prices
CREATE TABLE IF NOT EXISTS stock_prices (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    date DATE NOT NULL,
    open DECIMAL(15,2),
    high DECIMAL(15,2),
    low DECIMAL(15,2),
    close DECIMAL(15,2),
    volume BIGINT,
    adj_close DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, date)
);

-- Table: technical_indicators
CREATE TABLE IF NOT EXISTS technical_indicators (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    date DATE NOT NULL,
    rsi_14 DECIMAL(10,2),
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    bb_upper DECIMAL(15,2),
    bb_middle DECIMAL(15,2),
    bb_lower DECIMAL(15,2),
    sma_20 DECIMAL(15,2),
    sma_50 DECIMAL(15,2),
    sma_200 DECIMAL(15,2),
    ema_12 DECIMAL(15,2),
    ema_26 DECIMAL(15,2),
    volume_sma_20 BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, date)
);

-- Table: news_sentiment
CREATE TABLE IF NOT EXISTS news_sentiment (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    date DATE NOT NULL,
    title TEXT,
    content TEXT,
    source VARCHAR(200),
    url TEXT,
    sentiment_score DECIMAL(5,4),
    sentiment_label VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: predictions
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    prediction_date TIMESTAMP NOT NULL,
    target_date DATE NOT NULL,
    predicted_direction VARCHAR(10),
    predicted_change_pct DECIMAL(10,4),
    confidence DECIMAL(5,4),
    model_version VARCHAR(50),
    features JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: prediction_results
CREATE TABLE IF NOT EXISTS prediction_results (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id),
    actual_direction VARCHAR(10),
    actual_change_pct DECIMAL(10,4),
    is_correct BOOLEAN,
    error_pct DECIMAL(10,4),
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: model_performance
CREATE TABLE IF NOT EXISTS model_performance (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    accuracy DECIMAL(5,4),
    precision_score DECIMAL(5,4),
    recall DECIMAL(5,4),
    f1_score DECIMAL(5,4),
    mae DECIMAL(10,4),
    rmse DECIMAL(10,4),
    training_date TIMESTAMP,
    evaluation_period_start DATE,
    evaluation_period_end DATE,
    total_predictions INTEGER,
    correct_predictions INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: model_metadata
CREATE TABLE IF NOT EXISTS model_metadata (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100),
    version VARCHAR(50),
    file_path TEXT,
    hyperparameters JSONB,
    training_samples INTEGER,
    features_used JSONB,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_stock_prices_stock_date ON stock_prices(stock_id, date DESC);
CREATE INDEX idx_predictions_stock_date ON predictions(stock_id, target_date);
CREATE INDEX idx_news_date ON news_sentiment(date DESC);
CREATE INDEX idx_model_active ON model_metadata(is_active, version);

-- Insert sample stocks
INSERT INTO stocks (symbol, name, sector) VALUES
('BBCA.JK', 'Bank Central Asia Tbk', 'Financial'),
('BBRI.JK', 'Bank Rakyat Indonesia Tbk', 'Financial'),
('TLKM.JK', 'Telkom Indonesia Tbk', 'Telecommunications'),
('ASII.JK', 'Astra International Tbk', 'Automotive'),
('UNVR.JK', 'Unilever Indonesia Tbk', 'Consumer Goods')
ON CONFLICT (symbol) DO NOTHING;
```

---

## 🧠 Machine Learning Components

### 1. Feature Engineering

**Technical Indicators:**
- Moving Averages (SMA, EMA)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Volume indicators
- Momentum indicators

**Market Features:**
- IHSG (Jakarta Composite Index) movement
- Sector performance
- Market breadth indicators
- Foreign flow data

**Sentiment Features:**
- News sentiment score
- Social media sentiment (Twitter/Reddit)
- Analyst ratings changes

**Time-based Features:**
- Day of week
- Month
- Quarter
- Trading sessions patterns

### 2. Model Architecture

#### LSTM Model (Time Series)
```python
# Pseudo architecture
Input Layer (sequence_length, n_features)
    ↓
LSTM Layer 1 (128 units, return_sequences=True)
    ↓
Dropout (0.2)
    ↓
LSTM Layer 2 (64 units, return_sequences=True)
    ↓
Dropout (0.2)
    ↓
LSTM Layer 3 (32 units)
    ↓
Dense Layer (16 units, ReLU)
    ↓
Output Layer (2 units: direction probability, change %)
```

#### XGBoost Model
```python
# Hyperparameters
- n_estimators: 1000
- learning_rate: 0.01
- max_depth: 7
- subsample: 0.8
- colsample_bytree: 0.8
- objective: 'multi:softprob' for direction
             'reg:squarederror' for change %
```

#### Ensemble Strategy
- Weighted average of LSTM + XGBoost
- Voting for direction prediction
- Average for percentage change
- Dynamic weight adjustment based on recent performance

### 3. Continuous Learning Pipeline

```
Step 1: Collect new data daily
    ↓
Step 2: Generate predictions for next day
    ↓
Step 3: Wait for actual results
    ↓
Step 4: Evaluate predictions vs actual
    ↓
Step 5: Store feedback in database
    ↓
Step 6: Accumulate feedback (weekly/monthly)
    ↓
Step 7: Retrain model with new data + feedback
    ↓
Step 8: Validate new model performance
    ↓
Step 9: Deploy if performance improved
    ↓
Step 10: Loop back to Step 1
```

### 4. Training Strategy

**Initial Training:**
- Historical data: 2-3 years
- Train/validation/test split: 70/15/15
- Cross-validation with time series split

**Continuous Learning:**
- Incremental learning every week
- Rolling window approach
- Keep last N months of data
- Prioritize recent data with time-weighted learning

**Backtesting:**
- Walk-forward optimization
- Out-of-sample testing
- Performance metrics tracking

---

## 📊 API Endpoints

### FastAPI Routes

```python
# Health Check
GET /health
Response: {"status": "healthy", "timestamp": "..."}

# Get Stock List
GET /api/v1/stocks
Response: [{"symbol": "BBCA.JK", "name": "...", "sector": "..."}]

# Get Stock Price History
GET /api/v1/stocks/{symbol}/history?days=30
Response: {"symbol": "BBCA.JK", "data": [...]}

# Get Latest Prediction
GET /api/v1/predictions/{symbol}/latest
Response: {
    "symbol": "BBCA.JK",
    "prediction_date": "2024-01-15",
    "target_date": "2024-01-16",
    "direction": "UP",
    "change_pct": 1.25,
    "confidence": 0.73,
    "model_version": "v1.2.3"
}

# Get Prediction History
GET /api/v1/predictions/{symbol}/history?limit=30
Response: {"symbol": "BBCA.JK", "predictions": [...]}

# Get Model Performance
GET /api/v1/models/performance
Response: {
    "accuracy": 0.62,
    "precision": 0.65,
    "recall": 0.60,
    "f1_score": 0.62,
    "total_predictions": 1250,
    "correct_predictions": 775
}

# Request New Prediction
POST /api/v1/predictions/{symbol}
Body: {"target_date": "2024-01-20", "features": {...}}
Response: {"prediction_id": 123, "status": "created"}

# Submit Feedback
POST /api/v1/feedback
Body: {
    "prediction_id": 123,
    "actual_direction": "UP",
    "actual_change_pct": 1.5
}
Response: {"status": "feedback_recorded"}

# Trigger Model Retraining
POST /api/v1/models/retrain
Body: {"force": true}
Response: {"status": "retraining_started", "job_id": "..."}

# WebSocket - Real-time Updates
WS /ws/predictions/{symbol}
Message: {"type": "prediction_update", "data": {...}}
```

---

## 📈 Dashboard Features

### Streamlit Dashboard Components

1. **Overview Dashboard**
   - Portfolio summary
   - Today's predictions
   - Model accuracy trends
   - Top performing stocks

2. **Stock Analysis**
   - Interactive price charts
   - Technical indicators overlay
   - Prediction vs actual comparison
   - Confidence levels visualization

3. **Model Performance**
   - Accuracy metrics over time
   - Confusion matrix
   - ROC curves
   - Feature importance

4. **Backtesting Results**
   - Strategy returns
   - Benchmark comparison
   - Drawdown analysis
   - Win/loss ratio

5. **Live Predictions**
   - Real-time prediction feed
   - Confidence filters
   - Alert notifications

---

## 🚀 Getting Started

### 1. Prerequisites

```bash
# Install Docker & Docker Compose
# Docker version 24.0+
# Docker Compose version 2.20+

# Install Git
sudo apt-get install git
```

### 2. Clone & Setup

```bash
# Clone repository
git clone https://github.com/yourusername/stock-ml-predictor.git
cd stock-ml-predictor

# Copy environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 3. Build & Run

```bash
# Build all containers
docker-compose build

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Access services:
# - API: http://localhost:8000
# - Dashboard: http://localhost:8501
# - API Docs: http://localhost:8000/docs
```

### 4. Initialize Data

```bash
# Collect initial historical data
docker-compose exec ml_trainer python scripts/collect_initial_data.py

# Train initial model
docker-compose exec ml_trainer python scripts/train_initial_model.py
```

### 5. Monitor

```bash
# Check service status
docker-compose ps

# View ML trainer logs
docker-compose logs -f ml_trainer

# View API logs
docker-compose logs -f api

# Access database
docker-compose exec postgres psql -U stockml -d stock_ml
```

---

## 🔄 Continuous Learning Workflow

### Daily Routine

```bash
# 1. Morning: Collect overnight data (runs automatically)
# Scheduled via cron or APScheduler in data_collector

# 2. Market Open: Generate predictions
# Automatically triggered by predictor service

# 3. Market Close: Collect end-of-day data
# Scheduled collection

# 4. Evening: Evaluate today's predictions
# Automated evaluation of morning predictions

# 5. Store feedback for learning
# Feedback stored in prediction_results table
```

### Weekly Retraining

```bash
# Automatic weekly retraining
# Configured in docker-compose with schedule

# Manual trigger if needed:
docker-compose exec ml_trainer python -m src.training.continuous_learner

# Or via API:
curl -X POST http://localhost:8000/api/v1/models/retrain
```

### Performance Monitoring

```python
# Monitor model drift
# Check accuracy trends
# Alert if performance degrades below threshold
# Automatic rollback to previous model if new model underperforms
```

---

## 📊 Metrics & Evaluation

### Key Performance Indicators (KPIs)

1. **Direction Accuracy**: % predictions correct untuk arah (naik/turun)
2. **MAE (Mean Absolute Error)**: Rata-rata error persentase perubahan
3. **RMSE (Root Mean Squared Error)**: Error dengan penalti untuk outliers
4. **Sharpe Ratio**: Risk-adjusted returns (untuk trading simulation)
5. **Maximum Drawdown**: Largest peak-to-trough decline
6. **Win Rate**: % profitable predictions
7. **Average Return per Trade**: Rata-rata profit per prediksi benar

### Evaluation Criteria

```python
# Model dianggap "mature" ketika:
- Direction accuracy > 60% (consistently over 3 months)
- MAE < 2% (average error dalam prediksi perubahan harga)
- Sharpe Ratio > 1.0 (if used for trading)
- Consistent performance across different market conditions
```

---

## 🎯 Optimization Tips

### 1. Feature Selection
- Gunakan feature importance dari XGBoost
- Remove features dengan correlation > 0.95
- Test different feature combinations

### 2. Hyperparameter Tuning
- Bayesian optimization
- Grid search dengan cross-validation
- AutoML tools (Optuna, Ray Tune)

### 3. Data Quality
- Handle missing data properly
- Outlier detection & treatment
- Ensure data consistency

### 4. Model Ensemble
- Combine multiple model types
- Weighted voting based on recent performance
- Stack models for better predictions

### 5. Risk Management
- Set confidence thresholds
- Only act on high-confidence predictions
- Diversify across multiple stocks
- Position sizing based on confidence

---

## ⚠️ Important Considerations

### Legal & Ethical

1. **Disclaimer**: Ini adalah tool pembelajaran, bukan financial advice
2. **Regulation**: Pastikan compliance dengan OJK regulations
3. **Data Usage**: Respect API terms of service
4. **Privacy**: Tidak share trading strategies secara publik

### Technical Limitations

1. **Market Efficiency**: Pasar saham sulit diprediksi dengan perfect accuracy
2. **Black Swan Events**: Model tidak bisa predict kejadian ekstrem
3. **Overfitting Risk**: Always validate dengan out-of-sample data
4. **Data Latency**: Real-time data may have delays
5. **Computational Cost**: Training models requires significant resources

### Risk Warnings

⚠️ **PERINGATAN PENTING:**
- Model ML tidak guarantee profit
- Past performance ≠ future results
- Gunakan dengan risk management yang ketat
- Jangan invest lebih dari yang Anda sanggup kehilangan
- Selalu lakukan due diligence sendiri
- Consider consulting licensed financial advisors

---

## 🔧 Troubleshooting

### Common Issues

**1. Container won't start**
```bash
# Check logs
docker-compose logs [service_name]

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**2. Database connection errors**
```bash
# Check if postgres is running
docker-compose ps postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

**3. Out of memory errors**
```bash
# Increase Docker memory limit
# Docker Desktop > Settings > Resources > Memory

# Or reduce batch size in training configs
```

**4. Slow predictions**
```bash
# Check model size
# Implement model quantization
# Use Redis caching
# Enable GPU acceleration if available
```

**5. Data collection failures**
```bash
# Verify API keys in .env
# Check internet connection
# Verify stock symbols are correct
# Check API rate limits
```

---

## 🚀 Advanced Features (Future Enhancements)

### 1. Reinforcement Learning Agent
```python
# Q-Learning / DQN for optimal trading decisions
- State: Current portfolio + market conditions
- Actions: Buy, Sell, Hold
- Reward: Portfolio returns
- Train agent to maximize long-term returns
```

### 2. Multi-Timeframe Analysis
```python
# Analyze multiple timeframes simultaneously
- 1-minute for intraday
- 5-minute for short-term
- 1-hour for medium-term
- Daily for long-term trends
- Combine signals from all timeframes
```

### 3. Portfolio Optimization
```python
# Modern Portfolio Theory implementation
- Diversification across multiple stocks
- Risk-return optimization
- Correlation analysis
- Dynamic rebalancing
```

### 4. Alternative Data Sources
```python
# Incorporate non-traditional data
- Social media sentiment (Twitter, Reddit)
- Google Trends data
- Economic indicators (inflation, GDP, interest rates)
- Commodity prices (oil, gold)
- Foreign exchange rates
```

### 5. Real-time Streaming
```python
# WebSocket connections for live data
- Real-time price updates
- Live prediction adjustments
- Instant alerts on opportunities
- Low-latency execution
```

### 6. Explainable AI (XAI)
```python
# SHAP/LIME for model interpretability
- Feature contribution analysis
- Decision explanation
- Trust building with users
- Regulatory compliance
```

### 7. AutoML Integration
```python
# Automated model selection & tuning
- Auto-sklearn
- H2O.ai
- Neural Architecture Search
- Hyperparameter optimization
```

### 8. Multi-Asset Support
```python
# Beyond stocks
- Cryptocurrency (Bitcoin, Ethereum)
- Forex pairs
- Commodities
- Bonds
```

---

## 📚 Learning Resources

### Machine Learning for Finance
- **Books:**
  - "Machine Learning for Algorithmic Trading" - Stefan Jansen
  - "Advances in Financial Machine Learning" - Marcos Lopez de Prado
  - "Python for Finance" - Yves Hilpisch

- **Courses:**
  - Coursera: Machine Learning for Trading (Georgia Tech)
  - Udacity: AI for Trading Nanodegree
  - Quantopian Lectures (archived)

### Technical Analysis
- Investopedia Technical Analysis Course
- TradingView Education Portal
- Indonesian Stock Exchange (IDX) Education Center

### Deep Learning
- Deep Learning Specialization (Andrew Ng)
- Fast.ai Practical Deep Learning
- TensorFlow & PyTorch Documentation

### Time Series Forecasting
- Forecasting: Principles and Practice (Rob Hyndman)
- Time Series Analysis with Python
- LSTM Networks for Time Series

---

## 🤝 Contributing

### Development Workflow

```bash
# 1. Fork repository
# 2. Create feature branch
git checkout -b feature/amazing-feature

# 3. Make changes and commit
git commit -m "Add amazing feature"

# 4. Push to branch
git push origin feature/amazing-feature

# 5. Open Pull Request
```

### Code Standards
- Follow PEP 8 for Python code
- Add docstrings to all functions
- Write unit tests (target >80% coverage)
- Update documentation
- Use type hints

### Testing
```bash
# Run all tests
docker-compose exec ml_trainer pytest

# Run with coverage
docker-compose exec ml_trainer pytest --cov=src tests/

# Run specific test
docker-compose exec ml_trainer pytest tests/test_models.py
```

---

## 📝 Example Implementation Snippets

### 1. Data Collection Script

```python
# src/data_collection/stock_collector.py
import yfinance as yf
from datetime import datetime, timedelta
from src.utils.database import Database

class StockCollector:
    def __init__(self, db: Database):
        self.db = db
    
    def collect_historical_data(self, symbol: str, days: int = 365):
        """Collect historical stock data"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Download data from Yahoo Finance
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        # Store in database
        for index, row in df.iterrows():
            self.db.insert_stock_price(
                symbol=symbol,
                date=index.date(),
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                close=row['Close'],
                volume=row['Volume'],
                adj_close=row['Close']
            )
        
        return df
    
    def collect_realtime_data(self, symbol: str):
        """Collect real-time price data"""
        ticker = yf.Ticker(symbol)
        data = ticker.info
        
        return {
            'symbol': symbol,
            'current_price': data.get('currentPrice'),
            'previous_close': data.get('previousClose'),
            'change_pct': data.get('regularMarketChangePercent'),
            'volume': data.get('volume')
        }
```

### 2. Feature Engineering

```python
# src/feature_engineering/technical_indicators.py
import pandas as pd
import ta

class TechnicalIndicators:
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators"""
        
        # Trend Indicators
        df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
        df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
        df['sma_200'] = ta.trend.sma_indicator(df['close'], window=200)
        df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
        df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)
        
        # MACD
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()
        
        # RSI
        df['rsi_14'] = ta.momentum.rsi(df['close'], window=14)
        
        # Bollinger Bands
        bollinger = ta.volatility.BollingerBands(df['close'])
        df['bb_upper'] = bollinger.bollinger_hband()
        df['bb_middle'] = bollinger.bollinger_mavg()
        df['bb_lower'] = bollinger.bollinger_lband()
        
        # Volume indicators
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']
        
        # Price momentum
        df['momentum_5'] = df['close'].pct_change(periods=5)
        df['momentum_10'] = df['close'].pct_change(periods=10)
        
        # Volatility
        df['volatility_20'] = df['close'].rolling(window=20).std()
        
        return df
```

### 3. LSTM Model

```python
# src/models/lstm_model.py
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np

class LSTMStockPredictor:
    def __init__(self, sequence_length=60, n_features=20):
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.model = self._build_model()
    
    def _build_model(self):
        """Build LSTM architecture"""
        model = keras.Sequential([
            layers.LSTM(128, return_sequences=True, 
                       input_shape=(self.sequence_length, self.n_features)),
            layers.Dropout(0.2),
            
            layers.LSTM(64, return_sequences=True),
            layers.Dropout(0.2),
            
            layers.LSTM(32, return_sequences=False),
            layers.Dropout(0.2),
            
            layers.Dense(16, activation='relu'),
            layers.Dense(2)  # [direction_probability, change_percentage]
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )
        
        return model
    
    def prepare_sequences(self, data, target):
        """Prepare sequences for LSTM"""
        X, y = [], []
        
        for i in range(self.sequence_length, len(data)):
            X.append(data[i-self.sequence_length:i])
            y.append(target[i])
        
        return np.array(X), np.array(y)
    
    def train(self, X_train, y_train, X_val, y_val, epochs=100):
        """Train the model"""
        early_stopping = keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )
        
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=32,
            callbacks=[early_stopping],
            verbose=1
        )
        
        return history
    
    def predict(self, X):
        """Make predictions"""
        predictions = self.model.predict(X)
        
        return {
            'direction': 'UP' if predictions[0][0] > 0.5 else 'DOWN',
            'change_pct': predictions[0][1],
            'confidence': abs(predictions[0][0] - 0.5) * 2
        }
```

### 4. XGBoost Model

```python
# src/models/xgboost_model.py
import xgboost as xgb
import pandas as pd
import numpy as np

class XGBoostStockPredictor:
    def __init__(self):
        self.direction_model = None
        self.change_model = None
    
    def train_direction_model(self, X_train, y_train):
        """Train model for direction prediction"""
        params = {
            'objective': 'binary:logistic',
            'max_depth': 7,
            'learning_rate': 0.01,
            'n_estimators': 1000,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'eval_metric': 'logloss'
        }
        
        self.direction_model = xgb.XGBClassifier(**params)
        self.direction_model.fit(
            X_train, y_train,
            eval_set=[(X_train, y_train)],
            early_stopping_rounds=50,
            verbose=False
        )
    
    def train_change_model(self, X_train, y_train):
        """Train model for percentage change prediction"""
        params = {
            'objective': 'reg:squarederror',
            'max_depth': 7,
            'learning_rate': 0.01,
            'n_estimators': 1000,
            'subsample': 0.8,
            'colsample_bytree': 0.8
        }
        
        self.change_model = xgb.XGBRegressor(**params)
        self.change_model.fit(
            X_train, y_train,
            eval_set=[(X_train, y_train)],
            early_stopping_rounds=50,
            verbose=False
        )
    
    def predict(self, X):
        """Make predictions"""
        direction_prob = self.direction_model.predict_proba(X)[0]
        change_pct = self.change_model.predict(X)[0]
        
        return {
            'direction': 'UP' if direction_prob[1] > 0.5 else 'DOWN',
            'change_pct': change_pct,
            'confidence': max(direction_prob)
        }
    
    def get_feature_importance(self):
        """Get feature importance"""
        importance = self.direction_model.feature_importances_
        return importance
```

### 5. Continuous Learner

```python
# src/training/continuous_learner.py
from datetime import datetime, timedelta
from src.utils.database import Database
from src.models.lstm_model import LSTMStockPredictor
from src.models.xgboost_model import XGBoostStockPredictor
import pandas as pd

class ContinuousLearner:
    def __init__(self, db: Database):
        self.db = db
        self.lstm_model = LSTMStockPredictor()
        self.xgb_model = XGBoostStockPredictor()
    
    def collect_feedback(self, days_back=7):
        """Collect prediction results from past days"""
        query = """
            SELECT p.*, pr.actual_direction, pr.actual_change_pct, 
                   pr.is_correct, pr.error_pct
            FROM predictions p
            JOIN prediction_results pr ON p.id = pr.prediction_id
            WHERE p.prediction_date >= NOW() - INTERVAL '%s days'
        """ % days_back
        
        results = self.db.execute_query(query)
        return pd.DataFrame(results)
    
    def evaluate_model_performance(self, feedback_df):
        """Evaluate current model performance"""
        total = len(feedback_df)
        correct = feedback_df['is_correct'].sum()
        accuracy = correct / total if total > 0 else 0
        
        mae = feedback_df['error_pct'].abs().mean()
        
        return {
            'accuracy': accuracy,
            'mae': mae,
            'total_predictions': total,
            'correct_predictions': correct
        }
    
    def should_retrain(self, performance):
        """Decide if model needs retraining"""
        # Retrain if accuracy drops below threshold
        if performance['accuracy'] < 0.55:
            return True
        
        # Retrain if MAE is too high
        if performance['mae'] > 3.0:
            return True
        
        # Regular scheduled retraining (weekly)
        last_training = self.db.get_last_training_date()
        if (datetime.now() - last_training).days >= 7:
            return True
        
        return False
    
    def retrain_models(self):
        """Retrain all models with latest data"""
        # Fetch latest data
        data = self.db.get_training_data(days=365)
        
        # Prepare features and targets
        X, y_direction, y_change = self.prepare_training_data(data)
        
        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_dir_train, y_dir_val = y_direction[:split_idx], y_direction[split_idx:]
        y_chg_train, y_chg_val = y_change[:split_idx], y_change[split_idx:]
        
        # Train LSTM
        print("Training LSTM model...")
        self.lstm_model.train(X_train, 
                             np.column_stack([y_dir_train, y_chg_train]),
                             X_val,
                             np.column_stack([y_dir_val, y_chg_val]))
        
        # Train XGBoost
        print("Training XGBoost models...")
        self.xgb_model.train_direction_model(X_train, y_dir_train)
        self.xgb_model.train_change_model(X_train, y_chg_train)
        
        # Validate new models
        val_performance = self.validate_models(X_val, y_dir_val, y_chg_val)
        
        # Save models if performance improved
        if val_performance['accuracy'] > 0.60:
            self.save_models()
            self.db.log_model_performance(val_performance)
            print(f"Models saved! Accuracy: {val_performance['accuracy']:.2%}")
        else:
            print(f"New models underperformed. Keeping current models.")
        
        return val_performance
```

### 6. FastAPI Implementation

```python
# src/api/main.py
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
from src.utils.database import Database
from src.prediction.predictor import StockPredictor

app = FastAPI(title="Stock ML Predictor API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
db = Database()
predictor = StockPredictor(db)

# Models
class PredictionRequest(BaseModel):
    symbol: str
    target_date: date

class PredictionResponse(BaseModel):
    prediction_id: int
    symbol: str
    prediction_date: datetime
    target_date: date
    direction: str
    change_pct: float
    confidence: float
    model_version: str

class FeedbackRequest(BaseModel):
    prediction_id: int
    actual_direction: str
    actual_change_pct: float

# Endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/api/v1/stocks")
async def get_stocks():
    stocks = db.get_all_stocks()
    return stocks

@app.get("/api/v1/stocks/{symbol}/history")
async def get_stock_history(symbol: str, days: int = 30):
    history = db.get_stock_history(symbol, days)
    return {"symbol": symbol, "data": history}

@app.get("/api/v1/predictions/{symbol}/latest", 
         response_model=PredictionResponse)
async def get_latest_prediction(symbol: str):
    prediction = db.get_latest_prediction(symbol)
    if not prediction:
        raise HTTPException(status_code=404, detail="No predictions found")
    return prediction

@app.post("/api/v1/predictions/{symbol}")
async def create_prediction(symbol: str, request: PredictionRequest):
    # Generate prediction
    result = predictor.predict(symbol, request.target_date)
    
    # Store in database
    prediction_id = db.store_prediction(result)
    
    return {"prediction_id": prediction_id, "status": "created", **result}

@app.post("/api/v1/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    # Store feedback
    db.store_feedback(
        prediction_id=feedback.prediction_id,
        actual_direction=feedback.actual_direction,
        actual_change_pct=feedback.actual_change_pct
    )
    
    return {"status": "feedback_recorded"}

@app.get("/api/v1/models/performance")
async def get_model_performance():
    performance = db.get_model_performance()
    return performance

@app.post("/api/v1/models/retrain")
async def trigger_retraining(force: bool = False):
    from src.training.continuous_learner import ContinuousLearner
    
    learner = ContinuousLearner(db)
    
    # Check if retraining needed
    if not force:
        feedback = learner.collect_feedback(days_back=7)
        performance = learner.evaluate_model_performance(feedback)
        
        if not learner.should_retrain(performance):
            return {"status": "retraining_not_needed", "performance": performance}
    
    # Start retraining
    result = learner.retrain_models()
    
    return {"status": "retraining_completed", "performance": result}

# WebSocket for real-time updates
@app.websocket("/ws/predictions/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await websocket.accept()
    
    try:
        while True:
            # Send real-time predictions
            prediction = predictor.predict(symbol)
            await websocket.send_json(prediction)
            
            # Wait for next update interval
            await asyncio.sleep(60)  # Update every minute
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()
```

### 7. Streamlit Dashboard

```python
# src/dashboard/app.py
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import requests
from datetime import datetime, timedelta

# Page config
st.set_page_config(
    page_title="Stock ML Predictor",
    page_icon="📈",
    layout="wide"
)

# API URL
API_URL = "http://api:8000"

# Title
st.title("📈 Indonesian Stock Market ML Predictor")

# Sidebar
st.sidebar.header("Settings")
selected_stock = st.sidebar.selectbox(
    "Select Stock",
    ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK", "UNVR.JK"]
)
days_history = st.sidebar.slider("History Days", 30, 365, 90)

# Fetch data
@st.cache_data(ttl=300)
def get_stock_history(symbol, days):
    response = requests.get(f"{API_URL}/api/v1/stocks/{symbol}/history?days={days}")
    return response.json()

@st.cache_data(ttl=60)
def get_latest_prediction(symbol):
    response = requests.get(f"{API_URL}/api/v1/predictions/{symbol}/latest")
    return response.json()

@st.cache_data(ttl=300)
def get_model_performance():
    response = requests.get(f"{API_URL}/api/v1/models/performance")
    return response.json()

# Main dashboard
col1, col2, col3, col4 = st.columns(4)

# Fetch latest prediction
try:
    prediction = get_latest_prediction(selected_stock)
    
    with col1:
        st.metric(
            "Direction",
            prediction['direction'],
            delta=f"{prediction['change_pct']:.2f}%"
        )
    
    with col2:
        st.metric(
            "Confidence",
            f"{prediction['confidence']:.1%}"
        )
    
    with col3:
        st.metric(
            "Target Date",
            prediction['target_date']
        )
    
    with col4:
        st.metric(
            "Model Version",
            prediction['model_version']
        )
except:
    st.warning("No predictions available yet")

# Stock price chart
st.subheader(f"📊 {selected_stock} Price History")

history = get_stock_history(selected_stock, days_history)
df = pd.DataFrame(history['data'])

fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=df['date'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    name='Price'
))

fig.update_layout(
    title=f"{selected_stock} - Last {days_history} Days",
    yaxis_title="Price (IDR)",
    xaxis_title="Date",
    height=500
)

st.plotly_chart(fig, use_container_width=True)

# Model performance
st.subheader("🎯 Model Performance")

performance = get_model_performance()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Accuracy", f"{performance['accuracy']:.2%}")
    st.metric("Precision", f"{performance['precision_score']:.2%}")

with col2:
    st.metric("Total Predictions", performance['total_predictions'])
    st.metric("Correct Predictions", performance['correct_predictions'])

with col3:
    st.metric("MAE", f"{performance['mae']:.2f}%")
    st.metric("RMSE", f"{performance['rmse']:.2f}%")

# Accuracy trend chart
st.subheader("📈 Accuracy Trend")
# Add chart showing accuracy over time

# Prediction history table
st.subheader("📋 Recent Predictions")
# Add table showing recent predictions with results
```

---

## 🎓 Best Practices

### 1. Data Management
- **Version Control**: Track data versions alongside model versions
- **Data Validation**: Always validate incoming data quality
- **Backup Strategy**: Regular database backups (daily recommended)
- **Data Cleaning**: Handle missing values, outliers, duplicates

### 2. Model Development
- **Start Simple**: Begin with baseline models before complex architectures
- **Incremental Complexity**: Add features/complexity gradually
- **Cross-Validation**: Always use proper time-series cross-validation
- **Ensemble Methods**: Combine multiple models for robustness

### 3. Production Deployment
- **A/B Testing**: Test new models alongside old ones
- **Gradual Rollout**: Deploy to subset of stocks first
- **Monitoring**: Continuous performance monitoring
- **Rollback Plan**: Keep previous model versions for quick rollback

### 4. Risk Management
- **Position Sizing**: Never risk more than 2% per trade
- **Stop Loss**: Always set stop-loss levels
- **Diversification**: Don't put all capital in one stock
- **Confidence Threshold**: Only act on high-confidence predictions (>70%)

### 5. Continuous Improvement
- **Regular Retraining**: Weekly or monthly retraining schedule
- **Feature Engineering**: Continuously test new features
- **Performance Review**: Weekly performance analysis
- **Market Adaptation**: Adjust strategy based on market conditions

---

## 🔒 Security Considerations

### 1. API Security
```python
# Add API key authentication
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

@app.get("/api/v1/protected")
async def protected_route(api_key: str = Depends(API_KEY_HEADER)):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return {"message": "Access granted"}
```

### 2. Database Security
- Use strong passwords
- Enable SSL connections
- Implement role-based access control
- Regular security audits

### 3. Data Privacy
- Encrypt sensitive data at rest
- Use HTTPS for all API calls
- Don't log sensitive information
- Comply with data protection regulations

### 4. Container Security
```bash
# Scan images for vulnerabilities
docker scan stock-ml-predictor:latest

# Use non-root users in containers
# Run with read-only file system where possible
# Limit container resources
```

---

## 📊 Performance Benchmarks

### Expected Performance Metrics

**Good Performance:**
- Direction Accuracy: 58-65%
- MAE: 1.5-2.5%
- Sharpe Ratio: > 1.0
- Max Drawdown: < 20%

**Excellent Performance:**
- Direction Accuracy: 65-70%
- MAE: < 1.5%
- Sharpe Ratio: > 1.5
- Max Drawdown: < 15%

**Note**: Consistently achieving >70% accuracy is extremely rare and should be validated thoroughly to avoid overfitting.

---

## 🆘 Support & Community

### Getting Help
- **Documentation**: Read this guide thoroughly
- **Issues**: Report bugs via GitHub Issues
- **Discussions**: Join project discussions
- **Stack Overflow**: Tag questions with `stock-ml-predictor`

### Contributing
We welcome contributions! Areas needing help:
- [ ] Additional data sources integration
- [ ] New model architectures
- [ ] Performance optimizations
- [ ] Documentation improvements
- [ ] Test coverage expansion
- [ ] Feature requests

---

## 📄 License

This project is for educational purposes. 

**Disclaimer**: 
- Not financial advice
- Use at your own risk
- Past performance doesn't guarantee future results
- Author not liable for trading losses

---

## 🙏 Acknowledgments

- Yahoo Finance for market data
- TensorFlow & PyTorch communities
- Scikit-learn contributors
- Indonesian Stock Exchange (IDX)
- Open source ML community

---

## 📞 Contact & Support

**Project Repository**: https://github.com/yourusername/stock-ml-predictor

**Issues**: https://github.com/yourusername/stock-ml-predictor/issues

**Email**: support@yourproject.com

---

**Last Updated**: December 2024

**Version**: 1.0.0

---

## 🎯 Quick Start Checklist

- [ ] Install Docker & Docker Compose
- [ ] Clone repository
- [ ] Copy .env.example to .env
- [ ] Add API keys to .env
- [ ] Run `docker-compose build`
- [ ] Run `docker-compose up -d`
- [ ] Initialize database with `scripts/init_db.sql`
- [ ] Collect initial data
- [ ] Train initial model
- [ ] Access dashboard at http://localhost:8501
- [ ] Test API at http://localhost:8000/docs
- [ ] Monitor logs with `docker-compose logs -f`
- [ ] Set up scheduled retraining
- [ ] Configure alerts
- [ ] Start with paper trading
- [ ] Review and improve continuously

**Good luck with your machine learning stock prediction project! 🚀📈**