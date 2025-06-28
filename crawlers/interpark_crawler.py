import logging
import time
import random
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup


def get_interpark_notices(max_retries=3, retry_delay=2):
    """
    인터파크 티켓 공지사항을 크롤링합니다.
    """
    logging.info("인터파크 크롤링 시작...")
    
    for attempt in range(max_retries):
        try:
            # 두 단계의 크롤링 결과를 병합
            return _crawl_interpark_with_retry(attempt + 1, max_retries)
        except Exception as e:
            logging.warning(f"인터파크 크롤링 시도 {attempt + 1}/{max_retries} 실패: {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                logging.info(f"{wait_time:.1f}초 후 재시도합니다...")
                time.sleep(wait_time)
            else:
                logging.error("인터파크 크롤링 최대 재시도 횟수 초과")
                return []

def _launch_playwright_browser(p):
    """Playwright 브라우저와 컨텍스트, 페이지를 초기화하는 헬퍼 함수"""
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    page.set_default_timeout(30000)
    return browser, page

def _crawl_interpark_with_retry(attempt, max_attempts):
    """
    2단계 분리 크롤링을 수행하는 최종 로직
    """
    logging.info(f"인터파크 크롤링 시도 {attempt}/{max_attempts}")
    
    all_tickets = []
    seen_ids = set()
    item_selector = "a[class*='NoticeItem_ticketItem__']"
    url = "https://tickets.interpark.com/contents/notice"

    with sync_playwright() as p:
        # --- 1단계: 초기 데이터 수집 (전체 페이지 스크롤) ---
        logging.info("--- 1단계: 초기 데이터 수집 시작 ---")
        browser1, page1 = _launch_playwright_browser(p)
        try:
            page1.goto(url, wait_until='domcontentloaded')
            page1.wait_for_selector(item_selector, state='visible', timeout=15000)
            
            logging.info("전체 페이지 스크롤 5회 실행...")
            for i in range(5):
                page1.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(random.uniform(0.5, 1.0))

            html = page1.content()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select(item_selector)
            for item in items:
                _parse_and_add_item(item, all_tickets, seen_ids)
            logging.info(f"1단계 완료. 초기 아이템 {len(all_tickets)}건 수집.")
        except Exception as e:
            logging.error(f"1단계 크롤링 중 오류 발생: {e}")
        finally:
            browser1.close()

        # --- 2단계: 추가 데이터 수집 (내부 가상 스크롤) ---
        logging.info("--- 2단계: 추가 데이터 수집 시작 ---")
        browser2, page2 = _launch_playwright_browser(p)
        try:
            page2.goto(url, wait_until='domcontentloaded')
            page2.wait_for_selector(item_selector, state='visible', timeout=15000)

            scroll_selector = 'div[class*="Panel_fill-scroll"]'
            no_new_item_streak = 0
            MAX_NO_NEW_ITEM_STREAK = 5

            logging.info(f"내부 스크롤 시작 (대상: {scroll_selector})")
            for i in range(40): # 최대 40회 스크롤
                page2.evaluate(f'''
                    const element = document.querySelector('{scroll_selector}');
                    if (element) {{
                        element.scrollBy(0, element.clientHeight);
                    }}
                ''')
                time.sleep(random.uniform(0.5, 1.0))
                
                html = page2.content()
                soup = BeautifulSoup(html, "html.parser")
                current_items = soup.select(item_selector)
                
                new_items_found = 0
                for item in current_items:
                    if _parse_and_add_item(item, all_tickets, seen_ids):
                        new_items_found += 1
                
                if new_items_found > 0:
                    logging.info(f"내부 스크롤 {i+1}: 새 아이템 {new_items_found}건 발견. (총 {len(all_tickets)}건)")
                    no_new_item_streak = 0
                else:
                    no_new_item_streak += 1
                    logging.info(f"내부 스크롤 {i+1}: 새 아이템 없음. 연속 {no_new_item_streak}/{MAX_NO_NEW_ITEM_STREAK}회")
                
                if no_new_item_streak >= MAX_NO_NEW_ITEM_STREAK:
                    logging.info("더 이상 새로운 아이템이 발견되지 않아 스크롤을 종료합니다.")
                    break
            logging.info("2단계 완료.")
        except Exception as e:
            logging.error(f"2단계 크롤링 중 오류 발생: {e}")
        finally:
            browser2.close()

    logging.info(f"최종 크롤링 완료. 총 {len(all_tickets)}건의 데이터를 수집했습니다.")
    return all_tickets


def _parse_and_add_item(item, ticket_list, seen_ids):
    """개별 아이템을 파싱하고, 새로운 경우 리스트에 추가합니다."""
    title, open_date, place, unique_id = _extract_item_data(item)
    
    if not unique_id or unique_id in seen_ids:
        return False

    seen_ids.add(unique_id)
    
    title = _clean_text(title)
    open_date = _clean_text(open_date)
    place = _clean_text(place) if place else ""
    
    ticket_info = {
        "open_date": open_date,
        "title": f"{title} - {place}" if place else title,
        "link": "상세 링크 정보 없음 (클릭 시 이동)",
        "source": "인터파크"
    }
    ticket_list.append(ticket_info)
    return True

def _extract_item_data(item):
    """아이템에서 데이터를 추출하는 헬퍼 함수. gtm-label을 고유 ID로 사용."""
    try:
        title_element = item.select_one("[class*='NoticeItem_goodsName__']")
        date_element = item.select_one("[class*='NoticeItem_playDate__']")
        place_element = item.select_one("[class*='NoticeItem_placeName__']")
        unique_id = item.get('gtm-label')
        
        title = title_element.get_text(strip=True) if title_element else None
        open_date = date_element.get_text(strip=True) if date_element else None
        place = place_element.get_text(strip=True) if place_element else None
        
        return title, open_date, place, unique_id
    except Exception:
        return None, None, None, None

def _clean_text(text):
    """텍스트를 정제하는 헬퍼 함수"""
    if not text:
        return ""
    return ' '.join(text.split())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    tickets = get_interpark_notices()
    if tickets:
        logging.info(f"--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            logging.info(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")