import logging
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def get_melon_notices(max_retries=3, retry_delay=2):
    """
    멜론티켓 공지사항을 크롤링하여 티켓 정보를 반환합니다.
    
    Args:
        max_retries (int): 최대 재시도 횟수
        retry_delay (int): 재시도 간격 (초)
    
    Returns:
        list: 티켓 정보 리스트
    """
    for attempt in range(max_retries):
        try:
            logging.info(f"멜론티켓 크롤링 시도 {attempt + 1}/{max_retries}")
            return _crawl_melon_notices()
        except Exception as e:
            logging.warning(f"멜론티켓 크롤링 시도 {attempt + 1} 실패: {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                logging.info(f"{wait_time:.1f}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                logging.error("멜론티켓 크롤링 최대 재시도 횟수 초과")
                return []

def _crawl_melon_notices():
    """
    실제 멜론티켓 크롤링을 수행하는 내부 함수
    """
    logging.info("멜론티켓 크롤링 시작...")
    ticket_list = []
    seen_links = set()  # 중복 티켓을 제거하기 위한 set

    with sync_playwright() as p:
        # 봇 탐지 방지를 위한 브라우저 설정
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',  # 이미지 로딩 비활성화로 속도 향상
                '--disable-javascript',  # 불필요한 JS 비활성화
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            permissions=["geolocation", "notifications", "camera", "microphone", "clipboard-read", "clipboard-write"],
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        # 봇 탐지 방지 스크립트
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en'],
            });
        """)
        
        # 타임아웃 설정
        page.set_default_navigation_timeout(30000)
        page.set_default_timeout(30000)

        try:
            # 페이지 로드 전 랜덤 지연
            time.sleep(random.uniform(1, 3))
            
            url = "https://ticket.melon.com/csoon/index.htm#orderType=0&pageIndex=1&schGcode=GENRE_ALL&schText=&schDt="
            # 페이지 이동
            response = page.goto(url, timeout=60000, wait_until='domcontentloaded')
            
            # 응답 상태 확인
            if response and response.status >= 400:
                raise Exception(f"HTTP 오류: {response.status}")
            
            # 페이지 로드 완료 대기
            page.wait_for_load_state('networkidle', timeout=10000)
            
            # 스크롤을 통해 더 많은 데이터 로드 (개선된 방식)
            scroll_count = 3
            logging.info(f"데이터를 더 불러오기 위해 페이지를 {scroll_count}번 스크롤합니다.")
            for i in range(scroll_count):
                # 부드러운 스크롤
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # 랜덤 지연
                time.sleep(random.uniform(1, 2))
                
                # 네트워크 안정화 대기
                try:
                    page.wait_for_load_state('networkidle', timeout=5000)
                except Exception:
                    logging.debug(f"스크롤 {i+1} 후 네트워크 대기 타임아웃")
                    pass
                
                logging.info(f"스크롤 {i+1}/{scroll_count} 완료...")
            
            # 최종 HTML 가져오기
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 1. "HOT 공연 오픈 소식" 크롤링
            hot_items = soup.select("ul.list_hot_issue div.cont")
            logging.info(f"HOT 공연 섹션에서 {len(hot_items)}개 아이템을 파싱합니다.")
            for item in hot_items:
                try:
                    link_element = item.select_one("a")
                    if not link_element or not link_element.has_attr('href'):
                        continue
                    
                    relative_link = link_element['href']
                    # 링크를 고유 ID로 사용 (상대 경로를 절대 경로로 변환)
                    link = "https://ticket.melon.com/csoon/" + relative_link.lstrip('./')

                    if link in seen_links:
                        continue  # 이미 추가된 티켓이면 건너뛰기
                    
                    title_element = item.select_one("a strong.tit_consert")
                    date_element = item.select_one("a span.date")

                    if not all([title_element, date_element]):
                        continue

                    title = title_element.get_text(strip=True)
                    open_date = date_element.get_text(strip=True)
                    
                    ticket_info = {
                        "open_date": open_date,
                        "title": title,
                        "link": link,
                        "source": "멜론티켓"
                    }
                    ticket_list.append(ticket_info)
                    seen_links.add(link)  # 처리된 링크로 기록
                except Exception as e:
                    logging.warning(f"HOT 공연 아이템 파싱 중 오류 발생: {e}")
                    continue

            # 2. 메인 "티켓오픈" 목록 크롤링
            main_items = soup.select("ul.list_ticket_cont > li")
            logging.info(f"메인 목록 섹션에서 {len(main_items)}개 아이템을 파싱합니다.")
            for item in main_items:
                try:
                    link_element = item.select_one("a.tit")
                    if not link_element or not link_element.has_attr('href'):
                        continue
                    
                    relative_link = link_element['href']
                    link = "https://ticket.melon.com/csoon/" + relative_link.lstrip('./')

                    if link in seen_links:
                        continue

                    title_element = item.select_one("a.tit")
                    date_element = item.select_one("div.ticket_data span.date")

                    if not all([title_element, date_element]):
                        continue
                        
                    title = title_element.get_text(strip=True)
                    open_date = date_element.get_text(strip=True)

                    ticket_info = {
                        "open_date": open_date,
                        "title": title,
                        "link": link,
                        "source": "멜론티켓"
                    }
                    ticket_list.append(ticket_info)
                    seen_links.add(link)
                except Exception as e:
                    logging.warning(f"메인 목록 아이템 파싱 중 오류 발생: {e}")
                    continue
            
            if not ticket_list:
                logging.warning("공지사항 아이템을 찾을 수 없습니다. 웹사이트 구조가 변경되었을 수 있습니다.")
                page.screenshot(path="melon_error.png")
                logging.info("'melon_error.png' 파일로 현재 페이지를 저장했습니다.")
                browser.close()
                return []
            
            logging.info(f"멜론티켓 크롤링 완료. 중복 제거 후 총 {len(ticket_list)}건 발견.")
            browser.close()
            return ticket_list
            
        except Exception as e:
            logging.error(f"멜론티켓 크롤링 중 예상치 못한 오류 발생: {e}", exc_info=True)
            try:
                if browser.is_connected():
                    page.screenshot(path="melon_error.png")
                    logging.info("'melon_error.png' 파일로 현재 페이지를 저장했습니다.")
                    browser.close()
            except Exception as cleanup_error:
                logging.warning(f"브라우저 정리 중 오류: {cleanup_error}")
            raise  # 재시도를 위해 예외를 다시 발생시킴

def _extract_melon_data(item, section_type):
    """
    멜론티켓 아이템에서 데이터를 추출하는 헬퍼 함수
    
    Args:
        item: BeautifulSoup 요소
        section_type: 섹션 타입 ("HOT", "MAIN", "TICKET")
    
    Returns:
        tuple: (title, open_date, link)
    """
    title = open_date = link = None
    
    try:
        # 방법 1: 기본 선택자 사용
        if section_type in ["HOT", "MAIN"]:
            link_tag = item.find("a")
            if link_tag:
                title = link_tag.get_text(strip=True)
                link = link_tag.get("href")
                if link and not link.startswith('http'):
                    link = "https://ticket.melon.com" + link
                
                # 날짜 정보 찾기
                date_span = item.find("span", class_="date")
                open_date = date_span.get_text(strip=True) if date_span else None
                
                if title and open_date:
                    return title, open_date, link
        
        elif section_type == "TICKET":
            # 제목 추출
            title_element = item.select_one(".tit a")
            if title_element:
                title = title_element.get_text(strip=True)
                link = title_element.get("href")
                
                # 날짜 정보 추출
                date_element = item.select_one(".date")
                open_date = date_element.get_text(strip=True) if date_element else None
                
                if title and open_date:
                    return title, open_date, link
    except Exception:
        pass
    
    try:
        # 방법 2: 대체 선택자 사용
        link_elements = item.select("a")
        date_elements = item.select(".date, .time, [class*='date'], [class*='time']")
        title_elements = item.select(".title, .tit, .name, [class*='title'], [class*='tit'], [class*='name']")
        
        if link_elements:
            link_tag = link_elements[0]
            title = title or link_tag.get_text(strip=True)
            link = link or link_tag.get("href")
        
        if date_elements:
            open_date = open_date or date_elements[0].get_text(strip=True)
        
        if title_elements and not title:
            title = title_elements[0].get_text(strip=True)
        
        if title and open_date:
            if link and not link.startswith('http'):
                link = "https://ticket.melon.com" + link
            return title, open_date, link
    except Exception:
        pass
    
    try:
        # 방법 3: 전체 텍스트에서 추출
        full_text = item.get_text(strip=True)
        if full_text:
            # 간단한 패턴으로 날짜와 제목 분리 시도
            parts = full_text.split()
            if len(parts) >= 2:
                # 날짜 형식 찾기
                for i, part in enumerate(parts):
                    if any(char.isdigit() for char in part) and ('.' in part or '/' in part or '-' in part):
                        open_date = part
                        title = ' '.join(parts[i+1:]) if i+1 < len(parts) else ' '.join(parts[:i])
                        
                        # 링크 찾기
                        link_tag = item.find("a")
                        link = link_tag.get("href") if link_tag else None
                        
                        if title and open_date:
                            if link and not link.startswith('http'):
                                link = "https://ticket.melon.com" + link
                            return title, open_date, link
                        break
    except Exception:
        pass
    
    return None, None, None

def _clean_melon_text(text):
    """
    멜론티켓 텍스트를 정제하는 헬퍼 함수
    """
    if not text:
        return ""
    
    # 불필요한 공백 및 특수 문자 제거
    text = ' '.join(text.split())
    text = text.replace('\n', ' ').replace('\t', ' ').replace('\r', ' ')
    
    # 멜론티켓 특유의 불필요한 텍스트 제거
    unwanted_phrases = ['날짜 정보 없음', '제목 정보 없음', 'undefined', '티켓오픈']
    for phrase in unwanted_phrases:
        text = text.replace(phrase, '')
    
    return text.strip()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    tickets = get_melon_notices()
    if tickets:
        logging.info(f"--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            logging.info(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")