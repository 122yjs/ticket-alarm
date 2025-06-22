"""
티켓 정보 필터링 모듈

이 모듈은 수집된 티켓 정보를 다양한 기준으로 필터링하는 기능을 제공합니다.
- 시간순 정렬
- 공연명 정렬
- 아티스트별 필터링
- 키워드 검색
"""

import re
from datetime import datetime
import logging

def parse_date(date_str):
    """
    다양한 형식의 날짜 문자열을 파싱하여 datetime 객체로 변환합니다.
    정확한 시간 정보가 없으면 기본값으로 자정을 사용합니다.
    
    Args:
        date_str (str): 날짜 문자열
        
    Returns:
        datetime: 파싱된 날짜 객체, 파싱 실패 시 datetime.max 반환
    """
    try:
        # 일반적인 날짜 형식에 대한 정규 표현식 패턴
        patterns = [
            # YYYY.MM.DD HH:MM
            (r'(\d{4})[\.\-/](\d{1,2})[\.\-/](\d{1,2})[\s]+(\d{1,2}):(\d{1,2})', 5),
            # YYYY.MM.DD
            (r'(\d{4})[\.\-/](\d{1,2})[\.\-/](\d{1,2})', 3),
            # MM.DD HH:MM
            (r'(\d{1,2})[\.\-/](\d{1,2})[\s]+(\d{1,2}):(\d{1,2})', 4),
            # MM월 DD일 HH시 MM분
            (r'(\d{1,2})월\s*(\d{1,2})일\s*(\d{1,2})시\s*(\d{1,2})분', 4),
            # MM/DD(요일) HH:MM
            (r'(\d{1,2})/(\d{1,2})(?:\([가-힣]\))?\s*(\d{1,2}):(\d{1,2})', 4),
        ]
        
        for pattern, group_count in patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                now = datetime.now()
                if group_count == 5:  # YYYY.MM.DD HH:MM
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]), int(groups[3]), int(groups[4]))
                elif group_count == 3:  # YYYY.MM.DD
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                elif group_count == 4:  # MM.DD HH:MM or MM월 DD일 HH시 MM분
                    return datetime(now.year, int(groups[0]), int(groups[1]), int(groups[2]), int(groups[3]))
        
        # 알려진 패턴과 일치하지 않을 경우, 파싱 실패를 알립니다.
        logging.warning(f"날짜 형식을 파싱할 수 없습니다: '{date_str}'")
        return datetime.max # 정렬 시 맨 뒤로 가도록 설정
    except Exception as e:
        logging.error(f"날짜 파싱 중 예외 발생 - {e}, 입력: '{date_str}'")
        return datetime.max

def sort_by_date(tickets):
    """
    티켓 정보를 오픈 날짜순으로 정렬합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        
    Returns:
        list: 날짜순으로 정렬된 티켓 목록
    """
    logging.info("티켓을 날짜순으로 정렬합니다.")
    return sorted(tickets, key=lambda x: parse_date(x.get('open_date', '')))

def sort_by_title(tickets):
    """
    티켓 정보를 공연 제목의 가나다순으로 정렬합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        
    Returns:
        list: 제목순으로 정렬된 티켓 목록
    """
    logging.info("티켓을 제목순으로 정렬합니다.")
    return sorted(tickets, key=lambda x: x.get('title', '').strip())

def filter_by_artist(tickets, artist_name):
    """
    특정 아티스트 이름이 포함된 티켓만 필터링합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        artist_name (str): 검색할 아티스트 이름
        
    Returns:
        list: 필터링된 티켓 목록
    """
    if not artist_name:
        return tickets
    
    artist_name = artist_name.lower()
    logging.info(f"'{artist_name}' 아티스트로 티켓을 필터링합니다.")
    return [ticket for ticket in tickets if artist_name in ticket.get('title', '').lower()]

def search_by_keyword(tickets, keyword):
    """
    지정된 키워드가 제목에 포함된 티켓을 검색합니다. (대소문자 무시)
    
    Args:
        tickets (list): 티켓 정보 목록
        keyword (str): 검색할 키워드
        
    Returns:
        list: 검색된 티켓 목록
    """
    if not keyword:
        return tickets
    
    keyword = keyword.lower()
    logging.info(f"'{keyword}' 키워드로 티켓을 검색합니다.")
    return [ticket for ticket in tickets if keyword in ticket.get('title', '').lower()]

