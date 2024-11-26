# StockTrade24.com
# 한국투자증권 API를 활용한 국내 주식 자동매매 프로그램
# 작성자: StockTrade24
# 최종수정일: 2024.11.23

# 필요한 라이브러리들을 불러옵니다
import requests  # 인터넷을 통해 API 요청을 보내기 위한 라이브러리
import json     # API 응답을 처리하기 위한 JSON 데이터 처리 라이브러리
import datetime # 날짜와 시간을 다루기 위한 라이브러리
import time     # 프로그램 실행 중 일시 정지를 위한 라이브러리
import yaml     # 설정 파일을 읽기 위한 라이브러리

# 설정 파일(config.yaml)에서 필요한 값들을 불러옵니다.
# config.yaml 파일에는 API 키, 계좌번호 등 중요 정보가 저장되어 있습니다.
with open('config.yaml', encoding='UTF-8') as f:  # 설정 파일을 열고
    _cfg = yaml.load(f, Loader=yaml.FullLoader)   # 파일 내용을 읽어옵니다
    
# 설정 파일에서 읽어온 값들을 변수에 저장합니다
APP_KEY = _cfg['APP_KEY']        # 한국투자증권에서 발급받은 API 앱키
APP_SECRET = _cfg['APP_SECRET']  # 한국투자증권에서 발급받은 API 시크릿키
ACCESS_TOKEN = ""                # API 접근 토큰 (프로그램 실행시 발급됨)
CANO = _cfg['CANO']             # 계좌번호
ACNT_PRDT_CD = _cfg['ACNT_PRDT_CD']  # 계좌상품코드
DISCORD_WEBHOOK_URL = _cfg['DISCORD_WEBHOOK_URL']  # 디스코드 웹훅 URL (알림 발송용)
URL_BASE = _cfg['URL_BASE']     # API 기본 주소

def send_message(msg):
    """
    디스코드로 메시지를 전송하는 함수입니다.
    매매 결과와 에러 등 중요 정보를 실시간으로 받아볼 수 있습니다.
    
    사용법: send_message("매수 성공!")
    
    Parameters:
        msg (str): 전송할 메시지 내용
    """
    now = datetime.datetime.now()  # 현재 시간을 가져옵니다
    # 메시지 형식을 만듭니다 - [시간] 메시지내용
    message = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(msg)}"}
    # 디스코드로 메시지를 전송합니다
    requests.post(DISCORD_WEBHOOK_URL, data=message)
    print(message)  # 콘솔에도 같은 메시지를 출력합니다

def get_access_token():
    """
    한국투자증권 API 접근 토큰을 발급받는 함수입니다.
    토큰은 하루동안 유효하며, 매일 한번만 발급받으면 됩니다.
    
    Returns:
        str: 발급받은 접근 토큰
    """
    # API 요청에 필요한 헤더와 데이터를 설정합니다
    headers = {"content-type":"application/json"}
    body = {
        "grant_type":"client_credentials",
        "appkey":APP_KEY, 
        "appsecret":APP_SECRET
    }
    PATH = "oauth2/tokenP"
    URL = f"{URL_BASE}/{PATH}"
    
    # API 요청을 보내고 응답을 받습니다
    res = requests.post(URL, headers=headers, data=json.dumps(body))
    # 응답에서 접근 토큰을 추출하여 반환합니다
    ACCESS_TOKEN = res.json()["access_token"]
    return ACCESS_TOKEN

def hashkey(datas):
    """
    한국투자증권 API에서 사용하는 해시키를 발급받는 함수입니다.
    주문과 같은 중요 API 호출시 필요한 보안 키입니다.
    
    Parameters:
        datas (dict): 해시키를 발급받을 데이터
        
    Returns:
        str: 발급받은 해시키
    """
    PATH = "uapi/hashkey"
    URL = f"{URL_BASE}/{PATH}"
    headers = {
        'content-Type' : 'application/json',
        'appKey' : APP_KEY,
        'appSecret' : APP_SECRET,
    }
    # 해시키를 요청하고 응답을 받아 반환합니다
    res = requests.post(URL, headers=headers, data=json.dumps(datas))
    hashkey = res.json()["HASH"]
    return hashkey

def get_current_price(code="005930"):
    """
    특정 종목의 현재가를 조회하는 함수입니다.
    
    사용법: current_price = get_current_price("005930")  # 삼성전자의 현재가 조회
    
    Parameters:
        code (str): 종목코드 (기본값: 삼성전자 005930)
        
    Returns:
        int: 현재가
    """
    PATH = "uapi/domestic-stock/v1/quotations/inquire-price"
    URL = f"{URL_BASE}/{PATH}"
    headers = {
        "Content-Type":"application/json", 
        "authorization": f"Bearer {ACCESS_TOKEN}",
        "appKey":APP_KEY,
        "appSecret":APP_SECRET,
        "tr_id":"FHKST01010100"
    }
    params = {
        "fid_cond_mrkt_div_code":"J",
        "fid_input_iscd":code,
    }
    # API로 현재가를 요청하고 응답을 받아 반환합니다
    res = requests.get(URL, headers=headers, params=params)
    return int(res.json()['output']['stck_prpr'])

