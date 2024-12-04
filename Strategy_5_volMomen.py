import yfinance as yf
import pandas as pd
import pandas_ta as ta
import bt
import numpy as np
from datetime import datetime

class VolumeWeightedMomentumStrategy(bt.Algo):
    def __init__(self, momentum_period=20, volume_period=20, weighting_factor=0.5):
        """
        거래량 가중 모멘텀 전략 초기화
        
        Parameters:
        momentum_period (int): 모멘텀 계산 기간
        volume_period (int): 거래량 평균 계산 기간
        weighting_factor (float): 거래량 가중치 계수 (0~1)
        """
        super(VolumeWeightedMomentumStrategy, self).__init__()
        self.momentum_period = momentum_period
        self.volume_period = volume_period
        self.weighting_factor = weighting_factor
        self.last_position = 0

    def __call__(self, target):
        # 현재 시점의 데이터 확인
        current = target.now

        try:
            # 현재 시점의 지표값 확인
            momentum_score = data.loc[current, 'momentum_score']
            volume_signal = data.loc[current, 'volume_signal']
            combined_signal = data.loc[current, 'combined_signal']
        except:
            return False

        # 포트폴리오 구성
        selected = target.universe.columns
        weights = pd.Series(0, index=selected)

        # 매매 신호 생성
        if combined_signal > 0:
            new_position = 1  # 매수 신호
        elif combined_signal < 0:
            new_position = -1  # 매도 신호
        else:
            new_position = 0  # 중립

        # 포지션 변경시에만 수수료 부과
        if new_position != self.last_position:
            target.temp['trade_commission'] = abs(new_position - self.last_position) * 0.0018
        else:
            target.temp['trade_commission'] = 0

        self.last_position = new_position
        weights[selected] = new_position
        target.temp['weights'] = weights

        return True

def calculate_signals(df, momentum_period=20, volume_period=20, weighting_factor=0.5):
    """
    거래량 가중 모멘텀 신호 계산
    
    Parameters:
    df (pandas.DataFrame): OHLCV 데이터
    momentum_period (int): 모멘텀 계산 기간
    volume_period (int): 거래량 평균 계산 기간
    weighting_factor (float): 거래량 가중치 계수
    
    Returns:
    pandas.DataFrame: 신호가 추가된 데이터프레임
    """
    # 모멘텀 스코어 계산 (수익률 기반)
    df['momentum'] = df['Close'].pct_change(momentum_period)
    
    # 거래량 신호 계산
    df['volume_ma'] = df['Volume'].rolling(window=volume_period).mean()
    df['volume_ratio'] = df['Volume'] / df['volume_ma']
    
    # 표준화된 모멘텀 스코어
    df['momentum_score'] = (df['momentum'] - df['momentum'].rolling(window=momentum_period).mean()) / \
                          df['momentum'].rolling(window=momentum_period).std()
    
    # 표준화된 거래량 신호
    df['volume_signal'] = (df['volume_ratio'] - 1) / df['volume_ratio'].rolling(window=volume_period).std()
    
    # 최종 매매 신호 계산 (모멘텀과 거래량 가중 결합)
    df['combined_signal'] = (1 - weighting_factor) * df['momentum_score'] + \
                           weighting_factor * df['volume_signal']
    
    return df

# 데이터 다운로드 및 전처리
ticker = yf.Ticker("BND")  # S&P 500 ETF
start_date = "2018-01-01"
end_date = "2024-12-01"
ohlcv = ticker.history(start=start_date, end=end_date)

# 신호 계산
data = calculate_signals(ohlcv, 
                        momentum_period=20, 
                        volume_period=20, 
                        weighting_factor=0.5)

# 백테스트 전략 설정
volume_momentum_strategy = bt.Strategy('Volume Weighted Momentum',
    [bt.algos.SelectAll(),
     VolumeWeightedMomentumStrategy(momentum_period=20, 
                                   volume_period=20, 
                                   weighting_factor=0.5),
     bt.algos.Rebalance()])

# 단순 매수후 보유 전략 설정
def buy_and_hold(data, name):
    strategy = bt.Strategy(name, [
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),
        bt.algos.RunOnce(),
        bt.algos.Rebalance()
    ])
    return bt.Backtest(strategy, data)

# 백테스트 실행
volume_momentum_backtest = bt.Backtest(volume_momentum_strategy, data[['Close']])
buy_hold = buy_and_hold(data[['Close']], 'Buy & Hold')
results = bt.run(volume_momentum_backtest, buy_hold)

# 연도별 수익률 계산
def calculate_annual_returns(results):
    daily_returns = results.prices.pct_change()
    annual_returns = {}
    
    for strategy in daily_returns.columns:
        strategy_returns = daily_returns[strategy] + 1
        by_year = strategy_returns.groupby(strategy_returns.index.year)
        yearly_returns = (by_year.prod() - 1) * 100
        annual_returns[strategy] = yearly_returns
    
    annual_returns_df = pd.DataFrame(annual_returns)
    
    if 'Volume Weighted Momentum' in annual_returns_df.columns:
        commission_factor = (1 - 0.0018)  # 수수료 0.18% 반영
        annual_returns_df['Volume Weighted Momentum (After Commission)'] = \
            annual_returns_df['Volume Weighted Momentum'] * commission_factor
    
    return annual_returns_df.round(2)

# 결과 출력
print("\n===== 백테스트 통계 =====")
print(results.stats)
print("\n===== 연도별 수익률(%) =====")
annual_returns = calculate_annual_returns(results)
print(annual_returns)

# 수익률 그래프 표시
results.plot(title='Volume Weighted Momentum vs Buy & Hold')
