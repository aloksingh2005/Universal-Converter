// =================== GLOBAL STATE ===================
let currentFiles = {};
let currentSection = 'dashboard';
let currentRequest = null;

// Config
const MAX_SIZE_BYTES = 500 * 1024 * 1024; // 500MB
const DEFAULT_DOWNLOAD_NAME = 'converted';
const PROGRESS_MIN_DELAY_MS = 150;

// =================== DOM HOOKS ===================
const DOM = {
  sidebar: document.getElementById('sidebar'),
  sidebarToggle: document.getElementById('sidebarToggle'),
  progressModal: document.getElementById('progressModal'),
  toastContainer: document.getElementById('toastContainer'),
  menuItems: document.querySelectorAll('.menu-item'),
  contentSections: document.querySelectorAll('.content-section'),
  searchInput: document.getElementById('searchInput'),
  progressTitle: document.getElementById('progressTitle'),
  progressMessage: document.getElementById('progressMessage'),
  progressBar: document.getElementById('progressBar'),
  progressCancel: document.getElementById('progressCancel')
};

// Track bound elements to prevent double binding
const boundElements = new WeakSet();

// =================== INIT ===================
document.addEventListener('DOMContentLoaded', () => {
  try {
    initializeSidebar();
    setupMenuNavigation();
    initializeSearch();
    initializeUploadZones();

    if (DOM.progressCancel) {
      DOM.progressCancel.addEventListener('click', cancelActiveRequest);
    }

    showToast('success', 'Welcome!', 'Universal File Converter is ready to use!');
    console.log('✅ Universal File Converter loaded successfully! 🚀');
  } catch (err) {
    console.error('❌ App initialization error:', err);
    showToast('error', 'Initialization Error', 'Failed to load application properly');
  }
});

// =================== SIDEBAR & NAV ===================
function initializeSidebar() {
  if (DOM.sidebarToggle) DOM.sidebarToggle.addEventListener('click', toggleSidebar);
  
  if (window.innerWidth <= 768) {
    DOM.sidebar?.classList.add('collapsed');
  }
  window.addEventListener('resize', handleResize);
}

function toggleSidebar() {
  if (!DOM.sidebar) return;
  if (window.innerWidth <= 768) {
    DOM.sidebar.classList.toggle('open');
  } else {
    DOM.sidebar.classList.toggle('collapsed');
  }
}

function handleResize() {
  if (!DOM.sidebar) return;
  if (window.innerWidth <= 768) {
    DOM.sidebar.classList.remove('collapsed');
    DOM.sidebar.classList.remove('open');
  } else {
    DOM.sidebar.classList.remove('open');
  }
}

function setupMenuNavigation() {
  DOM.menuItems.forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      const category = item.dataset.category;
      if (category) {
        showCategory(category);
        setActiveMenuItem(item);
      }
    });
  });
}

function showCategory(category) {
  DOM.contentSections.forEach(section => section.classList.remove('active'));
  
  const targetSection = document.getElementById(category);
  if (targetSection) {
    targetSection.classList.add('active');
    currentSection = category;
    // Re-init upload zones for newly visible content
    setTimeout(initializeUploadZones, 50);
  }
  
  if (window.innerWidth <= 768) {
    DOM.sidebar?.classList.remove('open');
  }
}

function setActiveMenuItem(activeItem) {
  DOM.menuItems.forEach(item => item.classList.remove('active'));
  activeItem.classList.add('active');
}

// =================== SEARCH ===================
function initializeSearch() {
  if (!DOM.searchInput) return;
  DOM.searchInput.addEventListener('input', debounce(e => {
    handleSearch(e.target.value);
  }, 300));
}

function handleSearch(query) {
  const cards = document.querySelectorAll('.converter-card');
  if (!query.trim()) {
    cards.forEach(card => card.style.display = 'block');
    return;
  }
  const q = query.toLowerCase();
  cards.forEach(card => {
    const toolName = (card.dataset.tool || '').toLowerCase();
    const desc = (card.querySelector('.tool-description')?.textContent || '').toLowerCase();
    const match = toolName.includes(q) || desc.includes(q);
    card.style.display = match ? 'block' : 'none';
  });
}

