#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 알림 시스템 보안 점검 도구
시스템의 보안 설정, 권한, 취약점을 점검합니다.
"""

import os
import sys
import json
import stat
import pwd
import grp
import subprocess
import hashlib
import requests
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import logging
import re
import socket
import ssl

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/security_check.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SecurityChecker:
    """보안 점검 클래스"""
    
    def __init__(self, config_file='config.json'):
        self.config = self.load_config(config_file)
        self.db_path = 'security_audit.db'
        self.init_database()
        
        # 보안 점검 항목
        self.security_checks = {
            'file_permissions': self.check_file_permissions,
            'config_security': self.check_config_security,
            'network_security': self.check_network_security,
            'system_updates': self.check_system_updates,
            'service_security': self.check_service_security,
            'log_security': self.check_log_security,
            'dependency_security': self.check_dependency_security,
            'ssl_certificates': self.check_ssl_certificates,
            'firewall_status': self.check_firewall_status,
            'user_accounts': self.check_user_accounts
        }
        
        # 중요 파일 및 디렉토리
        self.critical_paths = [
            'config.json',
            '.env',
            'logs/',
            'data/',
            'backup/',
            'scripts/',
            'requirements.txt',
            'main.py',
            'crawler.py',
            'discord_notifier.py'
        ]
        
        # 민감한 설정 키
        self.sensitive_keys = [
            'password', 'secret', 'key', 'token', 'webhook',
            'api_key', 'private_key', 'credential', 'auth'
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
        """보안 감사 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 보안 점검 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    check_type TEXT,
                    status TEXT,
                    severity TEXT,
                    message TEXT,
                    details TEXT,
                    recommendation TEXT
                )
            ''')
            
            # 파일 무결성 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_integrity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    file_hash TEXT,
                    file_size INTEGER,
                    permissions TEXT,
                    owner TEXT,
                    last_modified DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 보안 알림 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    resolved BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info("보안 감사 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}")
    
    def check_file_permissions(self):
        """파일 권한 점검"""
        results = []
        
        try:
            for path in self.critical_paths:
                if not os.path.exists(path):
                    continue
                
                # 파일 정보 가져오기
                stat_info = os.stat(path)
                permissions = oct(stat_info.st_mode)[-3:]
                
                # 소유자 정보
                try:
                    owner = pwd.getpwuid(stat_info.st_uid).pw_name
                    group = grp.getgrgid(stat_info.st_gid).gr_name
                except (KeyError, OSError):
                    owner = str(stat_info.st_uid)
                    group = str(stat_info.st_gid)
                
                # 권한 점검
                issues = []
                
                # 설정 파일은 다른 사용자가 읽을 수 없어야 함
                if path in ['config.json', '.env']:
                    if int(permissions[1]) > 0 or int(permissions[2]) > 0:
                        issues.append("설정 파일이 다른 사용자에게 읽기 권한이 있습니다")
                
                # 실행 파일 점검
                if path.endswith('.py'):
                    if int(permissions[2]) >= 7:  # 다른 사용자에게 쓰기 권한
                        issues.append("실행 파일이 다른 사용자에게 쓰기 권한이 있습니다")
                
                # 로그 디렉토리 점검
                if path == 'logs/':
                    if int(permissions[2]) >= 7:
                        issues.append("로그 디렉토리가 다른 사용자에게 쓰기 권한이 있습니다")
                
                if issues:
                    results.append({
                        'status': 'FAIL',
                        'severity': 'HIGH',
                        'message': f"{path} 권한 문제 발견",
                        'details': {
                            'path': path,
                            'permissions': permissions,
                            'owner': owner,
                            'group': group,
                            'issues': issues
                        },
                        'recommendation': f"{path} 파일 권한을 적절히 설정하세요 (chmod 600 또는 640)"
                    })
                else:
                    results.append({
                        'status': 'PASS',
                        'severity': 'INFO',
                        'message': f"{path} 권한 설정이 적절합니다",
                        'details': {
                            'path': path,
                            'permissions': permissions,
                            'owner': owner,
                            'group': group
                        },
                        'recommendation': None
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"파일 권한 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'MEDIUM',
                'message': f"파일 권한 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "시스템 권한을 확인하고 다시 시도하세요"
            }]
    
    def check_config_security(self):
        """설정 보안 점검"""
        results = []
        
        try:
            # config.json 점검
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                issues = []
                
                # 민감한 정보가 평문으로 저장되어 있는지 확인
                def check_sensitive_data(data, path=""):
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_path = f"{path}.{key}" if path else key
                            if any(sensitive in key.lower() for sensitive in self.sensitive_keys):
                                if isinstance(value, str) and len(value) > 0:
                                    # 간단한 패턴으로 암호화되지 않은 데이터 확인
                                    if not (value.startswith('$') or len(value) > 50):
                                        issues.append(f"민감한 설정 '{current_path}'가 평문으로 저장되어 있을 수 있습니다")
                            check_sensitive_data(value, current_path)
                    elif isinstance(data, list):
                        for i, item in enumerate(data):
                            check_sensitive_data(item, f"{path}[{i}]")
                
                check_sensitive_data(config_data)
                
                # 기본값 사용 여부 확인
                default_checks = {
                    'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/',
                    'SECRET_KEY': 'your-secret-key',
                    'API_KEY': 'your-api-key'
                }
                
                for key, default_value in default_checks.items():
                    if config_data.get(key) == default_value:
                        issues.append(f"'{key}' 설정이 기본값을 사용하고 있습니다")
                
                if issues:
                    results.append({
                        'status': 'FAIL',
                        'severity': 'HIGH',
                        'message': "설정 파일 보안 문제 발견",
                        'details': {'issues': issues},
                        'recommendation': "민감한 정보를 환경변수나 암호화된 형태로 저장하세요"
                    })
                else:
                    results.append({
                        'status': 'PASS',
                        'severity': 'INFO',
                        'message': "설정 파일 보안 상태가 양호합니다",
                        'details': {},
                        'recommendation': None
                    })
            
            # .env 파일 점검
            if os.path.exists('.env'):
                with open('.env', 'r', encoding='utf-8') as f:
                    env_content = f.read()
                
                # 빈 값이나 예시 값 확인
                env_issues = []
                for line in env_content.split('\n'):
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        if not value.strip() or value.strip() in ['""', "''", 'your-value', 'example']:
                            env_issues.append(f"환경변수 '{key}'가 설정되지 않았습니다")
                
                if env_issues:
                    results.append({
                        'status': 'FAIL',
                        'severity': 'MEDIUM',
                        'message': "환경변수 설정 문제 발견",
                        'details': {'issues': env_issues},
                        'recommendation': "모든 필수 환경변수를 적절히 설정하세요"
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"설정 보안 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'MEDIUM',
                'message': f"설정 보안 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "설정 파일을 확인하고 다시 시도하세요"
            }]
    
    def check_network_security(self):
        """네트워크 보안 점검"""
        results = []
        
        try:
            # 열린 포트 확인
            web_port = self.config.get('WEB_PORT', 8000)
            
            # 포트가 외부에 노출되어 있는지 확인
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('0.0.0.0', web_port))
                sock.close()
                
                if result == 0:
                    results.append({
                        'status': 'WARN',
                        'severity': 'MEDIUM',
                        'message': f"포트 {web_port}이 모든 인터페이스에서 접근 가능합니다",
                        'details': {'port': web_port, 'interface': '0.0.0.0'},
                        'recommendation': "필요한 경우가 아니라면 localhost에서만 접근 가능하도록 설정하세요"
                    })
                else:
                    results.append({
                        'status': 'PASS',
                        'severity': 'INFO',
                        'message': f"포트 {web_port} 접근 제한이 적절합니다",
                        'details': {'port': web_port},
                        'recommendation': None
                    })
            except Exception as e:
                results.append({
                    'status': 'ERROR',
                    'severity': 'LOW',
                    'message': f"포트 {web_port} 점검 실패: {e}",
                    'details': {},
                    'recommendation': "네트워크 설정을 확인하세요"
                })
            
            # 외부 연결 보안 확인
            webhook_url = self.config.get('DISCORD_WEBHOOK_URL', '')
            if webhook_url:
                if not webhook_url.startswith('https://'):
                    results.append({
                        'status': 'FAIL',
                        'severity': 'HIGH',
                        'message': "디스코드 웹훅 URL이 HTTPS를 사용하지 않습니다",
                        'details': {'url': webhook_url[:50] + '...'},
                        'recommendation': "HTTPS를 사용하는 웹훅 URL로 변경하세요"
                    })
                else:
                    results.append({
                        'status': 'PASS',
                        'severity': 'INFO',
                        'message': "디스코드 웹훅이 HTTPS를 사용합니다",
                        'details': {},
                        'recommendation': None
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"네트워크 보안 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'MEDIUM',
                'message': f"네트워크 보안 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "네트워크 설정을 확인하고 다시 시도하세요"
            }]
    
    def check_system_updates(self):
        """시스템 업데이트 점검"""
        results = []
        
        try:
            # Python 패키지 업데이트 확인
            try:
                result = subprocess.run(
                    ['pip', 'list', '--outdated', '--format=json'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    outdated_packages = json.loads(result.stdout)
                    
                    if outdated_packages:
                        critical_packages = ['requests', 'urllib3', 'cryptography', 'flask']
                        critical_outdated = [pkg for pkg in outdated_packages 
                                           if pkg['name'].lower() in critical_packages]
                        
                        if critical_outdated:
                            results.append({
                                'status': 'FAIL',
                                'severity': 'HIGH',
                                'message': f"{len(critical_outdated)}개의 중요 패키지가 업데이트가 필요합니다",
                                'details': {'packages': critical_outdated},
                                'recommendation': "중요 보안 패키지를 즉시 업데이트하세요"
                            })
                        else:
                            results.append({
                                'status': 'WARN',
                                'severity': 'MEDIUM',
                                'message': f"{len(outdated_packages)}개의 패키지가 업데이트가 필요합니다",
                                'details': {'count': len(outdated_packages)},
                                'recommendation': "정기적으로 패키지를 업데이트하세요"
                            })
                    else:
                        results.append({
                            'status': 'PASS',
                            'severity': 'INFO',
                            'message': "모든 Python 패키지가 최신 상태입니다",
                            'details': {},
                            'recommendation': None
                        })
                
            except subprocess.TimeoutExpired:
                results.append({
                    'status': 'ERROR',
                    'severity': 'LOW',
                    'message': "패키지 업데이트 확인 시간 초과",
                    'details': {},
                    'recommendation': "네트워크 연결을 확인하세요"
                })
            
            # 시스템 패키지 업데이트 확인 (Ubuntu/Debian)
            try:
                result = subprocess.run(
                    ['apt', 'list', '--upgradable'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    upgradable_lines = [line for line in result.stdout.split('\n') 
                                      if '/' in line and 'upgradable' in line]
                    
                    if len(upgradable_lines) > 10:
                        results.append({
                            'status': 'WARN',
                            'severity': 'MEDIUM',
                            'message': f"{len(upgradable_lines)}개의 시스템 패키지가 업데이트가 필요합니다",
                            'details': {'count': len(upgradable_lines)},
                            'recommendation': "정기적으로 시스템 패키지를 업데이트하세요 (sudo apt update && sudo apt upgrade)"
                        })
                    else:
                        results.append({
                            'status': 'PASS',
                            'severity': 'INFO',
                            'message': "시스템 패키지가 최신 상태입니다",
                            'details': {},
                            'recommendation': None
                        })
                        
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # apt가 없는 시스템 (CentOS, macOS 등)
                pass
            
            return results
            
        except Exception as e:
            logger.error(f"시스템 업데이트 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'MEDIUM',
                'message': f"시스템 업데이트 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "시스템 패키지 관리자를 확인하세요"
            }]
    
    def check_service_security(self):
        """서비스 보안 점검"""
        results = []
        
        try:
            # Supervisor 설정 확인
            supervisor_configs = [
                '/etc/supervisor/conf.d/ticket-alarm.conf',
                'supervisor/ticket-alarm.conf'
            ]
            
            for config_path in supervisor_configs:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config_content = f.read()
                    
                    issues = []
                    
                    # 사용자 권한 확인
                    if 'user=root' in config_content:
                        issues.append("서비스가 root 권한으로 실행됩니다")
                    
                    # 자동 재시작 설정 확인
                    if 'autorestart=false' in config_content:
                        issues.append("자동 재시작이 비활성화되어 있습니다")
                    
                    if issues:
                        results.append({
                            'status': 'WARN',
                            'severity': 'MEDIUM',
                            'message': f"Supervisor 설정에 보안 문제가 있습니다: {config_path}",
                            'details': {'issues': issues, 'config_path': config_path},
                            'recommendation': "서비스를 전용 사용자로 실행하고 적절한 설정을 사용하세요"
                        })
                    else:
                        results.append({
                            'status': 'PASS',
                            'severity': 'INFO',
                            'message': f"Supervisor 설정이 적절합니다: {config_path}",
                            'details': {'config_path': config_path},
                            'recommendation': None
                        })
                    break
            else:
                results.append({
                    'status': 'WARN',
                    'severity': 'LOW',
                    'message': "Supervisor 설정 파일을 찾을 수 없습니다",
                    'details': {},
                    'recommendation': "프로세스 관리를 위해 Supervisor를 설정하세요"
                })
            
            return results
            
        except Exception as e:
            logger.error(f"서비스 보안 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'MEDIUM',
                'message': f"서비스 보안 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "서비스 설정을 확인하고 다시 시도하세요"
            }]
    
    def check_log_security(self):
        """로그 보안 점검"""
        results = []
        
        try:
            log_dir = 'logs'
            if not os.path.exists(log_dir):
                results.append({
                    'status': 'FAIL',
                    'severity': 'MEDIUM',
                    'message': "로그 디렉토리가 존재하지 않습니다",
                    'details': {},
                    'recommendation': "로그 디렉토리를 생성하고 적절한 권한을 설정하세요"
                })
                return results
            
            # 로그 파일 권한 확인
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            
            for log_file in log_files:
                log_path = os.path.join(log_dir, log_file)
                stat_info = os.stat(log_path)
                permissions = oct(stat_info.st_mode)[-3:]
                
                # 로그 파일이 다른 사용자에게 읽기 권한이 있는지 확인
                if int(permissions[2]) >= 4:
                    results.append({
                        'status': 'WARN',
                        'severity': 'MEDIUM',
                        'message': f"로그 파일 {log_file}이 다른 사용자에게 읽기 권한이 있습니다",
                        'details': {'file': log_file, 'permissions': permissions},
                        'recommendation': f"로그 파일 권한을 제한하세요 (chmod 640 {log_path})"
                    })
            
            # 로그 로테이션 설정 확인
            logrotate_config = '/etc/logrotate.d/ticket-alarm'
            if not os.path.exists(logrotate_config):
                results.append({
                    'status': 'WARN',
                    'severity': 'LOW',
                    'message': "로그 로테이션이 설정되지 않았습니다",
                    'details': {},
                    'recommendation': "로그 로테이션을 설정하여 디스크 공간을 관리하세요"
                })
            
            # 민감한 정보가 로그에 기록되는지 확인
            sensitive_patterns = [
                re.compile(r'password[\s=:]+[\w]+', re.IGNORECASE),
                re.compile(r'token[\s=:]+[\w-]+', re.IGNORECASE),
                re.compile(r'key[\s=:]+[\w-]+', re.IGNORECASE),
                re.compile(r'secret[\s=:]+[\w-]+', re.IGNORECASE)
            ]
            
            for log_file in log_files[:3]:  # 최근 3개 로그 파일만 확인
                log_path = os.path.join(log_dir, log_file)
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        content = f.read(10000)  # 처음 10KB만 확인
                    
                    for pattern in sensitive_patterns:
                        if pattern.search(content):
                            results.append({
                                'status': 'FAIL',
                                'severity': 'HIGH',
                                'message': f"로그 파일 {log_file}에 민감한 정보가 기록되어 있을 수 있습니다",
                                'details': {'file': log_file},
                                'recommendation': "로그에 민감한 정보가 기록되지 않도록 코드를 수정하세요"
                            })
                            break
                except Exception:
                    pass
            
            if not any(result['status'] in ['FAIL', 'WARN'] for result in results):
                results.append({
                    'status': 'PASS',
                    'severity': 'INFO',
                    'message': "로그 보안 설정이 적절합니다",
                    'details': {},
                    'recommendation': None
                })
            
            return results
            
        except Exception as e:
            logger.error(f"로그 보안 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'MEDIUM',
                'message': f"로그 보안 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "로그 설정을 확인하고 다시 시도하세요"
            }]
    
    def check_dependency_security(self):
        """의존성 보안 점검"""
        results = []
        
        try:
            # requirements.txt 확인
            if os.path.exists('requirements.txt'):
                with open('requirements.txt', 'r') as f:
                    requirements = f.read().strip().split('\n')
                
                # 버전이 고정되지 않은 패키지 확인
                unfixed_packages = []
                for req in requirements:
                    if req.strip() and not any(op in req for op in ['==', '>=', '<=', '~=']):
                        unfixed_packages.append(req.strip())
                
                if unfixed_packages:
                    results.append({
                        'status': 'WARN',
                        'severity': 'MEDIUM',
                        'message': f"{len(unfixed_packages)}개 패키지의 버전이 고정되지 않았습니다",
                        'details': {'packages': unfixed_packages},
                        'recommendation': "보안을 위해 패키지 버전을 고정하세요"
                    })
                else:
                    results.append({
                        'status': 'PASS',
                        'severity': 'INFO',
                        'message': "모든 패키지 버전이 적절히 고정되어 있습니다",
                        'details': {},
                        'recommendation': None
                    })
            
            # 알려진 취약한 패키지 확인 (간단한 예시)
            vulnerable_packages = {
                'requests': '2.25.0',  # 예시: 특정 버전 이하는 취약
                'urllib3': '1.26.0'
            }
            
            try:
                import pkg_resources
                installed_packages = {pkg.project_name.lower(): pkg.version 
                                    for pkg in pkg_resources.working_set}
                
                for pkg_name, min_version in vulnerable_packages.items():
                    if pkg_name in installed_packages:
                        installed_version = installed_packages[pkg_name]
                        if installed_version < min_version:
                            results.append({
                                'status': 'FAIL',
                                'severity': 'HIGH',
                                'message': f"취약한 버전의 {pkg_name} 패키지가 설치되어 있습니다",
                                'details': {
                                    'package': pkg_name,
                                    'installed': installed_version,
                                    'minimum': min_version
                                },
                                'recommendation': f"{pkg_name} 패키지를 {min_version} 이상으로 업데이트하세요"
                            })
            except ImportError:
                pass
            
            return results
            
        except Exception as e:
            logger.error(f"의존성 보안 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'MEDIUM',
                'message': f"의존성 보안 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "패키지 설정을 확인하고 다시 시도하세요"
            }]
    
    def check_ssl_certificates(self):
        """SSL 인증서 점검"""
        results = []
        
        try:
            # 웹훅 URL의 SSL 인증서 확인
            webhook_url = self.config.get('DISCORD_WEBHOOK_URL', '')
            if webhook_url and webhook_url.startswith('https://'):
                try:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(webhook_url)
                    hostname = parsed_url.hostname
                    port = parsed_url.port or 443
                    
                    # SSL 인증서 정보 가져오기
                    context = ssl.create_default_context()
                    with socket.create_connection((hostname, port), timeout=10) as sock:
                        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                            cert = ssock.getpeercert()
                    
                    # 인증서 만료일 확인
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.now()).days
                    
                    if days_until_expiry < 30:
                        results.append({
                            'status': 'WARN',
                            'severity': 'MEDIUM',
                            'message': f"SSL 인증서가 {days_until_expiry}일 후 만료됩니다",
                            'details': {
                                'hostname': hostname,
                                'expiry_date': not_after.isoformat(),
                                'days_remaining': days_until_expiry
                            },
                            'recommendation': "SSL 인증서 갱신을 준비하세요"
                        })
                    else:
                        results.append({
                            'status': 'PASS',
                            'severity': 'INFO',
                            'message': f"SSL 인증서가 유효합니다 ({days_until_expiry}일 남음)",
                            'details': {
                                'hostname': hostname,
                                'days_remaining': days_until_expiry
                            },
                            'recommendation': None
                        })
                        
                except Exception as e:
                    results.append({
                        'status': 'ERROR',
                        'severity': 'LOW',
                        'message': f"SSL 인증서 확인 실패: {e}",
                        'details': {},
                        'recommendation': "네트워크 연결을 확인하세요"
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"SSL 인증서 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'LOW',
                'message': f"SSL 인증서 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "SSL 설정을 확인하고 다시 시도하세요"
            }]
    
    def check_firewall_status(self):
        """방화벽 상태 점검"""
        results = []
        
        try:
            # UFW 상태 확인
            try:
                result = subprocess.run(
                    ['ufw', 'status'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    if 'Status: active' in result.stdout:
                        results.append({
                            'status': 'PASS',
                            'severity': 'INFO',
                            'message': "UFW 방화벽이 활성화되어 있습니다",
                            'details': {},
                            'recommendation': None
                        })
                    else:
                        results.append({
                            'status': 'WARN',
                            'severity': 'MEDIUM',
                            'message': "UFW 방화벽이 비활성화되어 있습니다",
                            'details': {},
                            'recommendation': "보안을 위해 방화벽을 활성화하세요 (sudo ufw enable)"
                        })
                        
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # UFW가 없는 시스템
                results.append({
                    'status': 'WARN',
                    'severity': 'LOW',
                    'message': "방화벽 상태를 확인할 수 없습니다",
                    'details': {},
                    'recommendation': "시스템에 적절한 방화벽을 설정하세요"
                })
            
            return results
            
        except Exception as e:
            logger.error(f"방화벽 상태 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'LOW',
                'message': f"방화벽 상태 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "방화벽 설정을 확인하고 다시 시도하세요"
            }]
    
    def check_user_accounts(self):
        """사용자 계정 점검"""
        results = []
        
        try:
            # 현재 사용자 확인
            current_user = os.getenv('USER') or os.getenv('USERNAME')
            
            if current_user == 'root':
                results.append({
                    'status': 'WARN',
                    'severity': 'HIGH',
                    'message': "애플리케이션이 root 사용자로 실행되고 있습니다",
                    'details': {'user': current_user},
                    'recommendation': "보안을 위해 전용 사용자 계정을 생성하여 사용하세요"
                })
            else:
                results.append({
                    'status': 'PASS',
                    'severity': 'INFO',
                    'message': f"애플리케이션이 적절한 사용자({current_user})로 실행되고 있습니다",
                    'details': {'user': current_user},
                    'recommendation': None
                })
            
            # sudo 권한 확인
            try:
                result = subprocess.run(
                    ['sudo', '-n', 'true'],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    results.append({
                        'status': 'WARN',
                        'severity': 'MEDIUM',
                        'message': "현재 사용자가 패스워드 없이 sudo 권한을 가지고 있습니다",
                        'details': {},
                        'recommendation': "보안을 위해 sudo 권한을 제한하거나 패스워드를 요구하도록 설정하세요"
                    })
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            return results
            
        except Exception as e:
            logger.error(f"사용자 계정 점검 실패: {e}")
            return [{
                'status': 'ERROR',
                'severity': 'LOW',
                'message': f"사용자 계정 점검 중 오류 발생: {e}",
                'details': {},
                'recommendation': "사용자 설정을 확인하고 다시 시도하세요"
            }]
    
    def save_check_results(self, check_type, results):
        """점검 결과를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for result in results:
                cursor.execute('''
                    INSERT INTO security_checks (
                        check_type, status, severity, message, details, recommendation
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    check_type,
                    result['status'],
                    result['severity'],
                    result['message'],
                    json.dumps(result['details']),
                    result['recommendation']
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"점검 결과 저장 실패: {e}")
    
    def run_security_check(self, check_types=None):
        """보안 점검 실행"""
        if check_types is None:
            check_types = list(self.security_checks.keys())
        
        all_results = {}
        
        for check_type in check_types:
            if check_type in self.security_checks:
                logger.info(f"{check_type} 점검 시작")
                try:
                    results = self.security_checks[check_type]()
                    all_results[check_type] = results
                    self.save_check_results(check_type, results)
                    logger.info(f"{check_type} 점검 완료: {len(results)}개 결과")
                except Exception as e:
                    logger.error(f"{check_type} 점검 실패: {e}")
                    all_results[check_type] = [{
                        'status': 'ERROR',
                        'severity': 'HIGH',
                        'message': f"{check_type} 점검 중 오류 발생: {e}",
                        'details': {},
                        'recommendation': "시스템 상태를 확인하고 다시 시도하세요"
                    }]
        
        return all_results
    
    def generate_security_report(self, results):
        """보안 점검 리포트 생성"""
        total_checks = sum(len(checks) for checks in results.values())
        
        status_counts = {'PASS': 0, 'WARN': 0, 'FAIL': 0, 'ERROR': 0}
        severity_counts = {'INFO': 0, 'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
        
        critical_issues = []
        
        for check_type, checks in results.items():
            for check in checks:
                status_counts[check['status']] += 1
                severity_counts[check['severity']] += 1
                
                if check['severity'] in ['HIGH', 'CRITICAL'] and check['status'] in ['FAIL', 'WARN']:
                    critical_issues.append({
                        'check_type': check_type,
                        'message': check['message'],
                        'severity': check['severity'],
                        'recommendation': check['recommendation']
                    })
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_checks': total_checks,
                'status_counts': status_counts,
                'severity_counts': severity_counts,
                'critical_issues_count': len(critical_issues)
            },
            'critical_issues': critical_issues,
            'detailed_results': results
        }
        
        return report
    
    def send_security_alert(self, report):
        """보안 알림 발송"""
        try:
            webhook_url = self.config.get('DISCORD_WEBHOOK_URL')
            if not webhook_url:
                return
            
            critical_count = report['summary']['critical_issues_count']
            fail_count = report['summary']['status_counts']['FAIL']
            warn_count = report['summary']['status_counts']['WARN']
            
            # 심각도에 따른 색상
            if critical_count > 0 or fail_count > 0:
                color = 0xe74c3c  # 빨간색
                emoji = '🚨'
            elif warn_count > 0:
                color = 0xf39c12  # 주황색
                emoji = '⚠️'
            else:
                color = 0x2ecc71  # 초록색
                emoji = '✅'
            
            embed = {
                'title': f"{emoji} 보안 점검 리포트",
                'color': color,
                'fields': [
                    {
                        'name': '📊 점검 요약',
                        'value': f"총 점검: {report['summary']['total_checks']}개\n"
                                f"통과: {report['summary']['status_counts']['PASS']}개\n"
                                f"경고: {report['summary']['status_counts']['WARN']}개\n"
                                f"실패: {report['summary']['status_counts']['FAIL']}개",
                        'inline': True
                    },
                    {
                        'name': '🔥 심각도별 분류',
                        'value': f"높음: {report['summary']['severity_counts']['HIGH']}개\n"
                                f"중간: {report['summary']['severity_counts']['MEDIUM']}개\n"
                                f"낮음: {report['summary']['severity_counts']['LOW']}개",
                        'inline': True
                    }
                ],
                'timestamp': datetime.now().isoformat(),
                'footer': {
                    'text': '티켓 알림 시스템 보안 점검'
                }
            }
            
            # 중요 이슈 추가
            if critical_count > 0:
                critical_text = '\n'.join([
                    f"• {issue['message']}"
                    for issue in report['critical_issues'][:3]
                ])
                embed['fields'].append({
                    'name': '🚨 중요 보안 이슈',
                    'value': critical_text,
                    'inline': False
                })
            
            payload = {
                'embeds': [embed],
                'username': '보안 점검기',
                'avatar_url': 'https://cdn-icons-png.flaticon.com/512/2920/2920277.png'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info("보안 점검 리포트 발송 완료")
            else:
                logger.error(f"보안 리포트 발송 실패: {response.status_code}")
                
        except Exception as e:
            logger.error(f"보안 알림 발송 오류: {e}")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='티켓 알림 시스템 보안 점검 도구')
    parser.add_argument('--config', '-c', default='config.json', help='설정 파일 경로')
    parser.add_argument('--checks', '-k', nargs='+', help='실행할 점검 항목')
    parser.add_argument('--report', '-r', action='store_true', help='리포트 발송')
    parser.add_argument('--output', '-o', help='결과를 파일로 저장')
    parser.add_argument('--quiet', '-q', action='store_true', help='조용한 모드')
    
    args = parser.parse_args()
    
    # 로그 디렉토리 생성
    os.makedirs('logs', exist_ok=True)
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # 보안 점검기 초기화
    checker = SecurityChecker(args.config)
    
    # 보안 점검 실행
    results = checker.run_security_check(args.checks)
    
    # 리포트 생성
    report = checker.generate_security_report(results)
    
    # 결과 출력
    if not args.quiet:
        print(f"\n=== 보안 점검 결과 ===")
        print(f"총 점검: {report['summary']['total_checks']}개")
        print(f"통과: {report['summary']['status_counts']['PASS']}개")
        print(f"경고: {report['summary']['status_counts']['WARN']}개")
        print(f"실패: {report['summary']['status_counts']['FAIL']}개")
        print(f"오류: {report['summary']['status_counts']['ERROR']}개")
        
        if report['critical_issues']:
            print(f"\n🚨 중요 보안 이슈 ({len(report['critical_issues'])}개):")
            for issue in report['critical_issues']:
                print(f"  [{issue['severity']}] {issue['message']}")
                if issue['recommendation']:
                    print(f"    권장사항: {issue['recommendation']}")
    
    # 파일로 저장
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"결과가 {args.output}에 저장되었습니다")
    
    # 리포트 발송
    if args.report:
        checker.send_security_alert(report)
    
    # 종료 코드 설정
    if report['summary']['status_counts']['FAIL'] > 0:
        sys.exit(1)
    elif report['summary']['status_counts']['WARN'] > 0:
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()