from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def get_melon_notices():
    print("멜론티켓 크롤링 시작...")
    ticket_list = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            permissions=["geolocation", "notifications", "camera", "microphone", "clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            url = "https://ticket.melon.com/csoon/index.htm#orderType=0&pageIndex=1&schGcode=GENRE_ALL&schText=&schDt="
            page.goto(url, timeout=60000)
            
            # 페이지 로딩 대기
            page.wait_for_selector(".wrap_soon", timeout=10000)
            
            # 더 많은 데이터를 로드하기 위해 페이지 스크롤
            scroll_count = 3
            print(f"데이터를 더 불러오기 위해 페이지를 {scroll_count}번 스크롤합니다.")
            for i in range(scroll_count):
                page.keyboard.press("End")
                print(f"스크롤 {i+1}/{scroll_count} 완료...")
                page.wait_for_timeout(1500)
            
            # 페이지 내용 가져오기
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # 공지사항 아이템 선택
            items = soup.select(".wrap_soon .lst_soon > li")
            
            if not items:
                print("[오류] 공지사항 아이템을 찾을 수 없습니다. 웹사이트 구조가 변경되었을 수 있습니다.")
                page.screenshot(path="melon_error.png")
                print("[알림] 'melon_error.png' 파일로 현재 페이지를 저장했습니다.")
                browser.close()
                return []
            
            print(f"파싱할 후보 {len(items)}건 발견. 유효한 데이터만 추출합니다.")
            for item in items:
                try:
                    # 제목 추출
                    title_element = item.select_one(".tit_soon")
                    title = title_element.get_text(strip=True) if title_element else "제목 정보 없음"
                    
                    # 오픈 날짜 추출
                    date_element = item.select_one(".date_open")
                    open_date = date_element.get_text(strip=True) if date_element else "시간 정보 없음"
                    
                    # 장소 추출
                    place_element = item.select_one(".txt_place")
                    place = place_element.get_text(strip=True) if place_element else ""
                    
                    # 링크 추출
                    link_element = item.select_one("a")
                    link = "https://ticket.melon.com" + link_element['href'] if link_element and link_element.has_attr('href') else "링크 없음"
                    
                    ticket_info = {
                        "open_date": open_date,
                        "title": f"{title} - {place}" if place else title,
                        "link": link,
                        "source": "멜론티켓"
                    }
                    ticket_list.append(ticket_info)
                except Exception as e:
                    print(f"아이템 파싱 중 오류 발생: {e}")
                    continue
            
            print(f"멜론티켓 크롤링 완료. 총 {len(ticket_list)}건 발견.")
            browser.close()
            return ticket_list
            
        except Exception as e:
            print(f"\n[오류] 예상치 못한 오류: {e}")
            if not browser.is_closed():
                page.screenshot(path="melon_error.png")
                browser.close()
            return []

if __name__ == "__main__":
    tickets = get_melon_notices()
    if tickets:
        print(f"\n--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            print(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")