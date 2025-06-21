import logging
from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def get_melon_notices():
    logging.info("멜론티켓 크롤링 시작...")
    ticket_list = []
    seen_links = set()  # 중복 티켓을 제거하기 위한 set

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
            
            scroll_count = 3
            logging.info(f"데이터를 더 불러오기 위해 페이지를 {scroll_count}번 스크롤합니다.")
            for i in range(scroll_count):
                page.keyboard.press("End")
                logging.info(f"스크롤 {i+1}/{scroll_count} 완료...")
                page.wait_for_timeout(1500)
            
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
            # browser 객체의 연결 상태를 확인하는 올바른 메서드는 is_connected() 입니다.
            if browser.is_connected():
                page.screenshot(path="melon_error.png")
                browser.close()
            return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    tickets = get_melon_notices()
    if tickets:
        logging.info(f"--- 최종 결과 ({len(tickets)}건) ---")
        for ticket in tickets:
            logging.info(f"[{ticket['source']}] {ticket['open_date']} - {ticket['title']}")