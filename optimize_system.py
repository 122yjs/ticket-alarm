#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 알림 시스템 성능 최적화 도구
시스템 리소스 사용량을 분석하고 성능을 최적화합니다.
"""

import os
import sys
import json
import psutil
import sqlite3
import argparse
import subprocess
import time
import gc
import threading
from datetime import datetime, timedelta
from pathlib import Path
import logging
import requests
from collections import defaultdict, deque
import signal

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/optimization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemOptimizer:
    """시스템 최적화 클래스"""
    
    def __init__(self, config_file='config.json'):
        self.config = self.load_config(config_file)
        self.db_path = 'optimization.db'
        self.init_database()
        
        # 최적화 임계값
        self.thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'disk_usage': 90.0,
            'disk_io_wait': 20.0,
            'network_latency': 1000,  # ms
            'response_time': 5000,    # ms
            'error_rate': 5.0,        # %
            'log_file_size': 100 * 1024 * 1024,  # 100MB
            'db_size': 500 * 1024 * 1024,        # 500MB
        }
        
        # 성능 메트릭 히스토리
        self.metrics_history = {
            'cpu': deque(maxlen=60),
            'memory': deque(maxlen=60),
            'disk_io': deque(maxlen=60),
            'network': deque(maxlen=60),
            'response_time': deque(maxlen=60)
        }
        
        # 최적화 작업
        self.optimization_tasks = {
            'memory_cleanup': self.optimize_memory,
            'disk_cleanup': self.optimize_disk,
            'log_rotation': self.optimize_logs,
            'database_optimization': self.optimize_database,
            'process_optimization': self.optimize_processes,
            'network_optimization': self.optimize_network,
            'cache_optimization': self.optimize_cache,
            'system_tuning': self.optimize_system_settings
        }
        
        self.running = False
        self.monitor_thread = None
    
    def load_config(self, config_file):
        """설정 파일 로드"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return {}
    
    def init_database(self):
        """최적화 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 성능 메트릭 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metric_type TEXT,
                    value REAL,
                    threshold REAL,
                    status TEXT,
                    details TEXT
                )
            ''')
            
            # 최적화 작업 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS optimization_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    task_type TEXT,
                    status TEXT,
                    before_value REAL,
                    after_value REAL,
                    improvement REAL,
                    details TEXT,
                    duration REAL
                )
            ''')
            
            # 시스템 상태 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cpu_usage REAL,
                    memory_usage REAL,
                    disk_usage REAL,
                    disk_io_read REAL,
                    disk_io_write REAL,
                    network_sent REAL,
                    network_recv REAL,
                    process_count INTEGER,
                    load_average REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("최적화 데이터베이스 초기화 완료")
            
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
            
            # 디스크 I/O
            disk_io = psutil.disk_io_counters()
            
            # 네트워크 I/O
            network_io = psutil.net_io_counters()
            
            # 프로세스 수
            process_count = len(psutil.pids())
            
            # 로드 평균 (Linux/macOS)
            try:
                load_avg = os.getloadavg()[0]
            except (OSError, AttributeError):
                load_avg = 0.0
            
            metrics = {
                'timestamp': datetime.now(),
                'cpu_usage': cpu_percent,
                'memory_usage': memory_percent,
                'disk_usage': disk_percent,
                'disk_io_read': disk_io.read_bytes if disk_io else 0,
                'disk_io_write': disk_io.write_bytes if disk_io else 0,
                'network_sent': network_io.bytes_sent if network_io else 0,
                'network_recv': network_io.bytes_recv if network_io else 0,
                'process_count': process_count,
                'load_average': load_avg
            }
            
            # 히스토리에 추가
            self.metrics_history['cpu'].append(cpu_percent)
            self.metrics_history['memory'].append(memory_percent)
            
            return metrics
            
        except Exception as e:
            logger.error(f"시스템 메트릭 수집 실패: {e}")
            return None
    
    def save_metrics(self, metrics):
        """메트릭을 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO system_status (
                    cpu_usage, memory_usage, disk_usage,
                    disk_io_read, disk_io_write,
                    network_sent, network_recv,
                    process_count, load_average
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics['cpu_usage'],
                metrics['memory_usage'],
                metrics['disk_usage'],
                metrics['disk_io_read'],
                metrics['disk_io_write'],
                metrics['network_sent'],
                metrics['network_recv'],
                metrics['process_count'],
                metrics['load_average']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"메트릭 저장 실패: {e}")
    
    def analyze_performance_issues(self, metrics):
        """성능 이슈 분석"""
        issues = []
        
        # CPU 사용률 확인
        if metrics['cpu_usage'] > self.thresholds['cpu_usage']:
            issues.append({
                'type': 'cpu_high',
                'severity': 'HIGH',
                'message': f"CPU 사용률이 높습니다: {metrics['cpu_usage']:.1f}%",
                'value': metrics['cpu_usage'],
                'threshold': self.thresholds['cpu_usage'],
                'recommendation': 'CPU 집약적인 프로세스를 확인하고 최적화하세요'
            })
        
        # 메모리 사용률 확인
        if metrics['memory_usage'] > self.thresholds['memory_usage']:
            issues.append({
                'type': 'memory_high',
                'severity': 'HIGH',
                'message': f"메모리 사용률이 높습니다: {metrics['memory_usage']:.1f}%",
                'value': metrics['memory_usage'],
                'threshold': self.thresholds['memory_usage'],
                'recommendation': '메모리 정리 및 캐시 최적화를 수행하세요'
            })
        
        # 디스크 사용률 확인
        if metrics['disk_usage'] > self.thresholds['disk_usage']:
            issues.append({
                'type': 'disk_high',
                'severity': 'CRITICAL',
                'message': f"디스크 사용률이 높습니다: {metrics['disk_usage']:.1f}%",
                'value': metrics['disk_usage'],
                'threshold': self.thresholds['disk_usage'],
                'recommendation': '불필요한 파일을 삭제하고 로그를 정리하세요'
            })
        
        # 로드 평균 확인
        cpu_count = psutil.cpu_count()
        if metrics['load_average'] > cpu_count * 2:
            issues.append({
                'type': 'load_high',
                'severity': 'HIGH',
                'message': f"시스템 로드가 높습니다: {metrics['load_average']:.2f}",
                'value': metrics['load_average'],
                'threshold': cpu_count * 2,
                'recommendation': '실행 중인 프로세스를 확인하고 불필요한 작업을 중단하세요'
            })
        
        # 트렌드 분석
        if len(self.metrics_history['cpu']) >= 10:
            recent_cpu = list(self.metrics_history['cpu'])[-10:]
            if all(cpu > self.thresholds['cpu_usage'] * 0.8 for cpu in recent_cpu):
                issues.append({
                    'type': 'cpu_trend',
                    'severity': 'MEDIUM',
                    'message': "CPU 사용률이 지속적으로 높습니다",
                    'value': sum(recent_cpu) / len(recent_cpu),
                    'threshold': self.thresholds['cpu_usage'] * 0.8,
                    'recommendation': '시스템 최적화를 고려하세요'
                })
        
        return issues
    
    def optimize_memory(self):
        """메모리 최적화"""
        start_time = time.time()
        
        try:
            # 시작 메모리 사용량
            memory_before = psutil.virtual_memory().percent
            
            optimizations = []
            
            # Python 가비지 컬렉션
            collected = gc.collect()
            if collected > 0:
                optimizations.append(f"가비지 컬렉션으로 {collected}개 객체 정리")
            
            # 시스템 캐시 정리 (Linux)
            try:
                if os.path.exists('/proc/sys/vm/drop_caches'):
                    subprocess.run(['sudo', 'sync'], check=True, timeout=10)
                    subprocess.run(
                        ['sudo', 'sh', '-c', 'echo 1 > /proc/sys/vm/drop_caches'],
                        check=True, timeout=10
                    )
                    optimizations.append("시스템 페이지 캐시 정리")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
            
            # 스왑 사용량 확인 및 최적화
            swap = psutil.swap_memory()
            if swap.percent > 50:
                try:
                    subprocess.run(['sudo', 'swapoff', '-a'], check=True, timeout=30)
                    subprocess.run(['sudo', 'swapon', '-a'], check=True, timeout=30)
                    optimizations.append("스왑 메모리 최적화")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass
            
            # 종료 메모리 사용량
            memory_after = psutil.virtual_memory().percent
            improvement = memory_before - memory_after
            
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': memory_before,
                'after_value': memory_after,
                'improvement': improvement,
                'details': '; '.join(optimizations) if optimizations else '최적화 작업 없음',
                'duration': duration
            }
            
            logger.info(f"메모리 최적화 완료: {memory_before:.1f}% → {memory_after:.1f}% ({improvement:+.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"메모리 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def optimize_disk(self):
        """디스크 최적화"""
        start_time = time.time()
        
        try:
            # 시작 디스크 사용량
            disk_before = psutil.disk_usage('/').percent
            
            optimizations = []
            freed_space = 0
            
            # 임시 파일 정리
            temp_dirs = ['/tmp', '/var/tmp', 'temp', 'tmp']
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    try:
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    # 1일 이상 된 임시 파일 삭제
                                    if os.path.getmtime(file_path) < time.time() - 86400:
                                        file_size = os.path.getsize(file_path)
                                        os.remove(file_path)
                                        freed_space += file_size
                                except (OSError, PermissionError):
                                    pass
                        if freed_space > 0:
                            optimizations.append(f"{temp_dir}에서 {freed_space // 1024 // 1024}MB 정리")
                    except Exception:
                        pass
            
            # 로그 파일 압축
            log_dir = 'logs'
            if os.path.exists(log_dir):
                try:
                    import gzip
                    import shutil
                    
                    for log_file in os.listdir(log_dir):
                        if log_file.endswith('.log'):
                            log_path = os.path.join(log_dir, log_file)
                            log_stat = os.stat(log_path)
                            
                            # 1일 이상 된 로그 파일이고 10MB 이상인 경우 압축
                            if (log_stat.st_mtime < time.time() - 86400 and 
                                log_stat.st_size > 10 * 1024 * 1024):
                                
                                compressed_path = log_path + '.gz'
                                with open(log_path, 'rb') as f_in:
                                    with gzip.open(compressed_path, 'wb') as f_out:
                                        shutil.copyfileobj(f_in, f_out)
                                
                                original_size = log_stat.st_size
                                compressed_size = os.path.getsize(compressed_path)
                                
                                os.remove(log_path)
                                freed_space += original_size - compressed_size
                                optimizations.append(f"{log_file} 압축 ({original_size // 1024 // 1024}MB → {compressed_size // 1024 // 1024}MB)")
                                
                except Exception as e:
                    logger.warning(f"로그 압축 실패: {e}")
            
            # 패키지 캐시 정리
            try:
                result = subprocess.run(
                    ['pip', 'cache', 'purge'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    optimizations.append("pip 캐시 정리")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            # APT 캐시 정리 (Ubuntu/Debian)
            try:
                subprocess.run(['sudo', 'apt', 'clean'], check=True, timeout=30)
                subprocess.run(['sudo', 'apt', 'autoremove', '-y'], check=True, timeout=60)
                optimizations.append("APT 캐시 및 불필요한 패키지 정리")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            # 종료 디스크 사용량
            disk_after = psutil.disk_usage('/').percent
            improvement = disk_before - disk_after
            
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': disk_before,
                'after_value': disk_after,
                'improvement': improvement,
                'details': '; '.join(optimizations) if optimizations else '최적화 작업 없음',
                'duration': duration
            }
            
            logger.info(f"디스크 최적화 완료: {disk_before:.1f}% → {disk_after:.1f}% ({improvement:+.1f}%)")
            return result
            
        except Exception as e:
            logger.error(f"디스크 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def optimize_logs(self):
        """로그 최적화"""
        start_time = time.time()
        
        try:
            log_dir = 'logs'
            if not os.path.exists(log_dir):
                return {
                    'status': 'SKIP',
                    'before_value': 0,
                    'after_value': 0,
                    'improvement': 0,
                    'details': '로그 디렉토리가 존재하지 않음',
                    'duration': time.time() - start_time
                }
            
            # 시작 로그 크기
            total_size_before = 0
            for root, dirs, files in os.walk(log_dir):
                for file in files:
                    total_size_before += os.path.getsize(os.path.join(root, file))
            
            optimizations = []
            
            # 오래된 로그 파일 삭제
            cutoff_time = time.time() - (30 * 24 * 3600)  # 30일
            deleted_files = 0
            
            for root, dirs, files in os.walk(log_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if os.path.getmtime(file_path) < cutoff_time:
                            os.remove(file_path)
                            deleted_files += 1
                    except (OSError, PermissionError):
                        pass
            
            if deleted_files > 0:
                optimizations.append(f"{deleted_files}개 오래된 로그 파일 삭제")
            
            # 큰 로그 파일 분할
            max_size = 50 * 1024 * 1024  # 50MB
            split_files = 0
            
            for root, dirs, files in os.walk(log_dir):
                for file in files:
                    if file.endswith('.log'):
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.getsize(file_path) > max_size:
                                # 파일을 분할 (간단한 방법: 뒤쪽 절반만 유지)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    lines = f.readlines()
                                
                                half_point = len(lines) // 2
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.writelines(lines[half_point:])
                                
                                split_files += 1
                        except (OSError, PermissionError, UnicodeDecodeError):
                            pass
            
            if split_files > 0:
                optimizations.append(f"{split_files}개 큰 로그 파일 분할")
            
            # 종료 로그 크기
            total_size_after = 0
            for root, dirs, files in os.walk(log_dir):
                for file in files:
                    try:
                        total_size_after += os.path.getsize(os.path.join(root, file))
                    except OSError:
                        pass
            
            improvement = (total_size_before - total_size_after) / 1024 / 1024  # MB
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': total_size_before / 1024 / 1024,
                'after_value': total_size_after / 1024 / 1024,
                'improvement': improvement,
                'details': '; '.join(optimizations) if optimizations else '최적화 작업 없음',
                'duration': duration
            }
            
            logger.info(f"로그 최적화 완료: {total_size_before/1024/1024:.1f}MB → {total_size_after/1024/1024:.1f}MB ({improvement:+.1f}MB)")
            return result
            
        except Exception as e:
            logger.error(f"로그 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def optimize_database(self):
        """데이터베이스 최적화"""
        start_time = time.time()
        
        try:
            db_files = ['performance.db', 'security_audit.db', 'optimization.db']
            optimizations = []
            total_size_before = 0
            total_size_after = 0
            
            for db_file in db_files:
                if os.path.exists(db_file):
                    size_before = os.path.getsize(db_file)
                    total_size_before += size_before
                    
                    try:
                        conn = sqlite3.connect(db_file)
                        cursor = conn.cursor()
                        
                        # VACUUM으로 데이터베이스 최적화
                        cursor.execute('VACUUM')
                        
                        # 오래된 데이터 정리 (30일 이상)
                        cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
                        
                        # 테이블별 정리
                        tables_to_clean = [
                            'performance_metrics',
                            'security_checks',
                            'system_status',
                            'optimization_tasks'
                        ]
                        
                        deleted_rows = 0
                        for table in tables_to_clean:
                            try:
                                cursor.execute(f'''
                                    DELETE FROM {table} 
                                    WHERE timestamp < ?
                                ''', (cutoff_date,))
                                deleted_rows += cursor.rowcount
                            except sqlite3.OperationalError:
                                # 테이블이 존재하지 않는 경우
                                pass
                        
                        conn.commit()
                        conn.close()
                        
                        size_after = os.path.getsize(db_file)
                        total_size_after += size_after
                        
                        if deleted_rows > 0 or size_after < size_before:
                            optimizations.append(f"{db_file}: {deleted_rows}행 삭제, {(size_before-size_after)/1024/1024:.1f}MB 절약")
                        
                    except Exception as e:
                        logger.warning(f"{db_file} 최적화 실패: {e}")
                        total_size_after += size_before
            
            improvement = (total_size_before - total_size_after) / 1024 / 1024  # MB
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': total_size_before / 1024 / 1024,
                'after_value': total_size_after / 1024 / 1024,
                'improvement': improvement,
                'details': '; '.join(optimizations) if optimizations else '최적화 작업 없음',
                'duration': duration
            }
            
            logger.info(f"데이터베이스 최적화 완료: {total_size_before/1024/1024:.1f}MB → {total_size_after/1024/1024:.1f}MB ({improvement:+.1f}MB)")
            return result
            
        except Exception as e:
            logger.error(f"데이터베이스 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def optimize_processes(self):
        """프로세스 최적화"""
        start_time = time.time()
        
        try:
            # 시작 프로세스 수
            processes_before = len(psutil.pids())
            
            optimizations = []
            terminated_processes = 0
            
            # 높은 CPU/메모리 사용 프로세스 확인
            high_usage_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    if (proc_info['cpu_percent'] > 50 or proc_info['memory_percent'] > 20):
                        # 시스템 중요 프로세스는 제외
                        if proc_info['name'] not in ['systemd', 'kernel', 'init', 'python3']:
                            high_usage_processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if high_usage_processes:
                optimizations.append(f"{len(high_usage_processes)}개 고사용량 프로세스 발견")
            
            # 좀비 프로세스 정리
            zombie_count = 0
            for proc in psutil.process_iter(['pid', 'status']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombie_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if zombie_count > 0:
                optimizations.append(f"{zombie_count}개 좀비 프로세스 발견")
            
            # 프로세스 우선순위 조정 (현재 프로세스)
            try:
                current_proc = psutil.Process()
                current_nice = current_proc.nice()
                if current_nice < 10:  # 우선순위가 너무 높은 경우
                    current_proc.nice(10)
                    optimizations.append("현재 프로세스 우선순위 조정")
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            
            # 종료 프로세스 수
            processes_after = len(psutil.pids())
            improvement = processes_before - processes_after
            
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': processes_before,
                'after_value': processes_after,
                'improvement': improvement,
                'details': '; '.join(optimizations) if optimizations else '최적화 작업 없음',
                'duration': duration
            }
            
            logger.info(f"프로세스 최적화 완료: {processes_before}개 → {processes_after}개 ({improvement:+d}개)")
            return result
            
        except Exception as e:
            logger.error(f"프로세스 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def optimize_network(self):
        """네트워크 최적화"""
        start_time = time.time()
        
        try:
            optimizations = []
            
            # 네트워크 연결 상태 확인
            connections = psutil.net_connections()
            established_count = len([c for c in connections if c.status == 'ESTABLISHED'])
            
            # DNS 캐시 플러시 (Windows)
            try:
                if os.name == 'nt':
                    subprocess.run(['ipconfig', '/flushdns'], check=True, timeout=10)
                    optimizations.append("DNS 캐시 플러시")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
            
            # 네트워크 설정 최적화 (Linux)
            try:
                if os.path.exists('/proc/sys/net/core/rmem_max'):
                    # TCP 버퍼 크기 확인
                    with open('/proc/sys/net/core/rmem_max', 'r') as f:
                        rmem_max = int(f.read().strip())
                    
                    if rmem_max < 16777216:  # 16MB
                        optimizations.append("TCP 수신 버퍼 크기 최적화 권장")
            except (OSError, ValueError):
                pass
            
            # 외부 연결 테스트
            webhook_url = self.config.get('DISCORD_WEBHOOK_URL', '')
            if webhook_url:
                try:
                    response = requests.head(webhook_url, timeout=5)
                    if response.status_code == 200:
                        optimizations.append("외부 연결 상태 양호")
                    else:
                        optimizations.append(f"외부 연결 응답 코드: {response.status_code}")
                except requests.RequestException as e:
                    optimizations.append(f"외부 연결 테스트 실패: {e}")
            
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': established_count,
                'after_value': established_count,
                'improvement': 0,
                'details': '; '.join(optimizations) if optimizations else '최적화 작업 없음',
                'duration': duration
            }
            
            logger.info(f"네트워크 최적화 완료: {established_count}개 연결")
            return result
            
        except Exception as e:
            logger.error(f"네트워크 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def optimize_cache(self):
        """캐시 최적화"""
        start_time = time.time()
        
        try:
            optimizations = []
            
            # Python 모듈 캐시 정리
            cache_dirs = ['__pycache__', '.pytest_cache']
            removed_files = 0
            
            for root, dirs, files in os.walk('.'):
                for cache_dir in cache_dirs:
                    if cache_dir in dirs:
                        cache_path = os.path.join(root, cache_dir)
                        try:
                            import shutil
                            shutil.rmtree(cache_path)
                            removed_files += 1
                        except (OSError, PermissionError):
                            pass
            
            if removed_files > 0:
                optimizations.append(f"{removed_files}개 캐시 디렉토리 정리")
            
            # 브라우저 캐시 정리 (사용자 홈 디렉토리)
            try:
                home_dir = os.path.expanduser('~')
                browser_caches = [
                    '.cache/google-chrome',
                    '.cache/firefox',
                    '.cache/chromium'
                ]
                
                for cache_dir in browser_caches:
                    cache_path = os.path.join(home_dir, cache_dir)
                    if os.path.exists(cache_path):
                        try:
                            # 캐시 크기 확인 (정리하지는 않음, 사용자 데이터이므로)
                            cache_size = sum(
                                os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, dirnames, filenames in os.walk(cache_path)
                                for filename in filenames
                            )
                            if cache_size > 100 * 1024 * 1024:  # 100MB 이상
                                optimizations.append(f"{cache_dir} 캐시 크기: {cache_size/1024/1024:.1f}MB")
                        except (OSError, PermissionError):
                            pass
            except Exception:
                pass
            
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': 0,
                'after_value': 0,
                'improvement': removed_files,
                'details': '; '.join(optimizations) if optimizations else '최적화 작업 없음',
                'duration': duration
            }
            
            logger.info(f"캐시 최적화 완료: {removed_files}개 항목 정리")
            return result
            
        except Exception as e:
            logger.error(f"캐시 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def optimize_system_settings(self):
        """시스템 설정 최적화"""
        start_time = time.time()
        
        try:
            optimizations = []
            
            # 파일 디스크립터 제한 확인
            try:
                import resource
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                if soft < 4096:
                    optimizations.append(f"파일 디스크립터 제한이 낮습니다: {soft} (권장: 4096+)")
                else:
                    optimizations.append(f"파일 디스크립터 제한 적절: {soft}")
            except (ImportError, OSError):
                pass
            
            # 스왑 설정 확인
            swap = psutil.swap_memory()
            if swap.total == 0:
                optimizations.append("스왑이 설정되지 않음 (권장: 시스템 메모리의 50-100%)")
            elif swap.total < psutil.virtual_memory().total * 0.5:
                optimizations.append(f"스왑 크기가 작습니다: {swap.total/1024/1024/1024:.1f}GB")
            else:
                optimizations.append(f"스왑 설정 적절: {swap.total/1024/1024/1024:.1f}GB")
            
            # 시스템 로드 확인
            try:
                load_avg = os.getloadavg()
                cpu_count = psutil.cpu_count()
                if load_avg[0] > cpu_count:
                    optimizations.append(f"시스템 로드가 높습니다: {load_avg[0]:.2f} (CPU: {cpu_count}개)")
                else:
                    optimizations.append(f"시스템 로드 정상: {load_avg[0]:.2f}")
            except (OSError, AttributeError):
                pass
            
            # 디스크 I/O 스케줄러 확인 (Linux)
            try:
                if os.path.exists('/sys/block/sda/queue/scheduler'):
                    with open('/sys/block/sda/queue/scheduler', 'r') as f:
                        scheduler = f.read().strip()
                    optimizations.append(f"I/O 스케줄러: {scheduler}")
            except (OSError, PermissionError):
                pass
            
            duration = time.time() - start_time
            
            result = {
                'status': 'SUCCESS',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': '; '.join(optimizations),
                'duration': duration
            }
            
            logger.info("시스템 설정 최적화 완료")
            return result
            
        except Exception as e:
            logger.error(f"시스템 설정 최적화 실패: {e}")
            return {
                'status': 'ERROR',
                'before_value': 0,
                'after_value': 0,
                'improvement': 0,
                'details': f"오류: {e}",
                'duration': time.time() - start_time
            }
    
    def save_optimization_result(self, task_type, result):
        """최적화 결과를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO optimization_tasks (
                    task_type, status, before_value, after_value,
                    improvement, details, duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_type,
                result['status'],
                result['before_value'],
                result['after_value'],
                result['improvement'],
                result['details'],
                result['duration']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"최적화 결과 저장 실패: {e}")
    
    def run_optimization(self, task_types=None):
        """최적화 실행"""
        if task_types is None:
            task_types = list(self.optimization_tasks.keys())
        
        results = {}
        
        for task_type in task_types:
            if task_type in self.optimization_tasks:
                logger.info(f"{task_type} 최적화 시작")
                try:
                    result = self.optimization_tasks[task_type]()
                    results[task_type] = result
                    self.save_optimization_result(task_type, result)
                    logger.info(f"{task_type} 최적화 완료: {result['status']}")
                except Exception as e:
                    logger.error(f"{task_type} 최적화 실패: {e}")
                    results[task_type] = {
                        'status': 'ERROR',
                        'before_value': 0,
                        'after_value': 0,
                        'improvement': 0,
                        'details': f"오류: {e}",
                        'duration': 0
                    }
        
        return results
    
    def start_monitoring(self, interval=60):
        """성능 모니터링 시작"""
        self.running = True
        
        def monitor_loop():
            while self.running:
                try:
                    # 메트릭 수집
                    metrics = self.collect_system_metrics()
                    if metrics:
                        self.save_metrics(metrics)
                        
                        # 성능 이슈 분석
                        issues = self.analyze_performance_issues(metrics)
                        
                        # 심각한 이슈가 있으면 자동 최적화
                        critical_issues = [i for i in issues if i['severity'] in ['HIGH', 'CRITICAL']]
                        if critical_issues:
                            logger.warning(f"{len(critical_issues)}개 심각한 성능 이슈 발견")
                            
                            # 자동 최적화 실행
                            auto_tasks = ['memory_cleanup', 'log_rotation']
                            self.run_optimization(auto_tasks)
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"모니터링 오류: {e}")
                    time.sleep(interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"성능 모니터링 시작 (간격: {interval}초)")
    
    def stop_monitoring(self):
        """성능 모니터링 중지"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("성능 모니터링 중지")
    
    def generate_optimization_report(self, results):
        """최적화 리포트 생성"""
        total_tasks = len(results)
        successful_tasks = len([r for r in results.values() if r['status'] == 'SUCCESS'])
        total_improvement = sum(r['improvement'] for r in results.values() if r['improvement'] > 0)
        total_duration = sum(r['duration'] for r in results.values())
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tasks': total_tasks,
                'successful_tasks': successful_tasks,
                'success_rate': (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0,
                'total_improvement': total_improvement,
                'total_duration': total_duration
            },
            'detailed_results': results
        }
        
        return report
    
    def send_optimization_alert(self, report):
        """최적화 알림 발송"""
        try:
            webhook_url = self.config.get('DISCORD_WEBHOOK_URL')
            if not webhook_url:
                return
            
            success_rate = report['summary']['success_rate']
            total_tasks = report['summary']['total_tasks']
            successful_tasks = report['summary']['successful_tasks']
            
            # 성공률에 따른 색상
            if success_rate >= 80:
                color = 0x2ecc71  # 초록색
                emoji = '✅'
            elif success_rate >= 50:
                color = 0xf39c12  # 주황색
                emoji = '⚠️'
            else:
                color = 0xe74c3c  # 빨간색
                emoji = '❌'
            
            embed = {
                'title': f"{emoji} 시스템 최적화 완료",
                'color': color,
                'fields': [
                    {
                        'name': '📊 최적화 요약',
                        'value': f"총 작업: {total_tasks}개\n"
                                f"성공: {successful_tasks}개\n"
                                f"성공률: {success_rate:.1f}%\n"
                                f"소요시간: {report['summary']['total_duration']:.1f}초",
                        'inline': True
                    }
                ],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': '티켓 알림 시스템 최적화'
                }
            }
            
            # 주요 개선사항 추가
            improvements = []
            for task_type, result in report['detailed_results'].items():
                if result['status'] == 'SUCCESS' and result['improvement'] > 0:
                    improvements.append(f"• {task_type}: {result['improvement']:+.1f}")
            
            if improvements:
                embed['fields'].append({
                    'name': '🚀 주요 개선사항',
                    'value': '\n'.join(improvements[:5]),
                    'inline': False
                })
            
            payload = {
                'embeds': [embed],
                'username': '시스템 최적화기',
                'avatar_url': 'https://cdn-icons-png.flaticon.com/512/2920/2920277.png'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info("최적화 리포트 발송 완료")
            else:
                logger.error(f"최적화 리포트 발송 실패: {response.status_code}")
                
        except Exception as e:
            logger.error(f"최적화 알림 발송 오류: {e}")

def signal_handler(signum, frame):
    """시그널 핸들러"""
    logger.info("종료 신호 수신")
    sys.exit(0)

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='티켓 알림 시스템 성능 최적화 도구')
    parser.add_argument('--config', '-c', default='config.json', help='설정 파일 경로')
    parser.add_argument('--tasks', '-t', nargs='+', help='실행할 최적화 작업')
    parser.add_argument('--monitor', '-m', action='store_true', help='성능 모니터링 시작')
    parser.add_argument('--interval', '-i', type=int, default=60, help='모니터링 간격 (초)')
    parser.add_argument('--report', '-r', action='store_true', help='리포트 발송')
    parser.add_argument('--output', '-o', help='결과를 파일로 저장')
    parser.add_argument('--auto', '-a', action='store_true', help='자동 최적화 모드')
    parser.add_argument('--quiet', '-q', action='store_true', help='조용한 모드')
    
    args = parser.parse_args()
    
    # 로그 디렉토리 생성
    os.makedirs('logs', exist_ok=True)
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 최적화기 초기화
    optimizer = SystemOptimizer(args.config)
    
    try:
        if args.monitor:
            # 모니터링 모드
            optimizer.start_monitoring(args.interval)
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                optimizer.stop_monitoring()
        
        else:
            # 최적화 실행
            if args.auto:
                # 자동 모드: 현재 상태를 분석하여 필요한 최적화만 실행
                metrics = optimizer.collect_system_metrics()
                if metrics:
                    issues = optimizer.analyze_performance_issues(metrics)
                    
                    auto_tasks = []
                    for issue in issues:
                        if issue['type'] == 'memory_high':
                            auto_tasks.append('memory_cleanup')
                        elif issue['type'] == 'disk_high':
                            auto_tasks.extend(['disk_cleanup', 'log_rotation'])
                        elif issue['type'] == 'load_high':
                            auto_tasks.append('process_optimization')
                    
                    if auto_tasks:
                        results = optimizer.run_optimization(list(set(auto_tasks)))
                    else:
                        print("최적화가 필요한 항목이 없습니다.")
                        sys.exit(0)
                else:
                    print("시스템 메트릭을 수집할 수 없습니다.")
                    sys.exit(1)
            else:
                # 수동 모드
                results = optimizer.run_optimization(args.tasks)
            
            # 리포트 생성
            report = optimizer.generate_optimization_report(results)
            
            # 결과 출력
            if not args.quiet:
                print(f"\n=== 최적화 결과 ===")
                print(f"총 작업: {report['summary']['total_tasks']}개")
                print(f"성공: {report['summary']['successful_tasks']}개")
                print(f"성공률: {report['summary']['success_rate']:.1f}%")
                print(f"소요시간: {report['summary']['total_duration']:.1f}초")
                
                for task_type, result in results.items():
                    status_emoji = '✅' if result['status'] == 'SUCCESS' else '❌'
                    print(f"  {status_emoji} {task_type}: {result['details']}")
            
            # 파일로 저장
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                print(f"결과가 {args.output}에 저장되었습니다")
            
            # 리포트 발송
            if args.report:
                optimizer.send_optimization_alert(report)
            
            # 종료 코드 설정
            if report['summary']['success_rate'] < 50:
                sys.exit(1)
            else:
                sys.exit(0)
    
    except Exception as e:
        logger.error(f"최적화 도구 실행 오류: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()