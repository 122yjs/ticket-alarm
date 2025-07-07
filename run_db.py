#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 기반 티켓 정보 수집 및 관리 스크립트

이 스크립트는 다음 작업을 수행합니다:
1. 설정된 모든 웹사이트에서 티켓 공지 정보를 크롤링합니다.
2. 수집된 모든 티켓 정보를 SQLite 데이터베이스에 저장합니다.
3. 키워드 필터링 및 통계 정보를 제공합니다.
4. 웹 인터페이스를 통해 결과를 확인할 수 있습니다.
"""

import logging
import argparse
import sys
from datetime import datetime
from typing import Dict, Any

from db_data_manager import get_data_manager
from monitor_db import collect_all_tickets, run_once
from discord_notifier_db import DatabaseDiscordNotifier

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s]: %(message)s'
)
logger = logging.getLogger(__name__)

def display_statistics(data_manager):
    """통계 정보를 콘솔에 출력"""
    stats = data_manager.get_statistics()
    
    logger.info("="*80)
    logger.info("📊 데이터베이스 통계")
    logger.info("="*80)
    logger.info(f"총 티켓 수: {stats['total_count']:,}개")
    logger.info(f"오늘 오픈: {stats['today_count']}개")
    logger.info(f"내일 오픈: {stats['tomorrow_count']}개")
    logger.info(f"이번 주 오픈: {stats['week_count']}개")
    
    logger.info("\n📈 소스별 분포:")
    for source, count in stats['source_counts'].items():
        logger.info(f"  {source}: {count:,}개")
    
    logger.info("\n🎭 장르별 분포:")
    for genre, count in stats['genre_counts'].items():
        logger.info(f"  {genre}: {count:,}개")
    
    logger.info("="*80)

def display_recent_tickets(data_manager, limit=10):
    """최근 티켓들을 콘솔에 출력"""
    recent_tickets = data_manager.load_tickets(
        limit=limit, 
        filters={'order_by': 'created_at', 'order_desc': True}
    )
    
    logger.info(f"\n🎫 최근 등록된 티켓 {len(recent_tickets)}개:")
    logger.info("-"*80)
    
    for i, ticket in enumerate(recent_tickets, 1):
        logger.info(f"{i:2d}. [{ticket['source'].upper()}] {ticket['open_date']} - {ticket['title']}")
        if ticket.get('place'):
            logger.info(f"    📍 {ticket['place']}")
        if ticket.get('link'):
            logger.info(f"    🔗 {ticket['link']}")
        logger.info("")

def search_tickets(data_manager, keyword, limit=20):
    """키워드로 티켓 검색"""
    filters = {
        'search': keyword,
        'order_by': 'open_datetime',
        'order_desc': False
    }
    
    tickets = data_manager.load_tickets(limit=limit, filters=filters)
    total_count = data_manager.get_ticket_count(filters)
    
    logger.info(f"\n🔍 '{keyword}' 검색 결과: {total_count}개 (상위 {len(tickets)}개 표시)")
    logger.info("-"*80)
    
    if not tickets:
        logger.info("검색 결과가 없습니다.")
        return
    
    for i, ticket in enumerate(tickets, 1):
        logger.info(f"{i:2d}. [{ticket['source'].upper()}] {ticket['open_date']} - {ticket['title']}")
        if ticket.get('place'):
            logger.info(f"    📍 {ticket['place']}")
        if ticket.get('genre'):
            logger.info(f"    🎭 {ticket['genre']}")
        logger.info("")

def test_discord_webhook(data_manager):
    """디스코드 웹훅 테스트"""
    config = data_manager.load_config()
    
    if not config.get('DISCORD_WEBHOOK_URL'):
        logger.error("디스코드 웹훅 URL이 설정되지 않았습니다.")
        return False
    
    notifier = DatabaseDiscordNotifier(
        webhook_url=config['DISCORD_WEBHOOK_URL'],
        data_manager=data_manager
    )
    
    logger.info("디스코드 웹훅 연결을 테스트합니다...")
    
    if notifier.test_webhook():
        logger.info("✅ 디스코드 웹훅 테스트 성공!")
        
        # 요약 정보도 전송
        stats = data_manager.get_statistics()
        notifier.send_summary_notification(stats)
        
        return True
    else:
        logger.error("❌ 디스코드 웹훅 테스트 실패!")
        return False

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description="데이터베이스 기반 티켓 정보 수집 및 관리 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run_db.py                    # 기본 실행 (크롤링 + 통계)
  python run_db.py --stats-only       # 통계만 표시
  python run_db.py --search "뮤지컬"   # 키워드 검색
  python run_db.py --test-webhook     # 디스코드 웹훅 테스트
  python run_db.py --crawl-only       # 크롤링만 실행
        """
    )
    
    parser.add_argument(
        '--stats-only', 
        action='store_true',
        help='크롤링 없이 현재 데이터베이스 통계만 표시'
    )
    
    parser.add_argument(
        '--crawl-only',
        action='store_true', 
        help='크롤링만 실행하고 통계는 표시하지 않음'
    )
    
    parser.add_argument(
        '--search',
        type=str,
        help='키워드로 티켓 검색'
    )
    
    parser.add_argument(
        '--test-webhook',
        action='store_true',
        help='디스코드 웹훅 연결 테스트'
    )
    
    parser.add_argument(
        '--recent',
        type=int,
        default=10,
        help='표시할 최근 티켓 수 (기본값: 10)'
    )
    
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("🎫 데이터베이스 기반 티켓 알림 시스템")
    logger.info("="*80)
    
    # 데이터 매니저 초기화
    data_manager = get_data_manager()
    
    try:
        # 설정 로드
        config = data_manager.load_config()
        
        if not config:
            logger.error("설정을 로드할 수 없습니다. 먼저 migrate_to_db.py를 실행하거나 config.json을 확인하세요.")
            return 1
        
        # 디스코드 웹훅 테스트
        if args.test_webhook:
            success = test_discord_webhook(data_manager)
            return 0 if success else 1
        
        # 키워드 검색
        if args.search:
            search_tickets(data_manager, args.search)
            return 0
        
        # 통계만 표시
        if args.stats_only:
            display_statistics(data_manager)
            display_recent_tickets(data_manager, args.recent)
            return 0
        
        # 크롤링 실행
        if not args.crawl_only:
            logger.info("현재 데이터베이스 상태:")
            display_statistics(data_manager)
            logger.info("\n")
        
        logger.info("🕷️ 크롤링을 시작합니다...")
        result = run_once(config)
        
        logger.info(f"✅ 크롤링 완료!")
        logger.info(f"   수집된 티켓: {result['collected_count']}개")
        logger.info(f"   새로운 티켓: {result['new_count']}개")
        logger.info(f"   키워드 매칭: {result['filtered_count']}개")
        
        if not args.crawl_only:
            logger.info("\n업데이트된 데이터베이스 상태:")
            display_statistics(data_manager)
            display_recent_tickets(data_manager, args.recent)
        
        # 웹 인터페이스 안내
        logger.info("\n🌐 웹 인터페이스에서 더 자세한 정보를 확인하세요:")
        logger.info("   python web_app_db.py")
        logger.info("   http://localhost:8000")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단되었습니다.")
        return 0
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())