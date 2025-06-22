#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 알림 시스템 성능 모니터링
시스템 리소스, 애플리케이션 성능, 네트워크 상태를 모니터링하고 알림을 발송합니다.
"""

import os
import sys
import json
import time
import psutil
import sqlite3
import requests
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import logging
import signal
import argparse
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/performance_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    def __init__(self, config_file='config.json'):
        self.config = self.load_config(config_file)
        self.running = False
        self.metrics_history = deque(maxlen=1000)
        self.alerts_sent = set()
        self.db_path = 'performance_metrics.db'
        self.init_database()
        
        # 임계값 설정
        self.thresholds = {
            'cpu_percent': self.config.get('CPU_THRESHOLD', 80),
            'memory_percent': self.config.get('MEMORY_THRESHOLD', 85),
            'disk_percent': self.config.get('DISK_THRESHOLD', 90),
            'response_time': self.config.get('RESPONSE_TIME_THRESHOLD', 5.0),
            'error_rate': self.config.get('ERROR_RATE_THRESHOLD', 0.05)
        }
        
        # 모니터링 간격 (초)
        self.monitor_interval = self.config.get('MONITOR_INTERVAL', 60)
        
        # 알림 쿨다운 (초)
        self.alert_cooldown = self.config.get('ALERT_COOLDOWN', 300)
        
    def load_config(self, config_file):
        """설정 파일 로드"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return {}
    
    def init_database(self):
        """성능 메트릭 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 성능 메트릭 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cpu_percent REAL,
                    memory_percent REAL,
                    disk_percent REAL,
                    network_bytes_sent INTEGER,
                    network_bytes_recv INTEGER,
                    process_count INTEGER,
                    load_average REAL,
                    response_time REAL,
                    error_count INTEGER
                )
            ''')
            
            # 알림 이력 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    metric_value REAL,
                    threshold_value REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("성능 메트릭 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
    
    def collect_system_metrics(self):
        """시스템 메트릭 수집"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # 네트워크 통계
            network = psutil.net_io_counters()
            
            # 프로세스 수
            process_count = len(psutil.pids())
            
            # 로드 평균 (Linux/Unix만)
            try:
                load_average = os.getloadavg()[0]
            except (OSError, AttributeError):
                load_average = 0.0
            
            return {
                'timestamp': datetime.now(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk_percent,
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv,
                'process_count': process_count,
                'load_average': load_average
            }
            
        except Exception as e:
            logger.error(f"시스템 메트릭 수집 실패: {e}")
            return None
    
    def collect_application_metrics(self):
        """애플리케이션 메트릭 수집"""
        metrics = {
            'response_time': 0.0,
            'error_count': 0,
            'active_processes': 0
        }
        
        try:
            # 웹 서버 응답 시간 측정
            web_port = self.config.get('WEB_PORT', 8000)
            start_time = time.time()
            
            try:
                response = requests.get(
                    f'http://localhost:{web_port}/health',
                    timeout=10
                )
                metrics['response_time'] = time.time() - start_time
                
                if response.status_code != 200:
                    metrics['error_count'] += 1
                    
            except requests.RequestException:
                metrics['response_time'] = 10.0  # 타임아웃으로 간주
                metrics['error_count'] += 1
            
            # 티켓 알림 프로세스 확인
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if any('ticket-alarm' in str(item) for item in proc.info['cmdline'] or []):
                        metrics['active_processes'] += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return metrics
            
        except Exception as e:
            logger.error(f"애플리케이션 메트릭 수집 실패: {e}")
            return metrics
    
    def save_metrics(self, system_metrics, app_metrics):
        """메트릭을 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO performance_metrics (
                    cpu_percent, memory_percent, disk_percent,
                    network_bytes_sent, network_bytes_recv,
                    process_count, load_average, response_time, error_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                system_metrics['cpu_percent'],
                system_metrics['memory_percent'],
                system_metrics['disk_percent'],
                system_metrics['network_bytes_sent'],
                system_metrics['network_bytes_recv'],
                system_metrics['process_count'],
                system_metrics['load_average'],
                app_metrics['response_time'],
                app_metrics['error_count']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"메트릭 저장 실패: {e}")
    
    def check_thresholds(self, system_metrics, app_metrics):
        """임계값 확인 및 알림 발송"""
        alerts = []
        
        # CPU 사용률 확인
        if system_metrics['cpu_percent'] > self.thresholds['cpu_percent']:
            alerts.append({
                'type': 'cpu_high',
                'severity': 'warning' if system_metrics['cpu_percent'] < 90 else 'critical',
                'message': f"CPU 사용률이 높습니다: {system_metrics['cpu_percent']:.1f}%",
                'value': system_metrics['cpu_percent'],
                'threshold': self.thresholds['cpu_percent']
            })
        
        # 메모리 사용률 확인
        if system_metrics['memory_percent'] > self.thresholds['memory_percent']:
            alerts.append({
                'type': 'memory_high',
                'severity': 'warning' if system_metrics['memory_percent'] < 95 else 'critical',
                'message': f"메모리 사용률이 높습니다: {system_metrics['memory_percent']:.1f}%",
                'value': system_metrics['memory_percent'],
                'threshold': self.thresholds['memory_percent']
            })
        
        # 디스크 사용률 확인
        if system_metrics['disk_percent'] > self.thresholds['disk_percent']:
            alerts.append({
                'type': 'disk_high',
                'severity': 'critical',
                'message': f"디스크 사용률이 높습니다: {system_metrics['disk_percent']:.1f}%",
                'value': system_metrics['disk_percent'],
                'threshold': self.thresholds['disk_percent']
            })
        
        # 응답 시간 확인
        if app_metrics['response_time'] > self.thresholds['response_time']:
            alerts.append({
                'type': 'response_slow',
                'severity': 'warning',
                'message': f"응답 시간이 느립니다: {app_metrics['response_time']:.2f}초",
                'value': app_metrics['response_time'],
                'threshold': self.thresholds['response_time']
            })
        
        # 프로세스 확인
        if app_metrics['active_processes'] == 0:
            alerts.append({
                'type': 'process_down',
                'severity': 'critical',
                'message': "티켓 알림 프로세스가 실행되지 않고 있습니다",
                'value': 0,
                'threshold': 1
            })
        
        # 알림 발송
        for alert in alerts:
            self.send_alert(alert)
    
    def send_alert(self, alert):
        """알림 발송"""
        alert_key = f"{alert['type']}_{alert['severity']}"
        current_time = time.time()
        
        # 쿨다운 확인
        if alert_key in self.alerts_sent:
            last_sent = self.alerts_sent[alert_key]
            if current_time - last_sent < self.alert_cooldown:
                return
        
        try:
            # 데이터베이스에 알림 이력 저장
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO alert_history (
                    alert_type, severity, message, metric_value, threshold_value
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                alert['type'],
                alert['severity'],
                alert['message'],
                alert['value'],
                alert['threshold']
            ))
            
            conn.commit()
            conn.close()
            
            # 디스코드 웹훅으로 알림 발송
            webhook_url = self.config.get('DISCORD_WEBHOOK_URL')
            if webhook_url:
                self.send_discord_alert(webhook_url, alert)
            
            # 로그 기록
            logger.warning(f"성능 알림: {alert['message']}")
            
            # 쿨다운 설정
            self.alerts_sent[alert_key] = current_time
            
        except Exception as e:
            logger.error(f"알림 발송 실패: {e}")
    
    def send_discord_alert(self, webhook_url, alert):
        """디스코드 웹훅으로 알림 발송"""
        try:
            # 심각도에 따른 색상 설정
            color_map = {
                'info': 0x3498db,      # 파란색
                'warning': 0xf39c12,   # 주황색
                'critical': 0xe74c3c   # 빨간색
            }
            
            # 이모지 설정
            emoji_map = {
                'cpu_high': '🔥',
                'memory_high': '💾',
                'disk_high': '💿',
                'response_slow': '🐌',
                'process_down': '💀'
            }
            
            embed = {
                'title': f"{emoji_map.get(alert['type'], '⚠️')} 성능 알림",
                'description': alert['message'],
                'color': color_map.get(alert['severity'], 0x95a5a6),
                'fields': [
                    {
                        'name': '현재 값',
                        'value': f"{alert['value']:.2f}",
                        'inline': True
                    },
                    {
                        'name': '임계값',
                        'value': f"{alert['threshold']:.2f}",
                        'inline': True
                    },
                    {
                        'name': '심각도',
                        'value': alert['severity'].upper(),
                        'inline': True
                    }
                ],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': '티켓 알림 시스템 성능 모니터'
                }
            }
            
            payload = {
                'embeds': [embed],
                'username': '성능 모니터',
                'avatar_url': 'https://cdn-icons-png.flaticon.com/512/2920/2920277.png'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info("디스코드 성능 알림 발송 완료")
            else:
                logger.error(f"디스코드 알림 발송 실패: {response.status_code}")
                
        except Exception as e:
            logger.error(f"디스코드 알림 발송 오류: {e}")
    
    def cleanup_old_data(self):
        """오래된 데이터 정리"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 30일 이전 데이터 삭제
            cutoff_date = datetime.now() - timedelta(days=30)
            
            cursor.execute(
                'DELETE FROM performance_metrics WHERE timestamp < ?',
                (cutoff_date,)
            )
            
            cursor.execute(
                'DELETE FROM alert_history WHERE timestamp < ?',
                (cutoff_date,)
            )
            
            deleted_metrics = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_metrics > 0:
                logger.info(f"오래된 성능 데이터 {deleted_metrics}개 정리 완료")
                
        except Exception as e:
            logger.error(f"데이터 정리 실패: {e}")
    
    def get_performance_summary(self, hours=24):
        """성능 요약 정보 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute('''
                SELECT 
                    AVG(cpu_percent) as avg_cpu,
                    MAX(cpu_percent) as max_cpu,
                    AVG(memory_percent) as avg_memory,
                    MAX(memory_percent) as max_memory,
                    AVG(disk_percent) as avg_disk,
                    MAX(disk_percent) as max_disk,
                    AVG(response_time) as avg_response_time,
                    MAX(response_time) as max_response_time,
                    SUM(error_count) as total_errors,
                    COUNT(*) as sample_count
                FROM performance_metrics 
                WHERE timestamp > ?
            ''', (cutoff_time,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] is not None:
                return {
                    'period_hours': hours,
                    'avg_cpu': round(result[0], 2),
                    'max_cpu': round(result[1], 2),
                    'avg_memory': round(result[2], 2),
                    'max_memory': round(result[3], 2),
                    'avg_disk': round(result[4], 2),
                    'max_disk': round(result[5], 2),
                    'avg_response_time': round(result[6], 3),
                    'max_response_time': round(result[7], 3),
                    'total_errors': int(result[8] or 0),
                    'sample_count': int(result[9])
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"성능 요약 조회 실패: {e}")
            return None
    
    def monitor_loop(self):
        """모니터링 메인 루프"""
        logger.info("성능 모니터링 시작")
        
        while self.running:
            try:
                # 시스템 메트릭 수집
                system_metrics = self.collect_system_metrics()
                if not system_metrics:
                    time.sleep(self.monitor_interval)
                    continue
                
                # 애플리케이션 메트릭 수집
                app_metrics = self.collect_application_metrics()
                
                # 메트릭 저장
                self.save_metrics(system_metrics, app_metrics)
                
                # 임계값 확인
                self.check_thresholds(system_metrics, app_metrics)
                
                # 메트릭 히스토리에 추가
                combined_metrics = {**system_metrics, **app_metrics}
                self.metrics_history.append(combined_metrics)
                
                # 로그 출력
                logger.info(
                    f"성능 메트릭 - CPU: {system_metrics['cpu_percent']:.1f}%, "
                    f"메모리: {system_metrics['memory_percent']:.1f}%, "
                    f"디스크: {system_metrics['disk_percent']:.1f}%, "
                    f"응답시간: {app_metrics['response_time']:.2f}초"
                )
                
                # 주기적으로 오래된 데이터 정리 (1시간마다)
                if len(self.metrics_history) % 60 == 0:
                    self.cleanup_old_data()
                
                time.sleep(self.monitor_interval)
                
            except KeyboardInterrupt:
                logger.info("사용자에 의해 모니터링이 중단되었습니다")
                break
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                time.sleep(self.monitor_interval)
    
    def start(self):
        """모니터링 시작"""
        self.running = True
        self.monitor_loop()
    
    def stop(self):
        """모니터링 중지"""
        self.running = False
        logger.info("성능 모니터링 중지")

def signal_handler(signum, frame):
    """시그널 핸들러"""
    logger.info(f"시그널 {signum} 수신, 모니터링을 종료합니다")
    if 'monitor' in globals():
        monitor.stop()
    sys.exit(0)

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='티켓 알림 시스템 성능 모니터')
    parser.add_argument('--config', '-c', default='config.json', help='설정 파일 경로')
    parser.add_argument('--summary', '-s', action='store_true', help='성능 요약 정보 출력')
    parser.add_argument('--hours', type=int, default=24, help='요약 기간 (시간)')
    parser.add_argument('--daemon', '-d', action='store_true', help='데몬 모드로 실행')
    
    args = parser.parse_args()
    
    # 로그 디렉토리 생성
    os.makedirs('logs', exist_ok=True)
    
    # 성능 모니터 초기화
    global monitor
    monitor = PerformanceMonitor(args.config)
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.summary:
        # 성능 요약 출력
        summary = monitor.get_performance_summary(args.hours)
        if summary:
            print(f"\n=== 성능 요약 (최근 {args.hours}시간) ===")
            print(f"샘플 수: {summary['sample_count']}")
            print(f"CPU 사용률: 평균 {summary['avg_cpu']}%, 최대 {summary['max_cpu']}%")
            print(f"메모리 사용률: 평균 {summary['avg_memory']}%, 최대 {summary['max_memory']}%")
            print(f"디스크 사용률: 평균 {summary['avg_disk']}%, 최대 {summary['max_disk']}%")
            print(f"응답 시간: 평균 {summary['avg_response_time']}초, 최대 {summary['max_response_time']}초")
            print(f"총 오류 수: {summary['total_errors']}")
        else:
            print("성능 데이터가 없습니다")
    else:
        # 모니터링 시작
        if args.daemon:
            # 데몬 모드 (백그라운드 실행)
            import daemon
            with daemon.DaemonContext():
                monitor.start()
        else:
            # 포그라운드 실행
            monitor.start()

if __name__ == '__main__':
    main()