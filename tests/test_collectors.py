import pytest
from unittest.mock import MagicMock, patch
from src.data_collection.stock_collector import StockCollector

@pytest.fixture
def mock_db():
    return MagicMock()

def test_stock_collector_initialization(mock_db):
    collector = StockCollector(mock_db)
    assert collector.db == mock_db
    assert len(collector.symbols) > 0

@patch("src.data_collection.stock_collector.yf.Ticker")
def test_fetch_history(mock_ticker, mock_db):
    # Setup mock
    mock_ticker_instance = MagicMock()
    mock_ticker.return_value = mock_ticker_instance
    
    # Mock history dataframe
    import pandas as pd
    data = {
        'Open': [1000], 'High': [1100], 'Low': [900], 'Close': [1050], 'Volume': [1000000]
    }
    df = pd.DataFrame(data)
    # df.index should be dates
    df.index = pd.to_datetime(['2023-01-01'])
    mock_ticker_instance.history.return_value = df

    # Mock DB execution
    mock_db.execute.return_value.fetchone.return_value = [1] # Return stock_id 1

    collector = StockCollector(mock_db)
    collector.fetch_history("BBCA.JK", days=1)

    # Verify interactions
    mock_ticker.assert_called_with("BBCA.JK")
    assert mock_ticker_instance.history.called
    assert mock_db.execute.call_count >= 2 # 1 for select id, 1 for insert
    mock_db.commit.assert_called()