function debounce(fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

// =================== UPLOAD ZONES (FIXED) ===================
function initializeUploadZones() {
  // Bind upload zones (without cloning - this was the main issue)
  document.querySelectorAll('.upload-zone').forEach(zone => {
    if (boundElements.has(zone)) return; // Skip if already bound
    
    // Remove any existing listeners first
    zone.removeEventListener('click', handleUploadZoneClick);
    zone.removeEventListener('dragover', handleDragOver);
    zone.removeEventListener('dragleave', handleDragLeave);
    zone.removeEventListener('drop', handleDrop);
    
    // Add fresh listeners
    zone.addEventListener('click', handleUploadZoneClick);
    zone.addEventListener('dragover', handleDragOver);
    zone.addEventListener('dragleave', handleDragLeave);
    zone.addEventListener('drop', handleDrop);
    
    boundElements.add(zone);
  });

  // Bind file inputs (without cloning)
  document.querySelectorAll('input[type="file"]').forEach(input => {
    if (boundElements.has(input)) return; // Skip if already bound
    
    // Remove existing listener first
    input.removeEventListener('change', handleFileSelection);
    
    // Add fresh listener
    input.addEventListener('change', handleFileSelection);
    
    boundElements.add(input);
  });
}

function handleUploadZoneClick(e) {
  e.preventDefault();
  e.stopPropagation();
  
  const zone = e.currentTarget;
  const inputId = zone.dataset.inputId;
  
  console.log('Upload zone clicked:', inputId); // Debug log
  
  const input = document.getElementById(inputId);
  if (!input) {
    console.error('File input not found:', inputId);
    return;
  }
  
  if (!zone.classList.contains('file-selected')) {
    console.log('Triggering file input click'); // Debug log
    input.click();
  }
}

function handleFileSelection(e) {
  const files = Array.from(e.target.files || []);
  const inputId = e.target.id;
  
  console.log('Files selected:', files.length, 'for input:', inputId); // Debug log
  
  if (!files.length) return;

  // Validate client-side
  const zone = getUploadZoneForInput(e.target);
  const accept = zone?.dataset.accept || e.target.getAttribute('accept') || '';
  const errs = validateFiles(files, accept);
  
  if (errs.length) {
    showToast('warning', 'Invalid files', errs.join('<br/>'));
    return;
  }

  currentFiles[inputId] = files;
  updateUploadZone(e.target, files);
  showToast('success', 'Files Selected', `${files.length} file${files.length > 1 ? 's' : ''} ready for conversion`);
}

function updateUploadZone(input, files) {
  const zone = getUploadZoneForInput(input);
  if (!zone) return;

  const safeNames = files.map(f => escapeHTML(f.name)).join(', ');
  const totalSize = files.reduce((s, f) => s + (f.size || 0), 0);
  const isMultiple = input.hasAttribute('multiple');

  zone.classList.add('file-selected');
  zone.innerHTML = `
    <i class="fas fa-check-circle"></i>
    <p style="color: var(--secondary-color); font-weight: 600;">
      ${files.length} File${files.length > 1 ? 's' : ''} Selected
      ${isMultiple && files.length === 1 ? ' (You can select more)' : ''}
    </p>
    <span class="upload-hint">
      ${safeNames.length > 80 ? safeNames.substring(0, 80) + '...' : safeNames}<br>
      <small>Total size: ${formatFileSize(totalSize)}</small>
    </span>
  `;
}

function getUploadZoneForInput(inputEl) {
  // First try to find zone with matching data-input-id
  const zone = document.querySelector(`.upload-zone[data-input-id="${inputEl.id}"]`);
  if (zone) return zone;
  
  // Fallback: find zone in same card-body
  return inputEl.closest('.card-body')?.querySelector('.upload-zone');
}

function handleDragOver(e) {
  e.preventDefault();
  e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('dragover');
}

function handleDrop(e) {
  e.preventDefault();
  const zone = e.currentTarget;
  zone.classList.remove('dragover');

  const files = Array.from(e.dataTransfer?.files || []);
  if (!files.length) return;

  const inputId = zone.dataset.inputId;
  const input = document.getElementById(inputId);
  if (!input) return;

  // Validate client-side
  const accept = zone.dataset.accept || input.getAttribute('accept') || '';
  const errs = validateFiles(files, accept);
  if (errs.length) {
    showToast('warning', 'Invalid files', errs.join('<br/>'));
    return;
  }

  currentFiles[inputId] = files;
  updateUploadZone(input, files);
  showToast('success', 'Files Dropped', `${files.length} file${files.length > 1 ? 's' : ''} ready for conversion`);
}

function validateFiles(files, acceptStr) {
  const errors = [];

  // Size check
  const overs = files.filter(f => typeof f.size === 'number' && f.size > MAX_SIZE_BYTES);
  if (overs.length) {
    errors.push(`Some files exceed ${formatFileSize(MAX_SIZE_BYTES)} limit.`);
  }

  // Type check
  const accepts = (acceptStr || '')
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter(Boolean);

  if (accepts.length) {
    const bad = files.filter(f => {
      const name = (f.name || '').toLowerCase();
      const ext = '.' + (name.split('.').pop() || '');
      return !accepts.includes(ext);
    });
    if (bad.length) {
      errors.push(`Unsupported file type(s): ${escapeHTML(bad.map(b => b.name).join(', '))}`);
    }
  }
  return errors;
}

// =================== FILE PROCESSING ===================
async function processFile(endpoint, inputId, toolName, categoryId, toolIndex) {
  const files = currentFiles[inputId];
  if (!files || !files.length) {
    showToast('error', 'No Files Selected', 'Please select files before starting conversion');
    return;
  }

  const card = document.querySelector(`[data-input-id="${inputId}"]`)?.closest('.converter-card') ||
               document.getElementById(inputId)?.closest('.converter-card');
  const inputType = card?.dataset.inputType || 'single';
  const minFiles = parseInt(card?.dataset.minFiles || '0', 10) || 0;
  
  if (minFiles && files.length < minFiles) {
    showToast('warning', 'More files needed', `Please select at least ${minFiles} files for ${escapeHTML(toolName)}`);
    return;
  }
  
  if (toolName === 'Merge PDFs' && files.length < 2) {
    showToast('warning', 'Multiple Files Required', 'Please select at least 2 PDF files to merge');
    return;
  }

  const options = collectToolOptionsScoped(card, categoryId, toolIndex);
  const formData = new FormData();
  
  if (inputType === 'multiple' || files.length > 1) {
    files.forEach(f => formData.append('files', f));
  } else {
    formData.append('file', files[0]);
  }
  
  Object.entries(options).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}`.trim() !== '') {
      formData.append(key, value);
    }
  });

  const xhr = new XMLHttpRequest();
  currentRequest = xhr;

  showProgress(`Processing ${toolName}...`, 'Uploading files...');
  const startedAt = Date.now();

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      updateProgress(pct, `Uploading... ${pct}%`);
    }
  };

  xhr.onprogress = (e) => {
    if (xhr.readyState === 3 || xhr.readyState === 4) {
      updateProgress(undefined, 'Processing & downloading...');
    }
  };

  xhr.responseType = 'blob';
  xhr.open('POST', endpoint, true);

  xhr.onreadystatechange = () => {
    if (xhr.readyState !== 4) return;

    const elapsed = Date.now() - startedAt;
    const ensureVisible = Math.max(0, PROGRESS_MIN_DELAY_MS - elapsed);
    
    setTimeout(() => {
      try {
        if (xhr.status >= 200 && xhr.status < 300) {
          const serverName = getFilenameFromContentDisposition(xhr.getResponseHeader('Content-Disposition'));
          const fallbackName = getDownloadFilename(toolName, files[0]?.name || DEFAULT_DOWNLOAD_NAME);
          const downloadName = serverName || fallbackName;

          downloadFileFromBlob(xhr.response, downloadName);
          showToast('success', 'Conversion Complete!', `${escapeHTML(toolName)} completed successfully`);
          resetUploadZone(inputId);
        } else {
          handleErrorBlob(xhr.response, xhr.status, xhr.statusText);
        }
      } catch (err) {
        console.error('Conversion error:', err);
        showToast('error', 'Conversion Failed', err?.message || 'Unexpected error occurred');
      } finally {
        hideProgress();
        currentRequest = null;
      }
    }, ensureVisible);
  };

  xhr.onerror = () => {
    hideProgress();
    currentRequest = null;
    showToast('error', 'Network Error', 'Failed to communicate with server');
  };
  
  xhr.onabort = () => {
    hideProgress();
    currentRequest = null;
    showToast('info', 'Cancelled', 'Operation was cancelled by user');
  };

  try {
    xhr.send(formData);
  } catch (err) {
    hideProgress();
    currentRequest = null;
    showToast('error', 'Request Failed', err?.message || 'Could not start upload');
  }
}

function cancelActiveRequest() {
  try {
    if (currentRequest) {
      currentRequest.abort();
    } else {
      hideProgress();
    }
  } catch (e) {
    hideProgress();
  }
}

function collectToolOptionsScoped(cardEl, categoryId, toolIndex) {
  const options = {};
  if (!cardEl) return options;

  const fields = cardEl.querySelectorAll('input, select, textarea');
  fields.forEach(el => {
    const name = el.name || el.id?.split('-')[0] || '';
    if (!name || name === 'file' || name === 'files') return;
    
    const val = el.type === 'checkbox' ? (el.checked ? '1' : '') : (el.value?.trim() || '');
    if (val !== '') options[name] = val;
  });
  
  return options;
}

// =================== DOWNLOAD HELPERS ===================
function downloadFileFromBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = filename || DEFAULT_DOWNLOAD_NAME;

  document.body.appendChild(a);
  a.click();
  
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

function getFilenameFromContentDisposition(headerVal) {
  if (!headerVal) return '';
  const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(headerVal);
  let name = match?.[1] || match?.[2] || '';
  try {
    if (name.includes('%')) name = decodeURIComponent(name);
  } catch (_) {}
  return name.trim();
}

function getDownloadFilename(toolName, originalName = '') {
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
  const baseName = (originalName.split('.')[0] || DEFAULT_DOWNLOAD_NAME);

  const map = {
    'Merge PDFs': 'merged.pdf',
    'Split PDF': 'split_pages.zip',
    'Compress PDF': `${baseName}_compressed.pdf`,
    'Rotate PDF': `${baseName}_rotated.pdf`,
    'Add Watermark': `${baseName}_watermarked.pdf`,
    'PDF → Word': `${baseName}.docx`,
    'Word → PDF': `${baseName}.pdf`,
    'Excel → PDF': `${baseName}.pdf`,
    'Image → Any': `${baseName}_converted`,
    'JPG → PNG': `${baseName}.png`,
    'PNG → JPG': `${baseName}.jpg`,
    'Image → PDF': 'images.pdf',
    'MP3 → WAV': `${baseName}.wav`,
    'WAV → MP3': `${baseName}.mp3`,
    'RAR → ZIP': `${baseName}.zip`,
    'JSON → CSV': `${baseName}.csv`,
    'CSV → JSON': `${baseName}.json`
  };
  
  return map[toolName] || `${baseName}_converted_${timestamp}`;
}

// =================== PROGRESS & TOAST ===================
function showProgress(title = 'Converting...', message = 'Please wait...') {
  if (DOM.progressTitle) DOM.progressTitle.textContent = title;
  if (DOM.progressMessage) DOM.progressMessage.textContent = message;
  if (DOM.progressBar) DOM.progressBar.style.width = '0%';

  DOM.progressModal?.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function updateProgress(percent, message) {
  if (typeof percent === 'number' && DOM.progressBar) {
    DOM.progressBar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
  }
  if (message && DOM.progressMessage) {
    DOM.progressMessage.textContent = message;
  }
}

function hideProgress() {
  DOM.progressModal?.classList.remove('active');
  document.body.style.overflow = '';
}

function showToast(type, title, message, duration = 5000) {
  if (!DOM.toastContainer) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const iconMap = {
    success: 'fas fa-check-circle',
    error: 'fas fa-exclamation-triangle',
    info: 'fas fa-info-circle',
    warning: 'fas fa-exclamation-circle'
  };

  toast.innerHTML = `
    <i class="${iconMap[type] || iconMap.info}"></i>
    <div class="toast-content">
      <div class="toast-title">${escapeHTML(title)}</div>
      <div class="toast-message">${message}</div>
    </div>
    <button class="toast-close" aria-label="Close" onclick="removeToast(this.parentElement)">
      <i class="fas fa-times"></i>
    </button>
  `;

  DOM.toastContainer.appendChild(toast);
  setTimeout(() => removeToast(toast), duration);
}

function removeToast(toast) {
  if (toast && toast.parentElement) {
    toast.style.animation = 'slideOut 0.3s ease forwards';
    setTimeout(() => toast?.remove(), 300);
  }
}

function resetUploadZone(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;

  const zone = getUploadZoneForInput(input);
  const isMultiple = input.hasAttribute('multiple');

  delete currentFiles[inputId];
  input.value = '';

  if (zone) {
    zone.classList.remove('file-selected');
    zone.innerHTML = `
      <i class="fas fa-cloud-upload-alt" aria-hidden="true"></i>
      <p>${isMultiple ? 'Drop multiple files here' : 'Drop file here'}</p>
      <span class="upload-hint">Supported formats • or click to browse</span>
    `;
  }
}

// =================== UTILS ===================
function formatFileSize(bytes) {
  if (!bytes) return '0 Bytes';
  const k = 1024, sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

function escapeHTML(str) {
  return (str || '').toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function handleErrorBlob(blob, status, statusText) {
  try {
    const text = await blob.text();
    try {
      const obj = JSON.parse(text);
      showToast('error', `Error ${status}`, escapeHTML(obj.error || statusText || 'Request failed'));
    } catch {
      showToast('error', `Error ${status}`, escapeHTML(text || statusText || 'Request failed'));
    }
  } catch {
    showToast('error', `Error ${status}`, statusText || 'Unknown error occurred');
  }
}

// =================== GLOBAL WINDOW FUNCTIONS ===================
window.showCategory = showCategory;
window.processFile = processFile;
window.triggerFileInput = (inputId) => document.getElementById(inputId)?.click();
window.removeToast = removeToast;
window.resetUploadZone = resetUploadZone;

// Debug helpers
window.getCurrentFiles = () => currentFiles;
window.debugUpload = (inputId) => console.log('Files for', inputId, ':', currentFiles[inputId]);
