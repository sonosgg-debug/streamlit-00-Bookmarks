import streamlit as st
import streamlit.components.v1 as components
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
    .bookmark-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        text-align: center;
        margin-bottom: 20px;
    }
    
    .bookmark-card:hover {
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
    
    /* Action toolbar */
    .bookmark-toolbar {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        margin-top: 15px;
    }
    
    .toolbar-btn {
        background-color: #334155;
        color: #e2e8f0;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 6px;
        text-align: center;
        text-decoration: none;
        flex: 1;
        font-size: 0.9rem;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .toolbar-btn:hover {
        background-color: #475569;
        color: #ffffff;
        border-color: #64748b;
    }
    
    .toolbar-btn.disabled {
        background-color: #1e293b;
        color: #475569;
        border-color: #334155;
        cursor: not-allowed;
        pointer-events: none;
    }
    
    /* Delete Confirmation Card */
    .delete-confirm-card {
        border-color: #b91c1c !important;
        background: linear-gradient(135deg, #7f1d1d, #450a0a) !important;
    }
    
    .confirm-message {
        font-weight: bold;
        color: #fca5a5;
        margin-bottom: 15px;
        font-size: 1.1rem;
    }
    
    .confirm-actions {
        display: flex;
        gap: 10px;
    }
    
    .confirm-btn {
        flex: 1;
        padding: 8px;
        border-radius: 6px;
        text-align: center;
        text-decoration: none;
        font-weight: bold;
        transition: all 0.2s;
    }
    
    .yes-btn {
        background-color: #b91c1c;
        color: white;
        border: 1px solid #ef4444;
    }
    
    .yes-btn:hover {
        background-color: #dc2626;
    }
    
    .no-btn {
        background-color: #475569;
        color: #e2e8f0;
        border: 1px solid #64748b;
    }
    
    .no-btn:hover {
        background-color: #64748b;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# 3. Data Storage Helper Functions
DATA_FILE = "bookmarks.json"

def load_bookmarks():
    """Load bookmarks from file or fallback to session_state / defaults"""
    if 'bookmarks' not in st.session_state:
        if os.path.exists(DATA_FILE):
            # Check if file is empty (0 bytes)
            if os.path.getsize(DATA_FILE) == 0:
                st.session_state.bookmarks = []
                save_bookmarks()  # Self-heal the empty file
            else:
                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        st.session_state.bookmarks = json.load(f)
                except Exception as e:
                    st.error(f"북마크 로드 중 오류 발생 (초기화 및 복구 진행): {e}")
                    st.session_state.bookmarks = []
                    save_bookmarks()  # Self-heal the corrupted file
        else:
            # Fallback to empty list if no file exists
            st.session_state.bookmarks = []
            save_bookmarks()
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
if 'last_processed_event_id' not in st.session_state:
    st.session_state.last_processed_event_id = None

# Declare Custom Drag-and-Drop Component
parent_dir = os.path.dirname(os.path.abspath(__file__))
dnd_grid_path = os.path.join(parent_dir, "dnd_component")
dnd_grid = components.declare_component("dnd_grid", path=dnd_grid_path)

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
st.markdown(
    "<div style='font-size: 0.9rem; color: #94a3b8; margin-bottom: 15px;'>"
    "인공지능(AI)의 도움으로 구축한 투자 종목 스크리닝 프로그램과 자주 방문하는 웹사이트를 모아놓은 개인용 대시보드입니다."
    "</div>",
    unsafe_allow_html=True
)

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
    # Render the custom Drag-and-Drop Grid Component
    event = dnd_grid(bookmarks=filtered_bookmarks, delete_id=st.session_state.delete_id, key="dnd_grid_component")
    
    # Process events returned by the component
    if event is not None:
        event_id = event.get("event_id")
        
        # Process only if this event has not been processed yet
        if event_id != st.session_state.last_processed_event_id:
            st.session_state.last_processed_event_id = event_id
            
            action = event.get("action")
            item_id = event.get("id")
            
            if action == "edit" and item_id:
                st.session_state.edit_id = item_id
                st.rerun()
                
            elif action == "delete" and item_id:
                st.session_state.delete_id = item_id
                st.rerun()
                
            elif action == "confirm_delete" and item_id:
                # Find item and delete it
                bookmarks = st.session_state.bookmarks
                item_to_del = next((x for x in bookmarks if x["id"] == item_id), None)
                if item_to_del:
                    bookmarks.remove(item_to_del)
                    save_bookmarks()
                st.session_state.delete_id = None
                st.rerun()
                
            elif action == "cancel_delete":
                st.session_state.delete_id = None
                st.rerun()
                
            elif action == "reorder":
                new_order = event.get("order", [])
                # Map items to the new order
                bookmarks_dict = {item["id"]: item for item in st.session_state.bookmarks}
                reordered_bookmarks = []
                
                # First, add the items in the new order
                for iid in new_order:
                    if iid in bookmarks_dict:
                        reordered_bookmarks.append(bookmarks_dict[iid])
                
                # If there are any items not in new_order (e.g. filtered out by search), append them at the end
                for item in st.session_state.bookmarks:
                    if item["id"] not in new_order:
                        reordered_bookmarks.append(item)
                        
                st.session_state.bookmarks = reordered_bookmarks
                save_bookmarks()
                st.rerun()

# 6. Page Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748b; font-size: 0.85rem;'>"
    "투자 북마크 대시보드 | GitHub 업로드 및 Streamlit Cloud 배포용"
    "</div>",
    unsafe_allow_html=True
)
