const $ = (sel) => document.querySelector(sel);

const dropZone = $("#drop-zone");
const fileInput = $("#file-input");
const uploadArea = $("#upload-area");
const progressSection = $("#progress-section");
const progressFill = $("#progress-fill");
const progressText = $("#progress-text");
const inspectSection = $("#inspect-section");
const metadataGrid = $("#metadata-grid");
const cziOptions = $("#czi-options");
const tiffOptions = $("#tiff-options");
const convertBtn = $("#convert-btn");
const successSection = $("#success-section");
const errorSection = $("#error-section");
const errorMessage = $("#error-message");

let currentFile = null;
let inspectionData = null;

function showOnly(section) {
    [uploadArea, progressSection, inspectSection, successSection, errorSection].forEach(
        (el) => el.classList.add("hidden")
    );
    if (section) section.classList.remove("hidden");
}

function showError(msg) {
    showOnly(errorSection);
    errorMessage.textContent = msg;
}

function resetUI() {
    currentFile = null;
    inspectionData = null;
    fileInput.value = "";
    cziOptions.classList.add("hidden");
    tiffOptions.classList.add("hidden");
    metadataGrid.innerHTML = "";
    showOnly(uploadArea);
}

function populateSelect(selectEl, count) {
    selectEl.innerHTML = "";
    for (let i = 0; i < count; i++) {
        const opt = document.createElement("option");
        opt.value = i;
        opt.textContent = i;
        selectEl.appendChild(opt);
    }
}

function addMeta(label, value) {
    const item = document.createElement("div");
    item.className = "meta-item";
    item.innerHTML = `<div class="meta-label">${label}</div><div class="meta-value">${value}</div>`;
    metadataGrid.appendChild(item);
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
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
        handleFile(e.dataTransfer.files[0]);
    }
});

dropZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
        handleFile(fileInput.files[0]);
    }
});

async function handleFile(file) {
    currentFile = file;
    showOnly(progressSection);
    progressFill.style.width = "0%";
    progressText.textContent = "Uploading and inspecting...";

    const formData = new FormData();
    formData.append("file", file);

    try {
        progressFill.style.width = "50%";

        const resp = await fetch("/api/inspect", { method: "POST", body: formData });
        progressFill.style.width = "100%";

        if (!resp.ok) {
            const err = await resp.json();
            showError(err.detail || "Inspection failed.");
            return;
        }

        inspectionData = await resp.json();
        showInspectionResult();
    } catch (e) {
        showError("Failed to connect to the server. Please try again.");
    }
}

function showInspectionResult() {
    metadataGrid.innerHTML = "";
    const d = inspectionData;

    addMeta("Filename", d.filename);
    addMeta("Format", d.format);
    addMeta("File Size", formatSize(d.size));

    if (d.width && d.height) addMeta("Dimensions", `${d.width} x ${d.height}`);
    if (d.channels != null) addMeta("Channels", d.channels);
    if (d.bit_depth != null) addMeta("Bit Depth", d.bit_depth + "-bit");
    if (d.mode) addMeta("Mode", d.mode);

    cziOptions.classList.add("hidden");
    tiffOptions.classList.add("hidden");

    if (d.format === "CZI") {
        const zp = d.z_planes || 1;
        const ch = d.channels || 1;
        const tp = d.time_points || 1;
        const sc = d.scenes || 1;

        if (zp > 1 || ch > 1 || tp > 1 || sc > 1) {
            addMeta("Z Planes", zp);
            addMeta("Time Points", tp);
            if (sc > 1) addMeta("Scenes", sc);

            populateSelect($("#sel-z"), zp);
            populateSelect($("#sel-channel"), ch);
            populateSelect($("#sel-timepoint"), tp);
            populateSelect($("#sel-scene"), sc);
            cziOptions.classList.remove("hidden");
        }
    }

    if (d.format === "TIFF" && d.pages && d.pages > 1) {
        addMeta("Pages", d.pages);
        populateSelect($("#sel-page"), d.pages);
        tiffOptions.classList.remove("hidden");
    }

    showOnly(inspectSection);
}

convertBtn.addEventListener("click", async () => {
    if (!currentFile) return;

    convertBtn.disabled = true;
    convertBtn.textContent = "Converting...";

    const formData = new FormData();
    formData.append("file", currentFile);
    formData.append("quality", $("#sel-quality").value);

    if (inspectionData.format === "CZI") {
        formData.append("z", $("#sel-z").value || "0");
        formData.append("channel", $("#sel-channel").value || "0");
        formData.append("timepoint", $("#sel-timepoint").value || "0");
        formData.append("scene", $("#sel-scene").value || "0");
    }

    if (inspectionData.format === "TIFF") {
        formData.append("page", $("#sel-page").value || "0");
    }

    try {
        const resp = await fetch("/api/convert", { method: "POST", body: formData });

        if (!resp.ok) {
            const err = await resp.json();
            showError(err.detail || "Conversion failed.");
            convertBtn.disabled = false;
            convertBtn.textContent = "Convert to JPEG";
            return;
        }

        const result = await resp.json();

        if (result.success) {
            $("#original-name").textContent = inspectionData.filename;
            $("#output-name").textContent = result.filename;
            $("#download-btn").href = result.download_url;
            showOnly(successSection);
        } else {
            showError(result.error || "Conversion failed.");
        }
    } catch (e) {
        showError("Failed to connect to the server. Please try again.");
    }

    convertBtn.disabled = false;
    convertBtn.textContent = "Convert to JPEG";
});

$("#reset-btn").addEventListener("click", resetUI);
$("#error-reset-btn").addEventListener("click", resetUI);
