import requests, time, json
from bs4 import BeautifulSoup
from datetime import datetime
import schedule, os
import requests
import time
import json

BASE = "https://www.ticketlink.co.kr"
LIST_API = f"{BASE}/help/getNoticeList"          # JS에서 호출하는 엔드포인트[2]

sess = requests.Session()
sess.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": f"{BASE}/help/notice"
})

def fetch_list(page=1, category="", keyword=""):
    try:
        print(f"📋 공지사항 목록 요청 중... (페이지: {page})")
        res = sess.get(LIST_API,
                       params={"page": page,
                               "noticeCategoryCode": category,
                               "title": keyword.replace(" ", "") if keyword else None},
                       timeout=10).json()
        items = res["result"]["result"]
        print(f"📋 {len(items)}개의 공지사항을 찾았습니다.")
        return items
    except Exception as e:
        print(f"✗ 공지사항 목록 요청 실패: {str(e)}")
        return []

def fetch_detail(nid):
    url = f"{BASE}/help/notice/{nid}"
    try:
        html = sess.get(url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        
        # 제목 찾기 - 실제 HTML 구조에 맞는 선택자 사용
        title_element = soup.select_one('dd.title') or soup.select_one('#noticeTitle') or soup.select_one('h2')
        title = title_element.get_text(strip=True) if title_element else f"제목 없음 (ID: {nid})"

        # 본문 찾기 - 실제 HTML 구조에 맞는 선택자 사용
        body_element = soup.select_one('dd.list_cont') or soup.select_one('.list_cont') or soup.select_one('.content')
        body = body_element.get_text("\n", strip=True) if body_element else "본문을 찾을 수 없습니다."
        
        print(f"✓ 공지사항 {nid} 수집 완료: {title[:50]}...")
        return {"id": nid, "title": title, "body": body, "url": url}
        
    except Exception as e:
        print(f"✗ 공지사항 {nid} 수집 실패: {str(e)}")
        return {"id": nid, "title": f"오류 (ID: {nid})", "body": f"수집 실패: {str(e)}", "url": url}

def job():
    print(f"\n🚀 티켓링크 공지사항 수집 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    items = fetch_list(page=1, category="", keyword="")
    if not items:
        print("❌ 수집할 공지사항이 없습니다.")
        return
    
    saved = []
    total = len(items)
    
    for i, it in enumerate(items, 1):
        print(f"\n[{i}/{total}] 공지사항 수집 중...")
        d = fetch_detail(it["noticeId"])
        saved.append(d)
        time.sleep(0.3)  # 서버 부하 방지를 위한 지연
    
    # 결과 저장
    today = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("data", exist_ok=True)
    filename = f"data/notice_{today}.json"
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(saved, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 수집 완료! {len(saved)}건의 공지사항을 '{filename}'에 저장했습니다.")
    except Exception as e:
        print(f"\n❌ 파일 저장 실패: {str(e)}")
    
    print(f"⏰ 다음 수집은 10분 후에 실행됩니다.\n")

if __name__ == "__main__":
    # 10분마다 실행
    schedule.every(10).minutes.do(job)                           # 자동 스케줄[6]
    job()                                                        # 첫 실행
    while True:
        schedule.run_pending()
        time.sleep(1)
