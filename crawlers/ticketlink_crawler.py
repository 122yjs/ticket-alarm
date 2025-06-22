import logging
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import random
import time
import json
import traceback
import logging

def get_ticketlink_notices(max_retries=3, retry_delay=2):
    """티켓링크 모바일 웹사이트에서 티켓 오픈 공지사항을 크롤링하는 함수
    
    Args:
        max_retries (int): 최대 재시도 횟수
        retry_delay (int): 재시도 간격 (초)
    
    Returns:
        list: 크롤링된 티켓 정보 리스트
    """
    logging.info("티켓링크 모바일 크롤링 시작...")
    
    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = retry_delay * (2 ** (attempt - 1))  # 지수 백오프
            logging.info(f"재시도 {attempt}/{max_retries - 1} - {wait_time}초 대기 중...")
            time.sleep(wait_time)
        
        try:
            return _crawl_ticketlink_with_retry()
        except Exception as e:
            logging.error(f"시도 {attempt + 1} 실패: {e}")
            if attempt == max_retries - 1:
                logging.error("모든 재시도 실패")
                return []
    
    return []

def _crawl_ticketlink_with_retry():
    """실제 크롤링 로직을 수행하는 내부 함수"""
    ticket_list = []
    
    with sync_playwright() as p:
        # 모바일 브라우저 설정 - 안정성 개선
        browser = p.chromium.launch(
            headless=True,  # 안정성을 위해 headless 모드 사용
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection'
            ]
        )
        
        try:
            # 모바일 디바이스 설정 (iPhone 15 Pro)
            # User-Agent를 최신 모바일 기기로 위장
            user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"
            
            context = browser.new_context(
                user_agent=user_agent,
                viewport={'width': 393, 'height': 852},
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                ignore_https_errors=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            page = context.new_page()
            
            # 페이지 타임아웃 설정
            page.set_default_navigation_timeout(30000)
            page.set_default_timeout(30000)
            
            # 강화된 Anti-detection 설정
            page.add_init_script("""
                // Override the navigator.webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock touch support
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 5
                });
                
                // Hide automation indicators
                window.chrome = {
                    runtime: {},
                };
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ko-KR', 'ko', 'en-US', 'en']
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            # 1. 모바일 공지사항 페이지로 직접 이동
            logging.info("1. 티켓링크 모바일 공지사항 페이지 접속 중...")
            try:
                # wait_until을 'domcontentloaded'로 변경하여 더 빠르게 로드
                page.goto("https://m.ticketlink.co.kr/help/notice",
                         wait_until="domcontentloaded",
                         timeout=30000)
                logging.info("   페이지 접속 성공")
                
                # 인간적인 행동 모방: 페이지 로드 후 불규칙한 대기
                time.sleep(random.uniform(1.5, 3.5))
                
                # 스크린샷 저장
                page.screenshot(path="ticketlink_mobile_notice.png", full_page=True)
                logging.info("   스크린샷 저장: ticketlink_mobile_notice.png")
                
            except TimeoutError:
                logging.warning("   타임아웃 발생, 페이지 상태 확인 중...")
                # 페이지가 부분적으로라도 로드되었는지 확인
                current_url = page.url
                logging.info(f"   현재 URL: {current_url}")
                
            except Exception as e:
                logging.error(f"페이지 접속 실패: {e}", exc_info=True)
                return []
            
            # 2. 티켓 오픈 탭 찾기
            logging.info("2. 티켓 오픈 탭 찾는 중...")
            tab_found = False
            
            # 모바일 페이지의 일반적인 탭 선택자들
            tab_selectors = [
                'text=티켓오픈',
                'text=티켓 오픈',
                'text=TICKET OPEN',
                '[href*="TICKET_OPEN"]',
                'button:has-text("티켓오픈")',
                '.tab:has-text("티켓오픈")',
                '[class*="tab"]:has-text("티켓오픈")'
            ]
            
            for selector in tab_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        # 인간적인 행동 모방: 클릭 전 대기
                        time.sleep(random.uniform(0.5, 1.5))
                        page.click(selector, timeout=5000)
                        tab_found = True
                        logging.info(f"   티켓 오픈 탭 클릭 성공: {selector}")
                        # 인간적인 행동 모방: 클릭 후 대기
                        time.sleep(random.uniform(1.0, 2.5))
                        break
                except Exception as e:
                    logging.warning(f"   탭 클릭 실패 (selector: '{selector}'). 다음으로 넘어갑니다. 오류: {e}")
                    continue
            
            if not tab_found:
                logging.info("   티켓 오픈 탭을 찾을 수 없음 - 전체 공지사항을 확인합니다")
            
            # 3. 스크롤하여 더 많은 콘텐츠 로드 (모바일은 무한 스크롤인 경우가 많음)
            logging.info("3. 페이지 스크롤 중...")
            last_height = page.evaluate("document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 5
            
            while scroll_attempts < max_scrolls:
                # 페이지 끝까지 스크롤
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    # 인간적인 행동 모방: 스크롤 후 대기
                    time.sleep(random.uniform(1.8, 3.2))
                except Exception as e:
                    logging.warning(f"   스크롤 중 오류 발생: {e}. 스크롤을 중단합니다.")
                    break
                
                # 새로운 콘텐츠가 로드되었는지 확인
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    logging.info(f"   더 이상 로드할 콘텐츠가 없습니다 (스크롤 {scroll_attempts + 1}회)")
                    break
                
                last_height = new_height
                scroll_attempts += 1
                logging.info(f"   스크롤 {scroll_attempts}/{max_scrolls} 완료")
            
            # 4. 페이지 내용 가져오기
            logging.info("4. 페이지 내용 추출 중...")
            html_content = page.content()
            
            # HTML 저장
            with open("ticketlink_mobile_content.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("   HTML 저장: ticketlink_mobile_content.html")
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(html_content, "html.parser")
            
            # 5. 공지사항 목록 찾기
            logging.info("5. 공지사항 목록 파싱 중...")
            
            # 모바일 페이지의 일반적인 리스트 구조
            items = []
            list_selectors = [
                # 일반적인 모바일 리스트 구조
                'ul.notice-list li',
                'ul.list li',
                '.notice-item',
                '.list-item',
                'article',
                '[class*="notice"] li',
                '[class*="list"] > li',
                '[class*="item"]',
                # 더 일반적인 선택자
                'ul li',
                'div.item',
                'div.notice'
            ]
            
            for selector in list_selectors:
                items = soup.select(selector)
                if items and len(items) > 0:
                    # 실제 공지사항인지 확인 (텍스트가 있고 너무 짧지 않은지)
                    valid_items = [item for item in items if len(item.get_text(strip=True)) > 10]
                    if valid_items:
                        items = valid_items
                        logging.info(f"   선택자 '{selector}'로 {len(items)}개 항목 발견")
                        break
            
            if not items:
                logging.warning("   공지사항 목록을 찾을 수 없습니다")
                logging.warning("   HTML 파일을 확인하여 구조를 분석해주세요")
            
            # 6. 각 항목 파싱
            logging.info("6. 개별 항목 파싱 중...")
            for idx, item in enumerate(items[:50]):  # 최대 50개
                try:
                    item_text = item.get_text(strip=True)
                    if len(item_text) < 5:  # 너무 짧은 텍스트는 제외
                        continue
                    
                    # 제목 추출 - 다양한 방법 시도
                    title = ""
                    
                    # 방법 1: 링크 텍스트
                    link_elem = item.find('a')
                    if link_elem:
                        title = link_elem.get_text(strip=True)
                    
                    # 방법 2: 특정 클래스
                    if not title:
                        for class_name in ['title', 'subject', 'tit', 'name']:
                            elem = item.find(class_=lambda x: x and class_name in str(x).lower())
                            if elem:
                                title = elem.get_text(strip=True)
                                break
                    
                    # 방법 3: 첫 번째 텍스트 노드
                    if not title:
                        # 날짜를 제외한 가장 긴 텍스트를 제목으로 추정
                        texts = [t.strip() for t in item.stripped_strings]
                        texts = [t for t in texts if len(t) > 5 and not any(d in t for d in ['2024', '2025', ':', '.', '-'])]
                        if texts:
                            title = max(texts, key=len)
                    
                    if not title:
                        continue
                    
                    # 날짜 추출
                    date = ""
                    date_patterns = ['2024', '2025', '12.', '01.', '02.']  # 날짜 패턴
                    for text in item.stripped_strings:
                        if any(pattern in text for pattern in date_patterns):
                            date = text.strip()
                            break
                    
                    # 링크 추출
                    link = ""
                    if link_elem and link_elem.get('href'):
                        href = link_elem['href']
                        if href.startswith('javascript:'):
                            # JavaScript 함수에서 실제 링크 추출 시도
                            import re
                            match = re.search(r"['\"](\d+)['\"]", href)
                            if match:
                                notice_id = match.group(1)
                                link = f"https://m.ticketlink.co.kr/help/notice/{notice_id}"
                        elif href.startswith('http'):
                            link = href
                        elif href.startswith('/'):
                            link = f"https://m.ticketlink.co.kr{href}"
                        else:
                            link = f"https://m.ticketlink.co.kr/{href}"
                    
                    # 티켓 오픈 관련 키워드 확인
                    ticket_keywords = ['티켓오픈', '티켓 오픈', '예매오픈', '예매 오픈', 'open', 'OPEN']
                    is_ticket_open = any(keyword in title.lower() for keyword in [k.lower() for k in ticket_keywords])
                    
                    # 티켓 정보 저장
                    if title:
                        ticket_info = {
                            "open_date": date or "날짜 정보 없음",
                            "title": title,
                            "link": link or "링크 없음",
                            "additional_info": "티켓오픈" if is_ticket_open else "",
                            "source": "티켓링크(모바일)"
                        }
                        ticket_list.append(ticket_info)
                        
                        if is_ticket_open:
                            logging.info(f"   [티켓오픈] {title[:40]}...")
                        else:
                            logging.info(f"   [일반공지] {title[:40]}...")
                    
                except Exception as e:
                    logging.warning(f"   항목 파싱 중 오류 발생 (index: {idx}). 건너뜁니다. 오류: {e}")
                    continue
            
            logging.info(f"총 {len(ticket_list)}개의 공지사항을 추출했습니다.")
            
            # 티켓 오픈 공지만 필터링 (선택사항)
            ticket_open_list = [t for t in ticket_list if t['additional_info'] == "티켓오픈"]
            logging.info(f"이 중 티켓 오픈 공지는 {len(ticket_open_list)}개입니다.")
            
        except Exception as e:
            logging.error(f"티켓링크 크롤링 중 예상치 못한 오류 발생: {e}", exc_info=True)
            
        finally:
            browser.close()
    
    return ticket_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    # 크롤링 실행
    tickets = get_ticketlink_notices()
    
    # 결과 출력
    if tickets:
        logging.info("="*70)
        logging.info(f"최종 결과: 총 {len(tickets)}건의 공지사항")
        logging.info("="*70)
        
        # 티켓 오픈 공지만 출력
        ticket_opens = [t for t in tickets if t['additional_info'] == "티켓오픈"]
        
        if ticket_opens:
            logging.info(f"티켓 오픈 공지 ({len(ticket_opens)}건):")
            logging.info("-"*70)
            for i, ticket in enumerate(ticket_opens[:10], 1):
                logging.info(f"[{i}] {ticket['title']}")
                logging.info(f"    날짜: {ticket['open_date']}")
                logging.info(f"    링크: {ticket['link']}")
        
        # 일반 공지도 일부 출력
        other_notices = [t for t in tickets if t['additional_info'] != "티켓오픈"]
        if other_notices:
            logging.info(f"기타 공지사항 ({len(other_notices)}건 중 5건):")
            logging.info("-"*70)
            for i, ticket in enumerate(other_notices[:5], 1):
                logging.info(f"[{i}] {ticket['title']}")
                logging.info(f"    날짜: {ticket['open_date']}")
    else:
        logging.warning("공지사항을 찾을 수 없습니다.")
        logging.info("디버깅 파일:")
        logging.info("- ticketlink_mobile_notice.png: 페이지 스크린샷")
        logging.info("- ticketlink_mobile_content.html: 페이지 HTML")