def get_target_price(code="005930"):
    """
    특정 종목의 매수 목표가를 계산하는 함수입니다.
    변동성 돌파 전략을 사용합니다.
    
    전일 고가와 저가의 차이(변동폭)를 계산하고,
    당일 시가에 변동폭의 0.5배를 더해 목표가를 정합니다.
    
    사용법: target_price = get_target_price("005930")  # 삼성전자의 목표가 계산
    
    Parameters:
        code (str): 종목코드 (기본값: 삼성전자 005930)
        
    Returns:
        float: 매수 목표가
    """
    PATH = "uapi/domestic-stock/v1/quotations/inquire-daily-price"
    URL = f"{URL_BASE}/{PATH}"
    headers = {
        "Content-Type":"application/json", 
        "authorization": f"Bearer {ACCESS_TOKEN}",
        "appKey":APP_KEY,
        "appSecret":APP_SECRET,
        "tr_id":"FHKST01010400"
    }
    params = {
        "fid_cond_mrkt_div_code":"J",
        "fid_input_iscd":code,
        "fid_org_adj_prc":"1",
        "fid_period_div_code":"D"
    }
    # API로 가격 정보를 요청합니다
    res = requests.get(URL, headers=headers, params=params)
    
    # 오늘 시가와 전일 고가/저가를 조회합니다
    stck_oprc = int(res.json()['output'][0]['stck_oprc']) # 오늘 시가
    stck_hgpr = int(res.json()['output'][1]['stck_hgpr']) # 전일 고가
    stck_lwpr = int(res.json()['output'][1]['stck_lwpr']) # 전일 저가
    
    # 변동성 돌파 전략으로 목표가를 계산합니다
    # (당일 시가 + (전일 고가 - 전일 저가) * 0.5)
    target_price = stck_oprc + (stck_hgpr - stck_lwpr) * 0.5
    return target_price

def get_stock_balance():
    """
    보유중인 주식 잔고를 조회하는 함수입니다.
    
    Returns:
        dict: 보유 종목 코드와 수량을 담은 딕셔너리
    """
    PATH = "uapi/domestic-stock/v1/trading/inquire-balance"
    URL = f"{URL_BASE}/{PATH}"
    headers = {
        "Content-Type":"application/json", 
        "authorization":f"Bearer {ACCESS_TOKEN}",
        "appKey":APP_KEY,
        "appSecret":APP_SECRET,
        "tr_id":"TTTC8434R",
        "custtype":"P",
    }
    params = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }
    # API로 잔고를 조회합니다
    res = requests.get(URL, headers=headers, params=params)
    stock_list = res.json()['output1']    # 보유종목 리스트
    evaluation = res.json()['output2']    # 평가 정보
    
    # 보유종목을 딕셔너리로 저장합니다
    stock_dict = {}
    send_message(f"====주식 보유잔고====")
    for stock in stock_list:
        if int(stock['hldg_qty']) > 0:  # 보유수량이 있는 종목만
            stock_dict[stock['pdno']] = stock['hldg_qty']
            send_message(f"{stock['prdt_name']}({stock['pdno']}): {stock['hldg_qty']}주")
            time.sleep(0.1)
    
    # 평가 정보를 메시지로 전송합니다        
    send_message(f"주식 평가 금액: {evaluation[0]['scts_evlu_amt']}원")
    time.sleep(0.1)
    send_message(f"평가 손익 합계: {evaluation[0]['evlu_pfls_smtl_amt']}원")
    time.sleep(0.1)
    send_message(f"총 평가 금액: {evaluation[0]['tot_evlu_amt']}원")
    time.sleep(0.1)
    send_message(f"=================")
    
    return stock_dict

def get_balance():
    """
    주문 가능한 현금 잔고를 조회하는 함수입니다.
    
    Returns:
        int: 주문 가능한 현금 잔고
    """
    PATH = "uapi/domestic-stock/v1/trading/inquire-psbl-order"
    URL = f"{URL_BASE}/{PATH}"
    headers = {
        "Content-Type":"application/json", 
        "authorization":f"Bearer {ACCESS_TOKEN}",
        "appKey":APP_KEY,
        "appSecret":APP_SECRET,
        "tr_id":"TTTC8908R",
        "custtype":"P",
    }
    params = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "PDNO": "005930",
        "ORD_UNPR": "65500",
        "ORD_DVSN": "01",
        "CMA_EVLU_AMT_ICLD_YN": "Y",
        "OVRS_ICLD_YN": "Y"
    }
    # API로 현금 잔고를 조회합니다
    res = requests.get(URL, headers=headers, params=params)
    cash = res.json()['output']['ord_psbl_cash']
    send_message(f"주문 가능 현금 잔고: {cash}원")
    return int(cash)

