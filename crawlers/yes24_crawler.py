import logging
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def get_yes24_notices(max_retries=3, retry_delay=2):
    """
    YES24 티켓 공지사항을 크롤링합니다.
    
    Args:
        max_retries (int): 최대 재시도 횟수
        retry_delay (int): 재시도 간격 (초)
    
    Returns:
        list: 티켓 정보 리스트
    """
    logging.info("YES24 크롤링 시작...")
    
    for attempt in range(max_retries):
        try:
            return _crawl_yes24_with_retry(attempt + 1, max_retries)
        except Exception as e:
            logging.warning(f"YES24 크롤링 시도 {attempt + 1}/{max_retries} 실패: {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                logging.info(f"{wait_time:.1f}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                logging.error("YES24 크롤링 최대 재시도 횟수 초과")
                return []

def _crawl_yes24_with_retry(attempt, max_attempts):
    """
    실제 크롤링 로직을 수행하는 내부 함수
    """
    logging.info(f"YES24 크롤링 시도 {attempt}/{max_attempts}")
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
            url = "https://m.ticket.yes24.com/Notice/List.aspx"
            logging.info(f"페이지 로딩 중: {url}")
            
            # 페이지 로드 전 랜덤 지연
            time.sleep(random.uniform(1, 3))
            
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            if not response or response.status != 200:
                raise Exception(f"페이지 로드 실패. 상태 코드: {response.status if response else 'None'}")
            
            # 페이지 로드 완료 대기
            page.wait_for_load_state('networkidle', timeout=10000)
            
            # 더보기 버튼 클릭으로 더 많은 데이터 로드
            click_count = 3
            more_button_selectors = [
                "a.btn_more",  # 기본 선택자
                ".btn_more",   # 클래스만
                "[class*='btn_more']",  # 부분 매치
                "a[onclick*='more']",  # onclick 속성 기반
            ]
            
            logging.info(f"데이터를 더 불러오기 위해 더보기 버튼을 {click_count}번 클릭 시도합니다.")
            
            for i in range(click_count):
                button_clicked = False
                
                # 여러 선택자로 더보기 버튼 찾기 시도
                for selector in more_button_selectors:
                    try:
                        # 버튼이 존재하고 보이는지 확인
                        if page.is_visible(selector, timeout=2000):
                            # 버튼을 화면 중앙으로 스크롤
                            page.locator(selector).scroll_into_view_if_needed()
                            
                            # 랜덤 지연 후 클릭
                            time.sleep(random.uniform(0.5, 1.5))
                            page.click(selector, timeout=5000)
                            
                            logging.info(f"더보기 클릭 {i+1}/{click_count} 완료 (선택자: {selector})")
                            button_clicked = True
                            
                            # 새 데이터 로드 대기
                            page.wait_for_load_state('networkidle', timeout=5000)
                            break
                            
                    except (TimeoutError, Exception) as e:
                        logging.debug(f"선택자 '{selector}'로 버튼 클릭 실패: {e}")
                        continue
                
                if not button_clicked:
                    logging.info(f"더보기 버튼을 찾을 수 없습니다. {i+1}번째 시도에서 중단합니다.")
                    break
                
                # 다음 클릭 전 대기
                time.sleep(random.uniform(1, 2))

            # 최종 HTML 가져오기
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # 다양한 선택자로 공지사항 찾기 시도
            notice_selectors = [
                "a.lnk_brd",  # 기본 선택자
                ".lnk_brd",   # 클래스만
                "a[class*='lnk_brd']",  # 부분 매치
                "li a[href*='Notice']",  # 링크 기반
                ".notice-item a",  # 대체 선택자
            ]
            
            notices = []
            for selector in notice_selectors:
                notices = soup.select(selector)
                if notices:
                    logging.info(f"선택자 '{selector}'로 {len(notices)}개 공지사항 발견")
                    break
                else:
                    logging.debug(f"선택자 '{selector}'로 공지사항을 찾을 수 없음")
            
            if not notices:
                logging.warning("모든 선택자로 공지사항 목록을 찾을 수 없습니다. 웹사이트 구조가 변경되었을 수 있습니다.")
                try:
                    page.screenshot(path="yes24_error_debug.png")
                    logging.info("'yes24_error_debug.png' 파일로 현재 페이지를 저장했습니다.")
                except Exception as screenshot_error:
                    logging.warning(f"스크린샷 저장 실패: {screenshot_error}")
                browser.close()
                return []

            logging.info(f"파싱할 후보 {len(notices)}건 발견. 유효한 데이터만 추출합니다.")
            
            for notice in notices:
                try:
                    # 다양한 방식으로 데이터 추출 시도
                    title, open_date, link = _extract_yes24_data(notice)
                    
                    if not title or not open_date:
                        logging.debug("필수 정보(제목, 날짜) 누락으로 아이템 건너뛰기")
                        continue
                    
                    # 데이터 정제
                    title = _clean_yes24_text(title)
                    open_date = _clean_yes24_text(open_date)
                    
                    # 링크 처리
                    if link and not link.startswith('http'):
                        link = "https://m.ticket.yes24.com" + link if link.startswith('/') else "https://m.ticket.yes24.com/" + link
                    elif not link:
                        link = "링크 없음"
                    
                    ticket_info = {
                        "open_date": open_date,
                        "title": title,
                        "link": link,
                        "source": "YES24"
                    }
                    ticket_list.append(ticket_info)
                    
                except Exception as item_error:
                    logging.warning(f"YES24 아이템 파싱 중 오류 발생: {item_error}")
                    continue

            logging.info(f"YES24 크롤링 완료. 총 {len(ticket_list)}건 발견.")
            browser.close()
            return ticket_list

        except Exception as e:
            logging.error(f"YES24 크롤링 중 예상치 못한 오류 발생: {e}", exc_info=True)
            try:
                if not browser.is_closed():
                    page.screenshot(path="yes24_error.png")
                    browser.close()
            except Exception as cleanup_error:
                logging.warning(f"브라우저 정리 중 오류: {cleanup_error}")
            raise  # 재시도를 위해 예외를 다시 발생시킴

def _extract_yes24_data(notice):
    """
    YES24 공지사항에서 데이터를 추출하는 헬퍼 함수
    """
    title = open_date = link = None
    
    try:
        # 방법 1: 기본 선택자 사용
        open_date_element = notice.select_one(".brd_dday .txt")
        title_element = notice.select_one(".brd_name")
        
        if open_date_element and title_element:
            open_date = open_date_element.get_text(strip=True)
            title = title_element.get_text(strip=True)
            link = notice.get('href') if notice.has_attr('href') else None
            
            if title and open_date:
                return title, open_date, link
    except Exception:
        pass
    
    try:
        # 방법 2: 대체 선택자 사용
        date_elements = notice.select(".txt, .date, [class*='date'], [class*='dday']")
        title_elements = notice.select(".name, .title, [class*='name'], [class*='title']")
        
        if date_elements and title_elements:
            open_date = date_elements[0].get_text(strip=True)
            title = title_elements[0].get_text(strip=True)
            link = notice.get('href') if notice.has_attr('href') else None
            
            if title and open_date:
                return title, open_date, link
    except Exception:
        pass
    
    try:
        # 방법 3: 전체 텍스트에서 추출
        full_text = notice.get_text(strip=True)
        if full_text:
            # 간단한 패턴으로 날짜와 제목 분리 시도
            parts = full_text.split()
            if len(parts) >= 2:
                # 날짜 형식 찾기
                for i, part in enumerate(parts):
                    if any(char.isdigit() for char in part) and ('.' in part or '/' in part or '-' in part):
                        open_date = part
                        title = ' '.join(parts[i+1:]) if i+1 < len(parts) else ' '.join(parts[:i])
                        link = notice.get('href') if notice.has_attr('href') else None
                        
                        if title and open_date:
                            return title, open_date, link
                        break
    except Exception:
        pass
    
    return None, None, None

def _clean_yes24_text(text):
    """
    YES24 텍스트를 정제하는 헬퍼 함수
    """
    if not text:
        return ""
    
    # 불필요한 공백 및 특수 문자 제거
    text = ' '.join(text.split())
    text = text.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
    
    # YES24 특유의 불필요한 텍스트 제거
    unwanted_phrases = ['시간 정보 없음', '제목 정보 없음', 'undefined']
    for phrase in unwanted_phrases:
        text = text.replace(phrase, '')
    
    return text.strip()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    tickets = get_yes24_notices()
    if tickets:
        logging.info(f"--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            logging.info(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")