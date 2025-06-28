import logging
import time
import json
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError

# 로거 설정
logger = logging.getLogger(__name__)

BASE_URL = "https://www.ticketlink.co.kr"

def get_ticketlink_notices(max_retries: int = 3, retry_delay: int = 5) -> List[Dict[str, Any]]:
    """
    Playwright를 사용하여 티켓링크의 동적으로 렌더링되는 상품 정보를 크롤링합니다.
    """
    # 파라미터를 URL에 직접 포함하여 한 번에 접속
    url = f"{BASE_URL}/product/getProductList?categoryId=P0001&page=1&size=100&sort=RECENT"
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Playwright로 티켓링크 상품 목록을 크롤링하는 중... (시도 {attempt + 1}/{max_retries})")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                logger.info(f"페이지 로딩: {url}")
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # 상품 카드 목록을 나타내는 선택자를 명확히 기다립니다.
                # 클래스 이름이 동적으로 변경될 수 있으므로, 'product_list_area'로 시작하는 클래스를 선택합니다.
                page.wait_for_selector('ul[class*="product_list_area"] > li', timeout=15000)

                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, 'html.parser')
            
            # 실제 웹사이트 구조 분석을 통해 얻은 정확한 선택자 사용
            items = soup.select('ul[class*="product_list_area"] > li')
            
            if not items:
                logger.warning("상품 목록을 찾을 수 없습니다. 웹사이트 구조가 변경되었을 수 있습니다.")
                return []

            tickets = _parse_html_and_map_data(items)
            logger.info(f"성공적으로 {len(tickets)}개의 티켓 정보를 찾았습니다.")
            return tickets

        except TimeoutError:
            logger.error(f"페이지 로딩 또는 특정 요소({url}) 대기 시간 초과")
        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {e}", exc_info=True)
        
        if attempt < max_retries - 1:
            logger.info(f"{retry_delay}초 후 재시도합니다.")
            time.sleep(retry_delay)
        else:
            logger.error("최대 재시도 횟수를 초과했습니다.")
            
    return []

def _parse_html_and_map_data(items: List[Any]) -> List[Dict[str, Any]]:
    """
    BeautifulSoup으로 파싱된 HTML 아이템에서 데이터를 추출하고 표준 형식으로 변환합니다.
    """
    tickets_list = []
    for item in items:
        # 실제 웹사이트의 HTML 구조를 분석하여 얻은 정확한 선택자
        title_element = item.select_one('strong[class*="name"]')
        date_element = item.select_one('span[class*="date"]')
        venue_element = item.select_one('span[class*="place"]')
        link_element = item.select_one('a[class*="product_card_item"]')
        img_element = item.select_one('img[class*="poster_image"]')

        # 필수 정보인 제목과 링크가 없으면 건너뜀
        if not title_element or not link_element:
            continue

        title = title_element.get_text(strip=True)
        date = date_element.get_text(strip=True) if date_element else ""
        venue = venue_element.get_text(strip=True) if venue_element else ""
        
        relative_url = link_element.get('href')
        full_url = f"{BASE_URL}{relative_url}" if relative_url else ""
        
        image_url = img_element.get('src') if img_element else ""

        ticket_info = {
            'site': '티켓링크',
            'title': title,
            'date': date,
            'url': full_url,
            'venue': venue,
            'genre': 'N/A', # HTML만으로는 장르 구분이 어려움
            'image_url': image_url
        }
        tickets_list.append(ticket_info)
    return tickets_list

# 테스트용 코드
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    notices = get_ticketlink_notices()
    
    if notices:
        print("\n--- 수집된 티켓 정보 ---")
        print(json.dumps(notices, indent=2, ensure_ascii=False))
    else:
        print("\n수집된 티켓 정보가 없습니다.")
