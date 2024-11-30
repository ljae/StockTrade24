# 필요한 라이브러리 임포트
import yfinance as yf          # 야후 파이낸스에서 주가 데이터를 가져오는 라이브러리
import pandas as pd            # 데이터 분석을 위한 판다스 라이브러리
import pandas_ta as ta         # 기술적 분석 지표를 계산하는 라이브러리
import bt                      # 백테스팅(투자전략 성과분석)을 위한 라이브러리
import numpy as np             # 수치 계산을 위한 넘파이 라이브러리
from datetime import datetime  # 날짜 처리를 위한 라이브러리

# TQQQ(나스닥100 3배 레버리지 ETF) 데이터 다운로드
ticker = yf.Ticker("TQQQ")
start_date = "2018-01-22"
end_date = "2024-11-22"
ohlcv = ticker.history(start=start_date, end=end_date)  # OHLCV(시가,고가,저가,종가,거래량) 데이터 가져오기

# RSI(상대강도지수) 계산
data = ohlcv[['Close']].copy()  # 종가 데이터만 복사
data['RSI'] = ta.rsi(data['Close'], length=14)  # 14일 RSI 계산
# RSI 전략 클래스 정의
class RSIStrategy(bt.Algo):
    def __init__(self, rsi_upper=70, rsi_lower=30):  # RSI 상단(70)과 하단(30) 기준값 설정
        super(RSIStrategy, self).__init__()
        self.rsi_upper = rsi_upper
        self.rsi_lower = rsi_lower
        self.last_position = 0  # 이전 포지션 기록용
        
    def __call__(self, target):
        current = target.now  # 현재 시점
        try:
            rsi = data.loc[current, 'RSI']  # 현재 RSI 값 확인
        except:
            return False
            
        selected = target.universe.columns
        weights = pd.Series(0, index=selected)
        
        # RSI 값에 따른 매매 전략
        if rsi > self.rsi_upper:      # RSI가 70 초과시 과매수로 판단하여 매도(-1)
            new_position = -1
        elif rsi < self.rsi_lower:    # RSI가 30 미만시 과매도로 판단하여 매수(1)
            new_position = 1
        else:                         # 그 외는 중립(0)
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
# RSI 전략과 단순 매수후 보유 전략 설정
rsi_strategy = bt.Strategy('RSI Mean Reversion',
    [bt.algos.SelectAll(),                    # 모든 종목 선택
     RSIStrategy(rsi_upper=70, rsi_lower=30), # RSI 전략 적용
     bt.algos.Rebalance()])                   # 포트폴리오 리밸런싱

# 단순 매수후 보유 전략 함수
def buy_and_hold(data, name):
    bt_strategy = bt.Strategy(name, [
        bt.algos.SelectAll(),        # 모든 종목 선택
        bt.algos.WeighEqually(),     # 동일 비중으로 투자
        bt.algos.RunOnce(),          # 한번만 실행 (매수후 보유)
        bt.algos.Rebalance()         # 포트폴리오 리밸런싱
    ])
    return bt.Backtest(bt_strategy, data)
# 백테스트 실행 및 결과 분석
rsi_backtest = bt.Backtest(rsi_strategy, data[['Close']])
stock = buy_and_hold(data[['Close']], name='Buy & Hold')
results = bt.run(rsi_backtest, stock)

# 연도별 수익률 계산 함수
def calculate_annual_returns(results):
    daily_returns = results.prices.pct_change()           # 일별 수익률 계산
    annual_returns = {}
    
    for strategy in daily_returns.columns:
        strategy_returns = daily_returns[strategy] + 1
        by_year = strategy_returns.groupby(strategy_returns.index.year)
        yearly_returns = (by_year.prod() - 1) * 100      # 연간 수익률을 퍼센트로 계산
        annual_returns[strategy] = yearly_returns
        
    annual_returns_df = pd.DataFrame(annual_returns)
    
    # 수수료(0.18%) 반영
    if 'RSI Mean Reversion' in annual_returns_df.columns:
        commission_factor = (1 - 0.0018)
        annual_returns_df['RSI Mean Reversion (After Commission)'] = \
            annual_returns_df['RSI Mean Reversion'] * commission_factor
            
    return annual_returns_df.round(2)

# 결과 출력 및 시각화
print("\n===== 백테스트 통계 =====")
print(results.stats)
print("\n===== 연도별 수익률(%) =====")
annual_returns = calculate_annual_returns(results)
print(annual_returns)
results.plot(title='RSI Mean Reversion vs Buy & Hold')  # 수익률 그래프 표시
