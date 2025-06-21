from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import random

def get_ticketlink_notices_wire():
    """Selenium-Wire로 네트워크 요청을 가로채는 방법"""
    print("Selenium-Wire로 티켓링크 크롤링 시작...")
    
    ticket_list = []
    
    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Selenium Wire 옵션
    seleniumwire_options = {
        'disable_encoding': True,  # 응답 디코딩 비활성화
        'suppress_connection_errors': True,
    }
    
    driver = webdriver.Chrome(
        options=chrome_options,
        seleniumwire_options=seleniumwire_options
    )
    
    try:
        # JavaScript로 webdriver 속성 제거
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            '''
        })
        
        # 페이지 방문
        print("1. 공지사항 페이지 방문...")
        driver.get('https://www.ticketlink.co.kr/help/notice')
        time.sleep(random.uniform(3, 5))
        
        # 네트워크 요청 확인 (API 엔드포인트 찾기)
        for request in driver.requests:
            if 'api' in request.url or 'ajax' in request.url:
                print(f"   API 요청 발견: {request.url}")
        
        # 페이지 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 이하 파싱 로직은 동일...
        
    finally:
        driver.quit()
    
    return ticket_list