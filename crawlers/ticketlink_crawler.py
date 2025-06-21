from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import random
import time
import os
import tempfile

def get_ticketlink_notices():
    print("티켓링크 크롤링 시작...")
    ticket_list = []

    # 임시 사용자 데이터 디렉토리 생성
    user_data_dir = os.path.join(tempfile.gettempdir(), "playwright_ticketlink_profile")
    os.makedirs(user_data_dir, exist_ok=True)
    print(f"사용자 데이터 디렉토리: {user_data_dir}")

    with sync_playwright() as p:
        # 브라우저 컨텍스트 설정 강화 (persistent context 사용)
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,  # 디버깅을 위해 헤드리스 모드 비활성화
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--window-size=1920,1080',
                '--start-maximized'
            ],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            viewport={"width": 1920, "height": 1080},
            permissions=["geolocation", "notifications", "camera", "microphone", "clipboard-read", "clipboard-write"],
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
                "Connection": "keep-alive",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        
        # 페이지 생성 및 스텔스 설정
        page = context.new_page()
        
        # 웹드라이버 감지 방지
        page.add_init_script("""
        // 웹드라이버 속성 제거
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // 자동화 감지 방지
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {
                    0: {type: "application/x-google-chrome-pdf", description: "Portable Document Format"},
                    description: "Portable Document Format",
                    filename: "internal-pdf-viewer",
                    length: 1,
                    name: "Chrome PDF Plugin"
                },
                {
                    0: {type: "application/pdf", description: "Portable Document Format"},
                    description: "Portable Document Format",
                    filename: "internal-pdf-viewer",
                    length: 1,
                    name: "Chrome PDF Viewer"
                },
                {
                    0: {type: "application/x-nacl", description: "Native Client Executable"},
                    1: {type: "application/x-pnacl", description: "Portable Native Client Executable"},
                    description: "Native Client",
                    filename: "internal-nacl-plugin",
                    length: 2,
                    name: "Native Client"
                }
            ]
        });
        
        // 언어 설정
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ko-KR', 'ko', 'en-US', 'en']
        });
        
        // 하드웨어 동시성 설정
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });
        
        // 사용자 에이전트 데이터 설정
        if (!window.navigator.userAgentData) {
            Object.defineProperty(navigator, 'userAgentData', {
                get: () => ({
                    brands: [
                        {brand: 'Not_A Brand', version: '8'},
                        {brand: 'Chromium', version: '120'},
                        {brand: 'Microsoft Edge', version: '120'}
                    ],
                    mobile: false,
                    platform: 'Windows'
                })
            });
        }
        """)

        try:
            # 인간과 유사한 브라우징 패턴 시뮬레이션
            
            # 1. 먼저 메인 페이지 방문
            print("티켓링크 메인 페이지 방문 중...")
            page.goto("https://www.ticketlink.co.kr/", timeout=60000)
            
            # 랜덤 대기 (인간처럼 행동)
            wait_time = random.uniform(2, 4)
            print(f"메인 페이지 로딩 대기 중... ({wait_time:.1f}초)")
            page.wait_for_timeout(wait_time * 1000)
            
            # 2. 스크롤 시뮬레이션
            print("자연스러운 스크롤 시뮬레이션 중...")
            for _ in range(3):
                # 랜덤한 거리만큼 스크롤
                scroll_distance = random.randint(300, 700)
                page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                page.wait_for_timeout(random.uniform(0.5, 1.5) * 1000)
            
            # 3. 고객센터 메뉴로 이동
            print("고객센터 메뉴로 이동 중...")
            try:
                # 고객센터 메뉴 찾기 및 클릭
                page.click('a:has-text("고객센터")', timeout=5000)
                page.wait_for_timeout(random.uniform(1, 2) * 1000)
            except Exception as e:
                print(f"고객센터 메뉴 클릭 실패, 직접 URL로 이동: {e}")
                # 실패 시 직접 URL로 이동
                page.goto("https://www.ticketlink.co.kr/help/notice", timeout=60000)
            
            # 4. 공지사항 페이지 로딩 대기
            print("공지사항 페이지 로딩 대기 중...")
            page.wait_for_selector(".board-list", timeout=15000)
            
            # 5. 티켓 오픈 공지 탭으로 이동
            print("티켓 오픈 공지 탭으로 이동 중...")
            try:
                # 티켓 오픈 탭 선택자 확인 및 클릭
                ticket_open_tab = page.locator('a[href="#TICKET_OPEN"]')
                if ticket_open_tab:
                    # 탭 위치로 스크롤
                    ticket_open_tab.scroll_into_view_if_needed()
                    page.wait_for_timeout(random.uniform(0.5, 1) * 1000)
                    
                    # 탭 클릭
                    ticket_open_tab.click()
                    wait_time = random.uniform(1.5, 2.5)
                    print(f"티켓 오픈 탭 클릭 후 대기 중... ({wait_time:.1f}초)")
                    page.wait_for_timeout(wait_time * 1000)
            except Exception as e:
                print(f"티켓 오픈 탭 클릭 중 오류: {e}")
                # URL 해시 직접 변경 시도
                page.evaluate("window.location.hash = '#TICKET_OPEN'")
                page.wait_for_timeout(2000)
            
            # 6. 페이지 로딩 대기
            print("티켓 오픈 공지 목록 로딩 대기 중...")
            page.wait_for_selector("#TICKET_OPEN .board-list", timeout=15000)
            
            # 7. 더 많은 데이터를 로드하기 위해 '더보기' 버튼 클릭 (있는 경우)
            try:
                more_button_selector = ".more-btn"
                click_count = 3
                
                for i in range(click_count):
                    # 더보기 버튼이 있는지 확인
                    if page.is_visible(more_button_selector):
                        # 버튼으로 스크롤
                        page.locator(more_button_selector).scroll_into_view_if_needed()
                        page.wait_for_timeout(random.uniform(0.5, 1) * 1000)
                        
                        # 버튼 클릭
                        page.click(more_button_selector)
                        wait_time = random.uniform(1.5, 2.5)
                        print(f"더보기 버튼 클릭 {i+1}/{click_count} 완료... ({wait_time:.1f}초 대기)")
                        page.wait_for_timeout(wait_time * 1000)
                    else:
                        print("더 이상 더보기 버튼이 없습니다.")
                        break
            except Exception as e:
                print(f"더보기 버튼 클릭 중 오류: {e}")
            
            # 8. 최종 페이지 스크롤
            print("페이지 전체 내용 확인을 위한 스크롤 중...")
            for _ in range(4):
                # 랜덤한 거리만큼 스크롤
                scroll_distance = random.randint(200, 500)
                page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                page.wait_for_timeout(random.uniform(0.3, 0.8) * 1000)
            
            # 9. 페이지 내용 가져오기
            print("페이지 내용 추출 중...")
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # 10. 티켓 오픈 공지 아이템 선택
            print("티켓 오픈 공지 데이터 추출 중...")
            ticket_open_section = soup.select_one("#TICKET_OPEN")
            if not ticket_open_section:
                print("[오류] 티켓 오픈 섹션을 찾을 수 없습니다.")
                # 디버깅을 위해 현재 페이지 스크린샷 및 HTML 저장
                page.screenshot(path="ticketlink_error.png")
                with open("ticketlink_error.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("[알림] 'ticketlink_error.png'와 'ticketlink_error.html' 파일로 현재 페이지를 저장했습니다.")
                context.close()
                return []
                
            items = ticket_open_section.select(".board-list li")
            
            if not items:
                print("[오류] 공지사항 아이템을 찾을 수 없습니다. 웹사이트 구조가 변경되었을 수 있습니다.")
                # 디버깅을 위해 현재 페이지 스크린샷 및 HTML 저장
                page.screenshot(path="ticketlink_error.png")
                with open("ticketlink_error.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("[알림] 'ticketlink_error.png'와 'ticketlink_error.html' 파일로 현재 페이지를 저장했습니다.")
                context.close()
                return []
            
            print(f"파싱할 후보 {len(items)}건 발견. 유효한 데이터만 추출합니다.")
            for item in items:
                try:
                    # 제목 추출
                    title_element = item.select_one(".title")
                    title = title_element.get_text(strip=True) if title_element else "제목 정보 없음"
                    
                    # 날짜 추출
                    date_element = item.select_one(".date")
                    open_date = date_element.get_text(strip=True) if date_element else "시간 정보 없음"
                    
                    # 링크 추출
                    link_element = item.select_one("a")
                    base_url = "https://www.ticketlink.co.kr"
                    link = base_url + link_element['href'] if link_element and link_element.has_attr('href') else "링크 없음"
                    
                    # 추가 정보 추출 시도 (있는 경우)
                    info_element = item.select_one(".info")
                    additional_info = info_element.get_text(strip=True) if info_element else ""
                    
                    # 최종 티켓 정보 구성
                    ticket_info = {
                        "open_date": open_date,
                        "title": title,
                        "link": link,
                        "additional_info": additional_info,
                        "source": "티켓링크"
                    }
                    ticket_list.append(ticket_info)
                except Exception as e:
                    print(f"아이템 파싱 중 오류 발생: {e}")
                    continue
            
            # 11. 크롤링 완료 및 결과 반환
            print(f"티켓링크 크롤링 완료. 총 {len(ticket_list)}건 발견.")
            
            # 브라우저 종료 전 랜덤 대기 (자연스러운 종료)
            wait_time = random.uniform(1, 2)
            page.wait_for_timeout(wait_time * 1000)
            context.close()
            return ticket_list
            
        except Exception as e:
            print(f"\n[오류] 예상치 못한 오류: {e}")
            try:
                # 디버깅을 위해 현재 페이지 스크린샷 및 HTML 저장
                page.screenshot(path="ticketlink_error.png")
                html_content = page.content()
                with open("ticketlink_error.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                print("[알림] 'ticketlink_error.png'와 'ticketlink_error.html' 파일로 현재 페이지를 저장했습니다.")
            except Exception as screenshot_error:
                print(f"스크린샷 저장 중 오류: {screenshot_error}")
            finally:
                context.close()
            return []

if __name__ == "__main__":
    tickets = get_ticketlink_notices()
    if tickets:
        print(f"\n--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            print(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")