def buy(code="005930", qty="1"):
    """
    주식 시장가 매수 주문을 하는 함수입니다.
    
    사용법: buy("005930", "1")  # 삼성전자 1주를 시장가로 매수
    
    Parameters:
        code (str): 종목코드 (기본값: 삼성전자 005930)
        qty (str): 주문수량 (기본값: 1주)
        
    Returns:
        bool: 매수 성공 여부
    """
    """주식 시장가 매수"""  
    PATH = "uapi/domestic-stock/v1/trading/order-cash"
    URL = f"{URL_BASE}/{PATH}"
    data = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "PDNO": code,
        "ORD_DVSN": "01",
        "ORD_QTY": str(int(qty)),
        "ORD_UNPR": "0",
    }
    headers = {"Content-Type":"application/json", 
        "authorization":f"Bearer {ACCESS_TOKEN}",
        "appKey":APP_KEY,
        "appSecret":APP_SECRET,
        "tr_id":"TTTC0802U",
        "custtype":"P",
        "hashkey" : hashkey(data)
    }
    res = requests.post(URL, headers=headers, data=json.dumps(data))
    if res.json()['rt_cd'] == '0':
        send_message(f"[매수 성공]{str(res.json())}")
        return True
    else:
        send_message(f"[매수 실패]{str(res.json())}")
        return False

def sell(code="005930", qty="1"):
    """주식 시장가 매도"""
    PATH = "uapi/domestic-stock/v1/trading/order-cash"
    URL = f"{URL_BASE}/{PATH}"
    data = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "PDNO": code,
        "ORD_DVSN": "01",
        "ORD_QTY": qty,
        "ORD_UNPR": "0",
    }
    headers = {"Content-Type":"application/json", 
        "authorization":f"Bearer {ACCESS_TOKEN}",
        "appKey":APP_KEY,
        "appSecret":APP_SECRET,
        "tr_id":"TTTC0801U",
        "custtype":"P",
        "hashkey" : hashkey(data)
    }
    res = requests.post(URL, headers=headers, data=json.dumps(data))
    if res.json()['rt_cd'] == '0':
        send_message(f"[매도 성공]{str(res.json())}")
        return True
    else:
        send_message(f"[매도 실패]{str(res.json())}")
        return False

# 자동매매 시작
try:
    ACCESS_TOKEN = get_access_token()

    symbol_list = ["005930","035720","000660","069500"] # 매수 희망 종목 리스트
    bought_list = [] # 매수 완료된 종목 리스트
    total_cash = get_balance() # 보유 현금 조회
    stock_dict = get_stock_balance() # 보유 주식 조회
    for sym in stock_dict.keys():
        bought_list.append(sym)
    target_buy_count = 3 # 매수할 종목 수
    buy_percent = 0.33 # 종목당 매수 금액 비율
    buy_amount = total_cash * buy_percent  # 종목별 주문 금액 계산
    soldout = False

    send_message("===국내 주식 자동매매 프로그램을 시작합니다===")
    while True:
        t_now = datetime.datetime.now()
        t_9 = t_now.replace(hour=9, minute=0, second=0, microsecond=0)
        t_start = t_now.replace(hour=9, minute=5, second=0, microsecond=0)
        t_sell = t_now.replace(hour=15, minute=15, second=0, microsecond=0)
        t_exit = t_now.replace(hour=15, minute=20, second=0,microsecond=0)
        today = datetime.datetime.today().weekday()
        if today == 5 or today == 6:  # 토요일이나 일요일이면 자동 종료
            send_message("주말이므로 프로그램을 종료합니다.")
            break
        if t_9 < t_now < t_start and soldout == False: # 잔여 수량 매도
            for sym, qty in stock_dict.items():
                sell(sym, qty)
            soldout == True
            bought_list = []
            stock_dict = get_stock_balance()
        if t_start < t_now < t_sell :  # AM 09:05 ~ PM 03:15 : 매수
            for sym in symbol_list:
                if len(bought_list) < target_buy_count:
                    if sym in bought_list:
                        continue
                    target_price = get_target_price(sym)
                    current_price = get_current_price(sym)
                    if target_price < current_price:
                        buy_qty = 0  # 매수할 수량 초기화
                        buy_qty = int(buy_amount // current_price)
                        if buy_qty > 0:
                            send_message(f"{sym} 목표가 달성({target_price} < {current_price}) 매수를 시도합니다.")
                            result = buy(sym, buy_qty)
                            if result:
                                soldout = False
                                bought_list.append(sym)
                                get_stock_balance()
                    time.sleep(1)
            time.sleep(1)
            if t_now.minute == 30 and t_now.second <= 5: 
                get_stock_balance()
                time.sleep(5)
        if t_sell < t_now < t_exit:  # PM 03:15 ~ PM 03:20 : 일괄 매도
            if soldout == False:
                stock_dict = get_stock_balance()
                for sym, qty in stock_dict.items():
                    sell(sym, qty)
                soldout = True
                bought_list = []
                time.sleep(1)
        if t_exit < t_now:  # PM 03:20 ~ :프로그램 종료
            send_message("프로그램을 종료합니다.")
            break
except Exception as e:
    send_message(f"[오류 발생]{e}")
    time.sleep(1)
