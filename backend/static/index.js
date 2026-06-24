// API Endpoint Configurations
const API_BASE = "/api/v1";

// Application State
let notes = [];
let activeNote = null;
let chatSessionId = "session_" + Math.random().toString(36).substring(2, 11);
let saveDebounceTimer = null;
let graphData = { nodes: [], links: [] };

// DOM Elements
const notesList = document.getElementById("notes-list");
const newNoteBtn = document.getElementById("new-note-btn");
const uploadDocBtn = document.getElementById("upload-doc-btn");
const searchInput = document.getElementById("search-input");
const noteTitle = document.getElementById("note-title");
const noteBody = document.getElementById("note-body");
const charCount = document.getElementById("char-count");
const wordCount = document.getElementById("word-count");
const deleteNoteBtn = document.getElementById("delete-note-btn");
const saveStatus = document.getElementById("save-status");

const tabButtons = document.querySelectorAll(".tab-btn");
const viewPanes = document.querySelectorAll(".view-pane");

const chatBox = document.getElementById("chat-box");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const clearChatBtn = document.getElementById("clear-chat-btn");

const settingsBtn = document.getElementById("settings-btn");
const settingsModal = document.getElementById("settings-modal");
const closeSettingsModal = document.getElementById("close-settings-modal");
const saveSettingsBtn = document.getElementById("save-settings-btn");
const geminiApiKeyInput = document.getElementById("gemini-api-key");
const geminiModelInput = document.getElementById("gemini-model");

const uploadModal = document.getElementById("upload-modal");
const closeUploadModal = document.getElementById("close-upload-modal");
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const uploadStatus = document.getElementById("upload-status");

const graphCanvas = document.getElementById("graph-canvas");

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
    loadSettings();
    loadNotes();
    createChatSession();
    setupEventHandlers();
    initGraph();
});

// --- SETTINGS STORAGE ---
function loadSettings() {
    const apiKey = localStorage.getItem("gemini-api-key") || "";
    const model = localStorage.getItem("gemini-model") || "gemini-2.0-flash";
    
    if (geminiApiKeyInput) geminiApiKeyInput.value = apiKey;
    if (geminiModelInput) geminiModelInput.value = model;
}

function saveSettings() {
    localStorage.setItem("gemini-api-key", geminiApiKeyInput.value);
    localStorage.setItem("gemini-model", geminiModelInput.value);
    
    settingsModal.style.display = "none";
    showNotification("Settings saved successfully.");
}

// --- API ACTIONS ---
async function loadNotes() {
    try {
        const response = await fetch(`${API_BASE}/notes/`);
        if (!response.ok) throw new Error("Failed to load notes");
        notes = await response.ok ? await response.json() : [];
        renderNotesList();
    } catch (e) {
        showNotification("Error loading notes: " + e.message, "danger");
    }
}

