from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def get_yes24_notices():
    print("YES24 크롤링 시작 (더보기 버튼 클릭 방식)...")
    ticket_list = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # 디버깅을 위해 창을 띄웁니다.
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            permissions=["geolocation", "notifications", "camera", "microphone", "clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            url = "https://m.ticket.yes24.com/Notice/List.aspx"
            page.goto(url, timeout=60000)
            
            # ---!!! 핵심 수정 1: '더보기' 버튼을 반복해서 클릭합니다. !!!---
            # 버튼을 몇 번 클릭할지 설정합니다. (3번 클릭 -> 10개 + 30개 = 총 40개 데이터)
            click_count = 3 
            more_button_selector = "a.btn_more" # 사용자님이 찾아주신 바로 그 버튼의 선택자

            print(f"데이터를 더 불러오기 위해 '{more_button_selector}' 버튼을 {click_count}번 클릭합니다.")
            for i in range(click_count):
                try:
                    # '더보기' 버튼이 화면에 보이고, 클릭 가능할 때까지 기다린 후 클릭합니다.
                    page.click(more_button_selector, timeout=5000) # 5초 내에 버튼이 안 보이면 오류 발생
                    print(f"더보기 클릭 {i+1}/{click_count} 완료...")
                    # 새 데이터가 로드될 시간을 1초간 기다립니다.
                    page.wait_for_timeout(1000) 
                except TimeoutError:
                    # ---!!! 핵심 수정 2: 버튼이 더 이상 없을 경우에 대비한 예외 처리 !!!---
                    # 페이지 끝까지 가서 '더보기' 버튼이 사라지면, 오류가 발생합니다.
                    # 이 때, 루프를 중단하고 다음 단계로 넘어갑니다.
                    print("'더보기' 버튼을 더 이상 찾을 수 없습니다. 데이터 수집을 시작합니다.")
                    break

            # 모든 클릭이 끝난 후, 최종적으로 로드된 페이지의 전체 HTML을 가져옵니다.
            html = page.content()
            
            # (이하 파싱 코드는 이전과 동일합니다.)
            soup = BeautifulSoup(html, "html.parser")
            notices = soup.select("a.lnk_brd")
            
            if not notices:
                print("[오류] 공지사항 목록을 찾을 수 없습니다.")
                browser.close()
                return []

            for notice in notices:
                open_date_element = notice.select_one(".brd_dday .txt")
                open_date = open_date_element.get_text(strip=True) if open_date_element else "시간 정보 없음"
                title_element = notice.select_one(".brd_name")
                title = title_element.get_text(strip=True) if title_element else "제목 정보 없음"
                link = "https://m.ticket.yes24.com" + notice['href']
                ticket_info = { "open_date": open_date, "title": title, "link": link, "source": "YES24" }
                ticket_list.append(ticket_info)

            print(f"YES24 크롤링 완료. 총 {len(ticket_list)}건 발견.")
            browser.close()
            return ticket_list

        except Exception as e:
            print(f"\n[오류] 예상치 못한 오류: {e}")
            if not browser.is_closed():
                page.screenshot(path="yes24_click_error.png")
                browser.close()
            return []

if __name__ == "__main__":
    tickets = get_yes24_notices()
    if tickets:
        print(f"\n--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            print(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")