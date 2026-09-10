import os
import sys
from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("STREAMLIT_APP_URL", "https://app-00-bookmarks.streamlit.app/")

def wake_streamlit():
    print(f"[1/4] 브라우저 세션 시작: 대상 URL -> {APP_URL}")
    
    with sync_playwright() as p:
        # 헤드리스 크롬 실행 (CI 환경 안정성을 위해 sandbox 및 shm 플래그 추가)
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("[2/4] 페이지 로딩 시도...")
        try:
            # 네트워크가 안정화되거나 DOM이 준비될 때까지 대기
            page.goto(APP_URL, wait_until="domcontentloaded", timeout=60000)
            # React / Streamlit 프레임워크 렌더링을 위한 5초 대기
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"경고: 초기 접속 지연 또는 타임아웃 ({e})")

        print("[3/4] 슬립 상태 및 깨우기 버튼 감지...")
        
        # Streamlit 슬립 화면의 버튼 텍스트 패턴
        wake_button_candidates = [
            page.get_by_role("button", name="Yes, get this app back up!"),
            page.locator("button:has-text('Yes, get this app back up!')"),
            page.locator("button:has-text('Wake up')"),
            page.locator("button:has-text('Wake app')")
        ]

        clicked = False
        # 1차: 즉시 감지 (is_visible()은 timeout 인자를 받지 않음)
        for btn in wake_button_candidates:
            try:
                if btn.first.is_visible():
                    print(">> 수면 상태 감지됨! 깨우기 버튼 클릭 시도...")
                    btn.first.click()
                    clicked = True
                    print(">> 깨우기 버튼 클릭 완료. 컨테이너 재기동 10초 대기 중...")
                    page.wait_for_timeout(10000)
                    break
            except Exception:
                continue

        # 2차: 렌더링 지연을 고려해 대표 버튼 3초 추가 대기
        if not clicked:
            try:
                primary_btn = page.get_by_role("button", name="Yes, get this app back up!")
                primary_btn.wait_for(state="visible", timeout=3000)
                print(">> 수면 상태 감지됨! 'Yes, get this app back up!' 버튼 클릭 시도...")
                primary_btn.click()
                clicked = True
                print(">> 깨우기 버튼 클릭 완료. 컨테이너 재기동 10초 대기 중...")
                page.wait_for_timeout(10000)
            except Exception:
                pass

        if not clicked:
            print(">> 앱이 이미 정상 동작 중이거나 깨우기 버튼이 없습니다.")

        print("[4/4] 웹소켓 세션 유지를 위해 10초간 페이지 유지 중...")
        page.wait_for_timeout(10000)

        browser.close()
        print("정상 완료: 슬립 방지 세션이 성공적으로 갱신되었습니다.")

if __name__ == "__main__":
    wake_streamlit()