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


def save_all_tickets(tickets: List[Dict[str, Any]], filename: str = "all_tickets.json"):
    """수집된 모든 티켓 정보를 JSON 파일로 저장합니다."""
    try:
        # data 디렉토리가 없으면 생성
        if not os.path.exists('data'):
            os.makedirs('data')
        
        filepath = os.path.join('data', filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "last_updated": datetime.now().isoformat(),
                "count": len(tickets),
                "tickets": tickets
            }, f, ensure_ascii=False, indent=2)
        logging.info(f"{len(tickets)}개의 티켓 정보를 {filepath}에 저장했습니다.")
    except Exception as e:
        logging.error(f"티켓 정보 저장 중 오류 발생: {e}")


def filter_tickets_by_keyword(tickets: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    """
    키워드로 티켓을 필터링합니다.
    
    Args:
        tickets: 티켓 정보 리스트
        keywords: 필터링할 키워드 리스트
        
    Returns:
        필터링된 티켓 리스트
    """
    if not keywords:
        return tickets
    
    filtered_tickets = []
    for ticket in tickets:
        title = ticket.get('title', '').lower()
        description = ticket.get('description', '').lower()
        
        # 제목과 설명에서 키워드 검색
        text_to_search = f"{title} {description}"
        if any(keyword.lower() in text_to_search for keyword in keywords):
            filtered_tickets.append(ticket)
    
    return filtered_tickets


def setup_discord_notifier(config: Dict[str, Any]) -> DiscordNotifier:
    """
    설정을 기반으로 디스코드 알림기를 설정합니다.
    
    Args:
        config: 설정 정보
        
    Returns:
        설정된 DiscordNotifier 인스턴스
    """
    webhook_url = config.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        raise ValueError("DISCORD_WEBHOOK_URL이 설정되지 않았습니다.")
    
    keywords = config.get('KEYWORDS', [])
    priority_keywords = config.get('PRIORITY_KEYWORDS', [])
    
    return DiscordNotifier(
        webhook_url=webhook_url,
        keywords=keywords,
        priority_keywords=priority_keywords
    )


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


def monitor_tickets():
    """
    티켓 정보를 주기적으로 모니터링하고 디스코드로 알림을 보냅니다.
    개선된 알림 시스템과 통계 기능을 포함합니다.
    """
    config = load_config()
    
    # 개선된 디스코드 알림기 초기화
    try:
        discord_notifier = setup_discord_notifier(config)
        logging.info("디스코드 알림기가 성공적으로 초기화되었습니다.")
    except Exception as e:
        logging.error(f"디스코드 알림기 초기화 실패: {e}")
        return
    
    logging.info("티켓 모니터링을 시작합니다...")
    
    # 모니터링 통계
    monitoring_stats = {
        'total_cycles': 0,
        'total_tickets_found': 0,
        'total_notifications_sent': 0,
        'start_time': datetime.now()
    }
    
    while True:
        try:
            monitoring_stats['total_cycles'] += 1
            cycle_start = datetime.now()
            
            logging.info(f"모니터링 사이클 #{monitoring_stats['total_cycles']} 시작")
            
            # 모든 소스에서 티켓 정보 수집
            all_tickets = collect_all_tickets(config['sources'])
            
            if all_tickets:
                monitoring_stats['total_tickets_found'] += len(all_tickets)
                
                # 키워드로 필터링 (디스코드 알림기에서도 추가 필터링 수행)
                filtered_tickets = filter_tickets_by_keyword(all_tickets, config.get('KEYWORDS', []))
                
                if filtered_tickets:
                    logging.info(f"필터링된 티켓 {len(filtered_tickets)}개를 발견했습니다.")
                    
                    # 배치 알림 전송 (개선된 시스템 사용)
                    batch_delay = config.get('notification_delay', 1.0)  # 기본 1초 지연
                    max_batch_size = config.get('max_notifications_per_cycle', 10)  # 기본 10개 제한
                    
                    result = discord_notifier.send_batch_notifications(
                        filtered_tickets, 
                        delay=batch_delay,
                        max_per_batch=max_batch_size
                    )
                    
                    monitoring_stats['total_notifications_sent'] += result['sent']
                    
                    # 결과 로깅
                    if result['sent'] > 0:
                        logging.info(f"알림 전송 완료: 성공 {result['sent']}개, 스킵 {result['skipped']}개, 실패 {result['failed']}개")
                    else:
                        logging.info("새로운 티켓이 없거나 모든 알림이 스킵되었습니다.")
                        
                    # 통계 정보 출력 (매 10사이클마다)
                    if monitoring_stats['total_cycles'] % 10 == 0:
                        stats = discord_notifier.get_notification_stats()
                        uptime = datetime.now() - monitoring_stats['start_time']
                        logging.info(f"모니터링 통계 - 가동시간: {uptime}, 총 사이클: {monitoring_stats['total_cycles']}, "
                                   f"오늘 알림: {stats['today_count']}개, 총 알림: {stats['total_count']}개")
                        
                else:
                    logging.info("키워드 조건에 맞는 티켓이 없습니다.")
            else:
                logging.info("수집된 티켓이 없습니다.")
            
            # 사이클 완료 시간 계산
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            
            # 다음 실행까지 대기
            interval = config.get('interval', 300)  # 기본 5분
            actual_wait = max(0, interval - cycle_duration)  # 실행 시간을 고려한 대기 시간
            
            if actual_wait > 0:
                logging.info(f"사이클 완료 (소요시간: {cycle_duration:.1f}초). {actual_wait:.0f}초 후 다시 확인합니다.")
                time.sleep(actual_wait)
            else:
                logging.warning(f"사이클 실행 시간({cycle_duration:.1f}초)이 설정된 간격({interval}초)을 초과했습니다.")
            
        except KeyboardInterrupt:
            logging.info("사용자 요청으로 모니터링을 중단합니다.")
            # 최종 통계 출력
            uptime = datetime.now() - monitoring_stats['start_time']
            logging.info(f"최종 통계 - 가동시간: {uptime}, 총 사이클: {monitoring_stats['total_cycles']}, "
                       f"발견된 티켓: {monitoring_stats['total_tickets_found']}개, 전송된 알림: {monitoring_stats['total_notifications_sent']}개")
            break
        except Exception as e:
            logging.error(f"모니터링 중 오류 발생: {e}")
            logging.info("60초 후 재시도합니다.")
            time.sleep(60)  # 오류 발생 시 1분 대기 후 재시도


def main():
    """메인 실행 함수"""
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')

    # 설정 로드
    config = load_config()
    
    # 모니터링 시작
    monitor_tickets()


if __name__ == "__main__":
    main()