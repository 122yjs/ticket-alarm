# 🔧 수동 패키지 정리 가이드

Python과 pip이 PATH에 등록되어 있지 않아 자동 스크립트 실행이 불가능합니다.
아래 가이드를 따라 수동으로 정리해주세요.

## 🚀 방법 1: Python 경로 찾기 (권장)

### 1단계: Python 설치 위치 찾기
Windows 검색에서 "python" 검색하거나 다음 위치들을 확인:
- `C:\Python3x\`
- `C:\Users\[사용자명]\AppData\Local\Programs\Python\`
- `C:\Program Files\Python3x\`

### 2단계: 명령 프롬프트에서 실행
```cmd
# Python 경로를 찾았다면 (예: C:\Python39\python.exe)
C:\Python39\python.exe -m pip list | findstr google

# Google 패키지들이 있다면 제거
C:\Python39\python.exe -m pip uninstall google-ai-generativelanguage -y
C:\Python39\python.exe -m pip uninstall google-api-core -y
C:\Python39\python.exe -m pip uninstall google-cloud-aiplatform -y
# ... (모든 google 패키지들)

# 최적화된 패키지 설치
C:\Python39\python.exe -m pip install -r requirements.txt
C:\Python39\python.exe -m playwright install chromium
```

## 🚀 방법 2: 새 가상환경 생성 (가장 깨끗함)

### 1단계: 새 가상환경 생성
```cmd
# Python 경로를 찾았다면
C:\Python39\python.exe -m venv venv_clean
```

### 2단계: 가상환경 활성화
```cmd
venv_clean\Scripts\activate
```

### 3단계: 최적화된 패키지 설치
```cmd
pip install -r requirements.txt
playwright install chromium
```

## 🚀 방법 3: Anaconda/Miniconda 사용자

```cmd
# 새 환경 생성
conda create -n ticket-alarm python=3.9
conda activate ticket-alarm

# 패키지 설치
pip install -r requirements.txt
playwright install chromium
```

## 📋 제거해야 할 패키지 목록

다음 패키지들이 설치되어 있다면 제거하세요:

### Google AI/Cloud 관련 (23개)
- google-ai-generativelanguage
- google-api-core
- google-api-python-client
- google-auth
- google-auth-httplib2
- google-auth-oauthlib
- google-cloud-aiplatform
- google-cloud-bigquery
- google-cloud-core
- google-cloud-resource-manager
- google-cloud-secret-manager
- google-cloud-speech
- google-cloud-storage
- google-cloud-trace
- google-crc32c
- google-genai
- google-generativeai
- google-resumable-media
- googleapis-common-protos
- grpc-google-iam-v1
- grpcio
- grpcio-status
- google-adk

### 기타 불필요한 패키지
- numpy
- joblib

## ✅ 설치해야 할 패키지 (requirements.txt)

```
fastapi
uvicorn
gunicorn
jinja2
peewee
playwright
beautifulsoup4
requests
```

## 🔍 확인 방법

설치 완료 후 다음 명령으로 확인:
```cmd
pip list
```

필요한 8개 패키지만 있고 Google 관련 패키지들이 없어야 합니다.

## 💡 팁

1. **가상환경 사용 권장**: 시스템 Python을 건드리지 않고 깨끗하게 관리
2. **PATH 설정**: Python을 PATH에 추가하면 앞으로 더 편리함
3. **IDE 사용**: PyCharm, VSCode 등에서 터미널 사용하면 Python 경로 자동 인식