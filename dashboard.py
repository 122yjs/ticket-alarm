#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 알림 시스템 모니터링 대시보드
실시간 시스템 상태, 통계, 로그를 웹 인터페이스로 제공합니다.
"""

import os
import sys
import json
import time
import psutil
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for
from werkzeug.serving import run_simple
import threading
import subprocess
import glob
import re
from collections import defaultdict, deque

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Flask 앱 초기화
app = Flask(__name__)
app.secret_key = 'ticket-alarm-dashboard-secret-key'

# 전역 변수
config = {}
stats_cache = {}
logs_cache = deque(maxlen=1000)
system_info = {}

# 설정 로드
def load_config():
    """설정 파일 로드"""
    global config
    
    config_file = 'config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            config = {}
    
    # 기본값 설정
    config.setdefault('WEB_PORT', 8000)
    config.setdefault('DASHBOARD_PORT', 8001)
    config.setdefault('LOG_LEVEL', 'INFO')
    config.setdefault('CHECK_INTERVAL', 300)
    
    return config

# 시스템 정보 수집
def get_system_info():
    """시스템 정보 수집"""
    try:
        # CPU 정보
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # 메모리 정보
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # 디스크 정보
        disk = psutil.disk_usage('/')
        
        # 네트워크 정보
        network = psutil.net_io_counters()
        
        # 프로세스 정보
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if 'ticket-alarm' in proc.info['name'] or 'python' in proc.info['name']:
                    processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'percent': cpu_percent,
                'count': cpu_count
            },
            'memory': {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent,
                'used': memory.used
            },
            'swap': {
                'total': swap.total,
                'used': swap.used,
                'percent': swap.percent
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': (disk.used / disk.total) * 100
            },
            'network': {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            },
            'processes': processes
        }
    except Exception as e:
        print(f"시스템 정보 수집 실패: {e}")
        return {}

# 서비스 상태 확인
def get_service_status():
    """서비스 상태 확인"""
    services = {}
    
    try:
        # Supervisor 상태 확인
        result = subprocess.run(['supervisorctl', 'status'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'ticket-alarm' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        service_name = parts[0]
                        status = parts[1]
                        services[service_name] = {
                            'status': status,
                            'type': 'supervisor'
                        }
    except Exception as e:
        print(f"Supervisor 상태 확인 실패: {e}")
    
    try:
        # Nginx 상태 확인
        result = subprocess.run(['systemctl', 'is-active', 'nginx'], 
                              capture_output=True, text=True, timeout=5)
        services['nginx'] = {
            'status': result.stdout.strip(),
            'type': 'systemd'
        }
    except Exception as e:
        print(f"Nginx 상태 확인 실패: {e}")
    
    return services

# 로그 파일 읽기
def read_logs(log_file, lines=100):
    """로그 파일에서 최근 라인 읽기"""
    try:
        if not os.path.exists(log_file):
            return []
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:]]
    except Exception as e:
        print(f"로그 파일 읽기 실패 {log_file}: {e}")
        return []

# 통계 데이터 수집
def collect_stats():
    """통계 데이터 수집"""
    stats = {
        'timestamp': datetime.now().isoformat(),
        'notifications': {
            'total': 0,
            'today': 0,
            'this_week': 0,
            'this_month': 0
        },
        'crawling': {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'last_success': None,
            'last_failure': None
        },
        'keywords': {
            'matches': {},
            'priority_matches': {}
        }
    }
    
    try:
        # 알림 이력 파일에서 통계 수집
        history_file = 'notification_history.json'
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            now = datetime.now()
            today = now.date()
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)
            
            for entry in history:
                entry_date = datetime.fromisoformat(entry['timestamp']).date()
                
                stats['notifications']['total'] += 1
                
                if entry_date == today:
                    stats['notifications']['today'] += 1
                
                if entry_date >= week_start:
                    stats['notifications']['this_week'] += 1
                
                if entry_date >= month_start:
                    stats['notifications']['this_month'] += 1
                
                # 키워드 매칭 통계
                for keyword in entry.get('matched_keywords', []):
                    stats['keywords']['matches'][keyword] = stats['keywords']['matches'].get(keyword, 0) + 1
                
                for keyword in entry.get('priority_keywords', []):
                    stats['keywords']['priority_matches'][keyword] = stats['keywords']['priority_matches'].get(keyword, 0) + 1
    
    except Exception as e:
        print(f"알림 통계 수집 실패: {e}")
    
    try:
        # 크롤링 로그에서 통계 수집
        log_files = glob.glob('logs/crawler_*.log') + ['logs/monitor.log']
        
        for log_file in log_files:
            if os.path.exists(log_file):
                logs = read_logs(log_file, 1000)
                
                for log_line in logs:
                    if 'crawling cycle completed' in log_line.lower():
                        stats['crawling']['total_cycles'] += 1
                        stats['crawling']['successful_cycles'] += 1
                        
                        # 타임스탬프 추출
                        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', log_line)
                        if timestamp_match:
                            stats['crawling']['last_success'] = timestamp_match.group(1)
                    
                    elif 'error' in log_line.lower() or 'failed' in log_line.lower():
                        if 'crawling' in log_line.lower():
                            stats['crawling']['failed_cycles'] += 1
                            
                            # 타임스탬프 추출
                            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', log_line)
                            if timestamp_match:
                                stats['crawling']['last_failure'] = timestamp_match.group(1)
    
    except Exception as e:
        print(f"크롤링 통계 수집 실패: {e}")
    
    return stats

# 웹 라우트
@app.route('/')
def dashboard():
    """메인 대시보드 페이지"""
    return render_template('dashboard.html')

@app.route('/api/system')
def api_system():
    """시스템 정보 API"""
    return jsonify(get_system_info())

@app.route('/api/services')
def api_services():
    """서비스 상태 API"""
    return jsonify(get_service_status())

@app.route('/api/stats')
def api_stats():
    """통계 정보 API"""
    return jsonify(collect_stats())

@app.route('/api/logs')
def api_logs():
    """로그 정보 API"""
    log_type = request.args.get('type', 'monitor')
    lines = int(request.args.get('lines', 100))
    
    log_files = {
        'monitor': 'logs/monitor.log',
        'crawler': 'logs/crawler.log',
        'discord': 'logs/discord.log',
        'web': 'logs/web.log',
        'supervisor': '/var/log/ticket-alarm/supervisor.log',
        'nginx_access': '/var/log/ticket-alarm/nginx_access.log',
        'nginx_error': '/var/log/ticket-alarm/nginx_error.log'
    }
    
    log_file = log_files.get(log_type, 'logs/monitor.log')
    logs = read_logs(log_file, lines)
    
    return jsonify({
        'type': log_type,
        'file': log_file,
        'lines': logs,
        'count': len(logs)
    })

@app.route('/api/config')
def api_config():
    """설정 정보 API"""
    # 민감한 정보 제거
    safe_config = config.copy()
    if 'DISCORD_WEBHOOK_URL' in safe_config:
        safe_config['DISCORD_WEBHOOK_URL'] = '***HIDDEN***'
    
    return jsonify(safe_config)

@app.route('/api/health')
def api_health():
    """헬스 체크 API"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'checks': {}
    }
    
    try:
        # 설정 파일 확인
        health_status['checks']['config'] = os.path.exists('config.json')
        
        # 로그 디렉토리 확인
        health_status['checks']['logs_dir'] = os.path.exists('logs')
        
        # 디스크 공간 확인
        disk = psutil.disk_usage('/')
        health_status['checks']['disk_space'] = (disk.free / disk.total) > 0.1  # 10% 이상 여유공간
        
        # 메모리 확인
        memory = psutil.virtual_memory()
        health_status['checks']['memory'] = memory.percent < 90  # 90% 미만 사용
        
        # 서비스 상태 확인
        services = get_service_status()
        health_status['checks']['services'] = any('RUNNING' in str(service.get('status', '')) for service in services.values())
        
        # 전체 상태 결정
        if not all(health_status['checks'].values()):
            health_status['status'] = 'warning'
        
        if not health_status['checks'].get('services', False):
            health_status['status'] = 'critical'
    
    except Exception as e:
        health_status['status'] = 'error'
        health_status['error'] = str(e)
    
    return jsonify(health_status)

