import sqlite3
import os
from datetime import datetime

# 데이터베이스 파일 경로 설정. REQ-005 기반.
DB_PATH = 'data/kopis.db'

def get_db_connection():
    """
    데이터베이스 연결을 생성하고 반환합니다.
    'data' 디렉터리가 없으면 자동으로 생성합니다.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    """
    'performances' 테이블을 생성합니다. REQ-005 명세 기반.
    테이블이 이미 존재하면 오류 없이 넘어갑니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS performances (
            kopis_id TEXT PRIMARY KEY,
            name TEXT,
            start_date TEXT,
            end_date TEXT,
            facility_name TEXT,
            poster_url TEXT,
            genre TEXT,
            status TEXT,
            cast TEXT,
            crew TEXT,
            runtime TEXT,
            age_limit TEXT,
            price TEXT,
            synopsis TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def upsert_performance(performance_data: dict):
    """
    공연 정보를 데이터베이스에 삽입하거나 업데이트(Upsert)합니다.
    REQ-003 기반. kopis_id를 기준으로 동작합니다.
    데이터가 존재하면 UPDATE, 없으면 INSERT를 수행합니다.
    UPDATE 시 updated_at 필드가 현재 시간으로 갱신됩니다.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # INSERT 시에는 created_at과 updated_at을 현재 시간으로 설정합니다.
    data_to_insert = performance_data.copy()
    data_to_insert['created_at'] = now
    data_to_insert['updated_at'] = now

    columns = ', '.join(data_to_insert.keys())
    placeholders = ', '.join(['?'] * len(data_to_insert))
    
    # UPDATE 시에는 performance_data의 모든 필드와 updated_at만 갱신합니다.
    # created_at은 기존 값을 유지해야 하므로 업데이트 목록에서 제외됩니다.
    update_columns = [f"{key} = excluded.{key}" for key in performance_data.keys()]
    update_columns.append(f"updated_at = excluded.updated_at")
    
    update_setters = ', '.join(update_columns)

    query = f'''
        INSERT INTO performances ({columns})
        VALUES ({placeholders})
        ON CONFLICT(kopis_id) DO UPDATE SET
            {update_setters};
    '''
    
    cursor.execute(query, list(data_to_insert.values()))
    
    conn.commit()
    conn.close()

def get_all_performances():
    """
    데이터베이스에서 모든 공연 목록을 가져옵니다.
    Returns:
        list: 공연 정보가 담긴 딕셔너리 리스트
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM performances ORDER BY start_date DESC")
    performances = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return performances

def get_performance_by_id(kopis_id: str):
    """
    kopis_id를 기준으로 특정 공연 정보를 가져옵니다.
    Args:
        kopis_id (str): 조회할 공연의 KOPIS ID
    Returns:
        dict: 해당 공연의 상세 정보 딕셔너리. 없으면 None.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM performances WHERE kopis_id = ?", (kopis_id,))
    performance = cursor.fetchone()
    conn.close()
    if performance:
        return dict(performance)
    return None

if __name__ == "__main__":
    # 스크립트가 직접 실행될 때 테이블이 준비되도록 초기화 로직을 수행합니다.
    print("Initializing database...")
    create_table()
    print("Database and table 'performances' are ready.")