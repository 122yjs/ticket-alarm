from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def get_interpark_notices():
    print("인터파크 크롤링 시작 (최종 진화 버전)...")
    ticket_list = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            url = "https://tickets.interpark.com/contents/notice"
            page.goto(url, timeout=60000)
            
            # 스크롤 방식을 유지하며 더 많은 데이터를 로드합니다.
            scroll_count = 3
            print(f"데이터를 더 불러오기 위해 페이지를 {scroll_count}번 스크롤합니다.")
            for i in range(scroll_count):
                page.keyboard.press("End")
                print(f"스크롤 {i+1}/{scroll_count} 완료...")
                page.wait_for_timeout(1500)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # ---!!! 최종 수정: 실제 HTML 구조 분석 기반으로 선택자 및 로직 최적화 !!!---
            # 1. 정확한 클래스 이름으로 아이템 목록을 선택합니다.
            #    각 아이템은 'NoticeItem_ticketItem__' 클래스를 포함하는 'a' 태그입니다.
            items = soup.select("a[class*='NoticeItem_ticketItem__']")
            
            if not items:
                print("[오류] 공지사항 아이템을 찾을 수 없습니다. 웹사이트 구조가 변경되었을 수 있습니다.")
                # 디버깅을 위해 현재 페이지 스크린샷 저장
                page.screenshot(path="interpark_final_error.png")
                print("[알림] 'interpark_final_error.png' 파일로 현재 페이지를 저장했습니다.")
                browser.close()
                return []

            print(f"파싱할 후보 {len(items)}건 발견. 유효한 데이터만 추출합니다.")
            for item in items:
                # 2. 아이템 내부의 제목, 날짜, 장소 정보 선택자를 find_all을 사용하여 더 유연하게 탐색합니다.
                #    a 태그의 모든 자손 중에서 li 태그를 직접 찾습니다.
                list_items = item.find_all("li")
                
                if len(list_items) < 2: # 최소한 날짜와 제목은 있어야 합니다.
                    continue

                date_element = list_items[0]
                title_element = list_items[1]
                place_element = list_items[2] if len(list_items) > 2 else None

                # 필수 정보(제목, 날짜)만 확인하고, 링크(href)는 선택적으로 처리합니다.
                if not all([title_element, date_element]):
                    continue

                title = title_element.get_text(strip=True)
                open_date = date_element.get_text(strip=True)
                place = place_element.get_text(strip=True) if place_element else ""
                
                base_url = "https://tickets.interpark.com"
                # 링크는 있을 경우에만 추가하고, 없으면 '링크 없음'으로 표시합니다.
                link = base_url + item['href'] if item.has_attr('href') else "링크 없음"
                
                ticket_info = {
                    "open_date": open_date,
                    "title": f"{title} - {place}" if place else title,
                    "link": link,
                    "source": "인터파크"
                }
                ticket_list.append(ticket_info)
            
            print(f"인터파크 크롤링 완료. 총 {len(ticket_list)}건 발견.")
            browser.close()
            return ticket_list

        except Exception as e:
            print(f"\n[오류] 예상치 못한 오류: {e}")
            if not browser.is_closed():
                page.screenshot(path="interpark_final_error.png")
                browser.close()
            return []

if __name__ == "__main__":
    tickets = get_interpark_notices()
    if tickets:
        print(f"\n--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            print(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")