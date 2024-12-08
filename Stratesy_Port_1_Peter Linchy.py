import yfinance as yf
import pandas as pd
import pandas_ta as ta
import bt
import numpy as np
from datetime import datetime

def download_data(tickers_dict, start_date, end_date):
    data = pd.DataFrame()
    
    # 미국 ETF 데이터 다운로드
    for category, ticker in tickers_dict['US'].items():
        try:
            ticker_data = yf.download(ticker, start=start_date, end=end_date)['Adj Close']
            if not ticker_data.empty:
                data[f"US_{ticker}"] = ticker_data
                print(f"Successfully downloaded {ticker}")
        except Exception as e:
            print(f"Error downloading US {ticker}: {e}")
    
    # 한국 ETF 데이터 다운로드
    for category, ticker in tickers_dict['KR'].items():
        try:
            ticker_data = yf.download(f"{ticker}.KS", start=start_date, end=end_date)['Adj Close']
            if not ticker_data.empty:
                data[f"KR_{ticker}"] = ticker_data
                print(f"Successfully downloaded {ticker}.KS")
        except Exception as e:
            print(f"Error downloading KR {ticker}: {e}")
    
    # 결측치 처리
    data = data.ffill()
    
    # 데이터가 있는지 확인
    if data.empty:
        raise ValueError("No data was downloaded. Please check the ticker symbols.")
    
    return data

class StaticAllocationStrategy(bt.Algo):
    def __init__(self, weights):
        super(StaticAllocationStrategy, self).__init__()
        self.weights = weights
    
    def __call__(self, target):
        target.temp['weights'] = self.weights
        return True

def create_strategy(name, weights):
    return bt.Strategy(name,
        [bt.algos.RunQuarterly(),
         bt.algos.SelectAll(),
         StaticAllocationStrategy(weights),
         bt.algos.Rebalance()])

def run_backtest():
    # ETF 티커 정의 (실제 거래되는 티커 심볼로 수정)
    tickers = {
        'US': {
            'sp500': 'SPY',       # SPDR S&P 500 ETF
            'dividend': 'VYM',     # Vanguard High Dividend Yield ETF
            'bond': 'AGG'         # iShares Core U.S. Aggregate Bond ETF
        },
        'KR': {
            'sp500': '069500',    # KODEX 200
            'dividend': '279530',  # KODEX 고배당
            'bond': '114820'      # KBSTAR 중기국고채
        }
    }
    
    # 데이터 다운로드
    start_date = "2018-01-01"
    end_date = "2024-11-22"
    
    print("Downloading data...")
    data = download_data(tickers, start_date, end_date)
    print("Data shape:", data.shape)
    print("Available columns:", data.columns.tolist())
    
    # 결측치 확인
    missing_data = data.isnull().sum()
    if missing_data.any():
        print("\nMissing data count:")
        print(missing_data[missing_data > 0])
    
    # 포트폴리오 가중치 설정
    us_weights = pd.Series({
        f"US_{tickers['US']['sp500']}": 0.4,
        f"US_{tickers['US']['dividend']}": 0.3,
        f"US_{tickers['US']['bond']}": 0.3
    })
    
    kr_weights = pd.Series({
        f"KR_{tickers['KR']['sp500']}": 0.4,
        f"KR_{tickers['KR']['dividend']}": 0.3,
        f"KR_{tickers['KR']['bond']}": 0.3
    })
    
    # 수수료 함수 정의
    us_commission = lambda q, p: max(0, abs(q) * 0.0018)  # 미국 ETF 수수료: 0.18%
    kr_commission = lambda q, p: max(0, abs(q) * 0.0003)  # 한국 ETF 수수료: 0.03%
    
    # 전략 생성 및 백테스트 실행
    us_strategy = create_strategy('US ETF Portfolio', us_weights)
    kr_strategy = create_strategy('KR ETF Portfolio', kr_weights)
    
    us_backtest = bt.Backtest(us_strategy, data, commissions=us_commission)
    kr_backtest = bt.Backtest(kr_strategy, data, commissions=kr_commission)
    
    res = bt.run(us_backtest, kr_backtest)
    return res

def calculate_annual_returns(results):
    daily_returns = results.prices.pct_change()
    annual_returns = {}
    
    for strategy in daily_returns.columns:
        strategy_returns = daily_returns[strategy] + 1
        by_year = strategy_returns.groupby(strategy_returns.index.year)
        yearly_returns = (by_year.prod() - 1) * 100
        annual_returns[strategy] = yearly_returns
    
    annual_df = pd.DataFrame(annual_returns).round(2)
    
    # 연평균 수익률 추가
    means = annual_df.mean().round(2)
    annual_df.loc['Average'] = means
    
    return annual_df

def calculate_detailed_metrics(results):
    metrics = pd.DataFrame(index=results.stats.index)
    
    for strategy in results.stats.index:
        metrics.loc[strategy, '연평균 수익률(CAGR)'] = f"{results.stats.loc[strategy, 'cagr']:.2%}"
        metrics.loc[strategy, '변동성'] = f"{results.stats.loc[strategy, 'yearly_vol']:.2%}"
        metrics.loc[strategy, '샤프비율'] = f"{results.stats.loc[strategy, 'yearly_sharpe']:.2f}"
        metrics.loc[strategy, '최대낙폭'] = f"{results.stats.loc[strategy, 'max_drawdown']:.2%}"
        metrics.loc[strategy, '수익률/위험'] = f"{results.stats.loc[strategy, 'calmar']:.2f}"
    
    return metrics

if __name__ == "__main__":
    try:
        # 백테스트 실행
        print("\n=== 백테스트 시작 ===")
        results = run_backtest()
        
        # 기본 통계 출력
        print("\n=== 백테스트 기본 통계 ===")
        print(results.stats)
        
        # 연도별 수익률 출력
        print("\n=== 연도별 수익률(%) ===")
        annual_returns = calculate_annual_returns(results)
        print(annual_returns)
        
        # 상세 지표 출력
        print("\n=== 상세 성과 지표 ===")
        detailed_metrics = calculate_detailed_metrics(results)
        print(detailed_metrics)
        
        # 수익률 그래프
        results.plot(title='미국 vs 한국 ETF 포트폴리오 성과 비교',
                    legend=True,
                    figsize=(12, 6))
        
        # 드로다운 그래프
        results.plot_drawdown(title='포트폴리오 낙폭 비교',
                            legend=True,
                            figsize=(12, 6))
                            
    except Exception as e:
        print(f"\n오류 발생: {str(e)}")
        print("\n데이터 다운로드나 처리 과정에서 문제가 발생했습니다.")
        print("티커 심볼을 확인하고 다시 시도해주세요.")
