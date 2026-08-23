import streamlit as st
import json
import os
import uuid

# 1. Page Configuration
st.set_page_config(
    page_title="투자 북마크 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Custom CSS for visually appealing interface
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1e293b !important;
        border-right: 1px solid #334155;
    }
    
    /* Input fields styling */
    .stTextInput input {
        background-color: #334155 !important;
        color: #f8fafc !important;
        border: 1px solid #475569 !important;
        border-radius: 6px !important;
    }
    
    /* Card Container */
    div[data-testid="stVerticalBlock"] > div:has(div.bookmark-card) {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    div[data-testid="stVerticalBlock"] > div:has(div.bookmark-card):hover {
        transform: translateY(-4px);
        border-color: #10b981; /* Emerald green highlight */
        box-shadow: 0 20px 25px -5px rgba(16, 185, 129, 0.1);
    }
    
    /* Bookmark Name link style */
    .bookmark-title {
        font-size: 1.25rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 12px;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .bookmark-link {
        color: #f8fafc;
        text-decoration: none;
        transition: color 0.2s;
        display: block;
        width: 100%;
        text-align: center;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    
    .bookmark-link:hover {
        color: #10b981;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #f8fafc !important;
        font-weight: 800 !important;
    }
    
    /* Customize Streamlit Buttons in toolbar */
    div.row-widget.stButton > button {
        background-color: #334155;
        color: #e2e8f0;
        border: 1px solid #475569;
        border-radius: 6px;
        font-size: 0.85rem;
        padding: 0.25rem 0.5rem;
        transition: all 0.2s;
        width: 100%;
    }
    
    div.row-widget.stButton > button:hover {
        background-color: #475569;
        color: #ffffff;
        border-color: #64748b;
    }
    
    /* Confirmation Dialog styling */
    .confirm-box {
        background-color: #7f1d1d;
        border: 1px solid #b91c1c;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 3. Data Storage Helper Functions
DATA_FILE = "bookmarks.json"

def load_bookmarks():
    """Load bookmarks from file or fallback to session_state / defaults"""
    if 'bookmarks' not in st.session_state:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    st.session_state.bookmarks = json.load(f)
            except Exception as e:
                st.error(f"북마크 로드 중 오류 발생: {e}")
                st.session_state.bookmarks = []
        else:
            # Fallback to empty list if no file exists
            st.session_state.bookmarks = []
    return st.session_state.bookmarks

def save_bookmarks():
    """Save bookmarks from session_state to local file"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state.bookmarks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"북마크 저장 중 오류 발생: {e}")

# Load initial bookmarks
load_bookmarks()

# Initialize session states for page routing/controls
if 'edit_id' not in st.session_state:
    st.session_state.edit_id = None
if 'delete_id' not in st.session_state:
    st.session_state.delete_id = None

# Helper to normalize URL
def clean_url(url):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

# 4. Sidebar Content (Form for Create/Edit, and Import/Export)
with st.sidebar:
    st.title("⚙️ 관리 패널")
    
    # A. Add / Edit Bookmark Section
    if st.session_state.edit_id is not None:
        st.subheader("✏️ 북마크 수정")
        # Find existing item
        edit_item = next((item for item in st.session_state.bookmarks if item['id'] == st.session_state.edit_id), None)
        if edit_item:
            edit_name = st.text_input("Name (이름)", value=edit_item['name'], key="edit_name")
            edit_url = st.text_input("URL (주소)", value=edit_item['url'], key="edit_url")
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("수정 완료", type="primary", use_container_width=True):
                    if edit_name.strip() == "" or edit_url.strip() == "":
                        st.error("이름과 URL을 모두 입력해 주세요.")
                    else:
                        edit_item['name'] = edit_name.strip()
                        edit_item['url'] = clean_url(edit_url)
                        save_bookmarks()
                        st.session_state.edit_id = None
                        st.success("수정되었습니다!")
                        st.rerun()
            with col_cancel:
                if st.button("취소", use_container_width=True):
                    st.session_state.edit_id = None
                    st.rerun()
        else:
            st.session_state.edit_id = None
            st.rerun()
    else:
        st.subheader("➕ 새 북마크 추가")
        new_name = st.text_input("Name (이름)", placeholder="예: 네이버 증권", key="new_name")
        new_url = st.text_input("URL (주소)", placeholder="예: finance.naver.com", key="new_url")
        
        if st.button("생성", type="primary", use_container_width=True):
            if new_name.strip() == "" or new_url.strip() == "":
                st.error("이름과 URL을 모두 입력해 주세요.")
            else:
                new_item = {
                    "id": str(uuid.uuid4()),
                    "name": new_name.strip(),
                    "url": clean_url(new_url)
                }
                st.session_state.bookmarks.append(new_item)
                save_bookmarks()
                st.success(f"'{new_name}' 추가 완료!")
                st.rerun()

    st.markdown("---")
    
    # B. Backup & Restore Section (Import/Export JSON)
    st.subheader("💾 데이터 백업 및 복원")
    st.caption("Streamlit Cloud 서버가 재부팅될 때를 대비해 북마크 데이터를 로컬에 백업해 두세요.")
    
    # Export
    bookmarks_json_str = json.dumps(st.session_state.bookmarks, ensure_ascii=False, indent=2)
    st.download_button(
        label="📥 북마크 내보내기 (JSON)",
        data=bookmarks_json_str,
        file_name="bookmarks_backup.json",
        mime="application/json",
        use_container_width=True
    )
    
    # Import
    uploaded_file = st.file_uploader("📤 백업 파일 가져오기 (JSON)", type=["json"])
    if uploaded_file is not None:
        try:
            imported_data = json.load(uploaded_file)
            # Basic validation
            if isinstance(imported_data, list) and all('name' in item and 'url' in item for item in imported_data):
                # Ensure all imported items have a unique ID
                for item in imported_data:
                    if 'id' not in item:
                        item['id'] = str(uuid.uuid4())
                st.session_state.bookmarks = imported_data
                save_bookmarks()
                st.success("북마크 복원 성공!")
                st.rerun()
            else:
                st.error("올바른 백업 파일 형식이 아닙니다.")
        except Exception as e:
            st.error(f"파일을 읽는 도중 오류가 발생했습니다: {e}")

# 5. Main Dashboard Area
st.title("📈 투자 정보 북마크 대시보드")
st.markdown("자주 방문하는 투자 관련 웹사이트를 모아놓은 개인 대시보드입니다. 패널을 클릭하면 새 탭으로 즉시 이동합니다.")

# A. Search / Filter bar
search_query = st.text_input("🔍 북마크 검색", placeholder="이름으로 검색...")

# Filter bookmarks based on search query
filtered_bookmarks = st.session_state.bookmarks
if search_query.strip() != "":
    filtered_bookmarks = [
        item for item in st.session_state.bookmarks
        if search_query.lower() in item['name'].lower()
    ]

# B. Render Grid of Bookmarks
if len(filtered_bookmarks) == 0:
    st.info("등록된 북마크가 없습니다. 왼쪽 관리 패널에서 북마크를 생성하거나 백업 파일을 불러오세요.")
else:
    # Grid config: 4 cards per row
    cols_per_row = 4
    
    # Iterate through bookmarks in chunks of cols_per_row
    for r in range(0, len(filtered_bookmarks), cols_per_row):
        row_items = filtered_bookmarks[r:r+cols_per_row]
        cols = st.columns(cols_per_row)
        
        for idx, item in enumerate(row_items):
            # Calculate absolute index in the main list
            abs_idx = st.session_state.bookmarks.index(item)
            
            with cols[idx]:
                # Wrap inside a div with bookmark-card class for CSS styling
                st.markdown(f'<div class="bookmark-card">', unsafe_allow_html=True)
                
                # Render the clickable name card opening in a new tab
                st.markdown(
                    f'<div class="bookmark-title"><a class="bookmark-link" href="{item["url"]}" target="_blank" title="{item["name"]}">{item["name"]}</a></div>',
                    unsafe_allow_html=True
                )
                
                # Check if this card is currently in delete-confirmation mode
                if st.session_state.delete_id == item['id']:
                    st.markdown('<div class="confirm-box">정말 삭제할까요?</div>', unsafe_allow_html=True)
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("예", key=f"yes_{item['id']}", use_container_width=True):
                            # Remove bookmark
                            st.session_state.bookmarks.remove(item)
                            save_bookmarks()
                            st.session_state.delete_id = None
                            st.rerun()
                    with col_no:
                        if st.button("아니오", key=f"no_{item['id']}", use_container_width=True):
                            st.session_state.delete_id = None
                            st.rerun()
                else:
                    # Render Action Toolbar: ◀️, ✏️, 🗑️, ▶️
                    tool_cols = st.columns([1, 1, 1, 1])
                    
                    # ◀️ Move Left button
                    with tool_cols[0]:
                        if abs_idx > 0:
                            if st.button("◀️", key=f"move_left_{item['id']}", help="왼쪽으로 이동"):
                                # Swap with previous element
                                st.session_state.bookmarks[abs_idx], st.session_state.bookmarks[abs_idx - 1] = \
                                    st.session_state.bookmarks[abs_idx - 1], st.session_state.bookmarks[abs_idx]
                                save_bookmarks()
                                st.rerun()
                        else:
                            # Disabled look/empty space if first element
                            st.button("🚫", key=f"move_left_dis_{item['id']}", disabled=True)
                            
                    # ✏️ Edit button
                    with tool_cols[1]:
                        if st.button("✏️", key=f"edit_btn_{item['id']}", help="수정"):
                            st.session_state.edit_id = item['id']
                            st.rerun()
                            
                    # 🗑️ Delete button
                    with tool_cols[2]:
                        if st.button("🗑️", key=f"del_btn_{item['id']}", help="삭제"):
                            st.session_state.delete_id = item['id']
                            st.rerun()
                            
                    # ▶️ Move Right button
                    with tool_cols[3]:
                        if abs_idx < len(st.session_state.bookmarks) - 1:
                            if st.button("▶️", key=f"move_right_{item['id']}", help="오른쪽으로 이동"):
                                # Swap with next element
                                st.session_state.bookmarks[abs_idx], st.session_state.bookmarks[abs_idx + 1] = \
                                    st.session_state.bookmarks[abs_idx + 1], st.session_state.bookmarks[abs_idx]
                                save_bookmarks()
                                st.rerun()
                        else:
                            # Disabled look/empty space if last element
                            st.button("🚫", key=f"move_right_dis_{item['id']}", disabled=True)
                            
                st.markdown('</div>', unsafe_allow_html=True)

# 6. Page Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748b; font-size: 0.85rem;'>"
    "투자 북마크 대시보드 | GitHub 업로드 및 Streamlit Cloud 배포용"
    "</div>",
    unsafe_allow_html=True
)
