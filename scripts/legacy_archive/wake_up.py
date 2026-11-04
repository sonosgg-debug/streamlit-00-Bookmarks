import os
import sys
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKMARKS_FILE = os.path.join(BASE_DIR, "bookmarks.json")

# 본체(북마크 허브) 앱 기본 URL
DEFAULT_HUB_URL = os.environ.get("STREAMLIT_APP_URL", "https://app-00-bookmarks.streamlit.app/")


def load_streamlit_targets():
    """bookmarks.json에서 Streamlit 앱 URL 목록을 자동 추출하고 허브 앱을 포함합니다."""
    targets = []
    seen_urls = set()

    def normalize_url(url: str) -> str:
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        return url.rstrip("/")

    # 1. 북마크 허브 앱 자체 등록
    hub_url_norm = normalize_url(DEFAULT_HUB_URL)
    targets.append({
        "name": "00 Bookmarks (Hub)",
        "url": DEFAULT_HUB_URL
    })
    seen_urls.add(hub_url_norm)

    # 2. bookmarks.json 읽기
    if os.path.exists(BOOKMARKS_FILE):
        try:
            with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
                bookmarks = json.load(f)

            for item in bookmarks:
                url = item.get("url", "")
                name = item.get("name", "이름 없음")
                
                # Streamlit Cloud 도메인 포함 여부 확인
                if "streamlit.app" in url.lower():
                    norm_url = normalize_url(url)
                    if norm_url not in seen_urls:
                        targets.append({"name": name, "url": url.strip()})
                        seen_urls.add(norm_url)
        except Exception as e:
            print(f"[경고] bookmarks.json 파싱 중 오류 발생: {e}")
    else:
        print(f"[경고] {BOOKMARKS_FILE} 파일을 찾을 수 없습니다.")

    return targets


def wake_single_app(page, app_name: str, app_url: str) -> str:
    """단일 앱에 접속하여 슬립 상태를 확인하고 필요 시 깨우기를 수행합니다.
    반환값: 'already_awake' | 'woken_up' | 'error'
    """
    try:
        # DOM 로드 완료 대기 (최대 45초)
        page.goto(app_url, wait_until="domcontentloaded", timeout=45000)
        # 렌더링을 위한 4초 대기
        page.wait_for_timeout(4000)

        # Streamlit 슬립 버튼 후보군
        wake_button_candidates = [
            page.get_by_role("button", name="Yes, get this app back up!"),
            page.locator("button:has-text('Yes, get this app back up!')"),
            page.locator("button:has-text('Wake up')"),
            page.locator("button:has-text('Wake app')")
        ]

        clicked = False
        # 1차: 즉시 가시성 확인
        for btn in wake_button_candidates:
            try:
                if btn.first.is_visible():
                    print("   >> [수면 상태 감지] 깨우기 버튼 클릭 시도...")
                    btn.first.click()
                    clicked = True
                    print("   >> 깨우기 버튼 클릭 완료. 컨테이너 초기 기동 10초 대기...")
                    page.wait_for_timeout(10000)
                    return "woken_up"
            except Exception:
                continue

        # 2차: 렌더링 지연을 고려하여 대표 버튼 3초 대기
        if not clicked:
            try:
                primary_btn = page.get_by_role("button", name="Yes, get this app back up!")
                primary_btn.wait_for(state="visible", timeout=3000)
                print("   >> [수면 상태 감지] 'Yes, get this app back up!' 버튼 클릭 시도...")
                primary_btn.click()
                print("   >> 깨우기 버튼 클릭 완료. 컨테이너 초기 기동 10초 대기...")
                page.wait_for_timeout(10000)
                return "woken_up"
            except Exception:
                pass

        # 이미 정상 동작 중인 경우
        print("   >> [정상 동작 중] 웹소켓 세션 유지를 위해 3초 대기...")
        page.wait_for_timeout(3000)
        return "already_awake"

    except Exception as e:
        print(f"   >> [오류 발생] 접속 실패: {e}")
        return "error"


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[오류] Playwright 라이브러리가 설치되어 있지 않습니다.")
        print("  -> pip install playwright && playwright install chromium 명령으로 설치해 주세요.")
        sys.exit(1)

    targets = load_streamlit_targets()
    total_count = len(targets)
    print("=" * 60)
    print(f"  Streamlit 다중 앱 깨우기 세션 시작 (총 {total_count}개 대상)")
    print("=" * 60)

    summary = {
        "already_awake": [],
        "woken_up": [],
        "error": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        for idx, target in enumerate(targets, 1):
            name = target["name"]
            url = target["url"]
            print(f"\n[{idx}/{total_count}] {name} ({url})")

            page = context.new_page()
            try:
                status = wake_single_app(page, name, url)
                summary[status].append(f"{name} ({url})")
            except Exception as e:
                print(f"   >> [예외 처리] {name} 실행 중 오류: {e}")
                summary["error"].append(f"{name} ({url})")
            finally:
                try:
                    page.close()
                except Exception:
                    pass

        browser.close()

    print("\n" + "=" * 60)
    print("  Streamlit 깨우기 작업 완료 보고서")
    print(f"  - 총 대상 앱: {total_count}개")
    print(f"  - 정상 동작 중: {len(summary['already_awake'])}개")
    print(f"  - 깨우기 실행: {len(summary['woken_up'])}개")
    print(f"  - 오류/실패: {len(summary['error'])}개")
    print("=" * 60)

    if summary["woken_up"]:
        print("\n[깨우기 실행 목록]")
        for item in summary["woken_up"]:
            print(f" - {item}")

    if summary["error"]:
        print("\n[오류 발생 목록]")
        for item in summary["error"]:
            print(f" - {item}")


if __name__ == "__main__":
    main()