async function createChatSession() {
    try {
        const response = await fetch(`${API_BASE}/chat/sessions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: chatSessionId })
        });
        if (response.ok) {
            const data = await response.json();
            chatSessionId = data.id;
        }
    } catch (e) {
        console.error("Failed to create chat session: ", e);
    }
}

// --- RENDER FUNCTIONS ---
function renderNotesList(filterText = "") {
    notesList.innerHTML = "";
    const filtered = notes.filter(n => 
        n.title.toLowerCase().includes(filterText.toLowerCase()) || 
        n.content.toLowerCase().includes(filterText.toLowerCase())
    );
    
    if (filtered.length === 0) {
        notesList.innerHTML = `<div style="color: var(--text-muted); text-align: center; margin-top: 40px; font-size: 13px;">No results found</div>`;
        return;
    }
    
    filtered.forEach(note => {
        const item = document.createElement("div");
        item.className = `note-item ${activeNote && activeNote.id === note.id ? "active" : ""}`;
        item.onclick = () => selectNote(note);
        
        const badgeClass = note.is_file ? "file" : "note";
        const badgeLabel = note.is_file ? (note.file_type || "file") : "note";
        
        item.innerHTML = `
            <div class="note-item-meta">
                <span class="note-item-title">${escapeHtml(note.title)}</span>
                <span class="note-item-sub">
                    <span class="note-type-badge ${badgeClass}">${badgeLabel}</span>
                    <span>${new Date(note.updated_at).toLocaleDateString()}</span>
                </span>
            </div>
            <button class="note-delete-btn" data-note-id="${note.id}" title="Delete ${escapeHtml(note.title)}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
            </button>
        `;
        
        // Wire up the delete button with stopPropagation so it doesn't trigger selectNote
        const deleteBtn = item.querySelector(".note-delete-btn");
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            handleDeleteNoteById(note.id, note.title);
        };
        
        notesList.appendChild(item);
    });
}

function selectNote(note) {
    activeNote = note;
    noteTitle.value = note.title;
    noteBody.value = note.content;
    
    // Disable editing for binary files (e.g. PDF) to avoid editing raw parsed text unless they want to
    if (note.is_file && note.file_type === "pdf") {
        noteBody.placeholder = "Viewing parsed PDF document. Edit disabled for safety.";
        noteBody.readOnly = true;
    } else {
        noteBody.placeholder = "Write something... Use [[Note Title]] to link notes.";
        noteBody.readOnly = false;
    }
    
    updateCounts();
    renderNotesList();
    
    // Set active tab to Editor
    switchTab("editor-pane");
}

function updateCounts() {
    const text = noteBody.value || "";
    charCount.textContent = `${text.length} characters`;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    wordCount.textContent = `${words} words`;
}

// --- CRUD HANDLERS ---
async function handleNewNote() {
    const title = prompt("Enter Note Title:");
    if (!title || !title.trim()) return;
    
    try {
        const apiKey = localStorage.getItem("gemini-api-key") || "";
        const headers = { "Content-Type": "application/json" };
        if (apiKey) headers["X-Gemini-API-Key"] = apiKey;

        const response = await fetch(`${API_BASE}/notes/`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify({ title: title.trim(), content: "" })
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || "Failed to create note");
        }
        
        const newNote = await response.json();
        notes.unshift(newNote);
        selectNote(newNote);
        renderNotesList();
        refreshGraphData();
    } catch (e) {
        showNotification(e.message, "danger");
    }
}

async function handleDeleteNote() {
    if (!activeNote) return;
    if (!confirm(`Are you sure you want to delete note "${activeNote.title}"?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/notes/${activeNote.id}`, {
            method: "DELETE"
        });
        if (!response.ok) throw new Error("Failed to delete note");
        
        notes = notes.filter(n => n.id !== activeNote.id);
        activeNote = null;
        noteTitle.value = "";
        noteBody.value = "";
        updateCounts();
        renderNotesList();
        refreshGraphData();
        showNotification("Note deleted.");
    } catch (e) {
        showNotification(e.message, "danger");
    }
}

async function handleDeleteNoteById(noteId, noteTitle) {
    if (!confirm(`Are you sure you want to delete "${noteTitle}"? This action cannot be undone.`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/notes/${noteId}`, {
            method: "DELETE"
        });
        if (!response.ok) throw new Error("Failed to delete");
        
        notes = notes.filter(n => n.id !== noteId);
        
        // If we just deleted the active note, clear the editor
        if (activeNote && activeNote.id === noteId) {
            activeNote = null;
            document.getElementById("note-title").value = "";
            document.getElementById("note-body").value = "";
            updateCounts();
        }
        
        renderNotesList();
        refreshGraphData();
        showNotification(`"${noteTitle}" deleted successfully.`);
    } catch (e) {
        showNotification("Failed to delete: " + e.message, "danger");
    }
}

function queueAutoSave() {
    if (!activeNote || (activeNote.is_file && activeNote.file_type === "pdf")) return;
    
    setSaveStatus("Saving...", "warning");
    clearTimeout(saveDebounceTimer);
    
    saveDebounceTimer = setTimeout(async () => {
        try {
            const apiKey = localStorage.getItem("gemini-api-key") || "";
            const headers = { "Content-Type": "application/json" };
            if (apiKey) headers["X-Gemini-API-Key"] = apiKey;

            const response = await fetch(`${API_BASE}/notes/${activeNote.id}`, {
                method: "PUT",
                headers: headers,
                body: JSON.stringify({
                    title: noteTitle.value,
                    content: noteBody.value
                })
            });
            if (!response.ok) throw new Error("Auto-save failed");
            
            const updated = await response.json();
            
            // Update in local notes array
            const idx = notes.findIndex(n => n.id === activeNote.id);
            if (idx !== -1) {
                notes[idx] = updated;
            }
            activeNote = updated;
            renderNotesList();
            refreshGraphData(); // Update connections dynamically
            setSaveStatus("Saved", "success");
        } catch (e) {
            setSaveStatus("Error", "danger");
            showNotification("Failed to auto-save note: " + e.message, "danger");
        }
    }, 800);
}

