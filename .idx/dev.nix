# To learn more about how to use Nix to configure your environment
# see: https://firebase.google.com/docs/studio/customize-workspace
{ pkgs, ... }: {
  # 어떤 Nix 채널을 사용할지 결정합니다. "stable-24.05"는 안정적인 최신 버전입니다.
  channel = "stable-24.05";

  # https://search.nixos.org/packages 에서 필요한 패키지를 찾아 추가할 수 있습니다.
  # 우리 프로젝트의 개발 환경에 필요한 시스템 수준의 프로그램을 여기에 명시합니다.
  packages = [
    pkgs.python311                   # 파이썬 3.11 버전
    pkgs.python311Packages.pip       # 파이썬 패키지 설치 도구 (pip)
    pkgs.nodejs_20                   # Playwright 가 내부적으로 사용할 수 있는 NodeJS
  ];

  # 작업 공간 내에서 사용할 환경 변수를 설정합니다.
  env = {};

  idx = {
    # https://open-vsx.org/ 에서 원하는 VSCode 확장 프로그램을 찾아 추가할 수 있습니다.
    extensions = [
      # 예: "vscodevim.vim"
    ];

    # IDX의 미리보기 패널 기능을 활성화합니다.
    previews = {
      enable = true;
      previews = {
        # 'web' 이라는 이름의 미리보기를 설정합니다.
        web = {
          # 'web_app.py'의 FastAPI 앱을 실행하는 명령입니다.
          # 0.0.0.0 호스트를 사용해야 외부에서 접속 가능하며, $PORT는 IDX가 지정해주는 포트 번호입니다.
          command = ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "$PORT"];
          manager = "web"; # 웹 기반 미리보기임을 명시합니다.
        };
      };
    };

    # 작업 공간의 생명주기(Life-cycle)에 맞춰 실행될 명령을 설정합니다.
    workspace = {
      # 작업 공간이 맨 처음 생성될 때 딱 한 번 실행됩니다.
      onCreate = {
        # requirements.txt 파일에 있는 모든 파이썬 라이브러리를 설치합니다.
        requirements-install = "pip install -r requirements.txt";
        
        # Playwright가 크롤링에 필요한 브라우저들을 설치합니다. --with-deps 옵션은 관련 의존성도 함께 설치합니다.
        playwright-install = "playwright install --with-deps";

        # data 폴더를 만들고, 예제 설정 파일을 실제 설정 파일로 복사합니다.
        config-setup = "mkdir -p data && cp config.json.example data/config.json";
      };
      
      # 작업 공간이 시작될 때마다 실행됩니다. (현재는 설정할 내용이 없습니다.)
      onStart = {
        # 예: watch-backend = "npm run watch-backend";
      };
    };
  };
}
