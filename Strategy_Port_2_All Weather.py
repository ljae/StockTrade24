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
    
    # 결측치 전일 데이터로 채우기
    data = data.ffill()
    
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
        [bt.algos.RunQuarterly(),  # 분기별 리밸런싱
         bt.algos.SelectAll(),
         StaticAllocationStrategy(weights),
         bt.algos.Rebalance()])

def run_inflation_portfolio_backtest():
    # ETF 티커 정의
    tickers = {
        'US': {
            'tips': 'TIP',      # TIPS ETF
            'commodity': 'DBC',  # 원자재 ETF
            'gold': 'GLD',      # 금 ETF
            'reit': 'VNQ'       # 리츠 ETF
        },
        'KR': {
            'tips': '305080',    # KBSTAR 국고채TIPS
            'commodity': '261220', # KODEX 원자재
            'gold': '132030',     # KODEX 골드선물
            'reit': '329200'      # TIGER 리츠부동산
        }
    }
    
    # 데이터 다운로드 (5년치)
    start_date = "2023-01-01"
    end_date = "2024-12-02"
    
    print("Downloading data...")
    data = download_data(tickers, start_date, end_date)
    print("Data shape:", data.shape)
    print("Available columns:", data.columns.tolist())
    
    # 결측치 확인 및 보고
    missing_data = data.isnull().sum()
    if missing_data.any():
        print("\nMissing data count:")
        print(missing_data[missing_data > 0])
    
    # 포트폴리오 가중치 설정
    us_weights = pd.Series({
        f"US_{tickers['US']['tips']}": 0.3,       # TIPS 30%
        f"US_{tickers['US']['commodity']}": 0.2,   # 원자재 20%
        f"US_{tickers['US']['gold']}": 0.2,        # 금 20%
        f"US_{tickers['US']['reit']}": 0.3         # 리츠 30%
    })
    
    kr_weights = pd.Series({
        f"KR_{tickers['KR']['tips']}": 0.3,       # TIPS 30%
        f"KR_{tickers['KR']['commodity']}": 0.2,   # 원자재 20%
        f"KR_{tickers['KR']['gold']}": 0.2,        # 금 20%
        f"KR_{tickers['KR']['reit']}": 0.3         # 리츠 30%
    })
    
    # 수수료 설정
    us_commission = lambda q, p: max(0, abs(q) * 0.0018)  # 미국 ETF 수수료: 0.18%
    kr_commission = lambda q, p: max(0, abs(q) * 0.0003)  # 한국 ETF 수수료: 0.03%
    
    # 전략 생성 및 백테스트 실행
    us_strategy = create_strategy('US Inflation Portfolio', us_weights)
    kr_strategy = create_strategy('KR Inflation Portfolio', kr_weights)
    
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
    """
    백테스트 결과의 상세 지표를 계산하는 함수
    예외 처리를 강화하고 결과 포맷을 개선했습니다.
    """
    try:
        metrics = pd.DataFrame(index=results.stats.index)
        
        for strategy in results.stats.index:
            try:
                cagr = results.stats.loc[strategy, 'cagr']
                vol = results.stats.loc[strategy, 'yearly_vol']
                sharpe = results.stats.loc[strategy, 'daily_sharpe']
                max_dd = results.stats.loc[strategy, 'max_drawdown']
                calmar = results.stats.loc[strategy, 'calmar']
                
                metrics.loc[strategy, '연평균 수익률(CAGR)'] = f"{cagr*100:.2f}%"
                metrics.loc[strategy, '변동성'] = f"{vol*100:.2f}%" if not np.isnan(vol) else "N/A"
                metrics.loc[strategy, '샤프비율'] = f"{sharpe:.2f}"
                metrics.loc[strategy, '최대낙폭'] = f"{max_dd*100:.2f}%"
                metrics.loc[strategy, '수익률/위험'] = f"{calmar:.2f}"
                
            except KeyError as e:
                print(f"Warning: Missing metric for {strategy}: {e}")
                metrics.loc[strategy] = "N/A"
                
        return metrics
        
    except Exception as e:
        print(f"Error in calculate_detailed_metrics: {e}")
        return pd.DataFrame({"Error": "Failed to calculate metrics"})

