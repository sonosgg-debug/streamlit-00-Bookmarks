import urllib.request
import os

# 1. Fetch SortableJS minified code from the web
url = "https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"
print("Downloading SortableJS minified library...")
try:
    with urllib.request.urlopen(url) as response:
        sortable_js = response.read().decode('utf-8')
    print("SortableJS downloaded successfully!")
except Exception as e:
    print(f"Error downloading SortableJS: {e}")
    # Fallback to local system cache path if download fails
    cache_path = r"C:\Users\user\.gemini\antigravity\brain\2370a50e-4344-426e-b0a2-ee85f5e7fcbe\.system_generated\steps\190\content.md"
    if os.path.exists(cache_path):
        print("Reading SortableJS from local system cache...")
        with open(cache_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Find start of JS code
        js_lines = [l for l in lines if "Sortable 1.15.0" in l or "!function" in l]
        sortable_js = "".join(js_lines)
    else:
        raise Exception("Could not retrieve SortableJS source code.")

# 2. HTML Template (Using normal string replacement to avoid JS bracket escape issues)
html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Drag & Drop Bookmark Grid</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: transparent;
            color: #f8fafc;
            overflow: hidden; /* Scroll is handled by the parent page */
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            padding: 5px;
        }

        /* Responsive grid mapping for mobile and tablets */
        @media (max-width: 1200px) {
            .grid-container {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        @media (max-width: 768px) {
            .grid-container {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        @media (max-width: 480px) {
            .grid-container {
                grid-template-columns: 1fr;
            }
        }

        .bookmark-card {
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
            transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
            text-align: center;
            position: relative;
            box-sizing: border-box;
            user-select: none;
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
        }

        .drag-handle {
            touch-action: none;
            user-select: none;
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
        }

        .bookmark-card:hover {
            transform: translateY(-4px);
            border-color: #10b981; /* Emerald green highlight */
            box-shadow: 0 20px 25px -5px rgba(16, 185, 129, 0.1);
        }

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
            padding: 8px;
            text-align: center;
            text-decoration: none;
            flex: 1;
            font-size: 0.9rem;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-sizing: border-box;
        }

        .toolbar-btn:hover {
            background-color: #475569;
            color: #ffffff;
            border-color: #64748b;
        }

        /* Dragging ghost element effect */
        .sortable-ghost {
            opacity: 0.3;
            border: 2px dashed #10b981;
            background-color: #0f172a !important;
            transform: scale(0.95);
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
            text-align: center;
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
            border: none;
            font-weight: bold;
            transition: all 0.2s;
            cursor: pointer;
            box-sizing: border-box;
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
</head>
<body>
    <div id="grid" class="grid-container">
        <!-- Rendered dynamically -->
    </div>

    <!-- Embedded SortableJS Library (Prevents CDN block issues in Google Chrome) -->
    <script>
        {sortable_js}
    </script>

    <script>
        // 1. Raw Message communication helper for Streamlit
        function sendMessageToStreamlitClient(type, data) {
            const message = {
                ...data,
                isStreamlitMessage: true,
                type: type,
            };
            window.parent.postMessage(message, "*");
        }

        // Action trigger helper
        function onAction(actionName, itemId) {
            sendMessageToStreamlitClient("streamlit:setComponentValue", {
                value: { 
                    action: actionName, 
                    id: itemId, 
                    event_id: Date.now().toString() + "_" + Math.random().toString(36).substr(2, 9) 
                }
            });
        }

        // Set frame height helper
        function sendHeight() {
            sendMessageToStreamlitClient("streamlit:setFrameHeight", {
                height: document.body.scrollHeight
            });
        }

        // 2. Render function
        function renderGrid(bookmarks, deleteId) {
            const grid = document.getElementById("grid");
            grid.innerHTML = ""; // Clear existing grid

            if (!bookmarks || bookmarks.length === 0) {
                grid.innerHTML = '<div style="color: #64748b; text-align: center; grid-column: span 4; padding: 40px; font-size: 1.1rem;">등록된 북마크가 없습니다.</div>';
                sendHeight();
                return;
            }

            bookmarks.forEach((item, index) => {
                const card = document.createElement("div");
                card.className = "bookmark-card";
                card.setAttribute("data-id", item.id);

                if (deleteId === item.id) {
                    card.className += " delete-confirm-card";
                    card.innerHTML = `
                        <div class="confirm-message">정말 삭제할까요?</div>
                        <div class="confirm-actions">
                            <button class="confirm-btn yes-btn" onclick="onAction('confirm_delete', '${item.id}')">예</button>
                            <button class="confirm-btn no-btn" onclick="onAction('cancel_delete', '${item.id}')">아니오</button>
                        </div>
                    `;
                } else {
                    // Check boundary positions to disable buttons
                    const leftDisabled = (index === 0) ? 'disabled' : '';
                    const rightDisabled = (index === bookmarks.length - 1) ? 'disabled' : '';
                    
                    const leftOnClick = (index === 0) ? 'onclick="return false;"' : `onclick="onAction('move_left', '${item.id}')"`;
                    const rightOnClick = (index === bookmarks.length - 1) ? 'onclick="return false;"' : `onclick="onAction('move_right', '${item.id}')"`;

                    card.innerHTML = `
                        <div class="bookmark-title">
                            <a class="bookmark-link" href="${item.url}" target="_blank" title="${item.name}">${item.name}</a>
                        </div>
                        <div class="bookmark-toolbar">
                            <div class="drag-handle toolbar-btn" style="cursor: move;" title="드래그하여 순서 변경">☰</div>
                            <button class="toolbar-btn ${leftDisabled}" ${leftOnClick} title="왼쪽으로 이동">◀️</button>
                            <button class="toolbar-btn" onclick="onAction('edit', '${item.id}')" title="수정">✏️</button>
                            <button class="toolbar-btn" onclick="onAction('delete', '${item.id}')" title="삭제">🗑️</button>
                            <button class="toolbar-btn ${rightDisabled}" ${rightOnClick} title="오른쪽으로 이동">▶️</button>
                        </div>
                    `;
                }
                grid.appendChild(card);
            });

            // 3. Initialize Drag & Drop
            if (typeof Sortable !== 'undefined') {
                console.log("SortableJS loaded successfully. Initializing...");
                const sortable = new Sortable(grid, {
                    handle: '.drag-handle', // Restrict dragging to the drag handle
                    animation: 250,
                    ghostClass: 'sortable-ghost',
                    // Use native HTML5 Drag and Drop for stable coordinates inside sandboxed iframes
                    forceFallback: false,
                    onEnd: function (evt) {
                        triggerReorder();
                    }
                });
            } else {
                console.warn("SortableJS not loaded. Falling back to native HTML5 Drag & Drop...");
                initializeNativeDragAndDrop(grid);
            }

            // Adjust frame height automatically
            setTimeout(sendHeight, 50);
        }

        // Helper to trigger reorder event back to Streamlit
        function triggerReorder() {
            const grid = document.getElementById("grid");
            const newOrder = [];
            const cards = grid.querySelectorAll(".bookmark-card");
            cards.forEach(card => {
                const id = card.getAttribute("data-id");
                if (id) newOrder.push(id);
            });
            sendMessageToStreamlitClient("streamlit:setComponentValue", {
                value: { 
                    action: "reorder", 
                    order: newOrder,
                    event_id: Date.now().toString() + "_" + Math.random().toString(36).substr(2, 9)
                }
            });
        }

        // Native HTML5 Drag and Drop fallback implementation
        let dragSrcEl = null;

        function initializeNativeDragAndDrop(grid) {
            const cards = grid.querySelectorAll(".bookmark-card");
            cards.forEach(card => {
                card.setAttribute("draggable", "true");
                card.addEventListener("dragstart", handleDragStart);
                card.addEventListener("dragover", handleDragOver);
                card.addEventListener("drop", handleDrop);
                card.addEventListener("dragend", handleDragEnd);
            });
        }

        function handleDragStart(e) {
            this.style.opacity = '0.4';
            dragSrcEl = this;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', this.getAttribute('data-id'));
        }

        function handleDragOver(e) {
            if (e.preventDefault) {
                e.preventDefault();
            }
            e.dataTransfer.dropEffect = 'move';
            return false;
        }

        function handleDrop(e) {
            if (e.stopPropagation) {
                e.stopPropagation();
            }
            if (dragSrcEl !== this) {
                const draggedId = dragSrcEl.getAttribute('data-id');
                const targetId = this.getAttribute('data-id');
                
                const grid = document.getElementById("grid");
                const cards = Array.from(grid.querySelectorAll(".bookmark-card"));
                const draggedIdx = cards.findIndex(c => c.getAttribute('data-id') === draggedId);
                const targetIdx = cards.findIndex(c => c.getAttribute('data-id') === targetId);
                
                if (draggedIdx !== -1 && targetIdx !== -1) {
                    const [removed] = cards.splice(draggedIdx, 1);
                    cards.splice(targetIdx, 0, removed);
                    
                    const newOrder = cards.map(c => c.getAttribute('data-id'));
                    sendMessageToStreamlitClient("streamlit:setComponentValue", {
                        value: { 
                            action: "reorder", 
                            order: newOrder,
                            event_id: Date.now().toString() + "_" + Math.random().toString(36).substr(2, 9)
                        }
                    });
                }
            }
            return false;
        }

        function handleDragEnd(e) {
            this.style.opacity = '1';
            const grid = document.getElementById("grid");
            const cards = grid.querySelectorAll(".bookmark-card");
            cards.forEach(card => card.style.opacity = '1');
        }

        // 4. Connect and listen to Streamlit parent rendering events
        window.addEventListener("message", function(event) {
            if (event.data.type === "streamlit:render") {
                const args = event.data.args;
                const bookmarks = args.bookmarks;
                const deleteId = args.delete_id;
                renderGrid(bookmarks, deleteId);
            }
        });

        // 5. Send ready signal to Streamlit parent (Start Handshake)
        sendMessageToStreamlitClient("streamlit:componentReady", { apiVersion: 1 });
    </script>
</body>
</html>
"""

# Inject SortableJS code
html_content = html_template.replace("{sortable_js}", sortable_js)

# Write to file
target_path = "dnd_component/index.html"
with open(target_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print("index.html compiled successfully with embedded SortableJS!")
