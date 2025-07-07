#!/usr/bin/env python3
"""
데이터베이스 설정 테스트 스크립트
Python 없이도 설정 과정을 시뮬레이션합니다.
"""

import json
import os
from datetime import datetime

def simulate_db_setup():
    """데이터베이스 설정 시뮬레이션"""
    print("🎫 티켓 오픈 알리미 (데이터베이스 버전) 설치 테스트")
    print("=" * 80)
    
    # 1. 디렉토리 확인
    print("📁 디렉토리 확인...")
    directories = ['data', 'static', 'templates', 'crawlers']
    for directory in directories:
        if os.path.exists(directory):
            print(f"   ✅ {directory}/ 디렉토리 존재")
        else:
            print(f"   ❌ {directory}/ 디렉토리 없음")
    
    # 2. 설정 파일 확인
    print("\n⚙️ 설정 파일 확인...")
    config_path = 'data/config.json'
    if os.path.exists(config_path):
        print(f"   ✅ {config_path} 존재")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"   📋 설정 키: {list(config.keys())}")
            
            webhook_url = config.get('DISCORD_WEBHOOK_URL', '')
            if "여기에_디스코드_웹훅_URL을_입력하세요" in webhook_url:
                print("   ⚠️  디스코드 웹훅 URL을 설정해야 합니다.")
            else:
                print("   ✅ 디스코드 웹훅 URL 설정됨")
                
        except Exception as e:
            print(f"   ❌ 설정 파일 읽기 실패: {e}")
    else:
        print(f"   ❌ {config_path} 없음")
    
    # 3. 기존 데이터 확인
    print("\n📦 기존 데이터 확인...")
    data_files = ['data/all_tickets.json', 'data/sent_notifications.json']
    total_tickets = 0
    
    for file_path in data_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path} 존재")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'tickets' in data:
                    count = len(data['tickets'])
                    total_tickets += count
                    print(f"      📊 티켓 수: {count}개")
                elif isinstance(data, list):
                    count = len(data)
                    total_tickets += count
                    print(f"      📊 항목 수: {count}개")
            except Exception as e:
                print(f"      ❌ 파일 읽기 실패: {e}")
        else:
            print(f"   ❌ {file_path} 없음")
    
    print(f"\n📈 총 기존 데이터: {total_tickets}개 티켓")
    
    # 4. 크롤러 모듈 확인
    print("\n🕷️ 크롤러 모듈 확인...")
    crawler_files = [
        'crawlers/interpark_crawler.py',
        'crawlers/yes24_crawler.py', 
        'crawlers/melon_crawler.py',
        'crawlers/ticketlink_crawler.py'
    ]
    
    for file_path in crawler_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path} 존재")
        else:
            print(f"   ❌ {file_path} 없음")
    
    # 5. 웹 앱 파일 확인
    print("\n🌐 웹 애플리케이션 파일 확인...")
    web_files = [
        'web_app_db.py',
        'monitor_db.py',
        'run_db.py',
        'database.py',
        'db_data_manager.py'
    ]
    
    for file_path in web_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path} 존재")
        else:
            print(f"   ❌ {file_path} 없음")
    
    print("\n🎉 설정 확인 완료!")
    print("\n📋 다음 단계 (Python 설치 후):")
    print("   1. pip install -r requirements.txt")
    print("   2. playwright install chromium")
    print("   3. data/config.json에서 디스코드 웹훅 URL 설정")
    print("   4. python migrate_to_db.py  # 기존 데이터 마이그레이션")
    print("   5. python run_db.py --test-webhook  # 웹훅 테스트")
    print("   6. python web_app_db.py  # 웹 인터페이스 실행")
    print("   7. python monitor_db.py  # 지속적인 모니터링")

if __name__ == "__main__":
    simulate_db_setup()