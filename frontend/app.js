// Global chat history memory
let chatHistory = [];

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatMessages = document.getElementById("chat-messages");
    const welcomeMessage = document.getElementById("welcome-message");
    const fileInput = document.getElementById("file-input");
    const uploadForm = document.getElementById("upload-form");
    const uploadProgress = document.getElementById("upload-progress");
    const dbStatusBadge = document.getElementById("db-status-badge");
    const dbProvider = document.getElementById("db-provider");
    const dbChunks = document.getElementById("db-chunks");
    const documentList = document.getElementById("document-list");

    // Init UI
    refreshStatus();
    refreshDocumentsList();

    // 1. Refresh System Status UI
    async function refreshStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            
            if (data.is_ready && data.chunks_count > 0) {
                dbStatusBadge.textContent = "Connected & Active";
                dbStatusBadge.className = "status-badge status-active";
                if (welcomeMessage) welcomeMessage.style.display = "none";
            } else {
                dbStatusBadge.textContent = "DB Not Initialized";
                dbStatusBadge.className = "status-badge status-inactive";
                if (welcomeMessage && chatHistory.length === 0) welcomeMessage.style.display = "block";
            }

            dbProvider.textContent = data.embedding_provider ? data.embedding_provider.toUpperCase() : "None";
            dbChunks.textContent = data.chunks_count;
        } catch (err) {
            console.error("Error checking database status:", err);
            dbStatusBadge.textContent = "Error Connecting";
            dbStatusBadge.className = "status-badge status-inactive";
        }
    }

    // 2. Fetch and Render Document List in Sidebar
    async function refreshDocumentsList() {
        try {
            const res = await fetch("/api/documents");
            const data = await res.json();
            
            documentList.innerHTML = "";
            
            const allDocs = [];
            data.pdfs.forEach(name => allDocs.push({ name, type: "PDF" }));
            data.notes.forEach(name => allDocs.push({ name, type: "Markdown/Text" }));

            if (allDocs.length === 0) {
                documentList.innerHTML = `<div class="list-empty">No documents found.</div>`;
                return;
            }

            allDocs.forEach((doc, idx) => {
                const icon = doc.type === "PDF" ? "📁" : "📝";
                const docItem = document.createElement("div");
                docItem.className = "doc-item";
                docItem.innerHTML = `
                    <span class="doc-name" title="${doc.name}">${icon} ${doc.name}</span>
                    <button class="doc-delete-btn" data-name="${doc.name}" data-idx="${idx}">🗑️</button>
                `;
                documentList.appendChild(docItem);
            });

            // Bind Delete Button Listeners
            document.querySelectorAll(".doc-delete-btn").forEach(btn => {
                btn.addEventListener("click", handleDeleteDocument);
            });

        } catch (err) {
            console.error("Error fetching document list:", err);
            documentList.innerHTML = `<div class="list-empty">Error loading files.</div>`;
        }
    }

    // 3. Handle File Delete Click
    async function handleDeleteDocument(e) {
        const fileName = e.target.getAttribute("data-name");
        if (!confirm(`Are you sure you want to delete "${fileName}"?`)) return;

        try {
            e.target.disabled = true;
            e.target.textContent = "⏳";
            
            const res = await fetch(`/api/documents/${encodeURIComponent(fileName)}`, {
                method: "DELETE"
            });
            const data = await res.json();

            if (res.ok) {
                showToast(`Deleted ${fileName} and updated index!`);
            } else {
                alert(`Delete failed: ${data.detail || "Unknown error"}`);
            }
        } catch (err) {
            console.error("Error deleting file:", err);
            alert("Connection error while deleting file.");
        } finally {
            refreshStatus();
            refreshDocumentsList();
        }
    }

    // 4. Handle Document Upload
    fileInput.addEventListener("change", handleUploadFiles);
    
    // Support click on upload label
    uploadForm.addEventListener("click", () => fileInput.click());

    // Support Drag and Drop
    uploadForm.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadForm.style.borderColor = "#3b82f6";
    });

    uploadForm.addEventListener("dragleave", () => {
        uploadForm.style.borderColor = "rgba(255, 255, 255, 0.1)";
    });

    uploadForm.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadForm.style.borderColor = "rgba(255, 255, 255, 0.1)";
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleUploadFiles();
        }
    });

    async function handleUploadFiles() {
        const files = fileInput.files;
        if (files.length === 0) return;

        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append("files", files[i]);
        }

        try {
            uploadProgress.style.display = "flex";
            
            const res = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });
            const data = await res.json();

            if (res.ok) {
                showToast(`Index compiled successfully: Ingested ${data.chunks_count} chunks!`);
            } else {
                alert(`Upload failed: ${data.detail || "Unknown error"}`);
            }
        } catch (err) {
            console.error("Error uploading files:", err);
            alert("Error connecting to upload endpoint.");
        } finally {
            uploadProgress.style.display = "none";
            fileInput.value = ""; // Clear file selector
            refreshStatus();
            refreshDocumentsList();
        }
    }

    // 5. Handle Chat Form Submit
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const prompt = chatInput.value.trim();
        if (!prompt) return;

        chatInput.value = "";

        // Remove welcome screen if visible
        if (welcomeMessage) welcomeMessage.style.display = "none";

        // Append User Message Bubble
        appendMessage("user", prompt);

        // Append Assistant "Thinking..." placeholder
        const thinkingId = appendMessage("assistant", "Thinking...");

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    input: prompt,
                    chat_history: chatHistory
                })
            });
            const data = await res.json();

            // Remove thinking message
            removeMessageElement(thinkingId);

            if (res.ok) {
                // Append Assistant Reply
                appendMessage("assistant", data.answer, data.sources);
                
                // Add to chat memory
                chatHistory.push({ role: "user", content: prompt });
                chatHistory.push({ role: "assistant", content: data.answer });
            } else {
                appendMessage("assistant", `An error occurred: ${data.detail || "Server failed to process query."}`);
            }
        } catch (err) {
            console.error("Error in chat query:", err);
            removeMessageElement(thinkingId);
            appendMessage("assistant", "Connection error: Failed to reach the backend API.");
        }
    });

    // Helper: Append a message bubble to log
    function appendMessage(role, text, sources = []) {
        const id = "msg_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
        const bubble = document.createElement("div");
        bubble.id = id;
        bubble.className = `chat-message ${role}`;
        
        // Escape HTML for text, but allow simple formatting or markdown if generated
        bubble.innerHTML = `<div>${formatMarkdown(text)}</div>`;

        // Render Sources Accordion if assistant response has sources
        if (role === "assistant" && sources && sources.length > 0) {
            const sourcesContainer = document.createElement("div");
            sourcesContainer.className = "sources-container";
            
            const trigger = document.createElement("button");
            trigger.className = "sources-trigger";
            trigger.textContent = "📚 View Sources";
            
            const content = document.createElement("div");
            content.className = "sources-content";
            
            sources.forEach((src, idx) => {
                const sourceName = src.metadata.source ? src.metadata.source.split(/[\\/]/).pop() : "Unknown File";
                const page = src.metadata.page !== undefined ? `, Page ${src.metadata.page + 1}` : "";
                
                const citation = document.createElement("div");
                citation.className = "source-citation";
                citation.innerHTML = `
                    <div class="source-title">Source ${idx + 1}: ${sourceName}${page}</div>
                    <div class="source-text">"${src.page_content}"</div>
                `;
                content.appendChild(citation);
            });
            
            trigger.addEventListener("click", () => {
                content.classList.toggle("expanded");
            });

            sourcesContainer.appendChild(trigger);
            sourcesContainer.appendChild(content);
            bubble.appendChild(sourcesContainer);
        }

        chatMessages.appendChild(bubble);
        scrollToBottom();
        return id;
    }

    function removeMessageElement(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Basic markdown formatting helper for chat bubble display
    function formatMarkdown(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>")
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/`(.*?)`/g, "<code>$1</code>");
    }

    // Temporary Status Toast implementation
    function showToast(message) {
        const toast = document.createElement("div");
        toast.style.position = "fixed";
        toast.style.bottom = "110px";
        toast.style.left = "50%";
        toast.style.transform = "translateX(-50%)";
        toast.style.background = "rgba(59, 130, 246, 0.9)";
        toast.style.color = "white";
        toast.style.padding = "10px 20px";
        toast.style.borderRadius = "20px";
        toast.style.fontSize = "0.9rem";
        toast.style.fontWeight = "600";
        toast.style.zIndex = "9999";
        toast.style.boxShadow = "var(--shadow)";
        toast.style.animation = "bubble-fade 0.2s ease-out";
        toast.textContent = message;
        
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
});
