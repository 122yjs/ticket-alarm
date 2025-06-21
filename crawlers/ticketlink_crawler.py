from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import random
import time
import json
import traceback

def get_ticketlink_notices():
    """티켓링크 모바일 웹사이트에서 티켓 오픈 공지사항을 크롤링하는 함수"""
    print("티켓링크 모바일 크롤링 시작...")
    ticket_list = []
    
    with sync_playwright() as p:
        # 모바일 브라우저 설정
        browser = p.chromium.launch(
            headless=False,  # 디버깅을 위해 False (나중에 True로 변경)
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--window-size=430,932'  # iPhone 14 Pro Max 크기
            ]
        )
        
        try:
            # 모바일 디바이스 설정 (iPhone)
            iphone_13 = p.devices['iPhone 13']
            context = browser.new_context(
                **iphone_13,
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                ignore_https_errors=True,
            )
            
            page = context.new_page()
            
            # Anti-detection 설정
            page.add_init_script("""
                // Override the navigator.webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock touch support
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 5
                });
                
                // Hide automation
                window.chrome = {
                    runtime: {},
                };
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            # 1. 모바일 공지사항 페이지로 직접 이동
            print("\n1. 티켓링크 모바일 공지사항 페이지 접속 중...")
            try:
                # wait_until을 'domcontentloaded'로 변경하여 더 빠르게 로드
                page.goto("https://m.ticketlink.co.kr/help/notice", 
                         wait_until="domcontentloaded", 
                         timeout=30000)
                print("   페이지 접속 성공")
                
                # 페이지 로드 대기
                page.wait_for_timeout(3000)
                
                # 스크린샷 저장
                page.screenshot(path="ticketlink_mobile_notice.png", full_page=True)
                print("   스크린샷 저장: ticketlink_mobile_notice.png")
                
            except TimeoutError:
                print("   타임아웃 발생, 페이지 상태 확인 중...")
                # 페이지가 부분적으로라도 로드되었는지 확인
                current_url = page.url
                print(f"   현재 URL: {current_url}")
                
            except Exception as e:
                print(f"\n[오류] 페이지 접속 실패: {e}")
                traceback.print_exc()
                return []
            
            # 2. 티켓 오픈 탭 찾기
            print("\n2. 티켓 오픈 탭 찾는 중...")
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
                        page.click(selector, timeout=5000)
                        tab_found = True
                        print(f"   티켓 오픈 탭 클릭 성공: {selector}")
                        page.wait_for_timeout(2000)
                        break
                except Exception as e:
                    print(f"   [경고] 탭 클릭 실패 (selector: '{selector}'). 다음으로 넘어갑니다. 오류: {e}")
                    traceback.print_exc()
                    continue
            
            if not tab_found:
                print("   티켓 오픈 탭을 찾을 수 없음 - 전체 공지사항을 확인합니다")
            
            # 3. 스크롤하여 더 많은 콘텐츠 로드 (모바일은 무한 스크롤인 경우가 많음)
            print("\n3. 페이지 스크롤 중...")
            last_height = page.evaluate("document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 5
            
            while scroll_attempts < max_scrolls:
                # 페이지 끝까지 스크롤
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"   [경고] 스크롤 중 오류 발생: {e}. 스크롤을 중단합니다.")
                    traceback.print_exc()
                    break
                
                # 새로운 콘텐츠가 로드되었는지 확인
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print(f"   더 이상 로드할 콘텐츠가 없습니다 (스크롤 {scroll_attempts + 1}회)")
                    break
                
                last_height = new_height
                scroll_attempts += 1
                print(f"   스크롤 {scroll_attempts}/{max_scrolls} 완료")
            
            # 4. 페이지 내용 가져오기
            print("\n4. 페이지 내용 추출 중...")
            html_content = page.content()
            
            # HTML 저장
            with open("ticketlink_mobile_content.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print("   HTML 저장: ticketlink_mobile_content.html")
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(html_content, "html.parser")
            
            # 5. 공지사항 목록 찾기
            print("\n5. 공지사항 목록 파싱 중...")
            
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
                        print(f"   선택자 '{selector}'로 {len(items)}개 항목 발견")
                        break
            
            if not items:
                print("   [경고] 공지사항 목록을 찾을 수 없습니다")
                print("   HTML 파일을 확인하여 구조를 분석해주세요")
            
            # 6. 각 항목 파싱
            print("\n6. 개별 항목 파싱 중...")
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
                            print(f"   [티켓오픈] {title[:40]}...")
                        else:
                            print(f"   [일반공지] {title[:40]}...")
                    
                except Exception as e:
                    print(f"   [경고] 항목 파싱 중 오류 발생 (index: {idx}). 건너뜁니다. 오류: {e}")
                    traceback.print_exc()
                    continue
            
            print(f"\n총 {len(ticket_list)}개의 공지사항을 추출했습니다.")
            
            # 티켓 오픈 공지만 필터링 (선택사항)
            ticket_open_list = [t for t in ticket_list if t['additional_info'] == "티켓오픈"]
            print(f"이 중 티켓 오픈 공지는 {len(ticket_open_list)}개입니다.")
            
        except Exception as e:
            print(f"\n[오류] 예상치 못한 오류: {e}")
            traceback.print_exc()
            
        finally:
            browser.close()
    
    return ticket_list

if __name__ == "__main__":
    # 크롤링 실행
    tickets = get_ticketlink_notices()
    
    # 결과 출력
    if tickets:
        print("\n" + "="*70)
        print(f"최종 결과: 총 {len(tickets)}건의 공지사항")
        print("="*70)
        
        # 티켓 오픈 공지만 출력
        ticket_opens = [t for t in tickets if t['additional_info'] == "티켓오픈"]
        
        if ticket_opens:
            print(f"\n티켓 오픈 공지 ({len(ticket_opens)}건):")
            print("-"*70)
            for i, ticket in enumerate(ticket_opens[:10], 1):
                print(f"\n[{i}] {ticket['title']}")
                print(f"    날짜: {ticket['open_date']}")
                print(f"    링크: {ticket['link']}")
        
        # 일반 공지도 일부 출력
        other_notices = [t for t in tickets if t['additional_info'] != "티켓오픈"]
        if other_notices:
            print(f"\n\n기타 공지사항 ({len(other_notices)}건 중 5건):")
            print("-"*70)
            for i, ticket in enumerate(other_notices[:5], 1):
                print(f"\n[{i}] {ticket['title']}")
                print(f"    날짜: {ticket['open_date']}")
    else:
        print("\n공지사항을 찾을 수 없습니다.")
        print("\n디버깅 파일:")
        print("- ticketlink_mobile_notice.png: 페이지 스크린샷")
        print("- ticketlink_mobile_content.html: 페이지 HTML")