// --- FILE UPLOADS ---
async function uploadFile(file) {
    uploadStatus.style.display = "block";
    uploadStatus.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:8px;align-items:center;">
            <div style="color:var(--text-secondary);font-size:13px;">📤 Saving <strong>${escapeHtml(file.name)}</strong>…</div>
            <div style="width:100%;height:3px;background:var(--bg-surface-hover);border-radius:2px;overflow:hidden;">
                <div id="upload-progress-bar" style="height:100%;width:0%;background:var(--accent);border-radius:2px;transition:width 0.4s ease;"></div>
            </div>
        </div>`;

    // Animate the progress bar to give visual feedback during the network request.
    // Advances quickly to 80% then slows — real completion snaps to 100%.
    const bar = document.getElementById("upload-progress-bar");
    let fakeProgress = 0;
    const progressTimer = setInterval(() => {
        const step = fakeProgress < 80 ? 6 : 1;
        fakeProgress = Math.min(fakeProgress + step, 92);
        if (bar) bar.style.width = fakeProgress + "%";
    }, 120);

    const formData = new FormData();
    formData.append("file", file);

    try {
        const apiKey = localStorage.getItem("gemini-api-key") || "";
        const headers = {};
        if (apiKey) headers["X-Gemini-API-Key"] = apiKey;

        const response = await fetch(`${API_BASE}/documents/upload`, {
            method: "POST",
            headers: headers,
            body: formData
        });

        clearInterval(progressTimer);
        if (bar) bar.style.width = "100%";

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || "Upload failed");
        }

        const newDoc = await response.json();
        notes.unshift(newDoc);

        uploadStatus.innerHTML = `
            <div style="display:flex;flex-direction:column;gap:6px;align-items:center;">
                <span style="color:var(--success);font-size:14px;font-weight:600;">✅ ${escapeHtml(file.name)} saved!</span>
                <span style="color:var(--text-muted);font-size:12px;">🔄 Indexing in background — it will be searchable in a few seconds.</span>
            </div>`;

        setTimeout(() => {
            uploadModal.style.display = "none";
            uploadStatus.style.display = "none";
            selectNote(newDoc);
            renderNotesList();
            refreshGraphData();
        }, 2000);

    } catch (e) {
        clearInterval(progressTimer);
        if (bar) bar.style.width = "0%";
        uploadStatus.innerHTML = `<span style="color:var(--danger)">❌ Error: ${escapeHtml(e.message)}</span>`;
    }
}

// --- CHAT AND RAG INTERACTION ---
async function handleChatSubmit(e) {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;
    
    chatInput.value = "";
    
    // Append user message
    appendMessage("user", query);
    
    // Create companion bubble for streaming
    const bubble = appendMessage("assistant", `<div class="typing-indicator"><span></span><span></span><span></span></div>`);
    let bubbleContentElement = bubble.querySelector(".msg-content") || bubble;
    
    try {
        // Build settings header properties dynamically based on local configuration
        const apiKey = localStorage.getItem("gemini-api-key") || "";
        const modelName = localStorage.getItem("gemini-model") || "";
        
        const headers = { "Content-Type": "application/json" };
        if (apiKey) headers["X-Gemini-API-Key"] = apiKey;
        if (modelName) headers["X-Gemini-Model"] = modelName;
        
        // Pass model custom selection preferences via Request JSON to enable live config changes
        const response = await fetch(`${API_BASE}/chat/sessions/${chatSessionId}/stream`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                query: query,
                chat_session_id: chatSessionId
            })
        });
        
        if (!response.ok) throw new Error("Chat stream connection lost");
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";
        let sources = [];
        
        bubbleContentElement.innerHTML = "";
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            
            // Check for source information prefix
            if (chunk.includes("[SOURCES]")) {
                const parts = chunk.split("[SOURCES]");
                // Extract sources json
                try {
                    sources = JSON.parse(parts[1]);
                } catch (err) {}
                
                // If there's content after the second sources token
                if (parts.length > 2 && parts[2]) {
                    fullText += parts[2];
                    bubbleContentElement.innerHTML = formatMarkdown(fullText);
                }
            } else {
                fullText += chunk;
                bubbleContentElement.innerHTML = formatMarkdown(fullText);
            }
            
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        
        // Render citations if found
        if (sources.length > 0) {
            const sourcesDiv = document.createElement("div");
            sourcesDiv.className = "message-sources";
            sourcesDiv.innerHTML = `<span style="font-size: 11px; color: var(--text-muted); display:block; margin-bottom:4px;">Sources & Context:</span>`;
            
            // Filter unique source titles
            const uniqueSources = [];
            const seen = new Set();
            for (const s of sources) {
                if (!seen.has(s.doc_id)) {
                    seen.add(s.doc_id);
                    uniqueSources.push(s);
                }
            }
            
            uniqueSources.forEach(s => {
                const link = document.createElement("a");
                link.href = "#";
                link.className = "source-tag";
                link.innerHTML = `📄 ${escapeHtml(s.title)}`;
                link.onclick = (event) => {
                    event.preventDefault();
                    // Load referenced document into view
                    const doc = notes.find(n => n.id === s.doc_id);
                    if (doc) selectNote(doc);
                };
                sourcesDiv.appendChild(link);
            });
            bubble.appendChild(sourcesDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        
    } catch (e) {
        bubbleContentElement.innerHTML = `<span style="color: var(--danger)">*Error streaming assistant response: ${e.message}*</span>`;
    }
}

function appendMessage(role, content) {
    const bubble = document.createElement("div");
    bubble.className = `message ${role}`;
    bubble.innerHTML = `<div class="msg-content">${content}</div>`;
    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
    return bubble;
}

// --- UTILITIES ---
function switchTab(paneId) {
    tabButtons.forEach(btn => {
        if (btn.getAttribute("data-pane") === paneId) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });
    
    viewPanes.forEach(pane => {
        if (pane.id === paneId) {
            pane.classList.add("active");
        } else {
            pane.classList.remove("active");
        }
    });
    
    if (paneId === "graph-pane") {
        refreshGraphData();
    }
}

function setSaveStatus(text, type) {
    let color = "var(--success)";
    if (type === "warning") color = "var(--warning)";
    if (type === "danger") color = "var(--danger)";
    
    saveStatus.innerHTML = `
        <span style="color: ${color}; font-size: 12px; display: flex; align-items: center; gap: 6px;">
            <span style="width: 6px; height: 6px; border-radius: 50%; background: ${color};"></span>
            ${text}
        </span>
    `;
}

function showNotification(text, type = "success") {
    const toast = document.createElement("div");
    toast.style.position = "fixed";
    toast.style.bottom = "20px";
    toast.style.right = "20px";
    toast.style.padding = "10px 18px";
    toast.style.borderRadius = "var(--radius-md)";
    toast.style.backgroundColor = "var(--bg-surface)";
    toast.style.border = `1px solid ${type === "success" ? "var(--success)" : "var(--danger)"}`;
    toast.style.color = "var(--text-primary)";
    toast.style.boxShadow = "var(--shadow-lg)";
    toast.style.fontSize = "13px";
    toast.style.zIndex = "2000";
    toast.textContent = text;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(10px)";
        toast.style.transition = "all 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

function escapeHtml(string) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(string).replace(/[&<>"']/g, m => map[m]);
}

function formatMarkdown(text) {
    // Escape standard tags to prevent XSS
    let html = escapeHtml(text);
    
    // Convert headers
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
    
    // Bold tags
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic tags
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
    // In-line code
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');
    
    // Convert newlines to paragraphs
    html = html.split('\n\n').map(p => p.trim() ? `<p>${p}</p>` : '').join('');
    
    return html;
}

// --- SETUP EVENT HANDLERS ---
function setupEventHandlers() {
    newNoteBtn.onclick = handleNewNote;
    deleteNoteBtn.onclick = handleDeleteNote;
    
    noteTitle.oninput = queueAutoSave;
    noteBody.oninput = () => {
        updateCounts();
        queueAutoSave();
    };
    
    searchInput.oninput = (e) => {
        renderNotesList(e.target.value);
    };
    
    // Tab switching
    tabButtons.forEach(btn => {
        btn.onclick = () => switchTab(btn.getAttribute("data-pane"));
    });
    
    // Chat Form
    chatForm.onsubmit = handleChatSubmit;
    clearChatBtn.onclick = () => {
        chatBox.innerHTML = `<div class="message assistant">Conversation history cleared. How else can I help?</div>`;
        chatSessionId = "session_" + Math.random().toString(36).substring(2, 11);
        createChatSession();
    };
    
    // Modal controls - Settings
    settingsBtn.onclick = () => { settingsModal.style.display = "flex"; };
    closeSettingsModal.onclick = () => { settingsModal.style.display = "none"; };
    saveSettingsBtn.onclick = saveSettings;
    
    // Modal controls - Ingestion
    uploadDocBtn.onclick = () => { 
        uploadModal.style.display = "flex";
        uploadStatus.style.display = "none";
    };
    closeUploadModal.onclick = () => { uploadModal.style.display = "none"; };
    
    // Drag & Drop
    dropZone.onclick = () => fileInput.click();
    fileInput.onchange = (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    };
    
    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.classList.add("active");
    };
    dropZone.ondragleave = () => {
        dropZone.classList.remove("active");
    };
    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove("active");
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    };
    
    // Click outside modals
    window.onclick = (e) => {
        if (e.target === settingsModal) settingsModal.style.display = "none";
        if (e.target === uploadModal) uploadModal.style.display = "none";
    };
}

// --- HARDWARE ACCELERATED FORCE GRAPH ---
let graphNodes = [];
let graphLinks = [];
let scale = 1.0;
let panX = 0;
let panY = 0;
let isPanning = false;
let startDragX = 0;
let startDragY = 0;
let draggedNode = null;
let hoveredNode = null;

async function refreshGraphData() {
    try {
        const response = await fetch(`${API_BASE}/notes/graph`);
        if (response.ok) {
            const data = await response.json();
            syncGraphData(data);
        }
    } catch (e) {
        console.error("Failed to load graph data: ", e);
    }
}

function syncGraphData(data) {
    // Keep existing coordinate references during sync to prevent jumpiness
    const nodeMap = new Map(graphNodes.map(n => [n.id, n]));
    
    graphNodes = data.nodes.map(n => {
        const existing = nodeMap.get(n.id);
        return {
            id: n.id,
            title: n.title,
            is_file: n.is_file,
            file_type: n.file_type,
            x: existing ? existing.x : (Math.random() - 0.5) * 200 + graphCanvas.width / 2,
            y: existing ? existing.y : (Math.random() - 0.5) * 200 + graphCanvas.height / 2,
            vx: existing ? existing.vx : 0,
            vy: existing ? existing.vy : 0,
            radius: n.is_file ? 10 : 8
        };
    });
    
    // Resolve links to reference objects instead of ID strings
    const nodesById = new Map(graphNodes.map(n => [n.id, n]));
    graphLinks = data.links.map(l => ({
        source: nodesById.get(l.source),
        target: nodesById.get(l.target)
    })).filter(l => l.source && l.target);
}

function initGraph() {
    // Set size
    resizeCanvas();
    window.onresize = resizeCanvas;
    
    // Setup listeners
    graphCanvas.onmousedown = onCanvasMouseDown;
    graphCanvas.onmousemove = onCanvasMouseMove;
    graphCanvas.onmouseup = onCanvasMouseUp;
    graphCanvas.onwheel = onCanvasWheel;
    
    // Physics Loop
    requestAnimationFrame(updatePhysics);
}

function resizeCanvas() {
    const parent = graphCanvas.parentElement;
    graphCanvas.width = parent.clientWidth;
    graphCanvas.height = parent.clientHeight;
}

function updatePhysics() {
    const width = graphCanvas.width;
    const height = graphCanvas.height;
    
    // Apply forces
    const repulsion = 400;
    const springStrength = 0.05;
    const gravity = 0.03;
    const damping = 0.85;
    const idealLength = 80;
    
    // 1. Repulsion between all node pairs (Coulomb's Law style)
    for (let i = 0; i < graphNodes.length; i++) {
        let n1 = graphNodes[i];
        for (let j = i + 1; j < graphNodes.length; j++) {
            let n2 = graphNodes[j];
            let dx = n2.x - n1.x;
            let dy = n2.y - n1.y;
            let dist = Math.hypot(dx, dy) || 1;
            
            // Force strength inversely proportional to distance
            let force = repulsion / (dist * dist);
            let fx = (dx / dist) * force;
            let fy = (dy / dist) * force;
            
            if (n1 !== draggedNode) {
                n1.vx -= fx;
                n1.vy -= fy;
            }
            if (n2 !== draggedNode) {
                n2.vx += fx;
                n2.vy += fy;
            }
        }
    }
    
    // 2. Spring force along links (Hooke's Law style)
    for (let link of graphLinks) {
        let n1 = link.source;
        let n2 = link.target;
        let dx = n2.x - n1.x;
        let dy = n2.y - n1.y;
        let dist = Math.hypot(dx, dy) || 1;
        let displacement = dist - idealLength;
        
        let force = displacement * springStrength;
        let fx = (dx / dist) * force;
        let fy = (dy / dist) * force;
        
        if (n1 !== draggedNode) {
            n1.vx += fx;
            n1.vy += fy;
        }
        if (n2 !== draggedNode) {
            n2.vx -= fx;
            n2.vy -= fy;
        }
    }
    
    // 3. Central gravity
    const cx = width / 2;
    const cy = height / 2;
    for (let node of graphNodes) {
        if (node === draggedNode) continue;
        let dx = cx - node.x;
        let dy = cy - node.y;
        node.vx += dx * gravity;
        node.vy += dy * gravity;
        
        // Apply velocity & damping
        node.x += node.vx;
        node.y += node.vy;
        node.vx *= damping;
        node.vy *= damping;
    }
    
    drawGraph();
    requestAnimationFrame(updatePhysics);
}

function drawGraph() {
    const ctx = graphCanvas.getContext("2d");
    const width = graphCanvas.width;
    const height = graphCanvas.height;
    
    ctx.clearRect(0, 0, width, height);
    
    ctx.save();
    // Translate and Scale canvas for Panning and Zooming
    ctx.translate(panX, panY);
    ctx.scale(scale, scale);
    
    // Draw links
    ctx.strokeStyle = "rgba(100, 100, 100, 0.25)";
    ctx.lineWidth = 1.5;
    for (let link of graphLinks) {
        ctx.beginPath();
        ctx.moveTo(link.source.x, link.source.y);
        ctx.lineTo(link.target.x, link.target.y);
        ctx.stroke();
    }
    
    // Draw nodes
    for (let node of graphNodes) {
        const isHovered = node === hoveredNode;
        const color = node.is_file ? "#6366f1" : "#10b981"; // Indigo for files, Green for notes
        
        ctx.shadowBlur = isHovered ? 12 : 2;
        ctx.shadowColor = color;
        
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fill();
        
        // Stroke outline
        ctx.shadowBlur = 0;
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = isHovered ? 2 : 1;
        ctx.stroke();
        
        // Draw Text Title
        ctx.fillStyle = isHovered ? "var(--text-primary)" : "var(--text-secondary)";
        ctx.font = isHovered ? "bold 12px var(--font-sans)" : "11px var(--font-sans)";
        ctx.textAlign = "center";
        ctx.fillText(node.title, node.x, node.y - node.radius - 6);
    }
    ctx.restore();
}

// Coordinate Translations
function getCanvasMouseCoords(e) {
    const rect = graphCanvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    
    // Inverse transformation matrix calculation
    const cx = (mx - panX) / scale;
    const cy = (my - panY) / scale;
    
    return { x: cx, y: cy };
}

function findNodeAt(x, y) {
    for (let node of graphNodes) {
        const dist = Math.hypot(node.x - x, node.y - y);
        if (dist <= node.radius + 4) return node;
    }
    return null;
}

function onCanvasMouseDown(e) {
    const m = getCanvasMouseCoords(e);
    const node = findNodeAt(m.x, m.y);
    
    if (node) {
        draggedNode = node;
    } else {
        isPanning = true;
        startDragX = e.clientX - panX;
        startDragY = e.clientY - panY;
    }
}

function onCanvasMouseMove(e) {
    const m = getCanvasMouseCoords(e);
    
    if (draggedNode) {
        draggedNode.x = m.x;
        draggedNode.y = m.y;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
    } else if (isPanning) {
        panX = e.clientX - startDragX;
        panY = e.clientY - startDragY;
    } else {
        hoveredNode = findNodeAt(m.x, m.y);
    }
}

function onCanvasMouseUp(e) {
    const m = getCanvasMouseCoords(e);
    
    if (draggedNode) {
        // If they didn't drag it far, treat as click to open note
        const node = draggedNode;
        draggedNode = null;
        
        // Lookup note id
        const noteId = parseInt(node.id.split("_")[1]);
        const targetNote = notes.find(n => n.id === noteId);
        if (targetNote) {
            selectNote(targetNote);
        }
    }
    isPanning = false;
}

function onCanvasWheel(e) {
    e.preventDefault();
    const zoomFactor = 1.05;
    const mouseBefore = getCanvasMouseCoords(e);
    
    if (e.deltaY < 0) {
        scale *= zoomFactor;
    } else {
        scale /= zoomFactor;
    }
    scale = Math.min(Math.max(scale, 0.2), 4.0); // limits
    
    // Shift pan offset to keep mouse pointer anchored to same coordinate
    const mouseAfter = getCanvasMouseCoords(e);
    panX += (mouseAfter.x - mouseBefore.x) * scale;
    panY += (mouseAfter.y - mouseBefore.y) * scale;
}