@app.route('/api/control/<action>')
def api_control(action):
    """서비스 제어 API"""
    if action not in ['start', 'stop', 'restart', 'reload']:
        return jsonify({'error': 'Invalid action'}), 400
    
    try:
        if action == 'start':
            result = subprocess.run(['supervisorctl', 'start', 'ticket-alarm:*'], 
                                  capture_output=True, text=True, timeout=30)
        elif action == 'stop':
            result = subprocess.run(['supervisorctl', 'stop', 'ticket-alarm:*'], 
                                  capture_output=True, text=True, timeout=30)
        elif action == 'restart':
            result = subprocess.run(['supervisorctl', 'restart', 'ticket-alarm:*'], 
                                  capture_output=True, text=True, timeout=30)
        elif action == 'reload':
            result = subprocess.run(['supervisorctl', 'reread'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                result = subprocess.run(['supervisorctl', 'update'], 
                                      capture_output=True, text=True, timeout=30)
        
        return jsonify({
            'action': action,
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    
    except Exception as e:
        return jsonify({
            'action': action,
            'success': False,
            'error': str(e)
        }), 500

# HTML 템플릿 생성
def create_templates():
    """HTML 템플릿 파일 생성"""
    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    # 메인 대시보드 템플릿
    dashboard_html = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>티켓 알림 시스템 대시보드</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 1.8rem;
            font-weight: 300;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .card {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        
        .card:hover {
            transform: translateY(-2px);
        }
        
        .card h3 {
            color: #667eea;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .metric-value {
            font-weight: bold;
            color: #333;
        }
        
        .status {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .status.running {
            background-color: #d4edda;
            color: #155724;
        }
        
        .status.stopped {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .status.warning {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background-color: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.5rem;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #28a745, #20c997);
            transition: width 0.3s ease;
        }
        
        .progress-fill.warning {
            background: linear-gradient(90deg, #ffc107, #fd7e14);
        }
        
        .progress-fill.danger {
            background: linear-gradient(90deg, #dc3545, #e83e8c);
        }
        
        .logs {
            grid-column: 1 / -1;
        }
        
        .log-container {
            background-color: #1e1e1e;
            color: #f8f8f2;
            padding: 1rem;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .log-line {
            margin-bottom: 0.25rem;
            word-wrap: break-word;
        }
        
        .log-line.error {
            color: #ff6b6b;
        }
        
        .log-line.warning {
            color: #feca57;
        }
        
        .log-line.info {
            color: #48dbfb;
        }
        
        .controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        
        .btn {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: background-color 0.2s;
        }
        
        .btn-primary {
            background-color: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background-color: #5a6fd8;
        }
        
        .btn-success {
            background-color: #28a745;
            color: white;
        }
        
        .btn-success:hover {
            background-color: #218838;
        }
        
        .btn-warning {
            background-color: #ffc107;
            color: #212529;
        }
        
        .btn-warning:hover {
            background-color: #e0a800;
        }
        
        .btn-danger {
            background-color: #dc3545;
            color: white;
        }
        
        .btn-danger:hover {
            background-color: #c82333;
        }
        
        .loading {
            opacity: 0.6;
            pointer-events: none;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }
            
            .grid {
                grid-template-columns: 1fr;
            }
            
            .controls {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎫 티켓 알림 시스템 대시보드</h1>
    </div>
    
    <div class="container">
        <div class="controls">
            <button class="btn btn-success" onclick="controlService('start')">시작</button>
            <button class="btn btn-warning" onclick="controlService('restart')">재시작</button>
            <button class="btn btn-danger" onclick="controlService('stop')">중지</button>
            <button class="btn btn-primary" onclick="refreshData()">새로고침</button>
        </div>
        
        <div class="grid">
            <!-- 시스템 정보 -->
            <div class="card">
                <h3>🖥️ 시스템 정보</h3>
                <div id="system-info">
                    <div class="metric">
                        <span>CPU 사용률</span>
                        <span class="metric-value" id="cpu-usage">-</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="cpu-progress"></div>
                    </div>
                    
                    <div class="metric">
                        <span>메모리 사용률</span>
                        <span class="metric-value" id="memory-usage">-</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="memory-progress"></div>
                    </div>
                    
                    <div class="metric">
                        <span>디스크 사용률</span>
                        <span class="metric-value" id="disk-usage">-</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="disk-progress"></div>
                    </div>
                </div>
            </div>
            
            <!-- 서비스 상태 -->
            <div class="card">
                <h3>⚙️ 서비스 상태</h3>
                <div id="service-status">
                    <div class="metric">
                        <span>로딩 중...</span>
                    </div>
                </div>
            </div>
            
            <!-- 알림 통계 -->
            <div class="card">
                <h3>📊 알림 통계</h3>
                <div id="notification-stats">
                    <div class="metric">
                        <span>오늘</span>
                        <span class="metric-value" id="notifications-today">-</span>
                    </div>
                    <div class="metric">
                        <span>이번 주</span>
                        <span class="metric-value" id="notifications-week">-</span>
                    </div>
                    <div class="metric">
                        <span>이번 달</span>
                        <span class="metric-value" id="notifications-month">-</span>
                    </div>
                    <div class="metric">
                        <span>전체</span>
                        <span class="metric-value" id="notifications-total">-</span>
                    </div>
                </div>
            </div>
            
            <!-- 크롤링 통계 -->
            <div class="card">
                <h3>🕷️ 크롤링 통계</h3>
                <div id="crawling-stats">
                    <div class="metric">
                        <span>총 사이클</span>
                        <span class="metric-value" id="crawling-total">-</span>
                    </div>
                    <div class="metric">
                        <span>성공</span>
                        <span class="metric-value" id="crawling-success">-</span>
                    </div>
                    <div class="metric">
                        <span>실패</span>
                        <span class="metric-value" id="crawling-failed">-</span>
                    </div>
                    <div class="metric">
                        <span>마지막 성공</span>
                        <span class="metric-value" id="crawling-last-success">-</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 로그 -->
        <div class="card logs">
            <h3>📋 실시간 로그</h3>
            <div class="controls">
                <select id="log-type" onchange="loadLogs()">
                    <option value="monitor">모니터</option>
                    <option value="crawler">크롤러</option>
                    <option value="discord">디스코드</option>
                    <option value="web">웹서버</option>
                    <option value="supervisor">Supervisor</option>
                </select>
                <button class="btn btn-primary" onclick="loadLogs()">로그 새로고침</button>
            </div>
            <div class="log-container" id="log-container">
                <div class="log-line">로그를 불러오는 중...</div>
            </div>
        </div>
    </div>
    
    <script>
        // 전역 변수
        let refreshInterval;
        
        // 페이지 로드 시 초기화
        document.addEventListener('DOMContentLoaded', function() {
            refreshData();
            startAutoRefresh();
        });
        
        // 자동 새로고침 시작
        function startAutoRefresh() {
            refreshInterval = setInterval(refreshData, 30000); // 30초마다
        }
        
        // 자동 새로고침 중지
        function stopAutoRefresh() {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
        }
        
        // 데이터 새로고침
        async function refreshData() {
            await Promise.all([
                loadSystemInfo(),
                loadServiceStatus(),
                loadStats(),
                loadLogs()
            ]);
        }
        
        // 시스템 정보 로드
        async function loadSystemInfo() {
            try {
                const response = await fetch('/api/system');
                const data = await response.json();
                
                document.getElementById('cpu-usage').textContent = data.cpu.percent.toFixed(1) + '%';
                document.getElementById('memory-usage').textContent = data.memory.percent.toFixed(1) + '%';
                document.getElementById('disk-usage').textContent = data.disk.percent.toFixed(1) + '%';
                
                updateProgressBar('cpu-progress', data.cpu.percent);
                updateProgressBar('memory-progress', data.memory.percent);
                updateProgressBar('disk-progress', data.disk.percent);
            } catch (error) {
                console.error('시스템 정보 로드 실패:', error);
            }
        }
        
        // 진행률 바 업데이트
        function updateProgressBar(elementId, percentage) {
            const element = document.getElementById(elementId);
            element.style.width = percentage + '%';
            
            // 색상 변경
            element.className = 'progress-fill';
            if (percentage > 80) {
                element.classList.add('danger');
            } else if (percentage > 60) {
                element.classList.add('warning');
            }
        }
        
        // 서비스 상태 로드
        async function loadServiceStatus() {
            try {
                const response = await fetch('/api/services');
                const data = await response.json();
                
                const container = document.getElementById('service-status');
                container.innerHTML = '';
                
                for (const [name, service] of Object.entries(data)) {
                    const div = document.createElement('div');
                    div.className = 'metric';
                    
                    const statusClass = service.status.includes('RUNNING') || service.status === 'active' ? 'running' : 'stopped';
                    
                    div.innerHTML = `
                        <span>${name}</span>
                        <span class="status ${statusClass}">${service.status}</span>
                    `;
                    
                    container.appendChild(div);
                }
            } catch (error) {
                console.error('서비스 상태 로드 실패:', error);
            }
        }
        
        // 통계 정보 로드
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                document.getElementById('notifications-today').textContent = data.notifications.today;
                document.getElementById('notifications-week').textContent = data.notifications.this_week;
                document.getElementById('notifications-month').textContent = data.notifications.this_month;
                document.getElementById('notifications-total').textContent = data.notifications.total;
                
                document.getElementById('crawling-total').textContent = data.crawling.total_cycles;
                document.getElementById('crawling-success').textContent = data.crawling.successful_cycles;
                document.getElementById('crawling-failed').textContent = data.crawling.failed_cycles;
                document.getElementById('crawling-last-success').textContent = data.crawling.last_success || '없음';
            } catch (error) {
                console.error('통계 정보 로드 실패:', error);
            }
        }
        
        // 로그 로드
        async function loadLogs() {
            try {
                const logType = document.getElementById('log-type').value;
                const response = await fetch(`/api/logs?type=${logType}&lines=50`);
                const data = await response.json();
                
                const container = document.getElementById('log-container');
                container.innerHTML = '';
                
                data.lines.forEach(line => {
                    const div = document.createElement('div');
                    div.className = 'log-line';
                    
                    // 로그 레벨에 따른 색상 적용
                    if (line.toLowerCase().includes('error')) {
                        div.classList.add('error');
                    } else if (line.toLowerCase().includes('warning')) {
                        div.classList.add('warning');
                    } else if (line.toLowerCase().includes('info')) {
                        div.classList.add('info');
                    }
                    
                    div.textContent = line;
                    container.appendChild(div);
                });
                
                // 스크롤을 맨 아래로
                container.scrollTop = container.scrollHeight;
            } catch (error) {
                console.error('로그 로드 실패:', error);
            }
        }
        
        // 서비스 제어
        async function controlService(action) {
            try {
                const button = event.target;
                button.disabled = true;
                button.textContent = '처리 중...';
                
                const response = await fetch(`/api/control/${action}`);
                const data = await response.json();
                
                if (data.success) {
                    alert(`${action} 명령이 성공적으로 실행되었습니다.`);
                    setTimeout(refreshData, 2000); // 2초 후 새로고침
                } else {
                    alert(`${action} 명령 실행 실패: ${data.error}`);
                }
            } catch (error) {
                alert(`오류 발생: ${error.message}`);
            } finally {
                // 버튼 복원
                setTimeout(() => {
                    const buttons = document.querySelectorAll('.controls .btn');
                    buttons.forEach(btn => {
                        btn.disabled = false;
                        if (btn.textContent === '처리 중...') {
                            switch(action) {
                                case 'start': btn.textContent = '시작'; break;
                                case 'restart': btn.textContent = '재시작'; break;
                                case 'stop': btn.textContent = '중지'; break;
                                default: btn.textContent = '새로고침'; break;
                            }
                        }
                    });
                }, 1000);
            }
        }
    </script>
</body>
</html>
    '''
    
    with open(os.path.join(templates_dir, 'dashboard.html'), 'w', encoding='utf-8') as f:
        f.write(dashboard_html)

# 메인 실행 함수
def main():
    """메인 실행 함수"""
    # 설정 로드
    load_config()
    
    # 템플릿 생성
    create_templates()
    
    # 로그 디렉토리 생성
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # 대시보드 포트 설정
    port = config.get('DASHBOARD_PORT', 8001)
    
    print(f"티켓 알림 시스템 대시보드 시작")
    print(f"접속 URL: http://localhost:{port}")
    print(f"종료하려면 Ctrl+C를 누르세요")
    
    try:
        # Flask 앱 실행
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n대시보드를 종료합니다")
    except Exception as e:
        print(f"대시보드 실행 오류: {e}")

if __name__ == '__main__':
    main()