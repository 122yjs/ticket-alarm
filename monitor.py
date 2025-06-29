"""
티켓 오픈 모니터링 시스템
주기적으로 티켓 사이트를 크롤링하고 새로운 정보를 디스코드로 알림을 보냅니다.
"""
import time
import random
import json
import os
import logging
import importlib
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any, Callable

from supabase import create_client, Client
from discord_notifier import DiscordNotifier


def load_config() -> Dict[str, Any]:
    """
    data/config.json 파일에서 설정을 로드합니다.
    필수 키가 없으면 프로그램을 종료합니다.
    """
    config_path = os.path.join('data', 'config.json')

    if not os.path.exists(config_path):
        logging.error(f"설정 파일({config_path})을 찾을 수 없습니다.")
        logging.error("config.json.example 파일을 복사하여 data/config.json 파일을 생성하고, 내용을 채워주세요.")
        exit(1)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        logging.error(f"{config_path} 파일이 올바른 JSON 형식이 아닙니다.")
        exit(1)
    except Exception as e:
        logging.error(f"설정 파일 로드 중 오류 발생: {e}")
        exit(1)

    # 필수 키 확인
    required_keys = ["DISCORD_WEBHOOK_URL", "KEYWORDS", "interval", "sources"]
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        logging.error(f"설정 파일에 다음 필수 키가 누락되었습니다: {', '.join(missing_keys)}")
        exit(1)

    if not config.get("DISCORD_WEBHOOK_URL") or "여기에_디스코드_웹훅_URL을_입력하세요" in config["DISCORD_WEBHOOK_URL"]:
        logging.error("data/config.json 파일에 디스코드 웹훅 URL을 설정해야 합니다.")
        exit(1)

    return config


