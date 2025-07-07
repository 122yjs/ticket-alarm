"""
데이터베이스 기반 티켓 오픈 모니터링 시스템
주기적으로 티켓 사이트를 크롤링하고 새로운 정보를 DB에 저장한 후 디스코드로 알림을 보냅니다.
"""
import time
import random
import logging
import importlib
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any, Callable

from db_data_manager import get_data_manager
from discord_notifier_db import DatabaseDiscordNotifier

logger = logging.getLogger(__name__)

def get_crawler_functions(sources: List[str]) -> Dict[str, Callable[[], List[Dict[str, Any]]]]:
    """
    crawlers 패키지에서 사용 가능한 크롤러 함수를 동적으로 로드합니다.
    config의 'sources'에 명시된 크롤러만 로드합니다.
    """
    crawler_functions = {}
    for source_name in sources:
        try:
            module_name = f"crawlers.{source_name.lower()}_crawler"
            module = importlib.import_module(module_name)

            func_name = f"get_{source_name.lower()}_notices"
            if hasattr(module, func_name):
                crawler_functions[source_name] = getattr(module, func_name)
                logger.info(f"크롤러 로드 성공: {source_name}")
            else:
                logger.warning(f"'{module_name}' 모듈에서 '{func_name}' 함수를 찾을 수 없습니다.")
        except ImportError:
            logger.warning(f"'{source_name}'에 대한 크롤러 모듈을 찾을 수 없습니다. ({module_name})")
        except Exception as e:
            logger.error(f"{source_name} 크롤러 로드 중 오류 발생: {e}", exc_info=True)
            
    return crawler_functions

def collect_all_tickets(sources: List[str]) -> List[Dict[str, Any]]:
    """
    모든 소스에서 티켓 정보를 병렬로 수집합니다.
    concurrent.futures를 사용하여 각 크롤러를 별도의 스레드에서 실행합니다.
    """
    all_tickets = []
    crawler_functions = get_crawler_functions(sources)
    
    if not crawler_functions:
        logger.error("실행할 크롤러를 찾지 못했습니다. 설정의 'sources' 설정을 확인하세요.")
        return all_tickets
    
    logger.info(f"{len(crawler_functions)}개의 크롤러로 티켓 정보 수집을 시작합니다...")
    
    # 병렬 실행을 위한 ThreadPoolExecutor 사용
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(crawler_functions)) as executor:
        # 각 크롤러를 별도 스레드에서 실행
        future_to_source = {
            executor.submit(crawler_func): source_name 
            for source_name, crawler_func in crawler_functions.items()
        }
        
        # 결과 수집
        for future in concurrent.futures.as_completed(future_to_source):
            source_name = future_to_source[future]
            try:
                tickets = future.result(timeout=300)  # 5분 타임아웃
                if tickets:
                    all_tickets.extend(tickets)
                    logger.info(f"{source_name}: {len(tickets)}개 티켓 수집 완료")
                else:
                    logger.info(f"{source_name}: 수집된 티켓 없음")
            except concurrent.futures.TimeoutError:
                logger.error(f"{source_name} 크롤러 타임아웃 (5분 초과)")
            except Exception as e:
                logger.error(f"{source_name} 크롤러 실행 중 오류: {e}", exc_info=True)
    
    logger.info(f"총 {len(all_tickets)}개의 티켓 정보를 수집했습니다.")
    return all_tickets