def run_inflation_portfolio_backtest():
    # ETF 티커 정의
    tickers = {
        'US': {
            'tips': 'TIP',      # TIPS ETF
            'commodity': 'DBC',  # 원자재 ETF
            'gold': 'GLD',      # 금 ETF
            'reit': 'VNQ'       # 리츠 ETF
        },
        'KR': {
            'tips': '305080',    # KBSTAR 국고채TIPS
            'commodity': '261220', # KODEX 원자재
            'gold': '132030',     # KODEX 골드선물
            'reit': '329200'      # TIGER 리츠부동산
        }
    }
    
    try:
        # 데이터 다운로드 (2년치)
        start_date = "2023-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        print("Downloading data...")
        data = download_data(tickers, start_date, end_date)
        
        if data.empty:
            raise ValueError("No data available for analysis")
            
        print("Data shape:", data.shape)
        print("Available columns:", data.columns.tolist())
        
        # 결측치 확인 및 처리
        missing_data = data.isnull().sum()
        if missing_data.any():
            print("\nMissing data count:")
            print(missing_data[missing_data > 0])
            # 결측치가 너무 많은 경우 경고
            if (missing_data / len(data) > 0.1).any():
                print("Warning: Some assets have more than 10% missing data")
        
        # 포트폴리오 가중치 설정
        us_weights = pd.Series({
            f"US_{tickers['US']['tips']}": 0.3,       # TIPS 30%
            f"US_{tickers['US']['commodity']}": 0.2,   # 원자재 20%
            f"US_{tickers['US']['gold']}": 0.2,        # 금 20%
            f"US_{tickers['US']['reit']}": 0.3         # 리츠 30%
        })
        
        kr_weights = pd.Series({
            f"KR_{tickers['KR']['tips']}": 0.3,       # TIPS 30%
            f"KR_{tickers['KR']['commodity']}": 0.2,   # 원자재 20%
            f"KR_{tickers['KR']['gold']}": 0.2,        # 금 20%
            f"KR_{tickers['KR']['reit']}": 0.3         # 리츠 30%
        })
        
        # 수수료 설정
        us_commission = lambda q, p: max(0, abs(q) * 0.0018)  # 미국 ETF 수수료: 0.18%
        kr_commission = lambda q, p: max(0, abs(q) * 0.0003)  # 한국 ETF 수수료: 0.03%
        
        # 전략 생성 및 백테스트 실행
        us_strategy = create_strategy('US Inflation Portfolio', us_weights)
        kr_strategy = create_strategy('KR Inflation Portfolio', kr_weights)
        
        us_backtest = bt.Backtest(us_strategy, data, commissions=us_commission)
        kr_backtest = bt.Backtest(kr_strategy, data, commissions=kr_commission)
        
        res = bt.run(us_backtest, kr_backtest)
        return res
        
    except Exception as e:
        print(f"Error in backtest: {e}")
        raise

if __name__ == "__main__":
    try:
        # 백테스트 실행
        print("\n=== 인플레이션 대응 포트폴리오 백테스트 시작 ===")
        results = run_inflation_portfolio_backtest()
        
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
        results.plot(title='미국 vs 한국 인플레이션 대응 포트폴리오 성과 비교',
                    legend=True,
                    figsize=(12, 6))
        
        # 드로다운 그래프
        results.plot_drawdown(title='포트폴리오 낙폭 비교',
                            legend=True,
                            figsize=(12, 6))
                            
    except Exception as e:
        print(f"\n오류 발생: {e}")
        print("\n문제 해결을 위한 제안:")
        print("1. 티커 심볼이 정확한지 확인")
        print("2. 데이터 기간이 적절한지 확인")
        print("3. 모든 ETF가 해당 기간 동안 거래되었는지 확인")
        print("4. 인터넷 연결 상태 확인")
