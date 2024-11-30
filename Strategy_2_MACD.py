import yfinance as yf
import pandas as pd
import pandas_ta as ta
import bt
import numpy as np
from datetime import datetime

# 데이터 다운로드
ticker = yf.Ticker("AGG")
start_date = "2018-01-01"
end_date = "2024-11-30"
ohlcv = ticker.history(start=start_date, end=end_date)

# MACD 계산을 위한 데이터프레임 준비
data = ohlcv[['Close']].copy()

# MACD 계산 (12,26,9)
macd = ta.macd(data['Close'], fast=12, slow=26, signal=9)
data['MACD'] = macd['MACD_12_26_9']
data['Signal'] = macd['MACDs_12_26_9']
data['MACD_Hist'] = macd['MACDh_12_26_9']

# MACD 전략 클래스 정의
class MACDStrategy(bt.Algo):
    def __init__(self):
        super(MACDStrategy, self).__init__()
        self.last_position = 0
        
    def __call__(self, target):
        current = target.now
        
        try:
            macd_val = data.loc[current, 'MACD']
            signal_val = data.loc[current, 'Signal']
            prev_macd = data.shift(1).loc[current, 'MACD']
            prev_signal = data.shift(1).loc[current, 'Signal']
        except:
            return False
            
        selected = target.universe.columns
        weights = pd.Series(0, index=selected)
        
        # MACD 크로스오버 전략
        if macd_val > signal_val and prev_macd <= prev_signal:  # 골든크로스: 매수
            new_position = 1
        elif macd_val < signal_val and prev_macd >= prev_signal:  # 데드크로스: 매도
            new_position = -1
        else:
            new_position = self.last_position  # 현재 포지션 유지
            
        # 거래 수수료 계산 (포지션 변경시에만)
        if new_position != self.last_position:
            target.temp['trade_commission'] = abs(new_position - self.last_position) * 0.0018
        else:
            target.temp['trade_commission'] = 0
            
        self.last_position = new_position
        weights[selected] = new_position
        target.temp['weights'] = weights
        
        return True

# MACD 전략과 단순 매수후 보유 전략 설정
macd_strategy = bt.Strategy('MACD Strategy',
    [bt.algos.SelectAll(),
     MACDStrategy(),
     bt.algos.Rebalance()])

# 단순 매수후 보유 전략 함수
def buy_and_hold(data, name):
    bt_strategy = bt.Strategy(name, [
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),
        bt.algos.RunOnce(),
        bt.algos.Rebalance()
    ])
    return bt.Backtest(bt_strategy, data)

# 백테스트 실행
macd_backtest = bt.Backtest(macd_strategy, data[['Close']])
stock = buy_and_hold(data[['Close']], name='Buy & Hold')
results = bt.run(macd_backtest, stock)

# 연도별 수익률 계산 함수
def calculate_annual_returns(results):
    daily_returns = results.prices.pct_change()
    annual_returns = {}
    
    for strategy in daily_returns.columns:
        strategy_returns = daily_returns[strategy] + 1
        by_year = strategy_returns.groupby(strategy_returns.index.year)
        yearly_returns = (by_year.prod() - 1) * 100
        annual_returns[strategy] = yearly_returns
        
    annual_returns_df = pd.DataFrame(annual_returns)
    
    # 수수료 반영
    if 'MACD Strategy' in annual_returns_df.columns:
        commission_factor = (1 - 0.0018)
        annual_returns_df['MACD Strategy (After Commission)'] = \
            annual_returns_df['MACD Strategy'] * commission_factor
            
    return annual_returns_df.round(2)

# 결과 출력 및 시각화
print("\n===== 백테스트 통계 =====")
print(results.stats)
print("\n===== 연도별 수익률(%) =====")
annual_returns = calculate_annual_returns(results)
print(annual_returns)
results.plot(title='MACD Strategy vs Buy & Hold')
