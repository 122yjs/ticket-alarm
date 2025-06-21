"""
playwright_stealth.stealth 모듈 검사 도구
"""
import inspect
import sys

def main():
    try:
        # 결과를 파일에도 저장
        with open("stealth_module.txt", "w", encoding="utf-8") as f:
            # stdout을 파일로 리디렉션
            original_stdout = sys.stdout
            sys.stdout = f
            
            print("playwright_stealth.stealth 모듈 검사")
            print("=" * 50)
            
            # playwright_stealth.stealth 모듈 가져오기
            try:
                from playwright_stealth import stealth
                print(f"\n모듈 파일 경로: {stealth.__file__}")
                
                # 모듈 내용 출력
                try:
                    with open(stealth.__file__, "r", encoding="utf-8") as stealth_file:
                        print("\n모듈 내용:")
                        print("=" * 30)
                        print(stealth_file.read())
                except Exception as e:
                    print(f"\n모듈 파일 읽기 실패: {e}")
                
                # 모듈 속성 검사
                print("\n모듈 속성:")
                print("=" * 30)
                for attr_name in dir(stealth):
                    if not attr_name.startswith('__'):
                        try:
                            attr = getattr(stealth, attr_name)
                            attr_type = type(attr).__name__
                            print(f"\n{attr_name} ({attr_type}):")
                            
                            # 함수인 경우 소스 코드 출력
                            if inspect.isfunction(attr):
                                try:
                                    print(f"  서명: {inspect.signature(attr)}")
                                    print(f"  문서: {inspect.getdoc(attr)}")
                                    source_lines, start_line = inspect.getsourcelines(attr)
                                    print(f"  소스 코드 (시작 줄: {start_line}):")
                                    print("  " + "  ".join(source_lines))
                                except Exception as func_error:
                                    print(f"  함수 검사 실패: {func_error}")
                            
                            # 클래스인 경우 메소드 출력
                            elif inspect.isclass(attr):
                                try:
                                    print(f"  문서: {inspect.getdoc(attr)}")
                                    print("  메소드:")
                                    for method_name in dir(attr):
                                        if not method_name.startswith('__'):
                                            try:
                                                method = getattr(attr, method_name)
                                                if inspect.isfunction(method) or inspect.ismethod(method):
                                                    print(f"    {method_name}")
                                            except:
                                                pass
                                except Exception as class_error:
                                    print(f"  클래스 검사 실패: {class_error}")
                            
                            # 모듈인 경우 속성 출력
                            elif inspect.ismodule(attr):
                                try:
                                    print(f"  파일 경로: {attr.__file__}")
                                    print("  속성:")
                                    for subattr_name in dir(attr):
                                        if not subattr_name.startswith('__'):
                                            try:
                                                subattr = getattr(attr, subattr_name)
                                                subattr_type = type(subattr).__name__
                                                print(f"    {subattr_name} ({subattr_type})")
                                            except:
                                                print(f"    {subattr_name} (접근 불가)")
                                except Exception as module_error:
                                    print(f"  모듈 검사 실패: {module_error}")
                        except Exception as attr_error:
                            print(f"\n{attr_name}: 검사 실패 - {attr_error}")
                
                # sync_api 모듈 특별 검사
                print("\n\nsync_api 모듈 특별 검사:")
                print("=" * 30)
                try:
                    sync_api = stealth.sync_api
                    print(f"모듈 파일 경로: {sync_api.__file__}")
                    print("\n속성:")
                    for name in dir(sync_api):
                        if not name.startswith('__'):
                            try:
                                attr = getattr(sync_api, name)
                                attr_type = type(attr).__name__
                                print(f"  {name} ({attr_type})")
                            except:
                                print(f"  {name} (접근 불가)")
                except Exception as sync_error:
                    print(f"sync_api 모듈 검사 실패: {sync_error}")
                
            except ImportError:
                print("playwright_stealth.stealth 모듈을 가져올 수 없습니다.")
            except Exception as e:
                print(f"오류 발생: {e}")
            
            # stdout 복원
            sys.stdout = original_stdout
        
        print("검사 완료! 결과가 stealth_module.txt 파일에 저장되었습니다.")
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()