def filter_by_source(tickets, sources):
    """
    특정 출처(인터파크, YES24 등)의 티켓만 필터링합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        sources (list): 필터링할 출처 목록 (예: ["인터파크", "YES24"])
        
    Returns:
        list: 필터링된 티켓 목록
    """
    if not sources:
        return tickets
    
    logging.info(f"{', '.join(sources)} 출처로 티켓을 필터링합니다.")
    return [ticket for ticket in tickets if ticket.get('source', '') in sources]

def filter_by_date_range(tickets, start_date=None, end_date=None):
    """
    특정 날짜 범위 내의 티켓만 필터링합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        start_date (datetime): 시작 날짜 (None이면 제한 없음)
        end_date (datetime): 종료 날짜 (None이면 제한 없음)
        
    Returns:
        list: 필터링된 티켓 목록
    """
    if not start_date and not end_date:
        return tickets
    
    filtered_tickets = []
    for ticket in tickets:
        ticket_date = parse_date(ticket.get('open_date', ''))
        if ticket_date == datetime.max:
            continue
            
        if start_date and ticket_date < start_date:
            continue
        if end_date and ticket_date > end_date:
            continue
            
        filtered_tickets.append(ticket)
    
    date_range_str = f"{start_date.strftime('%Y-%m-%d') if start_date else '처음'}부터 {end_date.strftime('%Y-%m-%d') if end_date else '끝'}까지"
    logging.info(f"{date_range_str} 기간 내 티켓을 필터링합니다. {len(filtered_tickets)}건 발견.")
    return filtered_tickets

def extract_artists_from_tickets(tickets):
    """
    티켓 목록에서 아티스트 이름을 추출합니다.
    제목에서 일반적인 아티스트 이름 패턴을 찾습니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        
    Returns:
        list: 추출된 아티스트 이름 목록 (중복 제거)
    """
    artists = set()
    
    # 일반적인 아티스트 이름 패턴 (예: "아이유 콘서트", "BTS(방탄소년단) 팬미팅")
    for ticket in tickets:
        title = ticket.get('title', '')
        
        # 괄호 안의 내용 추출 (예: "BTS(방탄소년단)" -> "방탄소년단")
        bracket_matches = re.findall(r'\(([^)]+)\)', title)
        for match in bracket_matches:
            if len(match) > 1 and not re.search(r'\d', match):  # 숫자가 없는 경우만 아티스트로 간주
                artists.add(match.strip())
        
        # 공연명에서 첫 단어가 아티스트인 경우가 많음 (예: "아이유 콘서트")
        words = re.split(r'[\s\-]+', title)
        if words and len(words[0]) > 1 and not re.search(r'\d', words[0]):
            artists.add(words[0].strip())
    
    return sorted(list(artists))

def filter_tickets_by_keywords(tickets, keywords):
    """
    키워드 목록으로 티켓을 필터링합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        keywords (list): 검색할 키워드 목록
        
    Returns:
        list: 필터링된 티켓 목록
    """
    if not keywords:
        return tickets
    
    filtered_tickets = []
    for ticket in tickets:
        title = ticket.get('title', '').lower()
        # 키워드 중 하나라도 포함되면 포함
        for keyword in keywords:
            if keyword.lower() in title:
                filtered_tickets.append(ticket)
                break
    
    return filtered_tickets

def filter_tickets_by_date_range(tickets, start_date=None, end_date=None):
    """
    날짜 범위로 티켓을 필터링합니다. (web_app.py 호환성을 위한 별칭)
    
    Args:
        tickets (list): 티켓 정보 목록
        start_date (datetime): 시작 날짜
        end_date (datetime): 종료 날짜
        
    Returns:
        list: 필터링된 티켓 목록
    """
    return filter_by_date_range(tickets, start_date, end_date)

def group_by_artist(tickets):
    """
    티켓을 아티스트별로 그룹화합니다.
    
    Args:
        tickets (list): 티켓 정보 목록
        
    Returns:
        dict: 아티스트별로 그룹화된 티켓 (키: 아티스트 이름, 값: 티켓 목록)
    """
    artists = extract_artists_from_tickets(tickets)
    grouped = {}
    
    # 각 아티스트별로 티켓 필터링
    for artist in artists:
        artist_tickets = filter_by_artist(tickets, artist)
        if artist_tickets:
            grouped[artist] = artist_tickets
    
    # 어떤 아티스트에도 매칭되지 않은 티켓은 '기타' 그룹으로 분류
    all_grouped_tickets = []
    for tickets_list in grouped.values():
        all_grouped_tickets.extend(tickets_list)
    
    ungrouped = [t for t in tickets if t not in all_grouped_tickets]
    if ungrouped:
        grouped['기타'] = ungrouped
    
    return grouped