def get_db_client() -> Client:
    """Supabase 클라이언트를 생성합니다."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        logging.error("SUPABASE_URL 또는 SUPABASE_KEY 환경변수가 설정되지 않았습니다.")
        raise ValueError("Supabase 접속 정보가 없습니다.")
    return create_client(url, key)


def get_existing_ticket_links(db: Client) -> set:
    """DB에 이미 저장된 모든 티켓 링크를 가져옵니다."""
    try:
        response = db.table('tickets').select('link').execute()
        links = {item['link'] for item in response.data}
        logging.info(f"DB에서 {len(links)}개의 기존 티켓 링크를 로드했습니다.")
        return links
    except Exception as e:
        logging.error(f"기존 티켓 링크 로드 중 오류: {e}")
        return set()


def save_new_tickets_to_db(db: Client, tickets: List[Dict[str, Any]]):
    """새로운 티켓 정보를 DB에 저장합니다."""
    if not tickets:
        return 0

    try:
        # DB 스키마에 맞게 데이터 정리
        records_to_insert = []
        for ticket in tickets:
            records_to_insert.append({
                'open_date': ticket.get('open_date'),
                'title': ticket.get('title'),
                'link': ticket.get('link'),
                'source': ticket.get('source'),
                'additional_info': ticket.get('additional_info')
            })

        response = db.table('tickets').insert(records_to_insert).execute()
        count = len(response.data)
        logging.info(f"{count}개의 새로운 티켓을 DB에 저장했습니다.")
        return count
    except Exception as e:
        logging.error(f"DB에 티켓 저장 중 오류: {e}")
        return 0


# def save_all_tickets(tickets: List[Dict[str, Any]], filename: str = "all_tickets.json"):
#     """수집된 모든 티켓 정보를 JSON 파일로 저장합니다."""
#     try:
#         # data 디렉토리가 없으면 생성
#         if not os.path.exists('data'):
#             os.makedirs('data')
#         
#         filepath = os.path.join('data', filename)
#         with open(filepath, 'w', encoding='utf-8') as f:
#             json.dump({
#                 "last_updated": datetime.now().isoformat(),
#                 "count": len(tickets),
#                 "tickets": tickets
#             }, f, ensure_ascii=False, indent=2)
#         logging.info(f"{len(tickets)}개의 티켓 정보를 {filepath}에 저장했습니다.")
#     except Exception as e:
#         logging.error(f"티켓 정보 저장 중 오류 발생: {e}")


def filter_tickets_by_keyword(tickets: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    """티켓 목록에서 키워드가 포함된 티켓만 필터링합니다."""
    if not keywords:
        return tickets
    
    filtered_tickets = []
    for ticket in tickets:
        # 티켓의 title, source, link 등 모든 텍스트 필드를 합쳐서 키워드 검색
        search_text = f"{ticket.get('title', '')} {ticket.get('source', '')}".lower()
        if any(keyword.lower() in search_text for keyword in keywords):
            filtered_tickets.append(ticket)
            
    return filtered_tickets


def get_crawler_functions(sources: List[str]) -> Dict[str, Callable[[], List[Dict[str, Any]]]]:
    """
    crawlers 패키지에서 사용 가능한 크롤러 함수를 동적으로 로드합니다.
    config.json의 'sources'에 명시된 크롤러만 로드합니다.
    """
    crawler_functions = {}
    for source_name in sources:
        try:
            module_name = f"crawlers.{source_name.lower()}_crawler"
            # ex) crawlers.interpark_crawler
            module = importlib.import_module(module_name)

            # ex) get_interpark_notices
            func_name = f"get_{source_name.lower()}_notices"
            if hasattr(module, func_name):
                crawler_functions[source_name] = getattr(module, func_name)
            else:
                logging.warning(f"'{module_name}' 모듈에서 '{func_name}' 함수를 찾을 수 없습니다.")
        except ImportError:
            logging.warning(f"'{source_name}'에 대한 크롤러 모듈을 찾을 수 없습니다. ({module_name})")
        except Exception as e:
            logging.error(f"{source_name} 크롤러 로드 중 오류 발생: {e}", exc_info=True)
            
    return crawler_functions


def collect_all_tickets(sources: List[str]) -> List[Dict[str, Any]]:
    """
    모든 소스에서 티켓 정보를 병렬로 수집합니다.
    concurrent.futures를 사용하여 각 크롤러를 별도의 스레드에서 실행합니다.
    """
    all_tickets = []
    crawler_functions = get_crawler_functions(sources)

    if not crawler_functions:
        logging.error("실행할 크롤러를 찾지 못했습니다. config.json의 'sources' 설정을 확인하세요.")
        return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(crawler_functions)) as executor:
        # 각 크롤러 함수를 실행하고 Future 객체를 딕셔너리에 저장
        future_to_source = {executor.submit(func): source for source, func in crawler_functions.items()}
        
        for future in concurrent.futures.as_completed(future_to_source):
            source = future_to_source[future]
            try:
                # 각 Future의 결과를 가져옵니다 (크롤링 결과).
                tickets = future.result()
                if tickets:
                    all_tickets.extend(tickets)
                    logging.info(f"{source.upper()} 크롤링 완료: {len(tickets)}개 수집")
                else:
                    logging.info(f"{source.upper()} 크롤링 완료: 수집된 정보 없음")
            except Exception as e:
                logging.error(f"{source.upper()} 크롤링 중 오류 발생: {e}", exc_info=True)
    
    return all_tickets


def monitor_tickets(config: Dict[str, Any]):
    """
    주기적으로 티켓 정보를 모니터링하고 DB에 저장 후 알림을 보냅니다.
    """
    db = get_db_client()  # DB 클라이언트 생성
    notifier = DiscordNotifier(config["DISCORD_WEBHOOK_URL"])
    
    logging.info("티켓 모니터링을 시작합니다...")
    
    # --- 메인 로직 시작 (while True 루프 대신 단일 실행으로 변경) ---
    start_time = time.time()
    logging.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 티켓 정보 수집 시작")
    
    # 1. 모든 티켓 정보 수집
    all_tickets = collect_all_tickets(config["sources"])
    
    # 2. DB에 이미 있는 티켓 필터링
    existing_links = get_existing_ticket_links(db)
    new_tickets = [t for t in all_tickets if t.get('link') and t['link'] not in existing_links]
    logging.info(f"총 {len(all_tickets)}개 수집, 신규 티켓: {len(new_tickets)}개")
    
    # 3. 새로운 티켓 DB에 저장
    if new_tickets:
        save_new_tickets_to_db(db, new_tickets)
    
    # 4. 키워드로 필터링 (새로운 티켓 중에서)
    filtered_tickets = filter_tickets_by_keyword(new_tickets, config["KEYWORDS"])
    logging.info(f"키워드 필터링 후 알림 보낼 티켓: {len(filtered_tickets)}개")
    
    # 5. 알림 전송
    if filtered_tickets:
        sent_count = notifier.send_batch_notifications(filtered_tickets)  # 이 함수는 내부에 sent_notifications.json 대신 DB를 사용하도록 수정하면 더 좋음
        logging.info(f"{sent_count}개의 새로운 티켓 정보를 디스코드로 전송했습니다.")
    else:
        logging.info("전송할 새로운 티켓 정보가 없습니다.")
    
    logging.info(f"작업 완료. (소요 시간: {time.time() - start_time:.2f}초)")


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    config = load_config()
    # GitHub Actions에서는 무한 루프가 필요 없으므로 monitor_tickets를 직접 호출
    monitor_tickets(config)


if __name__ == "__main__":
    main()