import yfinance as yf
import pandas as pd
import pandas_ta as ta
import bt
import numpy as np
from datetime import datetime

def download_data(tickers_dict, start_date, end_date):
    """Download and prepare ETF price data"""
    data = pd.DataFrame()
    
    # US ETF data download
    for category, tickers in tickers_dict['US'].items():
        for ticker in tickers:
            try:
                ticker_data = yf.download(ticker, start=start_date, end=end_date)['Adj Close']
                if not ticker_data.empty:
                    data[f"US_{ticker}"] = ticker_data
                    print(f"Successfully downloaded {ticker}")
            except Exception as e:
                print(f"Error downloading US {ticker}: {e}")
    
    # Korean ETF data download
    for category, ticker in tickers_dict['KR'].items():
        try:
            ticker_data = yf.download(f"{ticker}.KS", start=start_date, end=end_date)['Adj Close']
            if not ticker_data.empty:
                data[f"KR_{ticker}"] = ticker_data
                print(f"Successfully downloaded {ticker}.KS")
        except Exception as e:
            print(f"Error downloading KR {ticker}: {e}")
    
    # Handle missing data
    data = data.ffill().bfill()
    
    if data.empty:
        raise ValueError("No data was downloaded. Please check the ticker symbols.")
    
    return data

class GlobalAllocationStrategy(bt.Algo):
    """Custom strategy for global ETF allocation"""
    def __init__(self, weights):
        super(GlobalAllocationStrategy, self).__init__()
        self.weights = weights
    
    def __call__(self, target):
        target.temp['weights'] = self.weights
        return True

def create_strategy(name, weights):
    """Create a strategy with quarterly rebalancing"""
    return bt.Strategy(name,
        [bt.algos.RunQuarterly(),
         bt.algos.SelectAll(),
         GlobalAllocationStrategy(weights),
         bt.algos.Rebalance()])

def calculate_metrics(results):
    """Calculate detailed performance metrics"""
    metrics = pd.DataFrame(index=results.stats.index)
    
    for strategy in results.stats.index:
        metrics.loc[strategy, 'CAGR'] = f"{results.stats.loc[strategy, 'cagr']:.2%}"
        metrics.loc[strategy, 'Volatility'] = f"{results.stats.loc[strategy, 'yearly_vol']:.2%}"
        metrics.loc[strategy, 'Sharpe Ratio'] = f"{results.stats.loc[strategy, 'yearly_sharpe']:.2f}"
        metrics.loc[strategy, 'Max Drawdown'] = f"{results.stats.loc[strategy, 'max_drawdown']:.2%}"
        metrics.loc[strategy, 'Return/Risk'] = f"{results.stats.loc[strategy, 'calmar']:.2f}"
    
    return metrics

def calculate_annual_returns(results):
    """Calculate annual returns for each strategy"""
    daily_returns = results.prices.pct_change()
    annual_returns = {}
    
    for strategy in daily_returns.columns:
        strategy_returns = daily_returns[strategy] + 1
        by_year = strategy_returns.groupby(strategy_returns.index.year)
        yearly_returns = (by_year.prod() - 1) * 100
        annual_returns[strategy] = yearly_returns
    
    annual_df = pd.DataFrame(annual_returns).round(2)
    means = annual_df.mean().round(2)
    annual_df.loc['Average'] = means
    
    return annual_df

def run_backtest():
    # Define ETF tickers
    tickers = {
        'US': {
            'global': ['VT', 'ACWI'],
            'emerging': ['VWO', 'EEM'],
            'tech': ['VGT', 'QQQ']
        },
        'KR': {
            'global': '371460',
            'emerging': '195980',
            'tech': '133690'
        }
    }
    
    # Set time period
    start_date = "2018-01-01"
    end_date = "2024-11-22"
    
    print("Downloading data...")
    data = download_data(tickers, start_date, end_date)
    
    # Set portfolio weights
    us_weights = pd.Series({
        'US_VT': 0.2, 'US_ACWI': 0.2,  # Global stocks 40%
        'US_VWO': 0.15, 'US_EEM': 0.15,  # Emerging markets 30%
        'US_VGT': 0.15, 'US_QQQ': 0.15   # Tech stocks 30%
    })
    
    kr_weights = pd.Series({
        'KR_371460': 0.4,  # Global stocks 40%
        'KR_195980': 0.3,  # Emerging markets 30%
        'KR_133690': 0.3   # Tech stocks 30%
    })
    
    # Define trading costs
    us_commission = lambda q, p: max(0, abs(q) * 0.0018)  # US ETF fee: 0.18%
    kr_commission = lambda q, p: max(0, abs(q) * 0.0003)  # KR ETF fee: 0.03%
    
    # Create and run backtests
    us_strategy = create_strategy('US Global ETF Portfolio', us_weights)
    kr_strategy = create_strategy('KR Global ETF Portfolio', kr_weights)
    
    us_backtest = bt.Backtest(us_strategy, data, commissions=us_commission)
    kr_backtest = bt.Backtest(kr_strategy, data, commissions=kr_commission)
    
    return bt.run(us_backtest, kr_backtest)

if __name__ == "__main__":
    try:
        print("\n=== Starting Backtest ===")
        results = run_backtest()
        
        print("\n=== Basic Statistics ===")
        print(results.stats)
        
        print("\n=== Annual Returns (%) ===")
        annual_returns = calculate_annual_returns(results)
        print(annual_returns)
        
        print("\n=== Detailed Metrics ===")
        detailed_metrics = calculate_metrics(results)
        print(detailed_metrics)
        
        # Plot results
        results.plot(title='US vs KR Global ETF Portfolio Performance',
                    legend=True,
                    figsize=(12, 6))
        
        results.plot_drawdown(title='Portfolio Drawdown Comparison',
                            legend=True,
                            figsize=(12, 6))
                            
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        print("\nProblem occurred during data download or processing.")
        print("Please check ticker symbols and try again.")
