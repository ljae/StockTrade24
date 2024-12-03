import yfinance as yf
import pandas as pd
import pandas_ta as ta
import bt
import numpy as np
from datetime import datetime

# 볼린저밴드 전략 클래스 정의
class BollingerStrategy(bt.Algo):
    def __init__(self, bb_length=20, bb_std=2.0):
        super(BollingerStrategy, self).__init__()
        self.bb_length = bb_length  # 기간 설정 (기본 20일)
        self.bb_std = bb_std        # 표준편차 배수 설정 (기본 2배)
        self.last_position = 0      # 이전 포지션 기록용
        
    def __call__(self, target):
        current = target.now  # 현재 시점
        
        try:
            # 현재 볼린저밴드 값들 확인
            current_price = data.loc[current, 'Close']
            upper_band = data.loc[current, 'Upper_Band']
            lower_band = data.loc[current, 'Lower_Band']
        except:
            return False
            
        selected = target.universe.columns
        weights = pd.Series(0, index=selected)
        
        # 볼린저밴드 기반 매매 전략
        if current_price < lower_band:     # 하단밴드 아래로 진입시 매수(1)
            new_position = 1
        elif current_price > upper_band:   # 상단밴드 위로 진입시 매도(-1)
            new_position = -1
        else:                             # 밴드 내부에서는 중립(0)
            new_position = 0
            
        # 포지션 변경시에만 수수료(0.18%) 부과
        if new_position != self.last_position:
            target.temp['trade_commission'] = abs(new_position - self.last_position) * 0.0018
        else:
            target.temp['trade_commission'] = 0
            
        self.last_position = new_position
        weights[selected] = new_position
        target.temp['weights'] = weights
        return True

# 데이터 준비 함수
def prepare_data(ticker, start_date, end_date):
    # 주가 데이터 다운로드
    stock = yf.Ticker(ticker)
    data = stock.history(start=start_date, end=end_date)[['Close']]
    
    # 볼린저밴드 계산
    bb = ta.bbands(data['Close'], length=20, std=2)
    data['Middle_Band'] = bb['BBM_20_2.0']
    data['Upper_Band'] = bb['BBU_20_2.0']
    data['Lower_Band'] = bb['BBL_20_2.0']
    
    return data

def calculate_annual_returns(results):
    """연도별 수익률 계산 함수"""
    daily_returns = results.prices.pct_change()
    annual_returns = {}
    
    for strategy in daily_returns.columns:
        strategy_returns = daily_returns[strategy] + 1
        by_year = strategy_returns.groupby(strategy_returns.index.year)
        yearly_returns = (by_year.prod() - 1) * 100
        annual_returns[strategy] = yearly_returns
        
    annual_returns_df = pd.DataFrame(annual_returns)
    
    # 수수료 반영
    if 'Bollinger Bands Strategy' in annual_returns_df.columns:
        commission_factor = (1 - 0.0018)
        annual_returns_df['Bollinger Bands (After Commission)'] = \
            annual_returns_df['Bollinger Bands Strategy'] * commission_factor
            
    return annual_returns_df.round(2)

# 메인 실행 코드
if __name__ == "__main__":
    # 백테스트 기간 설정
    start_date = "2018-01-01"
    end_date = "2024-11-30"
    
    # TQQQ 데이터 준비
    data = prepare_data("TQQQ", start_date, end_date)
    
    # 볼린저밴드 전략 설정
    bollinger_strategy = bt.Strategy('Bollinger Bands Strategy',
        [bt.algos.SelectAll(),
         BollingerStrategy(bb_length=20, bb_std=2.0),
         bt.algos.Rebalance()])
    
    # 단순 매수후 보유 전략
    def buy_and_hold(data, name):
        strategy = bt.Strategy(name, [
            bt.algos.SelectAll(),
            bt.algos.WeighEqually(),
            bt.algos.RunOnce(),
            bt.algos.Rebalance()
        ])
        return bt.Backtest(strategy, data)
    
    # 백테스트 실행
    bollinger_backtest = bt.Backtest(bollinger_strategy, data[['Close']])
    buy_hold = buy_and_hold(data[['Close']], 'Buy & Hold')
    results = bt.run(bollinger_backtest, buy_hold)
    
    # 결과 출력
    print("\n===== 백테스트 통계 =====")
    print(results.stats)
    print("\n===== 연도별 수익률(%) =====")
    annual_returns = calculate_annual_returns(results)
    print(annual_returns)
    
    # 그래프 표시
    results.plot(title='Bollinger Bands Strategy vs Buy & Hold')
