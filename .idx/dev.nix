# To learn more about how to use Nix to configure your environment
# see: https://firebase.google.com/docs/studio/customize-workspace
{ pkgs, ... }:
let
  # 'python-with-packages' 라는 이름의 커스텀 파이썬 환경을 정의합니다.
  # 이 환경은 python3.11을 기반으로, 우리 프로젝트에 필요한 모든 라이브러리를 포함합니다.
  python-with-packages = pkgs.python311.withPackages (ps: with ps; [
    # requirements.txt 에 있는 모든 라이브러리를 여기에 명시합니다.
    # Nix가 이들을 모두 포함하는 파이썬 환경을 만들어줍니다.
    fastapi
    uvicorn
    requests
    beautifulsoup4
    selenium
    playwright
    pandas
    numpy
    python-dateutil
    python-multipart
    aiofiles
    loguru
    pydantic
    typing-extensions
    jinja2
  ]);
in
{
  channel = "stable-24.05";

  # Nix가 관리할 시스템 패키지 목록입니다.
  packages = [
    # 위에서 정의한, 모든 라이브러리가 포함된 커스텀 파이썬 환경을 설치합니다.
    python-with-packages

    # Playwright가 브라우저 조작을 위해 내부적으로 사용하는 프로그램들입니다.
    pkgs.nodejs_20
    pkgs.playwright-driver.browsers
  ];

  idx = {
    previews = {
      enable = true;
      previews = {
        web = {
          # 이제 uvicorn은 모든 라이브러리의 위치를 정확히 알고 있습니다.
          command = [ "uvicorn" "web_app:app" "--host" "0.0.0.0" "--port" "$PORT" ];
          manager = "web";
        };
      };
    };

    workspace = {
      # 작업 공간 생성 시 실행될 명령입니다.
      onCreate = {
        # 이제 Nix가 모든 파이썬 라이브러리를 관리하므로, pip install은 더 이상 필요 없습니다.
        # 설정 파일 복사 작업만 남겨둡니다.
        config-setup = "mkdir -p data && cp config.json.example data/config.json";
      };
      
      onStart = {};
    };
  };
}
