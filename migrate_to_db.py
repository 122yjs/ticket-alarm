"""
JSON 파일 기반 데이터를 SQLite 데이터베이스로 마이그레이션하는 스크립트
"""

import json
import os
import logging
from datetime import datetime
from database import get_database

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger(__name__)

def migrate_json_to_db():
    """JSON 파일의 데이터를 데이터베이스로 마이그레이션"""
    
    db = get_database()
    
    # 1. 기존 티켓 데이터 마이그레이션
    tickets_file = "data/all_tickets.json"
    if os.path.exists(tickets_file):
        logger.info(f"티켓 데이터 마이그레이션 시작: {tickets_file}")
        
        try:
            with open(tickets_file, 'r', encoding='utf-8') as f:
                tickets_data = json.load(f)
            
            if isinstance(tickets_data, dict) and 'tickets' in tickets_data:
                tickets = tickets_data['tickets']
            elif isinstance(tickets_data, list):
                tickets = tickets_data
            else:
                logger.error("알 수 없는 티켓 데이터 형식")
                return False
            
            # 데이터베이스에 삽입
            inserted_count = db.insert_tickets(tickets)
            logger.info(f"티켓 데이터 마이그레이션 완료: {inserted_count}개 삽입")
            
            # 백업 파일 생성
            backup_file = f"{tickets_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(tickets_file, backup_file)
            logger.info(f"기존 파일을 백업했습니다: {backup_file}")
            
        except Exception as e:
            logger.error(f"티켓 데이터 마이그레이션 실패: {e}")
            return False
    else:
        logger.info("기존 티켓 데이터 파일이 없습니다.")
    
    # 2. 설정 데이터 마이그레이션
    config_file = "data/config.json"
    if os.path.exists(config_file):
        logger.info(f"설정 데이터 마이그레이션 시작: {config_file}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 설정을 데이터베이스에 저장
            for key, value in config_data.items():
                db.save_setting(key, value)
            
            logger.info("설정 데이터 마이그레이션 완료")
            
        except Exception as e:
            logger.error(f"설정 데이터 마이그레이션 실패: {e}")
            return False
    else:
        logger.info("기존 설정 파일이 없습니다.")
    
    # 3. 알림 기록 마이그레이션
    notifications_file = "data/sent_notifications.json"
    if os.path.exists(notifications_file):
        logger.info(f"알림 기록 마이그레이션 시작: {notifications_file}")
        
        try:
            with open(notifications_file, 'r', encoding='utf-8') as f:
                notifications_data = json.load(f)
            
            # 기존 알림 기록을 바탕으로 티켓 ID 매핑
            if isinstance(notifications_data, dict):
                for ticket_key, notification_info in notifications_data.items():
                    # 티켓 키를 바탕으로 데이터베이스에서 티켓 찾기
                    # 이 부분은 기존 데이터 구조에 따라 조정 필요
                    pass
            
            # 백업 파일 생성
            backup_file = f"{notifications_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(notifications_file, backup_file)
            logger.info(f"기존 알림 파일을 백업했습니다: {backup_file}")
            
        except Exception as e:
            logger.error(f"알림 기록 마이그레이션 실패: {e}")
            return False
    else:
        logger.info("기존 알림 기록 파일이 없습니다.")
    
    logger.info("데이터베이스 마이그레이션이 완료되었습니다!")
    return True

def verify_migration():
    """마이그레이션 결과 확인"""
    db = get_database()
    
    # 통계 정보 출력
    stats = db.get_statistics()
    logger.info("=== 마이그레이션 결과 ===")
    logger.info(f"총 티켓 수: {stats['total_count']}")
    logger.info(f"소스별 분포: {stats['source_counts']}")
    logger.info(f"장르별 분포: {stats['genre_counts']}")
    logger.info(f"오늘 오픈: {stats['today_count']}")
    logger.info(f"내일 오픈: {stats['tomorrow_count']}")
    logger.info(f"이번 주 오픈: {stats['week_count']}")
    
    # 최근 티켓 몇 개 출력
    recent_tickets = db.get_tickets(limit=5, order_by='created_at', order_desc=True)
    logger.info("\n=== 최근 티켓 5개 ===")
    for ticket in recent_tickets:
        logger.info(f"[{ticket['source']}] {ticket['title']} - {ticket['open_date']}")

if __name__ == "__main__":
    logger.info("JSON 데이터를 데이터베이스로 마이그레이션을 시작합니다...")
    
    if migrate_json_to_db():
        verify_migration()
        logger.info("마이그레이션이 성공적으로 완료되었습니다!")
    else:
        logger.error("마이그레이션 중 오류가 발생했습니다.")