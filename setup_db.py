#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 기반 티켓 알림 시스템 설치 및 설정 도우미

이 스크립트는 다음 작업을 수행합니다:
1. 필요한 디렉토리 생성
2. 데이터베이스 초기화
3. 설정 파일 생성 도움
4. 기존 JSON 데이터 마이그레이션
5. 시스템 테스트
"""

import os
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s]: %(message)s'
)
logger = logging.getLogger(__name__)

def create_directories():
    """필요한 디렉토리 생성"""
    directories = [
        'data',
        'static', 
        'templates',
        'crawlers'
    ]
    
    logger.info("📁 필요한 디렉토리를 생성합니다...")
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"   ✅ {directory}/ 디렉토리 준비 완료")

def setup_config():
    """설정 파일 설정"""
    config_path = Path('data/config.json')
    example_path = Path('config.json.example')
    
    logger.info("⚙️ 설정 파일을 준비합니다...")
    
    if config_path.exists():
        logger.info("   ✅ 기존 설정 파일이 있습니다.")
        return True
    
    if example_path.exists():
        logger.info("   📋 예시 설정 파일을 복사합니다...")
        shutil.copy(example_path, config_path)
        
        logger.info("   ⚠️  중요: data/config.json 파일을 편집하여 디스코드 웹훅 URL을 설정하세요!")
        logger.info("   📝 편집할 내용:")
        logger.info("      - DISCORD_WEBHOOK_URL: 디스코드 웹훅 URL")
        logger.info("      - KEYWORDS: 관심 키워드 목록")
        logger.info("      - interval: 모니터링 간격 (초)")
        logger.info("      - sources: 크롤링할 사이트 목록")
        
        return False  # 사용자가 설정을 완료해야 함
    else:
        logger.error("   ❌ config.json.example 파일을 찾을 수 없습니다.")
        logger.info("   📝 수동으로 data/config.json 파일을 생성하세요:")
        
        sample_config = {
            "DISCORD_WEBHOOK_URL": "여기에_디스코드_웹훅_URL을_입력하세요",
            "KEYWORDS": ["뮤지컬", "콘서트", "임영웅", "아이유"],
            "interval": 3600,
            "sources": ["interpark", "yes24", "melon", "ticketlink"]
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"   ✅ 기본 설정 파일을 생성했습니다: {config_path}")
        logger.info("   ⚠️  디스코드 웹훅 URL을 설정하세요!")
        
        return False

def initialize_database():
    """데이터베이스 초기화"""
    logger.info("🗄️ 데이터베이스를 초기화합니다...")
    
    try:
        from database import get_database
        
        db = get_database()
        logger.info("   ✅ 데이터베이스 초기화 완료")
        
        # 기본 통계 확인
        stats = db.get_statistics()
        logger.info(f"   📊 현재 데이터베이스 상태: {stats['total_count']}개 티켓")
        
        return True
        
    except Exception as e:
        logger.error(f"   ❌ 데이터베이스 초기화 실패: {e}")
        return False

def migrate_existing_data():
    """기존 JSON 데이터 마이그레이션"""
    json_files = [
        'data/all_tickets.json',
        'all_tickets.json'
    ]
    
    existing_files = [f for f in json_files if Path(f).exists()]
    
    if not existing_files:
        logger.info("📦 기존 JSON 데이터 파일이 없습니다. 새로 시작합니다.")
        return True
    
    logger.info("📦 기존 JSON 데이터를 데이터베이스로 마이그레이션합니다...")
    
    try:
        from migrate_to_db import migrate_json_to_db
        
        if migrate_json_to_db():
            logger.info("   ✅ 데이터 마이그레이션 완료")
            return True
        else:
            logger.error("   ❌ 데이터 마이그레이션 실패")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ 마이그레이션 중 오류: {e}")
        return False

def test_system():
    """시스템 테스트"""
    logger.info("🧪 시스템을 테스트합니다...")
    
    try:
        # 데이터 매니저 테스트
        from db_data_manager import get_data_manager
        
        data_manager = get_data_manager()
        config = data_manager.load_config()
        
        if not config:
            logger.error("   ❌ 설정 로드 실패")
            return False
        
        logger.info("   ✅ 설정 로드 성공")
        
        # 웹훅 URL 확인
        webhook_url = config.get('DISCORD_WEBHOOK_URL', '')
        if not webhook_url or "여기에_디스코드_웹훅_URL을_입력하세요" in webhook_url:
            logger.warning("   ⚠️  디스코드 웹훅 URL이 설정되지 않았습니다.")
            logger.info("   📝 data/config.json 파일에서 DISCORD_WEBHOOK_URL을 설정하세요.")
            return False
        
        logger.info("   ✅ 디스코드 웹훅 URL 설정 확인")
        
        # 크롤러 모듈 확인
        sources = config.get('sources', [])
        for source in sources:
            try:
                module_name = f"crawlers.{source.lower()}_crawler"
                __import__(module_name)
                logger.info(f"   ✅ {source} 크롤러 모듈 확인")
            except ImportError:
                logger.warning(f"   ⚠️  {source} 크롤러 모듈을 찾을 수 없습니다.")
        
        logger.info("   ✅ 시스템 테스트 완료")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ 시스템 테스트 실패: {e}")
        return False

def show_next_steps():
    """다음 단계 안내"""
    logger.info("🎉 설치가 완료되었습니다!")
    logger.info("")
    logger.info("📋 다음 단계:")
    logger.info("   1. data/config.json 파일에서 디스코드 웹훅 URL 설정")
    logger.info("   2. 키워드 및 기타 설정 조정")
    logger.info("   3. 시스템 테스트:")
    logger.info("      python run_db.py --test-webhook")
    logger.info("   4. 크롤링 테스트:")
    logger.info("      python run_db.py --crawl-only")
    logger.info("   5. 웹 인터페이스 실행:")
    logger.info("      python web_app_db.py")
    logger.info("   6. 지속적인 모니터링 시작:")
    logger.info("      python monitor_db.py")
    logger.info("")
    logger.info("📚 더 자세한 사용법은 README_DB.md 파일을 참고하세요.")

def main():
    """메인 설치 함수"""
    logger.info("="*80)
    logger.info("🎫 티켓 오픈 알리미 (데이터베이스 버전) 설치")
    logger.info("="*80)
    
    # 1. 디렉토리 생성
    create_directories()
    
    # 2. 설정 파일 준비
    config_ready = setup_config()
    
    # 3. 데이터베이스 초기화
    if not initialize_database():
        logger.error("데이터베이스 초기화에 실패했습니다.")
        return 1
    
    # 4. 기존 데이터 마이그레이션
    if not migrate_existing_data():
        logger.error("데이터 마이그레이션에 실패했습니다.")
        return 1
    
    # 5. 시스템 테스트 (설정이 준비된 경우에만)
    if config_ready:
        if not test_system():
            logger.warning("시스템 테스트에서 일부 문제가 발견되었습니다.")
    
    # 6. 다음 단계 안내
    show_next_steps()
    
    logger.info("="*80)
    return 0

if __name__ == "__main__":
    exit(main())