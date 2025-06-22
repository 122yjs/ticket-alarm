import logging
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def get_interpark_notices(max_retries=3, retry_delay=2):
    """
    인터파크 티켓 공지사항을 크롤링합니다.
    
    Args:
        max_retries (int): 최대 재시도 횟수
        retry_delay (int): 재시도 간격 (초)
    
    Returns:
        list: 티켓 정보 리스트
    """
    logging.info("인터파크 크롤링 시작...")
    ticket_list = []
    
    for attempt in range(max_retries):
        try:
            return _crawl_interpark_with_retry(attempt + 1, max_retries)
        except Exception as e:
            logging.warning(f"인터파크 크롤링 시도 {attempt + 1}/{max_retries} 실패: {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)  # 지수 백오프
                logging.info(f"{wait_time:.1f}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                logging.error("인터파크 크롤링 최대 재시도 횟수 초과")
                return []

def _crawl_interpark_with_retry(attempt, max_attempts):
    """
    실제 크롤링 로직을 수행하는 내부 함수
    """
    logging.info(f"인터파크 크롤링 시도 {attempt}/{max_attempts}")
    ticket_list = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,  # 안정성을 위해 headless 모드 사용
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions'
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            permissions=["geolocation", "notifications", "camera", "microphone", "clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        
        # 봇 탐지 방지를 위한 스크립트 추가
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
        """)
        
        # 페이지 로드 타임아웃 설정
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(30000)

        try:
            url = "https://tickets.interpark.com/contents/notice"
            logging.info(f"페이지 로딩 중: {url}")
            
            # 페이지 로드 전 랜덤 지연
            time.sleep(random.uniform(1, 3))
            
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            if not response or response.status != 200:
                raise Exception(f"페이지 로드 실패. 상태 코드: {response.status if response else 'None'}")
            
            # 페이지 로드 완료 대기
            page.wait_for_load_state('networkidle', timeout=10000)
            
            # 점진적 스크롤로 더 많은 데이터 로드
            scroll_count = 3
            logging.info(f"데이터를 더 불러오기 위해 페이지를 {scroll_count}번 스크롤합니다.")
            
            for i in range(scroll_count):
                try:
                    # 부드러운 스크롤
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    logging.info(f"스크롤 {i+1}/{scroll_count} 완료...")
                    
                    # 랜덤 지연으로 자연스러운 동작 모방
                    wait_time = random.uniform(1.5, 2.5)
                    page.wait_for_timeout(int(wait_time * 1000))
                    
                    # 새로운 콘텐츠 로드 대기
                    page.wait_for_load_state('networkidle', timeout=5000)
                    
                except TimeoutError:
                    logging.warning(f"스크롤 {i+1} 중 타임아웃 발생, 계속 진행")
                    continue

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 다양한 선택자로 아이템 찾기 시도 (웹사이트 구조 변경 대응)
            selectors_to_try = [
                "a[class*='NoticeItem_ticketItem__']",  # 기본 선택자
                "a[class*='ticketItem']",  # 클래스명 변경 대응
                ".notice-item a",  # 대체 선택자 1
                ".ticket-item a",  # 대체 선택자 2
                "li a[href*='notice']",  # 링크 기반 선택자
            ]
            
            items = []
            for selector in selectors_to_try:
                items = soup.select(selector)
                if items:
                    logging.info(f"선택자 '{selector}'로 {len(items)}개 아이템 발견")
                    break
                else:
                    logging.debug(f"선택자 '{selector}'로 아이템을 찾을 수 없음")
            
            if not items:
                logging.warning("모든 선택자로 공지사항 아이템을 찾을 수 없습니다. 웹사이트 구조가 변경되었을 수 있습니다.")
                # 디버깅을 위해 현재 페이지 스크린샷 저장
                try:
                    page.screenshot(path="interpark_error_debug.png")
                    logging.info("'interpark_error_debug.png' 파일로 현재 페이지를 저장했습니다.")
                except Exception as screenshot_error:
                    logging.warning(f"스크린샷 저장 실패: {screenshot_error}")
                
                browser.close()
                return []

            logging.info(f"파싱할 후보 {len(items)}건 발견. 유효한 데이터만 추출합니다.")
            
            for item in items:
                try:
                    # 다양한 방식으로 데이터 추출 시도
                    title, open_date, place, link = _extract_item_data(item)
                    
                    if not title or not open_date:
                        logging.debug("필수 정보(제목, 날짜) 누락으로 아이템 건너뛰기")
                        continue
                    
                    # 데이터 정제
                    title = _clean_text(title)
                    open_date = _clean_text(open_date)
                    place = _clean_text(place) if place else ""
                    
                    # 링크 처리
                    base_url = "https://tickets.interpark.com"
                    if link and not link.startswith('http'):
                        link = base_url + link if link.startswith('/') else base_url + '/' + link
                    elif not link:
                        link = "링크 없음"
                    
                    ticket_info = {
                        "open_date": open_date,
                        "title": f"{title} - {place}" if place else title,
                        "link": link,
                        "source": "인터파크"
                    }
                    ticket_list.append(ticket_info)
                    
                except Exception as item_error:
                    logging.warning(f"아이템 파싱 중 오류 발생: {item_error}")
                    continue
            
            logging.info(f"인터파크 크롤링 완료. 총 {len(ticket_list)}건 발견.")
            browser.close()
            return ticket_list

        except Exception as e:
            logging.error(f"인터파크 크롤링 중 예상치 못한 오류 발생: {e}", exc_info=True)
            try:
                if not browser.is_closed():
                    page.screenshot(path="interpark_error.png")
                    browser.close()
            except Exception as cleanup_error:
                logging.warning(f"브라우저 정리 중 오류: {cleanup_error}")
            raise  # 재시도를 위해 예외를 다시 발생시킴

def _extract_item_data(item):
    """
    아이템에서 데이터를 추출하는 헬퍼 함수
    """
    title = open_date = place = link = None
    
    try:
        # 방법 1: li 태그 기반 추출
        list_items = item.find_all("li")
        if len(list_items) >= 2:
            date_element = list_items[0]
            title_element = list_items[1]
            place_element = list_items[2] if len(list_items) > 2 else None
            
            title = title_element.get_text(strip=True) if title_element else None
            open_date = date_element.get_text(strip=True) if date_element else None
            place = place_element.get_text(strip=True) if place_element else None
            link = item.get('href') if item.has_attr('href') else None
            
            if title and open_date:
                return title, open_date, place, link
    except Exception:
        pass
    
    try:
        # 방법 2: 직접 텍스트 추출
        full_text = item.get_text(strip=True)
        if full_text:
            # 간단한 패턴 매칭으로 날짜와 제목 분리 시도
            parts = full_text.split()
            if len(parts) >= 2:
                # 첫 번째 부분이 날짜 형식인지 확인
                potential_date = parts[0]
                if any(char.isdigit() for char in potential_date):
                    open_date = potential_date
                    title = ' '.join(parts[1:])
                    link = item.get('href') if item.has_attr('href') else None
                    return title, open_date, None, link
    except Exception:
        pass
    
    return None, None, None, None

def _clean_text(text):
    """
    텍스트를 정제하는 헬퍼 함수
    """
    if not text:
        return ""
    
    # 불필요한 공백 제거
    text = ' '.join(text.split())
    
    # 특수 문자 정리
    text = text.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
    
    return text.strip()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    tickets = get_interpark_notices()
    if tickets:
        logging.info(f"--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            logging.info(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")