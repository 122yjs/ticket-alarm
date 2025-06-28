import requests, sys, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.ticketlink.co.kr"
LIST_URL = f"{BASE}/help/notice"

# 1) 세션 & 브라우저 흉내 헤더
sess = requests.Session()
sess.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9"
})

def fetch_list():
    """공지 리스트 페이지에서 (제목, 링크) 튜플 목록 반환"""
    html = sess.get(LIST_URL, timeout=10).text

    # ── 디버그용으로 로컬에 저장 ──
    # with open("notice_list_raw.html", "w", encoding="utf-8") as f:
    #     f.write(html)

    soup = BeautifulSoup(html, "html.parser")

    # ① table 구조일 때
    links = soup.select("table tbody tr a")
    # ② ul·li 구조일 때(예비 선택자)
    if not links:
        links = soup.select("ul.board_list li a")

    results = []
    for a in links:
        title = a.get_text(strip=True)
        href  = urljoin(BASE, a["href"])
        results.append((title, href))

    return results

def fetch_detail(url: str) -> dict:
    """상세 페이지에서 제목·본문을 딕셔너리로 반환"""
    html = sess.get(url, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("h3").get_text(strip=True)        # 제목 태그[2]
    body  = soup.select_one(".cont_area").get_text("\n", strip=True)  # 본문 영역[2]
    return {"title": title, "body": body}

if __name__ == "__main__":
    notices = fetch_list()
    if not notices:
        print("공지 글을 찾지 못했습니다. 선택자 확인 필요!")
        sys.exit()

    print(f"총 {len(notices)}개의 글을 찾았습니다.\n첫 번째 글 살펴보기 ↓")
    first_title, first_link = notices[0]
    print("제목 :", first_title)
    print("URL :", first_link)

    detail = fetch_detail(first_link)
    print("\n===== 상세 내용 =====")
    print("제목 :", detail["title"])
    print("본문 앞 200자 :", detail["body"][:200], "…")