def monitor_tickets(config: Dict[str, Any]):
    """
    메인 모니터링 루프
    설정된 간격으로 크롤링을 실행하고 새로운 티켓 정보를 알림으로 전송합니다.
    """
    data_manager = get_data_manager()
    notifier = DatabaseDiscordNotifier(
        webhook_url=config["DISCORD_WEBHOOK_URL"],
        data_manager=data_manager
    )
    
    interval = config.get("interval", 3600)  # 기본 1시간
    keywords = config.get("KEYWORDS", [])
    sources = config.get("sources", ["interpark", "yes24", "melon", "ticketlink"])
    
    logger.info("="*80)
    logger.info("데이터베이스 기반 티켓 모니터링 시스템을 시작합니다.")
    logger.info(f"모니터링 간격: {interval}초 ({interval/60:.1f}분)")
    logger.info(f"모니터링 소스: {', '.join(sources)}")
    logger.info(f"키워드 필터: {', '.join(keywords) if keywords else '없음'}")
    logger.info("="*80)
    
    try:
        while True:
            start_time = time.time()
            logger.info(f"모니터링 사이클 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 1. 모든 소스에서 티켓 정보 수집
            all_tickets = collect_all_tickets(sources)
            
            if not all_tickets:
                logger.info("수집된 티켓 정보가 없습니다.")
            else:
                # 2. 데이터베이스에 저장
                new_ticket_count = data_manager.save_tickets(all_tickets)
                logger.info(f"데이터베이스에 {new_ticket_count}개의 새로운 티켓을 저장했습니다.")
                
                # 3. 키워드 필터링 및 알림 전송
                if new_ticket_count > 0:
                    # 아직 알림을 보내지 않은 티켓 조회 (키워드 필터링 포함)
                    unsent_tickets = data_manager.get_unsent_notifications(keywords)
                    
                    if unsent_tickets:
                        logger.info(f"{len(unsent_tickets)}개의 새로운 티켓에 대해 알림을 전송합니다.")
                        
                        # 배치로 알림 전송
                        sent_count = notifier.send_batch_notifications(unsent_tickets)
                        logger.info(f"{sent_count}개의 알림을 성공적으로 전송했습니다.")
                    else:
                        logger.info("키워드 조건에 맞는 새로운 티켓이 없습니다.")
                
                # 4. 통계 정보 출력
                stats = data_manager.get_statistics()
                logger.info(f"현재 DB 상태 - 총 티켓: {stats['total_count']}, "
                          f"오늘 오픈: {stats['today_count']}, "
                          f"내일 오픈: {stats['tomorrow_count']}")
            
            # 5. 다음 실행까지 대기
            elapsed = time.time() - start_time
            wait_time = max(interval - elapsed, 0)
            
            # 정확한 간격을 위해 조금의 랜덤 지연 추가 (봇 감지 방지)
            jitter = random.uniform(0, 60)
            wait_time += jitter
            
            next_run_str = datetime.fromtimestamp(time.time() + wait_time).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"다음 실행 시간: {next_run_str} (약 {wait_time/60:.1f}분 후)")
            logger.info("-" * 80)
            
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        logger.info("모니터링을 종료합니다.")
    except Exception as e:
        logger.critical(f"모니터링 중 치명적인 오류 발생: {e}", exc_info=True)
        raise

def run_once(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    한 번만 크롤링을 실행하고 결과를 반환합니다.
    테스트나 수동 실행용입니다.
    """
    data_manager = get_data_manager()
    sources = config.get("sources", ["interpark", "yes24", "melon", "ticketlink"])
    keywords = config.get("KEYWORDS", [])
    
    logger.info("일회성 크롤링을 시작합니다...")
    
    # 티켓 정보 수집
    all_tickets = collect_all_tickets(sources)
    
    if not all_tickets:
        return {
            "status": "success",
            "message": "수집된 티켓이 없습니다.",
            "collected_count": 0,
            "new_count": 0,
            "filtered_count": 0
        }
    
    # 데이터베이스에 저장
    new_count = data_manager.save_tickets(all_tickets)
    
    # 키워드 필터링
    if keywords:
        filtered_tickets = data_manager.filter_tickets_by_keywords(all_tickets, keywords)
        filtered_count = len(filtered_tickets)
    else:
        filtered_count = len(all_tickets)
    
    # 통계 정보
    stats = data_manager.get_statistics()
    
    result = {
        "status": "success",
        "message": "크롤링이 완료되었습니다.",
        "collected_count": len(all_tickets),
        "new_count": new_count,
        "filtered_count": filtered_count,
        "total_in_db": stats['total_count'],
        "sources": list(stats['source_counts'].keys()),
        "execution_time": datetime.now().isoformat()
    }
    
    logger.info(f"크롤링 완료: {result}")
    return result

def main():
    """메인 실행 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s [%(levelname)s]: %(message)s'
    )

    # 데이터 매니저 초기화
    data_manager = get_data_manager()
    
    # 설정 로드
    config = data_manager.load_config()
    
    if not config:
        logger.error("설정을 로드할 수 없습니다. config.json 파일을 확인하세요.")
        return
    
    # 필수 설정 확인
    required_keys = ["DISCORD_WEBHOOK_URL", "KEYWORDS", "interval", "sources"]
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        logger.error(f"설정에 다음 필수 키가 누락되었습니다: {', '.join(missing_keys)}")
        return
    
    if not config.get("DISCORD_WEBHOOK_URL") or "여기에_디스코드_웹훅_URL을_입력하세요" in config["DISCORD_WEBHOOK_URL"]:
        logger.error("디스코드 웹훅 URL을 설정해야 합니다.")
        return
    
    # 모니터링 시작
    monitor_tickets(config)

if __name__ == "__main__":
    main()