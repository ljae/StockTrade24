import yfinance as yf
import pandas as pd
import pandas_ta as ta
import bt
import numpy as np
from datetime import datetime

# 데이터 다운로드
def get_stock_data(symbol, start_date, end_date):
    ticker = yf.Ticker(symbol)
    data = ticker.history(start=start_date, end=end_date)
    return data[['Close']]

# 이동평균선 교차 전략 클래스 정의
class MACrossStrategy(bt.Algo):
    def __init__(self, short_period=20, long_period=60):
        super(MACrossStrategy, self).__init__()
        self.short_period = short_period
        self.long_period = long_period
        self.last_position = 0
        
    def __call__(self, target):
        # 현재 시점
        current = target.now
        
        # 전체 데이터에서 현재 시점의 이동평균 확인
        try:
            short_ma = data.loc[current, f'SMA_{self.short_period}']
            long_ma = data.loc[current, f'SMA_{self.long_period}']
        except:
            return False
            
        selected = target.universe.columns
        weights = pd.Series(0, index=selected)
        
        # 이동평균선 교차 조건에 따른 매매 전략
        if short_ma > long_ma:  # 골든크로스: 단기선이 장기선을 상향돌파
            new_position = 1
        elif short_ma < long_ma:  # 데드크로스: 단기선이 장기선을 하향돌파
            new_position = -1
        else:
            new_position = 0
            
        # 포지션 변경시에만 수수료 부과
        if new_position != self.last_position:
            target.temp['trade_commission'] = abs(new_position - self.last_position) * 0.0015
        else:
            target.temp['trade_commission'] = 0
            
        self.last_position = new_position
        weights[selected] = new_position
        target.temp['weights'] = weights
        return True

# 메인 실행 코드
if __name__ == "__main__":
    # 테스트할 종목 및 기간 설정
    symbol = "005930.KS"  # 삼성전자
    start_date = "2020-01-01"
    end_date = "2024-02-29"
    
    # 데이터 준비
    data = get_stock_data(symbol, start_date, end_date)
    
    # 이동평균선 계산
    data['SMA_20'] = ta.sma(data['Close'], length=20)
    data['SMA_60'] = ta.sma(data['Close'], length=60)
    
    # 전략 설정
    ma_cross_strategy = bt.Strategy('MA Crossover',
        [bt.algos.SelectAll(),
         MACrossStrategy(short_period=20, long_period=60),
         bt.algos.Rebalance()])
    
    # 단순 매수후 보유 전략 (벤치마크용)
    def buy_and_hold(data, name):
        strategy = bt.Strategy(name, [
            bt.algos.SelectAll(),
            bt.algos.WeighEqually(),
            bt.algos.RunOnce(),
            bt.algos.Rebalance()
        ])
        return bt.Backtest(strategy, data)
    
    # 백테스트 실행
    ma_backtest = bt.Backtest(ma_cross_strategy, data)
    stock = buy_and_hold(data, name='Buy & Hold')
    results = bt.run(ma_backtest, stock)
    
    # 연간 수익률 계산 함수
    def calculate_annual_returns(results):
        daily_returns = results.prices.pct_change()
        annual_returns = {}
        
        for strategy in daily_returns.columns:
            strategy_returns = daily_returns[strategy] + 1
            by_year = strategy_returns.groupby(strategy_returns.index.year)
            yearly_returns = (by_year.prod() - 1) * 100
            annual_returns[strategy] = yearly_returns
            
        annual_returns_df = pd.DataFrame(annual_returns)
        
        # 수수료(0.03%) 반영
        if 'MA Crossover' in annual_returns_df.columns:
            commission_factor = (1 - 0.0003)
            annual_returns_df['MA Crossover (After Commission)'] = \
                annual_returns_df['MA Crossover'] * commission_factor
                
        return annual_returns_df.round(2)
    
    # 결과 출력
    print("\n===== 백테스트 통계 =====")
    print(results.stats)
    print("\n===== 연도별 수익률(%) =====")
    annual_returns = calculate_annual_returns(results)
    print(annual_returns)
    
    # 수익률 그래프 표시
    results.plot(title='MA Crossover vs Buy & Hold')
