const $ = (sel) => document.querySelector(sel);

const dropZone = $("#drop-zone");
const fileInput = $("#file-input");
const uploadArea = $("#upload-area");
const fileListSection = $("#file-list-section");
const fileList = $("#file-list");
const fileCount = $("#file-count");
const clearFilesBtn = $("#clear-files-btn");
const convertBtn = $("#convert-btn");
const progressSection = $("#progress-section");
const progressFill = $("#progress-fill");
const progressText = $("#progress-text");
const resultsSection = $("#results-section");
const resultsSummary = $("#results-summary");
const resultsList = $("#results-list");
const outputDirDisplay = $("#output-dir-display");
const downloadAllBtn = $("#download-all-btn");
const errorSection = $("#error-section");
const errorMessage = $("#error-message");
const outputDirInput = $("#output-dir");

let selectedFiles = [];

function showSections(...sections) {
    [uploadArea, progressSection, resultsSection, errorSection].forEach(
        (el) => el.classList.add("hidden")
    );
    sections.forEach((s) => s.classList.remove("hidden"));
}

function showError(msg) {
    showSections(errorSection);
    errorMessage.textContent = msg;
}

function resetUI() {
    selectedFiles = [];
    fileInput.value = "";
    fileList.innerHTML = "";
    fileListSection.classList.add("hidden");
    resultsList.innerHTML = "";
    downloadAllBtn.classList.add("hidden");
    outputDirDisplay.classList.add("hidden");
    showSections(uploadArea);
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
}

function renderFileList() {
    fileList.innerHTML = "";
    fileCount.textContent = selectedFiles.length;

    if (selectedFiles.length === 0) {
        fileListSection.classList.add("hidden");
        return;
    }

    fileListSection.classList.remove("hidden");

    selectedFiles.forEach((file, idx) => {
        const li = document.createElement("li");
        li.innerHTML = `
            <span class="file-name">${escapeHtml(file.name)}</span>
            <span class="file-size">${formatSize(file.size)}</span>
            <button class="remove-file" data-idx="${idx}" title="Remove">&times;</button>
        `;
        fileList.appendChild(li);
    });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function addFiles(newFiles) {
    for (const f of newFiles) {
        const exists = selectedFiles.some(
            (sf) => sf.name === f.name && sf.size === f.size && sf.lastModified === f.lastModified
        );
        if (!exists) {
            selectedFiles.push(f);
        }
    }
    renderFileList();
}

// Drag & Drop
dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files);
    }
});

dropZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
        addFiles(fileInput.files);
        fileInput.value = "";
    }
});

fileList.addEventListener("click", (e) => {
    const btn = e.target.closest(".remove-file");
    if (!btn) return;
    const idx = parseInt(btn.dataset.idx, 10);
    selectedFiles.splice(idx, 1);
    renderFileList();
});

clearFilesBtn.addEventListener("click", () => {
    selectedFiles = [];
    renderFileList();
});

convertBtn.addEventListener("click", async () => {
    if (selectedFiles.length === 0) return;

    convertBtn.disabled = true;
    showSections(progressSection);
    progressFill.style.width = "0%";
    progressText.textContent = `0 / ${selectedFiles.length}`;

    const formData = new FormData();
    for (const f of selectedFiles) {
        formData.append("files", f);
    }
    formData.append("quality", $("#sel-quality").value);

    const outDir = outputDirInput.value.trim();
    if (outDir) {
        formData.append("output_directory", outDir);
    }

    try {
        const resp = await fetch("/api/convert-batch", { method: "POST", body: formData });

        if (!resp.ok) {
            const err = await resp.json();
            showError(err.detail || "Conversion failed.");
            convertBtn.disabled = false;
            return;
        }

        const data = await resp.json();
        progressFill.style.width = "100%";
        showResults(data);
    } catch (e) {
        showError("Failed to connect to the server. Please try again.");
    }

    convertBtn.disabled = false;
});

function showResults(data) {
    resultsList.innerHTML = "";
    resultsSummary.textContent = `${data.succeeded} of ${data.total} files converted successfully.`;

    if (data.output_directory) {
        outputDirDisplay.textContent = `Files saved to: ${data.output_directory}`;
        outputDirDisplay.classList.remove("hidden");
    } else {
        outputDirDisplay.classList.add("hidden");
    }

    for (const f of data.files) {
        const li = document.createElement("li");
        li.className = f.success ? "success" : "failure";

        let right = "";
        if (f.success && f.download_url) {
            right = `<span class="result-status">&#10003;</span><a class="result-dl" href="${f.download_url}" download>Download</a>`;
        } else {
            right = `<span class="result-status">&#10007;</span><span class="result-error">${escapeHtml(f.error || "Failed")}</span>`;
        }

        li.innerHTML = `<span class="result-name">${escapeHtml(f.filename)}</span>${right}`;
        resultsList.appendChild(li);
    }

    if (data.download_all_url) {
        downloadAllBtn.href = data.download_all_url;
        downloadAllBtn.classList.remove("hidden");
    } else {
        downloadAllBtn.classList.add("hidden");
    }

    showSections(resultsSection);
}

$("#reset-btn").addEventListener("click", resetUI);
$("#error-reset-btn").addEventListener("click", resetUI);
