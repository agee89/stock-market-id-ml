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
    timestamp TIMESTAMP NOT NULL,
    interval VARCHAR(10) NOT NULL DEFAULT '1d',
    open DECIMAL(15,2),
    high DECIMAL(15,2),
    low DECIMAL(15,2),
    close DECIMAL(15,2),
    volume BIGINT,
    adj_close DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, timestamp, interval)
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(url)
);

-- Table: predictions
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    prediction_date TIMESTAMP NOT NULL,
    target_date DATE NOT NULL,
    predicted_direction VARCHAR(10),
    predicted_change_pct DECIMAL(10,4),
    predicted_price DECIMAL(15,2),
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
    actual_price DECIMAL(15,2),
    is_correct BOOLEAN,
    error_pct DECIMAL(10,4),
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prediction_id)
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
    timeframe VARCHAR(10) DEFAULT '1d',
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
CREATE INDEX idx_stock_prices_stock_ts ON stock_prices(stock_id, timestamp DESC);
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
