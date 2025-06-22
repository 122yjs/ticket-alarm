#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 알림 시스템 로그 분석기
시스템 로그를 분석하여 패턴, 오류, 성능 이슈를 탐지합니다.
"""

import os
import re
import json
import sqlite3
import argparse
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path
import logging
import gzip
import requests

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LogAnalyzer:
    """로그 분석 클래스"""
    
    def __init__(self, config_file='config.json'):
        self.config = self.load_config(config_file)
        self.db_path = 'log_analysis.db'
        self.init_database()
        
        # 로그 파일 경로
        self.log_paths = {
            'app': 'logs/ticket_alarm.log',
            'crawler': 'logs/crawler.log',
            'discord': 'logs/discord.log',
            'error': 'logs/error.log',
            'access': 'logs/access.log',
            'performance': 'logs/performance_monitor.log'
        }
        
        # 로그 패턴 정의
        self.patterns = {
            'error': re.compile(r'ERROR|CRITICAL|Exception|Traceback', re.IGNORECASE),
            'warning': re.compile(r'WARNING|WARN', re.IGNORECASE),
            'success': re.compile(r'SUCCESS|완료|성공', re.IGNORECASE),
            'failed': re.compile(r'FAILED|실패|오류', re.IGNORECASE),
            'timeout': re.compile(r'timeout|시간초과', re.IGNORECASE),
            'connection': re.compile(r'connection|연결', re.IGNORECASE),
            'memory': re.compile(r'memory|메모리|OutOfMemory', re.IGNORECASE),
            'disk': re.compile(r'disk|디스크|No space', re.IGNORECASE),
            'network': re.compile(r'network|네트워크|DNS', re.IGNORECASE),
            'permission': re.compile(r'permission|권한|denied', re.IGNORECASE),
            'rate_limit': re.compile(r'rate.?limit|속도.?제한', re.IGNORECASE),
            'webhook': re.compile(r'webhook|웹훅', re.IGNORECASE),
            'crawling': re.compile(r'crawl|크롤링|scraping', re.IGNORECASE),
            'notification': re.compile(r'notification|알림|alert', re.IGNORECASE)
        }
        
        # 시간 패턴
        self.time_patterns = [
            re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'),  # YYYY-MM-DD HH:MM:SS
            re.compile(r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})'),  # MM/DD/YYYY HH:MM:SS
            re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'),  # ISO format
        ]
    
    def load_config(self, config_file):
        """설정 파일 로드"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return {}
    
    def init_database(self):
        """로그 분석 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 로그 엔트리 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS log_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    log_type TEXT,
                    level TEXT,
                    message TEXT,
                    file_path TEXT,
                    line_number INTEGER,
                    pattern_matches TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 로그 통계 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS log_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    log_type TEXT,
                    level TEXT,
                    count INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 패턴 분석 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pattern_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    pattern_name TEXT,
                    count INTEGER,
                    sample_messages TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 알림 이력 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    details TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("로그 분석 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
    
    def parse_log_line(self, line, log_type):
        """로그 라인 파싱"""
        try:
            # 시간 추출
            timestamp = None
            for pattern in self.time_patterns:
                match = pattern.search(line)
                if match:
                    time_str = match.group(1)
                    try:
                        # 다양한 시간 형식 처리
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                            try:
                                timestamp = datetime.strptime(time_str, fmt)
                                break
                            except ValueError:
                                continue
                        break
                    except ValueError:
                        pass
            
            # 로그 레벨 추출
            level = 'INFO'  # 기본값
            level_patterns = {
                'DEBUG': re.compile(r'DEBUG', re.IGNORECASE),
                'INFO': re.compile(r'INFO', re.IGNORECASE),
                'WARNING': re.compile(r'WARNING|WARN', re.IGNORECASE),
                'ERROR': re.compile(r'ERROR', re.IGNORECASE),
                'CRITICAL': re.compile(r'CRITICAL|FATAL', re.IGNORECASE)
            }
            
            for level_name, pattern in level_patterns.items():
                if pattern.search(line):
                    level = level_name
                    break
            
            # 패턴 매칭
            matched_patterns = []
            for pattern_name, pattern in self.patterns.items():
                if pattern.search(line):
                    matched_patterns.append(pattern_name)
            
            return {
                'timestamp': timestamp or datetime.now(),
                'log_type': log_type,
                'level': level,
                'message': line.strip(),
                'pattern_matches': ','.join(matched_patterns)
            }
            
        except Exception as e:
            logger.error(f"로그 라인 파싱 실패: {e}")
            return None
    
    def analyze_log_file(self, file_path, log_type):
        """로그 파일 분석"""
        if not os.path.exists(file_path):
            logger.warning(f"로그 파일이 존재하지 않습니다: {file_path}")
            return []
        
        entries = []
        line_number = 0
        
        try:
            # gzip 파일 처리
            if file_path.endswith('.gz'):
                file_obj = gzip.open(file_path, 'rt', encoding='utf-8')
            else:
                file_obj = open(file_path, 'r', encoding='utf-8')
            
            with file_obj as f:
                for line in f:
                    line_number += 1
                    
                    if not line.strip():
                        continue
                    
                    entry = self.parse_log_line(line, log_type)
                    if entry:
                        entry['file_path'] = file_path
                        entry['line_number'] = line_number
                        entries.append(entry)
            
            logger.info(f"{log_type} 로그 분석 완료: {len(entries)}개 엔트리")
            return entries
            
        except Exception as e:
            logger.error(f"로그 파일 분석 실패 {file_path}: {e}")
            return []
    
    def save_log_entries(self, entries):
        """로그 엔트리를 데이터베이스에 저장"""
        if not entries:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for entry in entries:
                cursor.execute('''
                    INSERT INTO log_entries (
                        timestamp, log_type, level, message, 
                        file_path, line_number, pattern_matches
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry['timestamp'],
                    entry['log_type'],
                    entry['level'],
                    entry['message'],
                    entry['file_path'],
                    entry['line_number'],
                    entry['pattern_matches']
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"{len(entries)}개 로그 엔트리 저장 완료")
            
        except Exception as e:
            logger.error(f"로그 엔트리 저장 실패: {e}")
    
    def generate_statistics(self, date=None):
        """로그 통계 생성"""
        if date is None:
            date = datetime.now().date()
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 기존 통계 삭제
            cursor.execute('DELETE FROM log_statistics WHERE date = ?', (date,))
            
            # 로그 타입별, 레벨별 통계
            cursor.execute('''
                SELECT log_type, level, COUNT(*) as count
                FROM log_entries 
                WHERE DATE(timestamp) = ?
                GROUP BY log_type, level
            ''', (date,))
            
            stats = cursor.fetchall()
            
            for log_type, level, count in stats:
                cursor.execute('''
                    INSERT INTO log_statistics (date, log_type, level, count)
                    VALUES (?, ?, ?, ?)
                ''', (date, log_type, level, count))
            
            conn.commit()
            conn.close()
            
            logger.info(f"{date} 로그 통계 생성 완료")
            
        except Exception as e:
            logger.error(f"로그 통계 생성 실패: {e}")
    
    def analyze_patterns(self, date=None, days=1):
        """패턴 분석"""
        if date is None:
            date = datetime.now().date()
        
        start_date = date - timedelta(days=days-1)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 기존 패턴 분석 삭제
            cursor.execute('DELETE FROM pattern_analysis WHERE date = ?', (date,))
            
            # 패턴별 통계
            cursor.execute('''
                SELECT pattern_matches, message
                FROM log_entries 
                WHERE DATE(timestamp) BETWEEN ? AND ?
                AND pattern_matches != ""
            ''', (start_date, date))
            
            results = cursor.fetchall()
            pattern_stats = defaultdict(list)
            
            for pattern_matches, message in results:
                for pattern in pattern_matches.split(','):
                    if pattern.strip():
                        pattern_stats[pattern.strip()].append(message)
            
            # 패턴 분석 결과 저장
            for pattern_name, messages in pattern_stats.items():
                count = len(messages)
                sample_messages = json.dumps(messages[:5])  # 샘플 5개만 저장
                
                cursor.execute('''
                    INSERT INTO pattern_analysis (date, pattern_name, count, sample_messages)
                    VALUES (?, ?, ?, ?)
                ''', (date, pattern_name, count, sample_messages))
            
            conn.commit()
            conn.close()
            
            logger.info(f"{date} 패턴 분석 완료: {len(pattern_stats)}개 패턴")
            return pattern_stats
            
        except Exception as e:
            logger.error(f"패턴 분석 실패: {e}")
            return {}
    
    def detect_anomalies(self, date=None):
        """이상 징후 탐지"""
        if date is None:
            date = datetime.now().date()
        
        anomalies = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 오늘과 어제 비교
            yesterday = date - timedelta(days=1)
            
            # 에러 급증 탐지
            cursor.execute('''
                SELECT 
                    (SELECT COUNT(*) FROM log_entries 
                     WHERE DATE(timestamp) = ? AND level IN ('ERROR', 'CRITICAL')) as today_errors,
                    (SELECT COUNT(*) FROM log_entries 
                     WHERE DATE(timestamp) = ? AND level IN ('ERROR', 'CRITICAL')) as yesterday_errors
            ''', (date, yesterday))
            
            result = cursor.fetchone()
            if result:
                today_errors, yesterday_errors = result
                if yesterday_errors > 0 and today_errors > yesterday_errors * 2:
                    anomalies.append({
                        'type': 'error_spike',
                        'severity': 'warning',
                        'message': f"오류 급증 탐지: 오늘 {today_errors}개, 어제 {yesterday_errors}개",
                        'details': {'today': today_errors, 'yesterday': yesterday_errors}
                    })
            
            # 특정 패턴 급증 탐지
            critical_patterns = ['timeout', 'connection', 'memory', 'disk']
            
            for pattern in critical_patterns:
                cursor.execute('''
                    SELECT 
                        (SELECT COALESCE(count, 0) FROM pattern_analysis 
                         WHERE date = ? AND pattern_name = ?) as today_count,
                        (SELECT COALESCE(count, 0) FROM pattern_analysis 
                         WHERE date = ? AND pattern_name = ?) as yesterday_count
                ''', (date, pattern, yesterday, pattern))
                
                result = cursor.fetchone()
                if result:
                    today_count, yesterday_count = result
                    if yesterday_count > 0 and today_count > yesterday_count * 3:
                        anomalies.append({
                            'type': 'pattern_spike',
                            'severity': 'warning',
                            'message': f"{pattern} 패턴 급증: 오늘 {today_count}개, 어제 {yesterday_count}개",
                            'details': {'pattern': pattern, 'today': today_count, 'yesterday': yesterday_count}
                        })
            
            # 로그 부재 탐지 (크롤링 중단 등)
            cursor.execute('''
                SELECT log_type, COUNT(*) as count
                FROM log_entries 
                WHERE DATE(timestamp) = ?
                GROUP BY log_type
            ''', (date,))
            
            log_counts = dict(cursor.fetchall())
            expected_logs = ['app', 'crawler', 'discord']
            
            for log_type in expected_logs:
                if log_counts.get(log_type, 0) < 10:  # 하루에 10개 미만이면 이상
                    anomalies.append({
                        'type': 'log_absence',
                        'severity': 'critical',
                        'message': f"{log_type} 로그가 거의 없습니다: {log_counts.get(log_type, 0)}개",
                        'details': {'log_type': log_type, 'count': log_counts.get(log_type, 0)}
                    })
            
            conn.close()
            
            # 이상 징후 저장
            if anomalies:
                self.save_anomalies(anomalies)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"이상 징후 탐지 실패: {e}")
            return []
    
    def save_anomalies(self, anomalies):
        """이상 징후를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for anomaly in anomalies:
                cursor.execute('''
                    INSERT INTO analysis_alerts (alert_type, severity, message, details)
                    VALUES (?, ?, ?, ?)
                ''', (
                    anomaly['type'],
                    anomaly['severity'],
                    anomaly['message'],
                    json.dumps(anomaly['details'])
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"이상 징후 저장 실패: {e}")
    
    def send_analysis_report(self, date=None):
        """분석 리포트 발송"""
        if date is None:
            date = datetime.now().date()
        
        try:
            # 통계 조회
            stats = self.get_daily_statistics(date)
            patterns = self.get_pattern_analysis(date)
            anomalies = self.detect_anomalies(date)
            
            # 리포트 생성
            report = self.generate_report(date, stats, patterns, anomalies)
            
            # 디스코드 웹훅으로 발송
            webhook_url = self.config.get('DISCORD_WEBHOOK_URL')
            if webhook_url:
                self.send_discord_report(webhook_url, report)
            
            logger.info(f"{date} 로그 분석 리포트 발송 완료")
            
        except Exception as e:
            logger.error(f"분석 리포트 발송 실패: {e}")
    
    def get_daily_statistics(self, date):
        """일일 통계 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT log_type, level, count
                FROM log_statistics 
                WHERE date = ?
                ORDER BY log_type, level
            ''', (date,))
            
            results = cursor.fetchall()
            conn.close()
            
            stats = defaultdict(dict)
            for log_type, level, count in results:
                stats[log_type][level] = count
            
            return dict(stats)
            
        except Exception as e:
            logger.error(f"일일 통계 조회 실패: {e}")
            return {}
    
    def get_pattern_analysis(self, date):
        """패턴 분석 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT pattern_name, count, sample_messages
                FROM pattern_analysis 
                WHERE date = ?
                ORDER BY count DESC
                LIMIT 10
            ''', (date,))
            
            results = cursor.fetchall()
            conn.close()
            
            patterns = []
            for pattern_name, count, sample_messages in results:
                patterns.append({
                    'name': pattern_name,
                    'count': count,
                    'samples': json.loads(sample_messages)
                })
            
            return patterns
            
        except Exception as e:
            logger.error(f"패턴 분석 조회 실패: {e}")
            return []
    
    def generate_report(self, date, stats, patterns, anomalies):
        """분석 리포트 생성"""
        report = {
            'date': date.strftime('%Y-%m-%d'),
            'summary': {
                'total_logs': sum(sum(levels.values()) for levels in stats.values()),
                'error_count': sum(stats.get(log_type, {}).get('ERROR', 0) + 
                                 stats.get(log_type, {}).get('CRITICAL', 0) 
                                 for log_type in stats),
                'warning_count': sum(stats.get(log_type, {}).get('WARNING', 0) 
                                   for log_type in stats),
                'anomaly_count': len(anomalies)
            },
            'statistics': stats,
            'top_patterns': patterns[:5],
            'anomalies': anomalies
        }
        
        return report
    
    def send_discord_report(self, webhook_url, report):
        """디스코드로 분석 리포트 발송"""
        try:
            # 심각도에 따른 색상
            color = 0x3498db  # 기본 파란색
            if report['summary']['anomaly_count'] > 0:
                color = 0xf39c12  # 주황색
            if report['summary']['error_count'] > 50:
                color = 0xe74c3c  # 빨간색
            
            # 임베드 생성
            embed = {
                'title': f"📊 로그 분석 리포트 - {report['date']}",
                'color': color,
                'fields': [
                    {
                        'name': '📈 요약',
                        'value': f"총 로그: {report['summary']['total_logs']:,}개\n"
                                f"오류: {report['summary']['error_count']:,}개\n"
                                f"경고: {report['summary']['warning_count']:,}개\n"
                                f"이상징후: {report['summary']['anomaly_count']}개",
                        'inline': True
                    }
                ],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': '티켓 알림 시스템 로그 분석기'
                }
            }
            
            # 주요 패턴 추가
            if report['top_patterns']:
                pattern_text = '\n'.join([
                    f"• {p['name']}: {p['count']}회"
                    for p in report['top_patterns'][:3]
                ])
                embed['fields'].append({
                    'name': '🔍 주요 패턴',
                    'value': pattern_text,
                    'inline': True
                })
            
            # 이상 징후 추가
            if report['anomalies']:
                anomaly_text = '\n'.join([
                    f"⚠️ {a['message']}"
                    for a in report['anomalies'][:3]
                ])
                embed['fields'].append({
                    'name': '🚨 이상 징후',
                    'value': anomaly_text,
                    'inline': False
                })
            
            payload = {
                'embeds': [embed],
                'username': '로그 분석기',
                'avatar_url': 'https://cdn-icons-png.flaticon.com/512/2920/2920277.png'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info("디스코드 로그 분석 리포트 발송 완료")
            else:
                logger.error(f"디스코드 리포트 발송 실패: {response.status_code}")
                
        except Exception as e:
            logger.error(f"디스코드 리포트 발송 오류: {e}")
    
    def analyze_all_logs(self, days=1):
        """모든 로그 파일 분석"""
        logger.info(f"최근 {days}일간 로그 분석 시작")
        
        all_entries = []
        
        # 각 로그 파일 분석
        for log_type, log_path in self.log_paths.items():
            if os.path.exists(log_path):
                entries = self.analyze_log_file(log_path, log_type)
                all_entries.extend(entries)
            
            # 로테이션된 로그 파일도 분석 (최근 며칠)
            for i in range(1, days + 1):
                rotated_path = f"{log_path}.{i}"
                if os.path.exists(rotated_path):
                    entries = self.analyze_log_file(rotated_path, log_type)
                    all_entries.extend(entries)
                
                # gzip 압축된 로그
                gz_path = f"{log_path}.{i}.gz"
                if os.path.exists(gz_path):
                    entries = self.analyze_log_file(gz_path, log_type)
                    all_entries.extend(entries)
        
        # 데이터베이스에 저장
        if all_entries:
            self.save_log_entries(all_entries)
        
        # 통계 및 패턴 분석
        today = datetime.now().date()
        self.generate_statistics(today)
        self.analyze_patterns(today, days)
        
        logger.info(f"로그 분석 완료: {len(all_entries)}개 엔트리 처리")
        
        return all_entries
    
    def cleanup_old_data(self, days=30):
        """오래된 분석 데이터 정리"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 오래된 데이터 삭제
            tables = ['log_entries', 'log_statistics', 'pattern_analysis', 'analysis_alerts']
            total_deleted = 0
            
            for table in tables:
                if table in ['log_entries', 'analysis_alerts']:
                    cursor.execute(f'DELETE FROM {table} WHERE timestamp < ?', (cutoff_date,))
                else:
                    cursor.execute(f'DELETE FROM {table} WHERE created_at < ?', (cutoff_date,))
                
                total_deleted += cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if total_deleted > 0:
                logger.info(f"오래된 로그 분석 데이터 {total_deleted}개 정리 완료")
                
        except Exception as e:
            logger.error(f"데이터 정리 실패: {e}")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='티켓 알림 시스템 로그 분석기')
    parser.add_argument('--config', '-c', default='config.json', help='설정 파일 경로')
    parser.add_argument('--days', '-d', type=int, default=1, help='분석할 일수')
    parser.add_argument('--report', '-r', action='store_true', help='분석 리포트 발송')
    parser.add_argument('--cleanup', action='store_true', help='오래된 데이터 정리')
    parser.add_argument('--anomalies', '-a', action='store_true', help='이상 징후만 탐지')
    
    args = parser.parse_args()
    
    # 로그 분석기 초기화
    analyzer = LogAnalyzer(args.config)
    
    if args.cleanup:
        # 데이터 정리
        analyzer.cleanup_old_data()
    elif args.anomalies:
        # 이상 징후 탐지만
        anomalies = analyzer.detect_anomalies()
        if anomalies:
            print(f"\n=== 이상 징후 탐지 결과 ===")
            for anomaly in anomalies:
                print(f"[{anomaly['severity'].upper()}] {anomaly['message']}")
        else:
            print("이상 징후가 탐지되지 않았습니다.")
    else:
        # 전체 로그 분석
        analyzer.analyze_all_logs(args.days)
        
        if args.report:
            # 분석 리포트 발송
            analyzer.send_analysis_report()
        
        # 이상 징후 탐지
        anomalies = analyzer.detect_anomalies()
        if anomalies:
            print(f"\n⚠️  {len(anomalies)}개의 이상 징후가 탐지되었습니다:")
            for anomaly in anomalies:
                print(f"  [{anomaly['severity'].upper()}] {anomaly['message']}")

if __name__ == '__main__':
    main()