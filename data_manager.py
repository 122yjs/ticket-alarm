"""
티켓 데이터 관리 모듈

이 모듈은 수집된 티켓 정보를 저장, 로드, 업데이트하는 기능을 제공합니다.
- 티켓 정보 저장 및 로드
- 새로운 티켓 정보 업데이트
- 알림 발송 기록 관리
"""

import os
import json
import logging
from datetime import datetime

# 데이터 저장 경로 설정
DATA_DIR = "data"
ALL_TICKETS_FILE = os.path.join(DATA_DIR, "all_tickets.json")
SENT_NOTIFICATIONS_FILE = os.path.join(DATA_DIR, "sent_notifications.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

def ensure_data_directory():
    """
    데이터 저장을 위한 'data' 폴더가 있는지 확인하고, 없으면 생성합니다.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    logging.info(f"'{DATA_DIR}' 폴더를 확인하고 준비했습니다.")

def load_config():
    """
    설정 파일을 로드합니다.
    
    Returns:
        dict: 설정 정보 (설정 파일이 없으면 기본 설정 반환)
    """
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        logging.info(f"설정 파일을 성공적으로 로드했습니다.")
        return config
    except FileNotFoundError:
        logging.warning(f"설정 파일({CONFIG_FILE})을 찾을 수 없습니다. 기본 설정을 사용합니다.")
        return {
            "DISCORD_WEBHOOK_URL": "",
            "KEYWORDS": [],
            "interval": 3600,
            "sources": ["interpark", "yes24", "melon", "ticketlink"]
        }
    except json.JSONDecodeError:
        logging.error(f"설정 파일({CONFIG_FILE})의 형식이 잘못되었습니다. 기본 설정을 사용합니다.")
        return {
            "DISCORD_WEBHOOK_URL": "",
            "KEYWORDS": [],
            "interval": 3600,
            "sources": ["interpark", "yes24", "melon", "ticketlink"]
        }

def save_tickets(tickets, filename=ALL_TICKETS_FILE):
    """
    티켓 정보를 JSON 파일로 저장합니다.
    
    Args:
        tickets (list): 저장할 티켓 정보 목록
        filename (str): 저장할 파일 경로 (기본값: all_tickets.json)
    
    Returns:
        bool: 저장 성공 여부
    """
    try:
        ensure_data_directory()
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(tickets, f, ensure_ascii=False, indent=2)
        logging.info(f"티켓 정보가 '{filename}' 파일에 성공적으로 저장되었습니다. (총 {len(tickets)}건)")
        return True
    except Exception as e:
        logging.error(f"'{filename}' 파일에 티켓 정보를 저장하는 중 오류 발생: {e}")
        return False

def load_tickets(filename=ALL_TICKETS_FILE):
    """
    저장된 티켓 정보를 로드합니다.
    
    Args:
        filename (str): 로드할 파일 경로 (기본값: all_tickets.json)
    
    Returns:
        list: 로드된 티켓 정보 목록 (파일이 없으면 빈 리스트 반환)
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            tickets = json.load(f)
        logging.info(f"'{filename}' 파일에서 티켓 정보를 성공적으로 로드했습니다. (총 {len(tickets)}건)")
        return tickets
    except FileNotFoundError:
        logging.warning(f"'{filename}' 파일을 찾을 수 없습니다. 빈 목록을 반환합니다.")
        return []
    except json.JSONDecodeError:
        logging.error(f"'{filename}' 파일의 형식이 잘못되었습니다. 빈 목록을 반환합니다.")
        return []

def load_sent_notifications():
    """
    이미 알림을 보낸 티켓 정보를 로드합니다.
    
    Returns:
        list: 알림을 보낸 티켓 ID 목록
    """
    return load_tickets(SENT_NOTIFICATIONS_FILE)

def save_sent_notifications(sent_notifications):
    """
    알림을 보낸 티켓 정보를 저장합니다.
    
    Args:
        sent_notifications (list): 알림을 보낸 티켓 ID 목록
    
    Returns:
        bool: 저장 성공 여부
    """
    return save_tickets(sent_notifications, SENT_NOTIFICATIONS_FILE)

def update_tickets(new_tickets):
    """
    기존 티켓 정보에 새로운 티켓 정보를 추가합니다.
    중복된 티켓은 최신 정보로 업데이트합니다.
    
    Args:
        new_tickets (list): 새로운 티켓 정보 목록
    
    Returns:
        tuple: (업데이트된 전체 티켓 목록, 새로 추가된 티켓 목록)
    """
    existing_tickets = load_tickets()
    
    # 티켓 ID를 키로 하는 딕셔너리 생성 (중복 제거를 위함)
    ticket_dict = {get_ticket_id(ticket): ticket for ticket in existing_tickets}
    
    # 새로운 티켓 추가 또는 기존 티켓 업데이트
    new_ticket_ids = []
    for ticket in new_tickets:
        ticket_id = get_ticket_id(ticket)
        if ticket_id not in ticket_dict:
            new_ticket_ids.append(ticket_id)
        ticket_dict[ticket_id] = ticket
    
    # 딕셔너리를 다시 리스트로 변환
    updated_tickets = list(ticket_dict.values())
    
    # 새로 추가된 티켓만 필터링
    newly_added_tickets = [ticket for ticket in updated_tickets if get_ticket_id(ticket) in new_ticket_ids]
    
    # 업데이트된 티켓 저장
    save_tickets(updated_tickets)
    
    logging.info(f"티켓 정보 업데이트 완료: 총 {len(updated_tickets)}건 (새로 추가: {len(newly_added_tickets)}건)")
    return updated_tickets, newly_added_tickets

def get_ticket_id(ticket):
    """
    티켓의 고유 ID를 생성합니다.
    제목, 오픈 날짜, 출처를 조합하여 고유 ID를 생성합니다.
    
    Args:
        ticket (dict): 티켓 정보
    
    Returns:
        str: 티켓의 고유 ID
    """
    title = ticket.get('title', '').strip()
    open_date = ticket.get('open_date', '').strip()
    source = ticket.get('source', '').strip()
    
    # 제목과 출처는 필수 정보로 간주
    if not title or not source:
        return None
    
    # 제목, 날짜, 출처를 조합하여 고유 ID 생성
    return f"{source}_{title}_{open_date}"

def mark_as_notified(ticket_ids):
    """
    티켓에 대한 알림을 보냈음을 기록합니다.
    
    Args:
        ticket_ids (list): 알림을 보낸 티켓 ID 목록
    
    Returns:
        bool: 저장 성공 여부
    """
    sent_notifications = load_sent_notifications()
    
    # 새로운 알림 ID 추가
    for ticket_id in ticket_ids:
        if ticket_id not in sent_notifications:
            sent_notifications.append(ticket_id)
    
    return save_sent_notifications(sent_notifications)

def get_new_tickets_for_notification(tickets):
    """
    아직 알림을 보내지 않은 새로운 티켓을 필터링합니다.
    
    Args:
        tickets (list): 전체 티켓 목록
    
    Returns:
        list: 알림을 보내지 않은 티켓 목록
    """
    sent_notifications = load_sent_notifications()
    
    # 알림을 보내지 않은 티켓만 필터링
    new_tickets = []
    for ticket in tickets:
        ticket_id = get_ticket_id(ticket)
        if ticket_id and ticket_id not in sent_notifications:
            new_tickets.append(ticket)
    
    logging.info(f"알림을 보내지 않은 새로운 티켓: {len(new_tickets)}건")
    return new_tickets

def add_timestamp_to_tickets(tickets):
    """
    티켓 정보에 수집 시간 정보를 추가합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
    
    Returns:
        list: 타임스탬프가 추가된 티켓 목록
    """
    now = datetime.now().isoformat()
    for ticket in tickets:
        if 'collected_at' not in ticket:
            ticket['collected_at'] = now
    return tickets