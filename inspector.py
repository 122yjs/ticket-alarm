# playwright_stealth 모듈 검사 도구
from playwright_stealth import stealth
import inspect
import sys

def inspect_module(module_name):
    """모듈의 함수와 클래스를 검사하고 출력합니다."""
    print(f"\n{module_name} 모듈 검사 결과:")
    print("=" * 50)
    
    # 모듈 내 모든 속성 가져오기
    attributes = dir(module_name)
    
    # 함수와 클래스 분류
    functions = []
    classes = []
    
    for attr_name in attributes:
        # 내장 속성은 건너뜁니다
        if attr_name.startswith('__') and attr_name.endswith('__'):
            continue
            
        attr = getattr(module_name, attr_name)
        
        if inspect.isfunction(attr):
            functions.append((attr_name, attr))
        elif inspect.isclass(attr):
            classes.append((attr_name, attr))
    
    # 함수 정보 출력
    if functions:
        print("\n함수:")
        print("-" * 20)
        for name, func in functions:
            try:
                signature = inspect.signature(func)
                print(f"{name}{signature}")
                doc = inspect.getdoc(func)
                if doc:
                    print(f"  설명: {doc}")
            except:
                print(f"{name}()")
    else:
        print("\n함수가 없습니다.")
    
    # 클래스 정보 출력
    if classes:
        print("\n클래스:")
        print("-" * 20)
        for name, cls in classes:
            print(f"{name}")
            try:
                doc = inspect.getdoc(cls)
                if doc:
                    print(f"  설명: {doc}")
            except:
                pass
    else:
        print("\n클래스가 없습니다.")

if __name__ == "__main__":
    print("Playwright Stealth 모듈 검사 도구")
    print("=" * 50)
    
    # stealth 모듈 검사
    print("\nstealth 모듈의 모든 속성:")
    print(dir(stealth))
    
    # stealth 모듈 상세 검사
    inspect_module(stealth)
    
    # Stealth 클래스 검사
    if hasattr(stealth, 'Stealth'):
        print("\nStealth 클래스 검사:")
        print("-" * 30)
        stealth_class = stealth.Stealth
        print(f"클래스 문서: {inspect.getdoc(stealth_class)}")
        print("\n메소드:")
        for method_name in dir(stealth_class):
            if not method_name.startswith('__'):
                try:
                    method = getattr(stealth_class, method_name)
                    if inspect.isfunction(method) or inspect.ismethod(method):
                        print(f"  {method_name}")
                except:
                    pass
    
    # 결과를 파일에 저장
    with open("stealth_module_inspection.txt", "w", encoding="utf-8") as f:
        original_stdout = sys.stdout
        sys.stdout = f
        
        print("Playwright Stealth 모듈 검사 결과")
        print("=" * 50)
        print("\nstealth 모듈의 모든 속성:")
        print(dir(stealth))
        inspect_module(stealth)
        
        # Stealth 클래스 검사
        if hasattr(stealth, 'Stealth'):
            print("\nStealth 클래스 검사:")
            print("-" * 30)
            stealth_class = stealth.Stealth
            print(f"클래스 문서: {inspect.getdoc(stealth_class)}")
            print("\n메소드:")
            for method_name in dir(stealth_class):
                if not method_name.startswith('__'):
                    try:
                        method = getattr(stealth_class, method_name)
                        if inspect.isfunction(method) or inspect.ismethod(method):
                            print(f"  {method_name}")
                    except:
                        pass
        
        sys.stdout = original_stdout
    
    print("\n검사 결과가 stealth_module_inspection.txt 파일에 저장되었습니다.")