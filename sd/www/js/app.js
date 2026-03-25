let currentPath = '/sd';

// =====================================================
// RETRO THEME TOGGLE - 16-bit / CRT mode
// =====================================================
const RETRO_STORAGE_KEY = 'jeb_retro_mode';

function toggleRetroTheme() {
    const enabled = document.body.classList.toggle('retro');
    try { localStorage.setItem(RETRO_STORAGE_KEY, enabled ? '1' : '0'); } catch (e) { console.warn('Retro theme: localStorage unavailable', e); }
    const btn = document.getElementById('retroToggleBtn');
    if (btn) btn.textContent = enabled ? '🖥 NORMAL' : '🕹 RETRO';
}

(function _initRetroTheme() {
    try {
        if (localStorage.getItem(RETRO_STORAGE_KEY) === '1') {
            document.body.classList.add('retro');
            document.addEventListener('DOMContentLoaded', function () {
                const btn = document.getElementById('retroToggleBtn');
                if (btn) btn.textContent = '🖥 NORMAL';
            });
        }
    } catch (e) { console.warn('Retro theme: could not restore state', e); }
})();

// =====================================================
// ADMIN EASTER EGG - Click title 5× to reveal Admin tab
// =====================================================
let _adminClickCount = 0;
let _adminClickTimer = null;
let _adminUnlocked = false;

function adminEasterEgg() {
    if (_adminUnlocked) return;
    _adminClickCount++;

    // Reset counter after 2 seconds of inactivity
    clearTimeout(_adminClickTimer);
    _adminClickTimer = setTimeout(() => { _adminClickCount = 0; }, 2000);

    if (_adminClickCount >= 5) {
        _adminUnlocked = true;
        const btn = document.getElementById('adminTabBtn');
        if (btn) {
            btn.classList.remove('admin-tab-hidden');
            btn.classList.add('admin-tab-visible');
        }
        const title = document.getElementById('mainTitle');
        if (title) title.style.color = '#FF9800';
        _adminClickCount = 0;
    }
}

function showTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById(tabName).classList.add('active');

    // Auto-load content for some tabs
    if (tabName === 'system') {
        loadSystemStatus();
        startTelemetry();
    }
    if (tabName === 'config') loadConfig();
    if (tabName === 'files') loadFiles();
    if (tabName === 'logs') loadLogs();
    if (tabName === 'console') loadConsole();
    if (tabName === 'modes') loadModes();
    if (tabName === 'pixelart') initPixelArtStudio();
    if (tabName === 'audiostudio') initAudioStudio();
    if (tabName === 'layout') loadLayout();
    if (tabName === 'admin') loadAdmin();
    if (tabName === 'gamepad') initGamepad();
}

// =====================================================
// ADMIN TAB
// =====================================================

function loadAdmin() {
    loadAdminVersionInfo();
    loadAdminLayout();
}

async function loadAdminVersionInfo() {
    const container = document.getElementById('adminVersionInfo');
    if (!container) return;
    container.innerHTML = '<em style="color:#555; font-size:0.9em;">Loading...</em>';
    try {
        const resp = await fetch('/api/admin/version');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();

        const localVer  = data.local_version  || '—';
        const remoteVer = data.remote_version || '—';
        const updateUrl = data.update_url     || '—';
        const isLatest  = localVer !== '—' && localVer === remoteVer;

        container.innerHTML = `
            <div class="admin-version-grid">
                <div class="admin-version-card">
                    <div class="label">Local Version</div>
                    <div class="value ${isLatest ? 'up-to-date' : 'outdated'}">${localVer}</div>
                </div>
                <div class="admin-version-card">
                    <div class="label">Remote Version</div>
                    <div class="value">${remoteVer}</div>
                </div>
                <div class="admin-version-card" style="grid-column: 1/-1;">
                    <div class="label">Update URL</div>
                    <div class="value" style="font-size:0.85em; word-break:break-all; color:#888;">${updateUrl}</div>
                </div>
            </div>
            ${isLatest ? '<p style="color:#4CAF50; font-size:0.85em; margin-top:6px;">✔ Firmware is up to date.</p>' : (localVer !== '—' ? '<p style="color:#FF9800; font-size:0.85em; margin-top:6px;">⚠ An update may be available.</p>' : '')}
        `;
    } catch (e) {
        container.innerHTML = '<em style="color:#666; font-size:0.9em;">Version info unavailable (device may not support this endpoint).</em>';
    }
}

async function triggerOTAUpdateAction(variant) {
    const actionName = variant === 'AUTO_FULL' ? 'Full Firmware Update' : 'SD Asset Repair';
    if (!confirm(`Trigger ${actionName} on the device? This will interrupt the current running mode.`)) return;

    try {
        const resp = await fetch('/api/actions/launch-mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode_id: 'OTA_UPDATER', variant: variant })
        });
        const data = await resp.json();

        if (resp.ok) {
            showStatus('adminOtaStatus', `🚀 ${actionName} launched. Check the device OLED for live progress.`, 'success');
        } else {
            showStatus('adminOtaStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('adminOtaStatus', 'Error: ' + e, 'error');
    }
}

// =====================================================
// ADMIN LAYOUT (mirror of loadLayout / saveLayout for Admin tab)
// =====================================================

let _adminLayoutData = {};

async function loadAdminLayout() {
    try {
        const resp = await fetch('/api/config/layout');
        _adminLayoutData = resp.ok ? await resp.json() : {};
    } catch (e) {
        _adminLayoutData = {};
    }
    _renderAdminLayout();
}

function _renderAdminLayout() {
    const controls = document.getElementById('adminLayoutControls');
    const canvas   = document.getElementById('adminLayoutCanvasContainer');
    if (!controls || !canvas) return;

    canvas.innerHTML = '<div style="position:absolute;top:calc(50% - 64px);left:calc(50% - 64px);width:128px;height:128px;background:rgba(0,150,255,0.1);border:2px solid #0096FF;display:flex;align-items:center;justify-content:center;color:#0096FF;font-weight:bold;font-size:0.85em;z-index:10;box-sizing:border-box;">CORE (0,0)</div>';
    controls.innerHTML = '<h4 style="margin-bottom:15px;color:#4CAF50;font-size:0.9em;">Offsets</h4>';

    const allSids = new Set([...Object.keys((_adminLayoutData.offsets)||{}), ...Object.keys((_adminLayoutData.live)||{})]);
    if (allSids.size === 0) {
        controls.innerHTML += '<em style="color:#666;">No satellites configured or connected.</em>';
        return;
    }

    Array.from(allSids).sort((a,b) => Number(a)-Number(b)).forEach(sid => {
        const saved = ((_adminLayoutData.offsets)||{})[sid] || { offset_x:0, offset_y:0 };
        const live  = ((_adminLayoutData.live)||{})[sid]    || { active:false, type:'OFFLINE/UNKNOWN' };
        const badgeClass = live.active ? 'online' : 'offline';
        const badgeText  = live.active ? 'ONLINE'  : 'OFFLINE';

        const row = document.createElement('div');
        row.style.cssText = 'margin-bottom:15px;padding:15px;background:#1a1a1a;border:1px solid #333;border-radius:4px;';
        row.innerHTML = `
            <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                <strong style="color:#e0e0e0;">SAT ${sid} <span style="font-weight:normal;color:#888;font-size:0.85em;">(${live.type})</span></strong>
                <span class="sat-badge ${badgeClass}">${badgeText}</span>
            </div>
            <div style="display:flex;gap:15px;">
                <div style="flex:1;"><label style="font-size:0.8em;">X Offset:</label>
                    <input type="number" id="alayout_x_${sid}" value="${saved.offset_x}" oninput="updateAdminCanvasPreview('${sid}')">
                </div>
                <div style="flex:1;"><label style="font-size:0.8em;">Y Offset:</label>
                    <input type="number" id="alayout_y_${sid}" value="${saved.offset_y}" oninput="updateAdminCanvasPreview('${sid}')">
                </div>
            </div>`;
        controls.appendChild(row);

        const satBox = document.createElement('div');
        satBox.id = `admin_canvas_sat_${sid}`;
        satBox.style.cssText = 'position:absolute;width:64px;height:128px;background:rgba(255,152,0,0.15);border:2px dashed #FF9800;display:flex;align-items:center;justify-content:center;color:#FF9800;font-weight:bold;font-size:0.85em;transition:top 0.1s ease,left 0.1s ease;box-sizing:border-box;';
        satBox.textContent = `SAT ${sid}`;
        canvas.appendChild(satBox);
        updateAdminCanvasPreview(sid);
    });
}

function updateAdminCanvasPreview(sid) {
    const xInput = document.getElementById(`alayout_x_${sid}`);
    const yInput = document.getElementById(`alayout_y_${sid}`);
    if (!xInput || !yInput) return;
    const x = parseInt(xInput.value) || 0;
    const y = parseInt(yInput.value) || 0;
    const satBox = document.getElementById(`admin_canvas_sat_${sid}`);
    if (satBox) {
        const scale = 8;
        satBox.style.left = `calc(50% - 64px + ${x * scale}px)`;
        satBox.style.top  = `calc(50% - 64px + ${y * scale}px)`;
    }
}

async function saveAdminLayout() {
    const payload = {};
    document.querySelectorAll('[id^="alayout_x_"]').forEach(xInput => {
        const sid = xInput.id.split('_')[2];
        const yInput = document.getElementById(`alayout_y_${sid}`);
        payload[sid] = { x: parseInt(xInput.value) || 0, y: parseInt(yInput.value) || 0 };
    });
    try {
        const resp = await fetch('/api/config/layout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (resp.ok) {
            showStatus('adminLayoutStatus', 'Layout saved to config & applied live!', 'success');
        } else {
            const data = await resp.json();
            showStatus('adminLayoutStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('adminLayoutStatus', 'Error: ' + e, 'error');
    }
}

async function loadSystemStatus() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();

        const html = `
            <div class="compact-info"><span>WiFi SSID</span> <strong>${data.wifi_ssid}</strong></div>
            <div class="compact-info"><span>IP Address</span> <strong>${data.ip_address}</strong></div>
            <div class="compact-info"><span>Debug Mode</span> <strong>${data.debug_mode ? 'ON' : 'OFF'}</strong></div>
            <div class="compact-info"><span>Uptime</span> <strong>${Math.floor(data.uptime)}s</strong></div>
            <div class="compact-info"><span>Free Memory</span> <strong>${Math.floor(data.free_memory / 1024)} KB</strong></div>
        `;
        document.getElementById('systemStatus').innerHTML = html;
    } catch (error) {
        showStatus('actionStatus', 'Error loading status: ' + error, 'error');
    }
}

let _currentConfigRaw = {};

// Keys to hide from the generic config tab because they have dedicated UI tabs
const CONFIG_IGNORE_KEYS = ['satellites'];

async function loadConfig() {
    try {
        const response = await fetch('/api/config/global');
        _currentConfigRaw = await response.json();

        const container = document.getElementById('dynamicConfigFields');
        container.innerHTML = '';

        // Sort keys alphabetically for a consistent UI
        const keys = Object.keys(_currentConfigRaw).sort();

        keys.forEach(key => {
            if (CONFIG_IGNORE_KEYS.includes(key)) return;

            const val = _currentConfigRaw[key];
            const type = typeof val;
            const prettyTopLabel = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

            // --- NESTED DICTIONARY CARD (1 Level Deep) ---
            if (type === 'object' && val !== null && !Array.isArray(val)) {
                let cardHtml = `
                    <div class="panel" style="margin: 5px 0 15px 0; padding: 15px; background: #1a1a1a; border: 1px solid #333; border-top: 3px solid #4CAF50;">
                        <h4 style="color: #e0e0e0; margin-bottom: 15px; font-size: 1.1em; letter-spacing: 0.05em;">${prettyTopLabel}</h4>
                        <div style="display: flex; flex-direction: column; gap: 12px;">
                `;

                // Iterate through the inside elements
                for (const [subKey, subVal] of Object.entries(val)) {
                    const subType = typeof subVal;
                    const subId = `cfg_${key}__${subKey}`;
                    const prettySubLabel = subKey.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                    let subInputHtml = '';

                    // Detect sub-types and append data-parent mapping attributes
                    if (subType === 'boolean') {
                        subInputHtml = `
                            <select id="${subId}" data-type="boolean" data-parent="${key}" data-key="${subKey}">
                                <option value="true" ${subVal ? 'selected' : ''}>Enabled</option>
                                <option value="false" ${!subVal ? 'selected' : ''}>Disabled</option>
                            </select>`;
                    } else if (subType === 'number') {
                        subInputHtml = `<input type="number" id="${subId}" value="${subVal}" data-type="number" step="any" data-parent="${key}" data-key="${subKey}">`;
                    } else {
                        const isPassword = subKey.toLowerCase().includes('password');
                        subInputHtml = `<input type="${isPassword ? 'password' : 'text'}" id="${subId}" value="${subVal !== null ? subVal : ''}" data-type="string" data-parent="${key}" data-key="${subKey}">`;
                    }

                    cardHtml += `
                        <div class="form-group" style="margin: 0;">
                            <label title="Internal key: ${key}.${subKey}" style="font-size: 0.85em;">${prettySubLabel}:</label>
                            ${subInputHtml}
                        </div>
                    `;
                }

                cardHtml += `</div></div>`;
                const row = document.createElement('div');
                row.innerHTML = cardHtml;
                container.appendChild(row);

            } else {
                // --- STANDARD TOP-LEVEL INPUTS & ARRAY FALLBACK ---
                let inputHtml = '';
                if (type === 'boolean') {
                    inputHtml = `
                        <select id="cfg_${key}" data-type="boolean" data-key="${key}">
                            <option value="true" ${val ? 'selected' : ''}>Enabled</option>
                            <option value="false" ${!val ? 'selected' : ''}>Disabled</option>
                        </select>`;
                } else if (type === 'number') {
                    inputHtml = `<input type="number" id="cfg_${key}" value="${val}" data-type="number" step="any" data-key="${key}">`;
                } else if (type === 'object' && val !== null) {
                    // Fallback for Arrays or complex structures (renders as raw JSON)
                    inputHtml = `<textarea id="cfg_${key}" data-type="object" data-key="${key}" rows="3" style="font-family: monospace;">${JSON.stringify(val, null, 2)}</textarea>`;
                } else {
                    const isPassword = key.toLowerCase().includes('password');
                    inputHtml = `<input type="${isPassword ? 'password' : 'text'}" id="cfg_${key}" value="${val || ''}" data-type="string" data-key="${key}">`;
                }

                const row = document.createElement('div');
                row.className = 'form-group';
                row.style.margin = '0';
                row.innerHTML = `
                    <label title="Internal key: ${key}">${prettyTopLabel}:</label>
                    ${inputHtml}
                `;
                container.appendChild(row);
            }
        });

        showStatus('configStatus', 'Configuration loaded', 'success');
    } catch (error) {
        showStatus('configStatus', 'Error loading config: ' + error, 'error');
    }
}

async function saveConfig() {
    try {
        const payload = {};
        const inputs = document.querySelectorAll('[id^="cfg_"]');

        inputs.forEach(el => {
            const parentKey = el.dataset.parent; // Identifies if this belongs inside a nested object
            const key = el.dataset.key;          // The actual setting key
            const type = el.dataset.type;

            let parsedVal;
            if (type === 'boolean') {
                parsedVal = (el.value === 'true');
            } else if (type === 'number') {
                parsedVal = Number(el.value);
            } else if (type === 'object') {
                try {
                    parsedVal = JSON.parse(el.value);
                } catch (e) {
                    console.warn(`Invalid JSON for ${key}, skipping.`);
                    return;
                }
            } else {
                parsedVal = el.value;
            }

            // Route the parsed value to the correct level of the payload dictionary
            if (parentKey) {
                if (!payload[parentKey]) payload[parentKey] = {};
                payload[parentKey][key] = parsedVal;
            } else {
                payload[key] = parsedVal;
            }
        });

        const response = await fetch('/api/config/global', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showStatus('configStatus', 'Configuration saved successfully', 'success');
            loadConfig(); // Refresh to ensure sync
        } else {
            const data = await response.json();
            showStatus('configStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        showStatus('configStatus', 'Error: ' + error, 'error');
    }
}

async function loadFiles() {
    try {
        const response = await fetch(`/api/files?path=${encodeURIComponent(currentPath)}`);
        const data = await response.json();

        const fileList = document.getElementById('fileList');
        fileList.innerHTML = '';

        // Add parent directory link if not at root
        if (currentPath !== '/sd' && currentPath !== '/') {
            const li = document.createElement('li');
            li.className = 'file-item';
            li.innerHTML = `
                <span>📁 ..</span>
                <button class="secondary" onclick="navigateUp()">Up</button>
            `;
            fileList.appendChild(li);
        }

        // Add files and directories
        data.items.forEach(item => {
            const li = document.createElement('li');
            li.className = 'file-item';
            const icon = item.is_dir ? '📁' : '📄';
            const size = item.is_dir ? '' : ` (${formatSize(item.size)})`;

            li.innerHTML = `
                <span>${icon} ${item.name}${size}</span>
                <div>
                    ${item.is_dir ?
                        `<button class="secondary" onclick="navigateTo('${item.path}')">Open</button>` :
                        `<button class="secondary" onclick="downloadFile('${item.path}')">Download</button>`
                    }
                </div>
            `;
            fileList.appendChild(li);
        });

        document.getElementById('currentPath').textContent = currentPath;
    } catch (error) {
        console.error('Error loading files:', error);
    }
}

function navigateTo(path) {
    currentPath = path;
    loadFiles();
}

function navigateUp() {
    const parts = currentPath.split('/');
    parts.pop();
    currentPath = parts.join('/') || '/';
    loadFiles();
}

function downloadFile(path) {
    window.location.href = `/api/files/download?path=${encodeURIComponent(path)}`;
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return Math.floor(bytes / 1024) + ' KB';
    return Math.floor(bytes / (1024 * 1024)) + ' MB';
}

const LOG_LEVEL_COLORS = {
    'DBUG': '#888',
    'INFO': '#4fc3f7',
    'NOTE': '#80deea',
    'WARN': '#ffcc02',
    'CRIT': '#ffa726',
    '!ERR': '#ef5350',
    'EMUL': '#ce93d8',
};

async function loadLogs() {
    try {
        const level = document.getElementById('logLevelFilter').value;
        const search = document.getElementById('logSearch').value.trim();
        let url = '/api/logs';
        const params = [];
        if (level !== '') params.push('level=' + encodeURIComponent(level));
        if (search) params.push('search=' + encodeURIComponent(search));
        if (params.length) url += '?' + params.join('&');

        const response = await fetch(url);
        const logs = await response.json();

        const logViewer = document.getElementById('logViewer');
        logViewer.innerHTML = '';

        logs.forEach(entry => {
            const line = document.createElement('div');
            const tag = entry.level_tag || '';
            const color = LOG_LEVEL_COLORS[tag] || '#e0e0e0';
            // Escape HTML to prevent XSS, then colorise
            const text = `[${entry.time}][${tag}][${entry.source}][${entry.module}] ${entry.message}`;
            const escaped = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;').replace(/"/g,'&quot;');
            line.innerHTML = `<span style="color:${color}">${escaped}</span>`;
            logViewer.appendChild(line);
        });

        if (logs.length === 0) {
            logViewer.textContent = 'No log entries.';
        }

        // Scroll to bottom
        logViewer.scrollTop = logViewer.scrollHeight;
    } catch (error) {
        document.getElementById('logViewer').textContent = 'Error loading logs: ' + error;
    }
}

async function clearLogs() {
    try {
        await fetch('/api/logs/clear', { method: 'POST' });
    } catch (_) {}
    document.getElementById('logViewer').textContent = '';
}

let _consoleAutoRefreshTimer = null;

function toggleConsoleAutoRefresh() {
    const enabled = document.getElementById('consoleAutoRefresh').checked;
    clearInterval(_consoleAutoRefreshTimer); // Safely kill any existing loop
    _consoleAutoRefreshTimer = null;

    if (enabled) {
        _consoleAutoRefreshTimer = setInterval(loadConsole, 2000);
    }
}

async function loadConsole() {
    try {
        const response = await fetch('/api/console');
        const data = await response.json();

        // Use textContent to prevent XSS attacks
        const consoleViewer = document.getElementById('consoleViewer');
        const atBottom = consoleViewer.scrollHeight - consoleViewer.scrollTop <= consoleViewer.clientHeight + 40; // 40px tolerance
        consoleViewer.textContent = data.output;
        if (atBottom) consoleViewer.scrollTop = consoleViewer.scrollHeight;
    } catch (error) {
        document.getElementById('consoleViewer').textContent = 'Error loading console: ' + error;
    }
}

async function sendConsoleInput() {
    const inputEl = document.getElementById('consoleInput');
    const line = inputEl.value.trim();
    if (!line) return;
    try {
        const response = await fetch('/api/console/input', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ input: line })
        });
        const data = await response.json();
        if (response.ok) {
            inputEl.value = '';
            setTimeout(loadConsole, 200);
        } else {
            showStatus('consoleStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        showStatus('consoleStatus', 'Error: ' + error, 'error');
    }
}

let currentSleepState = false;

function triggerReboot() {
    if (confirm("WARNING: This will restart the JEB Master Controller.\n\nAre you sure?")) {
        fetch('/api/action/reboot', { method: 'POST' })
            .then(() => {
                document.body.innerHTML = "<h1 style='text-align:center; margin-top:50px;'>Rebooting...</h1><p style='text-align:center;'>Please wait a few seconds and refresh the page.</p>";
            })
            .catch(err => console.error("Reboot error:", err));
    }
}

function toggleSleep() {
    const newState = !currentSleepState; // Flip the current state
    fetch('/api/action/sleep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sleep: newState })
    }).catch(err => console.error("Sleep toggle error:", err));
    // Note: We don't manually update the UI here. Telemetry will catch it and update it perfectly!
}

function triggerLED() {
    const payload = {
        index: parseInt(document.getElementById('ledActionIndex').value),
        color: document.getElementById('ledActionColor').value,
        anim: document.getElementById('ledActionAnim').value,
        speed: parseFloat(document.getElementById('ledActionSpeed').value)
    };

    fetch('/api/action/led', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).catch(err => console.error("LED trigger error:", err));
}

let _currentModeFilter = 'ALL';

function filterModes(menu, btn) {
    _currentModeFilter = menu;
    // Update filter button styles
    document.querySelectorAll('.mode-filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    // Show/hide mode cards
    document.querySelectorAll('.mode-card').forEach(card => {
        card.style.display = (menu === 'ALL' || card.dataset.menu === menu) ? '' : 'none';
    });
}

function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;').replace(/"/g,'&quot;');
}

async function loadModes() {
    try {
        const response = await fetch('/api/modes');
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const data = await response.json();

        // Show connected hardware
        const hwDiv = document.getElementById('modesHardware');
        const hwList = data.connected_hardware || ['CORE'];
        hwDiv.innerHTML = '<span style="color:#b0b0b0;">Connected hardware: </span>' +
            hwList.map(hw => `<span style="padding:1px 8px; background:#1a3a1a; border:1px solid #4CAF50; border-radius:3px; color:#4CAF50; font-size:0.85em; margin-right:4px;">${escapeHtml(hw)}</span>`).join('');

        const modesList = document.getElementById('modesList');
        modesList.innerHTML = '';

        const menuLabels = { CORE: 'Core', ZERO_PLAYER: 'Zero Player', EXP1: 'Industrial' };
        let currentMenu = null;

        for (const mode of (data.modes || [])) {
            // Menu section header
            if (mode.menu !== currentMenu) {
                currentMenu = mode.menu;
                const header = document.createElement('h3');
                header.textContent = menuLabels[currentMenu] || currentMenu;
                header.style.cssText = 'color:#888; font-size:0.85em; text-transform:uppercase; letter-spacing:2px; margin:18px 0 8px; padding-bottom:4px; border-bottom:1px solid #333;';
                header.dataset.menu = currentMenu;
                modesList.appendChild(header);
            }

            const modeDiv = document.createElement('div');
            modeDiv.className = 'mode-card';
            modeDiv.dataset.menu = mode.menu;
            modeDiv.style.cssText = 'margin-bottom:10px; padding:12px 14px; background:#1a1a1a; border-radius:5px; border-left:3px solid ' + (mode.playable ? '#4CAF50' : '#444') + ';';

            // Header row: name + hardware badges + action buttons
            let html = '<div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">';
            html += '<div style="flex:1;">';
            html += `<span style="font-weight:bold; color:${mode.playable ? '#e0e0e0' : '#888'};">${escapeHtml(mode.name)}</span>`;
            // Requires badges
            (mode.requires || []).forEach(hw => {
                html += ` <span style="padding:1px 5px; background:#222; border:1px solid ${mode.playable ? '#555' : '#333'}; border-radius:3px; font-size:0.75em; color:#888;">${escapeHtml(hw)}</span>`;
            });
            // Optional badges
            (mode.optional || []).forEach(hw => {
                html += ` <span style="padding:1px 5px; background:#1a1a1a; border:1px solid #333; border-radius:3px; font-size:0.75em; color:#555;" title="Optional">${escapeHtml(hw)}</span>`;
            });
            html += '</div>';

            // Action buttons
            html += '<div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center;">';
            if (mode.playable) {
                html += `<button onclick="launchMode('${escapeHtml(mode.id)}', false)" style="background:#1e3e1e; border-color:#4CAF50; color:#4CAF50; padding:4px 10px;">▶ Launch</button>`;
                if (mode.has_tutorial) {
                    html += `<button onclick="launchMode('${escapeHtml(mode.id)}', true)" style="background:#12283c; border-color:#4fc3f7; color:#4fc3f7; padding:4px 10px;">📖 Tutorial</button>`;
                }
            }
            if ((mode.settings || []).length > 0) {
                html += `<button onclick="saveModeSettings('${escapeHtml(mode.id)}')" style="background:#2a2a2a; padding:4px 10px;">💾 Save</button>`;
            }
            html += '</div>';
            html += '</div>';

            // Settings row
            if ((mode.settings || []).length > 0) {
                html += '<div style="margin-top:8px; display:flex; flex-wrap:wrap; gap:10px;">';
                mode.settings.forEach(setting => {
                    const current = mode.current || {};
                    const currentValue = current[setting.key] !== undefined ? current[setting.key] : setting.default;
                    html += `<div class="form-group" style="margin:0; min-width:120px;">`;
                    html += `<label style="font-size:0.82em; color:#aaa;">${escapeHtml(setting.label)}:</label>`;
                    html += `<select id="${escapeHtml(mode.id)}_${escapeHtml(setting.key)}">`;
                    (setting.options || []).forEach(opt => {
                        html += `<option value="${escapeHtml(opt)}"${opt === currentValue ? ' selected' : ''}>${escapeHtml(opt)}</option>`;
                    });
                    html += '</select></div>';
                });
                html += '</div>';
            }

            modeDiv.innerHTML = html;
            modesList.appendChild(modeDiv);
        }

        // Apply active filter
        filterModes(_currentModeFilter, null);

    } catch (error) {
        showStatus('modesStatus', 'Error loading modes: ' + error, 'error');
    }
}

async function launchMode(modeId, tutorial) {
    const label = tutorial ? 'tutorial' : 'main game';
    if (!confirm(`Launch "${modeId}" (${label}) on device?`)) return;
    try {
        const response = await fetch('/api/actions/launch-mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode_id: modeId, tutorial: tutorial })
        });
        const result = await response.json();
        if (response.ok) {
            showStatus('modesStatus', `Launching ${modeId} (${label}) on device…`, 'success');
        } else {
            showStatus('modesStatus', 'Error: ' + (result.error || 'Unknown'), 'error');
        }
    } catch (error) {
        showStatus('modesStatus', 'Error: ' + error, 'error');
    }
}

async function saveModeSettings(modeId) {
    try {
        // Collect all settings for this mode
        const settings = {};
        document.querySelectorAll(`[id^="${modeId}_"]`).forEach(elem => {
            const key = elem.id.replace(`${modeId}_`, '');
            settings[key] = elem.value;
        });

        const response = await fetch('/api/config/modes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode_id: modeId, settings: settings })
        });

        if (response.ok) {
            showStatus('modesStatus', `${escapeHtml(modeId)} settings saved`, 'success');
            loadModes();
        } else {
            showStatus('modesStatus', 'Error saving settings', 'error');
        }
    } catch (error) {
        showStatus('modesStatus', 'Error: ' + error, 'error');
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('fileUpload');
    const file = fileInput.files[0];

    if (!file) {
        alert('Please select a file first');
        return;
    }

    try {
        const reader = new FileReader();
        reader.onload = async (e) => {
            const content = e.target.result;

            const response = await fetch(
                `/api/files/upload?path=${encodeURIComponent(currentPath)}&filename=${encodeURIComponent(file.name)}`,
                {
                    method: 'POST',
                    body: content
                }
            );

            if (response.ok) {
                alert(`File ${file.name} uploaded successfully`);
                loadFiles();  // Refresh file list
            } else {
                const data = await response.json();
                alert('Upload failed: ' + data.error);
            }
        };
        reader.readAsArrayBuffer(file);
    } catch (error) {
        alert('Upload error: ' + error);
    }
}

function showStatus(elementId, message, type) {
    const status = document.getElementById(elementId);
    status.textContent = message;
    status.className = 'status ' + type;
    status.style.display = 'block';
    setTimeout(() => {
        status.style.display = 'none';
    }, 5000);
}

// --- Telemetry / Polling ---
let _telemetryTimer = null;
const _voltageHistory = {};
const CHART_MAX_POINTS = 60;
const VOLTAGE_LABELS = {
    input_20v:  'Input (20V)',
    satbus_20v: 'SatBus (20V)',
    main_5v:    'Logic (5V)',
    led_5v:     'LED (5V)',
};

// Hardware Topology Visualizer state (declared here so _topoRender() is safe to call early)
let _topoSatData = {};
let _topoPulses = [];
let _topoRafId = null;
let _topoInitialized = false;
let _topoXOff = 0;              // Centering offset updated each render frame
const _TOPO_NODE_R = 36;        // Node circle radius
const _TOPO_H_STEP = 170;       // Horizontal spacing between nodes
const _TOPO_ORIGIN_X = 75;      // X of the Core node
const _TOPO_H = 200;            // Canvas internal height
const _lastPulseSpawn = {};


async function fetchTelemetry() {
    try {
        const response = await fetch('/api/telemetry/status');
        if (response.ok) {
            const data = await response.json();
            updateTelemetryUI(data);

            const el = document.getElementById('telemetryStatus');
            el.textContent = 'Connected';
            el.className = 'telemetry-status connected';
        }
    } catch (err) {
        const el = document.getElementById('telemetryStatus');
        el.textContent = 'Reconnecting…';
        el.className = 'telemetry-status disconnected';
    }
}

function startTelemetry() {
    if (_telemetryTimer) return; // Already polling
    fetchTelemetry(); // Fetch immediately
    _telemetryTimer = setInterval(fetchTelemetry, 1000); // Poll every 1 second
}

function stopTelemetry() {
    if (_telemetryTimer) {
        clearInterval(_telemetryTimer);
        _telemetryTimer = null;
    }
    const el = document.getElementById('telemetryStatus');
    el.textContent = 'Disconnected';
    el.className = 'telemetry-status disconnected';
}

function updateTelemetryUI(data) {
    // --- System State Sync ---
    if (data.system !== undefined) {
        currentSleepState = data.system.sleeping;
        const sleepBtn = document.getElementById('btnSleepToggle');

        if (currentSleepState) {
            sleepBtn.textContent = "Wake System";
            sleepBtn.style.background = "#FF9800"; // Orange when asleep
        } else {
            sleepBtn.textContent = "Put to Sleep";
            sleepBtn.style.background = "#555";    // Grey when awake
        }

        const ramEl = document.getElementById('sysRam');
        if (ramEl && data.system.free_ram_kb !== undefined) {
            if (data.system.free_ram_kb === "Emulator") {
                ramEl.textContent = "Unlimited (Emulator)";
                ramEl.style.color = "#9C27B0"; // Purple for emulator
            } else {
                const ramVal = data.system.free_ram_kb;
                ramEl.textContent = ramVal.toFixed(1) + " KB";

                // Color coding based on Pico 2W thresholds
                if (ramVal < 40) {
                    ramEl.style.color = "#f44336"; // Red (Danger - GC struggles here)
                } else if (ramVal < 80) {
                    ramEl.style.color = "#ff9800"; // Orange (Warning)
                } else {
                    ramEl.style.color = "#4CAF50"; // Green (Healthy)
                }
            }
        }
    }

    // --- Voltage cards ---
    const power = data.power || {};
    const voltEl = document.getElementById('telemetryVoltages');
    let html = '';

    // Only draw cards for buses that actually exist in the payload
    const powerKeys = Object.keys(power);
    if (powerKeys.length === 0) {
        html = '<em style="color: #666;">No power data available</em>';
    } else {
        for (const [key, val] of Object.entries(power)) {
            if (val === undefined || val === null) continue;

            // Look up the pretty label, or default to the raw dictionary key
            const label = VOLTAGE_LABELS[key] || key;
            html += `<div class="info-card"><h3>${label}</h3><div class="value">${Number(val).toFixed(2)} V</div></div>`;
        }
    }
    voltEl.innerHTML = html;

    // --- Hardware Topology Visualizer ---
    const sats = data.satellites || {};
    drawTopologyMap(sats);

    // --- Sparkline charts for ALL voltages ---
    const chartsContainer = document.getElementById('telemetryCharts');
    for (const [key, val] of Object.entries(power)) {
        if (val === undefined || val === null) continue;

        if (!_voltageHistory[key]) _voltageHistory[key] = [];
        _voltageHistory[key].push(Number(val));
        if (_voltageHistory[key].length > CHART_MAX_POINTS) {
            _voltageHistory[key].shift();
        }

        let canvasId = 'chart_' + key;
        let canvas = document.getElementById(canvasId);

        // Dynamically create the canvas if it doesn't exist yet
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.id = canvasId;
            canvas.className = 'sparkline';
            canvas.width = 600;
            canvas.height = 90; // Slightly shorter to fit multiple cleanly on screen
            chartsContainer.appendChild(canvas);
        }

        const label = VOLTAGE_LABELS[key] || key;
        drawSparkline(canvasId, _voltageHistory[key], label);
    }

    // --- Remote HID interface ---
    rebuildHIDInterface(data.satellites);
}

function drawSparkline(canvasId, values, label) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (values.length < 2) return;

    const min = Math.min(...values) - 0.5;
    const max = Math.max(...values) + 0.5;
    const range = max - min || 1;

    // Grid lines
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    [0.25, 0.5, 0.75].forEach(frac => {
        const y = Math.round(h * frac) + 0.5;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    });

    // Line
    ctx.strokeStyle = '#4CAF50';
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((v, i) => {
        const x = (i / (CHART_MAX_POINTS - 1)) * w;
        const y = h - ((v - min) / range) * (h - 10) - 5;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Label
    ctx.fillStyle = '#b0b0b0';
    ctx.font = '11px monospace';
    ctx.fillText(`${label}  max:${Math.max(...values).toFixed(2)}V  min:${Math.min(...values).toFixed(2)}V`, 6, 14);
}

// Auto-load initial data
loadSystemStatus();
startTelemetry();

// Draw topology canvas in its empty state so it's visible before telemetry connects
_topoRender();

// --- Pixel Art Studio ---
const GRID_SIZE = 16;
let pixelData = new Array(GRID_SIZE * GRID_SIZE).fill(0);
let selectedColorIndex = 0;
let selectedColorRGB = '#000000';
let paletteColors = {};
let pixelArtInitialized = false;
let pixelLibraryLoaded = false;
let isDrawing = false;

// --- Animation state ---
let animFrames = [new Array(GRID_SIZE * GRID_SIZE).fill(0)];
let animDurations = [150]; // Track ms duration per frame
let currentFrameIndex = 0;
let animPlaying = false;
let animPlayTimeout = null;
let playbackFrameIdx = 0;
let onionSkinEnabled = false;
let isMatrixPushing = false; // Lock to prevent network flooding

function rgbToHex(r, g, b) {
    return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
}

async function initPixelArtStudio() {
    if (pixelArtInitialized) return;
    pixelArtInitialized = true;

    // Build the 16x16 grid with dynamic column count for resolution independence
    const grid = document.getElementById('pixelGrid');
    grid.innerHTML = '';
    grid.style.gridTemplateColumns = `repeat(${GRID_SIZE}, 1fr)`;
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < GRID_SIZE * GRID_SIZE; i++) {
        const cell = document.createElement('div');
        cell.className = 'pixel-cell';
        cell.dataset.index = i;
        fragment.appendChild(cell);
    }
    grid.appendChild(fragment);

    // Size the onion skin canvas to match the pixel grid
    _resizeOnionCanvas();

    // Fetch palette from server
    try {
        const resp = await fetch('/api/pixel-art/palette');
        paletteColors = await resp.json();
    } catch (e) {
        // Fallback minimal palette if server unavailable.
        // Indices match the JEB palette: 0=OFF, 11=RED, 41=GREEN, 61=BLUE
        paletteColors = {'0': {name:'OFF',r:0,g:0,b:0}, '11': {name:'RED',r:255,g:0,b:0}, '41': {name:'GREEN',r:0,g:200,b:0}, '61': {name:'BLUE',r:0,g:0,b:255}};
    }

    // Build palette swatches
    const paletteGrid = document.getElementById('paletteGrid');
    paletteGrid.innerHTML = '';
    for (const [idx, color] of Object.entries(paletteColors)) {
        const swatch = document.createElement('div');
        swatch.className = 'palette-swatch' + (parseInt(idx) === 0 ? ' selected' : '');
        const hex = rgbToHex(color.r, color.g, color.b);
        swatch.style.background = parseInt(idx) === 0 ? '#111' : hex;
        swatch.title = `${idx}: ${color.name}`;
        swatch.dataset.index = idx;
        swatch.onclick = () => selectColor(parseInt(idx));
        paletteGrid.appendChild(swatch);
    }

    // Initialise with a single blank frame
    animFrames = [new Array(GRID_SIZE * GRID_SIZE).fill(0)];
    animDurations = [150];
    currentFrameIndex = 0;
    pixelData = animFrames[0];
    renderTimeline();

    if (!pixelLibraryLoaded) {
        loadPixelLibrary();
    }
}

function _resizeOnionCanvas() {
    const canvas = document.getElementById('onionSkinCanvas');
    const grid = document.getElementById('pixelGrid');
    if (!canvas || !grid) return;
    const rect = grid.getBoundingClientRect();
    canvas.width = GRID_SIZE;
    canvas.height = GRID_SIZE;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
}

function selectColor(idx) {
    selectedColorIndex = idx;
    const color = paletteColors[String(idx)];
    if (!color) return;
    const hex = (idx === 0) ? '#000000' : rgbToHex(color.r, color.g, color.b);
    selectedColorRGB = hex;
    document.getElementById('selectedColorName').textContent = `${idx}: ${color.name}`;
    document.getElementById('selectedColorPreview').style.background = hex;
    // Update swatch borders
    document.querySelectorAll('.palette-swatch').forEach(s => {
        s.classList.toggle('selected', parseInt(s.dataset.index) === idx);
    });
}

function paintCell(index) {
    if (index < 0 || index >= GRID_SIZE * GRID_SIZE) return;
    pixelData[index] = selectedColorIndex;
    const cell = document.querySelector(`.pixel-cell[data-index="${index}"]`);
    if (cell) {
        const color = paletteColors[String(selectedColorIndex)];
        if (selectedColorIndex === 0 || !color) {
            cell.style.background = '#000';
        } else {
            cell.style.background = rgbToHex(color.r, color.g, color.b);
        }
    }
}

function getCellIndexFromEvent(e) {
    const target = e.target;
    if (target && target.dataset && target.dataset.index !== undefined) {
        return parseInt(target.dataset.index);
    }
    return -1;
}

function pixelMouseDown(e) {
    isDrawing = true;
    const idx = getCellIndexFromEvent(e);
    if (idx >= 0) paintCell(idx);
}

function pixelMouseMove(e) {
    const idx = getCellIndexFromEvent(e);
    if (isDrawing && idx >= 0) paintCell(idx);
    _updatePixelTooltip(e, idx);
}

function pixelMouseUp() {
    isDrawing = false;
}

function pixelMouseLeave() {
    isDrawing = false;
    const tip = document.getElementById('pixelTooltip');
    if (tip) tip.style.display = 'none';
}

function _updatePixelTooltip(e, idx) {
    const tip = document.getElementById('pixelTooltip');
    if (!tip) return;
    if (idx < 0) {
        tip.style.display = 'none';
        return;
    }
    const x = idx % GRID_SIZE;
    const y = Math.floor(idx / GRID_SIZE);
    const colorIdx = pixelData[idx];
    const color = paletteColors[String(colorIdx)];
    let colorInfo = 'OFF';
    if (color && colorIdx !== 0) {
        const hex = rgbToHex(color.r, color.g, color.b);
        colorInfo = `${color.name}  ${hex.toUpperCase()}  rgb(${color.r},${color.g},${color.b})`;
    }
    tip.textContent = `(${x}, ${y})  ${colorInfo}`;
    tip.style.display = 'block';
    tip.style.left = (e.clientX + 14) + 'px';
    tip.style.top  = (e.clientY + 14) + 'px';
}

function clearCanvas() {
    pixelData.fill(0);
    document.querySelectorAll('.pixel-cell').forEach(cell => {
        cell.style.background = '#000';
    });
    renderThumbnail(currentFrameIndex);
    if (onionSkinEnabled) renderOnionSkin();
}

// =====================================================================
// Animation Frame Management
// =====================================================================

function _renderFrameToCanvas(frameData, canvas) {
    const ctx = canvas.getContext('2d');
    canvas.width = GRID_SIZE;
    canvas.height = GRID_SIZE;
    for (let i = 0; i < GRID_SIZE * GRID_SIZE; i++) {
        const v = frameData[i];
        const color = paletteColors[String(v)];
        if (v === 0 || !color) {
            ctx.fillStyle = '#000';
        } else {
            ctx.fillStyle = rgbToHex(color.r, color.g, color.b);
        }
        const x = i % GRID_SIZE;
        const y = Math.floor(i / GRID_SIZE);
        ctx.fillRect(x, y, 1, 1);
    }
}

function renderThumbnail(frameIdx) {
    const thumb = document.querySelector(`.anim-frame-thumb[data-frame="${frameIdx}"]`);
    if (!thumb) return;
    const canvas = thumb.querySelector('canvas');
    if (!canvas) return;
    _renderFrameToCanvas(animFrames[frameIdx], canvas);
}

function renderTimeline() {
    const timeline = document.getElementById('animTimeline');
    if (!timeline) return;
    timeline.innerHTML = '';
    animFrames.forEach((frame, i) => {
        const thumb = document.createElement('div');
        thumb.className = 'anim-frame-thumb' + (i === currentFrameIndex ? ' active' : '');
        thumb.dataset.frame = i;
        thumb.title = `Frame ${i + 1}`;
        thumb.onclick = () => selectFrame(i);

        const canvas = document.createElement('canvas');
        canvas.width = GRID_SIZE;
        canvas.height = GRID_SIZE;
        canvas.style.imageRendering = 'pixelated';
        thumb.appendChild(canvas);

        const label = document.createElement('div');
        label.className = 'anim-frame-label';
        label.textContent = i + 1;
        thumb.appendChild(label);

        timeline.appendChild(thumb);
        _renderFrameToCanvas(frame, canvas);
    });
}

function selectFrame(idx) {
    if (idx < 0 || idx >= animFrames.length) return;
    // Save current canvas state back to current frame before switching
    animFrames[currentFrameIndex] = pixelData.slice();
    renderThumbnail(currentFrameIndex);

    currentFrameIndex = idx;
    pixelData = animFrames[currentFrameIndex];

    // Update duration UI for this frame
    const durInput = document.getElementById('animDuration');
    if (durInput) durInput.value = animDurations[currentFrameIndex] || 150;

    // Refresh canvas display
    for (let i = 0; i < GRID_SIZE * GRID_SIZE; i++) {
        const cell = document.querySelector(`.pixel-cell[data-index="${i}"]`);
        if (!cell) continue;
        const v = pixelData[i];
        const color = paletteColors[String(v)];
        if (v === 0 || !color) {
            cell.style.background = '#000';
        } else {
            cell.style.background = rgbToHex(color.r, color.g, color.b);
        }
    }

    // Update active highlight in timeline
    document.querySelectorAll('.anim-frame-thumb').forEach(t => {
        t.classList.toggle('active', parseInt(t.dataset.frame) === currentFrameIndex);
    });

    if (onionSkinEnabled) renderOnionSkin();
}

function updateFrameDuration(val) {
    animDurations[currentFrameIndex] = parseInt(val) || 150;
}

function animAddFrame() {
    animFrames[currentFrameIndex] = pixelData.slice();
    const newFrame = new Array(GRID_SIZE * GRID_SIZE).fill(0);
    animFrames.splice(currentFrameIndex + 1, 0, newFrame);
    animDurations.splice(currentFrameIndex + 1, 0, 150);
    renderTimeline();
    selectFrame(currentFrameIndex + 1);
}

function animDuplicateFrame() {
    animFrames[currentFrameIndex] = pixelData.slice();
    const copy = animFrames[currentFrameIndex].slice();
    animFrames.splice(currentFrameIndex + 1, 0, copy);
    animDurations.splice(currentFrameIndex + 1, 0, animDurations[currentFrameIndex]);
    renderTimeline();
    selectFrame(currentFrameIndex + 1);
}

function animDeleteFrame() {
    if (animFrames.length <= 1) {
        clearCanvas();
        return;
    }
    animFrames.splice(currentFrameIndex, 1);
    animDurations.splice(currentFrameIndex, 1);
    const newIdx = Math.min(currentFrameIndex, animFrames.length - 1);
    currentFrameIndex = newIdx;
    pixelData = animFrames[currentFrameIndex];
    renderTimeline();
    selectFrame(currentFrameIndex);
}

function animMoveFrame(dir) {
    const target = currentFrameIndex + dir;
    if (target < 0 || target >= animFrames.length) return;
    animFrames[currentFrameIndex] = pixelData.slice();

    const tmp = animFrames[currentFrameIndex];
    animFrames[currentFrameIndex] = animFrames[target];
    animFrames[target] = tmp;

    const tmpDur = animDurations[currentFrameIndex];
    animDurations[currentFrameIndex] = animDurations[target];
    animDurations[target] = tmpDur;

    renderTimeline();
    selectFrame(target);
}

// =====================================================================
// Onion Skinning
// =====================================================================

function toggleOnionSkin(enabled) {
    onionSkinEnabled = enabled;
    const canvas = document.getElementById('onionSkinCanvas');
    if (!canvas) return;
    if (enabled) {
        _resizeOnionCanvas();
        canvas.style.display = 'block';
        renderOnionSkin();
    } else {
        canvas.style.display = 'none';
    }
}

function renderOnionSkin() {
    const canvas = document.getElementById('onionSkinCanvas');
    if (!canvas || !onionSkinEnabled) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (currentFrameIndex === 0) return;

    const prevFrame = animFrames[currentFrameIndex - 1];
    ctx.globalAlpha = 0.3;
    for (let i = 0; i < GRID_SIZE * GRID_SIZE; i++) {
        const v = prevFrame[i];
        if (v === 0) continue;
        const color = paletteColors[String(v)];
        if (!color) continue;
        ctx.fillStyle = rgbToHex(color.r, color.g, color.b);
        const x = i % GRID_SIZE;
        const y = Math.floor(i / GRID_SIZE);
        ctx.fillRect(x, y, 1, 1);
    }
    ctx.globalAlpha = 1.0;
}

// =====================================================================
// Animation Playback
// =====================================================================

// =====================================================================
// Animation Playback
// =====================================================================

function animPlay() {
    if (animPlaying) return;
    if (animFrames.length < 2) {
        showStatus('pixelArtStatus', 'Add at least 2 frames to play an animation', 'error');
        return;
    }
    animFrames[currentFrameIndex] = pixelData.slice();
    animPlaying = true;
    document.getElementById('animPlayBtn').textContent = '⏸ Playing…';

    // Temporarily hide onion skin
    const onionCanvas = document.getElementById('onionSkinCanvas');
    if (onionCanvas) onionCanvas.style.opacity = '0';

    playbackFrameIdx = 0;
    _playNextFrame();
}

function _playNextFrame() {
    if (!animPlaying) return;
    selectFrame(playbackFrameIdx);
    _pushAnimFrameToMatrix(animFrames[playbackFrameIdx], playbackFrameIdx);

    // Get current frame duration and schedule next
    const duration = animDurations[playbackFrameIdx] || 150;
    playbackFrameIdx = (playbackFrameIdx + 1) % animFrames.length;

    animPlayTimeout = setTimeout(_playNextFrame, duration);
}

function animStop() {
    if (animPlayTimeout !== null) {
        clearTimeout(animPlayTimeout);
        animPlayTimeout = null;
    }
    animPlaying = false;
    const btn = document.getElementById('animPlayBtn');
    if (btn) btn.textContent = '▶ Play';

    // Restore onion skin
    const onionCanvas = document.getElementById('onionSkinCanvas');
    if (onionCanvas) onionCanvas.style.opacity = '1';
}

async function _pushAnimFrameToMatrix(frame, frameNum) {
    if (isMatrixPushing) return;
    isMatrixPushing = true;
    try {
        await fetch('/api/pixel-art/preview-animation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pixels: Array.from(frame), frame: frameNum})
        });
    } catch (_) {
        // Ignore errors during playback
    } finally {
        isMatrixPushing = false;
    }
}

async function previewPixelArt() {
    try {
        const resp = await fetch('/api/pixel-art/preview', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pixels: pixelData})
        });
        const data = await resp.json();
        if (resp.ok && data.status === 'success') {
            showStatus('pixelArtStatus', 'Preview sent to matrix!', 'success');
        } else if (data.status === 'no_matrix') {
            showStatus('pixelArtStatus', 'Matrix not connected to web server', 'error');
        } else {
            showStatus('pixelArtStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('pixelArtStatus', 'Error: ' + e, 'error');
    }
}

async function savePixelArt() {
    const name = document.getElementById('iconName').value.trim();
    if (!name) {
        showStatus('pixelArtStatus', 'Please enter an icon name', 'error');
        return;
    }
    try {
        const resp = await fetch('/api/pixel-art/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, pixels: pixelData})
        });
        const data = await resp.json();
        if (resp.ok && data.status === 'success') {
            showStatus('pixelArtStatus', `Saved to ${data.path}`, 'success');
            // Refresh SD card list so the newly saved file appears immediately
            loadPixelLibrary(true);
        } else {
            showStatus('pixelArtStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('pixelArtStatus', 'Error: ' + e, 'error');
    }
}

async function saveAnimation() {
    const name = document.getElementById('iconName').value.trim();
    if (!name) {
        showStatus('pixelArtStatus', 'Please enter a name for the animation', 'error');
        return;
    }
    if (animFrames.length < 1) {
        showStatus('pixelArtStatus', 'No frames to save', 'error');
        return;
    }
    // Flush current canvas edits back into the frame array
    animFrames[currentFrameIndex] = pixelData.slice();

    const frameCount = animFrames.length;

    // V2 spec: JANM + frame_count + (16-bit duration + 256 pixel bytes) per frame
    const bufSize = 5 + frameCount * 258;
    const buf = new Uint8Array(bufSize);
    buf[0] = 0x4A; // J
    buf[1] = 0x41; // A
    buf[2] = 0x4E; // N
    buf[3] = 0x4D; // M
    buf[4] = frameCount;

    for (let f = 0; f < frameCount; f++) {
        const offset = 5 + f * 258;
        const durationMs = animDurations[f] || 150;
        buf[offset] = durationMs & 0xFF;           // Little endian low byte
        buf[offset + 1] = (durationMs >> 8) & 0xFF; // Little endian high byte

        for (let i = 0; i < 256; i++) {
            buf[offset + 2 + i] = animFrames[f][i] & 0xFF;
        }
    }

    try {
        const resp = await fetch('/api/pixel-art/save-animation?name=' + encodeURIComponent(name), {
            method: 'POST',
            headers: {'Content-Type': 'application/octet-stream'},
            body: buf
        });
        const data = await resp.json();
        if (resp.ok && data.status === 'success') {
            showStatus('pixelArtStatus', `Animation saved to ${data.path} (${data.frames} frames)`, 'success');
            loadPixelLibrary(true);
        } else {
            showStatus('pixelArtStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('pixelArtStatus', 'Error: ' + e, 'error');
    }
}

// --- Pixel Library & Asset Loading ---

async function loadPixelLibrary(force = false) {
    if (pixelLibraryLoaded && !force) return;
    try {
        const resp = await fetch('/api/pixel/library');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        pixelLibraryLoaded = true;

        // Populate icons.py library dropdown
        const libSelect = document.getElementById('iconLibSelect');
        if (libSelect) {
            libSelect.innerHTML = '';
            if (data.icons && data.icons.length > 0) {
                const defOpt = document.createElement('option');
                defOpt.value = '';
                defOpt.textContent = 'Select icon…';
                libSelect.appendChild(defOpt);
                data.icons.forEach(name => {
                    const opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = name;
                    libSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No icons available';
                libSelect.appendChild(opt);
            }
        }

        // Populate SD card .bin dropdown
        const binSelect = document.getElementById('iconBinSelect');
        if (binSelect) {
            binSelect.innerHTML = '';
            if (data.bins && data.bins.length > 0) {
                const defOpt = document.createElement('option');
                defOpt.value = '';
                defOpt.textContent = 'Select file…';
                binSelect.appendChild(defOpt);
                data.bins.forEach(filename => {
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = filename;
                    binSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No .bin files on SD';
                binSelect.appendChild(opt);
            }
        }

        // Populate SD card .janim dropdown
        const janimSelect = document.getElementById('iconJanimSelect');
        if (janimSelect) {
            janimSelect.innerHTML = '';
            if (data.janims && data.janims.length > 0) {
                const defOpt = document.createElement('option');
                defOpt.value = '';
                defOpt.textContent = 'Select file…';
                janimSelect.appendChild(defOpt);
                data.janims.forEach(filename => {
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = filename;
                    janimSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No .janim files on SD';
                janimSelect.appendChild(opt);
            }
        }
    } catch (e) {
        pixelLibraryLoaded = false;
        const libSelect = document.getElementById('iconLibSelect');
        if (libSelect) libSelect.innerHTML = '<option value="">Error loading library</option>';
        const binSelect = document.getElementById('iconBinSelect');
        if (binSelect) binSelect.innerHTML = '<option value="">Error loading library</option>';
        const janimSelect = document.getElementById('iconJanimSelect');
        if (janimSelect) janimSelect.innerHTML = '<option value="">Error loading library</option>';
    }
}

async function pixelLoadIcon(source) {
    if (source === 'lib') {
        const select = document.getElementById('iconLibSelect');
        const name = select ? select.value : '';
        if (!name) {
            showStatus('pixelArtStatus', 'Please select an icon from the library', 'error');
            return;
        }
        // Load hardcoded icon: fetch the binary file by requesting the icon name
        // The server resolves it from the Icons class and returns raw bytes
        try {
            const resp = await fetch('/api/pixel/load?name=' + encodeURIComponent(name));
            if (!resp.ok) {
                let errMsg = 'Unknown error';
                try { const errData = await resp.json(); errMsg = errData.error || errMsg; } catch (_) {}
                throw new Error(errMsg);
            }
            const buf = await resp.arrayBuffer();
            _applyPixelBuffer(new Uint8Array(buf));
            // Library icons don't have a user-facing filename; leave the save field as-is
            showStatus('pixelArtStatus', `📂 Loaded ${name} from icons.py`, 'success');
        } catch (e) {
            showStatus('pixelArtStatus', 'Error loading icon: ' + e.message, 'error');
        }
    } else if (source === 'janim') {
        const select = document.getElementById('iconJanimSelect');
        const filename = select ? select.value : '';
        if (!filename) {
            showStatus('pixelArtStatus', 'Please select a .janim file from the SD card', 'error');
            return;
        }
        try {
            const resp = await fetch('/api/pixel/load?name=' + encodeURIComponent(filename));
            if (!resp.ok) {
                let errMsg = 'Unknown error';
                try { const errData = await resp.json(); errMsg = errData.error || errMsg; } catch (_) {}
                throw new Error(errMsg);
            }
            const buf = await resp.arrayBuffer();
            _applyAnimBuffer(new Uint8Array(buf), filename);
        } catch (e) {
            showStatus('pixelArtStatus', 'Error loading animation: ' + e.message, 'error');
        }
    } else {
        const select = document.getElementById('iconBinSelect');
        const filename = select ? select.value : '';
        if (!filename) {
            showStatus('pixelArtStatus', 'Please select a .bin file from the SD card', 'error');
            return;
        }
        try {
            const resp = await fetch('/api/pixel/load?name=' + encodeURIComponent(filename));
            if (!resp.ok) {
                let errMsg = 'Unknown error';
                try { const errData = await resp.json(); errMsg = errData.error || errMsg; } catch (_) {}
                throw new Error(errMsg);
            }
            const buf = await resp.arrayBuffer();
            _applyPixelBuffer(new Uint8Array(buf));
            // Auto-populate the save-as name so the user can overwrite in one click
            const baseName = filename.replace(/\.bin$/i, '');
            document.getElementById('iconName').value = baseName;
            showStatus('pixelArtStatus', `📂 Loaded ${filename}`, 'success');
        } catch (e) {
            showStatus('pixelArtStatus', 'Error loading icon: ' + e.message, 'error');
        }
    }
}

function _applyPixelBuffer(bytes) {
    if (bytes.length < GRID_SIZE * GRID_SIZE) {
        showStatus('pixelArtStatus', `Error: file too small (${bytes.length} bytes, expected ${GRID_SIZE * GRID_SIZE})`, 'error');
        return;
    }
    // Replace current frame with the loaded data and reset to single-frame mode
    const frame = Array.from(bytes.subarray(0, GRID_SIZE * GRID_SIZE));
    animFrames = [frame];
    currentFrameIndex = 0;
    pixelData = animFrames[0];
    for (let i = 0; i < GRID_SIZE * GRID_SIZE; i++) {
        const v = pixelData[i];
        const cell = document.querySelector(`.pixel-cell[data-index="${i}"]`);
        if (cell) {
            if (v === 0) {
                cell.style.background = '#000';
            } else {
                const color = paletteColors[String(v)];
                cell.style.background = color ? rgbToHex(color.r, color.g, color.b) : '#000';
            }
        }
    }
    renderTimeline();
}

function _applyAnimBuffer(bytes, filename) {
    // Parse V2 .janim binary
    const minSize = 5 + 258;
    if (bytes.length < minSize) {
        showStatus('pixelArtStatus', `Error: file too small to be a valid .janim (${bytes.length} bytes)`, 'error');
        return;
    }
    const magic = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
    if (magic !== 'JANM') {
        showStatus('pixelArtStatus', 'Error: not a valid .janim file (bad magic bytes)', 'error');
        return;
    }
    const frameCount = bytes[4];
    const expectedSize = 5 + frameCount * 258;
    if (bytes.length < expectedSize) {
        showStatus('pixelArtStatus', `Error: truncated .janim file (${bytes.length} bytes, expected ${expectedSize})`, 'error');
        return;
    }

    animFrames = [];
    animDurations = [];
    for (let f = 0; f < frameCount; f++) {
        const offset = 5 + f * 258;
        const durationMs = bytes[offset] | (bytes[offset + 1] << 8); // Reconstruct 16-bit duration
        animDurations.push(durationMs);
        animFrames.push(Array.from(bytes.subarray(offset + 2, offset + 258)));
    }
    currentFrameIndex = 0;
    pixelData = animFrames[0];

    const baseName = filename.replace(/\.janim$/i, '');
    document.getElementById('iconName').value = baseName;

    // Refresh canvas to show frame 0
    for (let i = 0; i < GRID_SIZE * GRID_SIZE; i++) {
        const v = pixelData[i];
        const cell = document.querySelector(`.pixel-cell[data-index="${i}"]`);
        if (cell) {
            if (v === 0) {
                cell.style.background = '#000';
            } else {
                const color = paletteColors[String(v)];
                cell.style.background = color ? rgbToHex(color.r, color.g, color.b) : '#000';
            }
        }
    }
    renderTimeline();
    showStatus('pixelArtStatus', `📂 Loaded ${filename} (${frameCount} frames)`, 'success');
}

// =====================================================================
// Audio Studio - Dynamic Timeline Sequencer
// =====================================================================
const AUDIO_NUM_CHANNELS = 3;
const BASE_RES = 0.125;  // Core data resolution locked to 1/32nd notes
const BASE_WIDTH = 14;   // Physical CSS width of 1/32nd block (px)
const GAP = 2;           // Physical CSS gap between blocks (px)

const JSEQ_PATCH_NAMES = [
    'RETRO_LEAD', 'RETRO_BASS', 'RETRO_NOISE',
    'BEEP', 'BEEP_SQUARE', 'PAD', 'PUNCH',
    'ALARM', 'SCANNER', 'CLICK', 'NOISE', 'SELECT',
];

const AUDIO_OCTAVES = [2, 3, 4, 5, 6, 7];
const AUDIO_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

const DURATION_OPTIONS = [
    ['𝅘𝅥𝅰 1/32', 0.125], ['𝅘𝅥𝅯 1/16', 0.25],
    ['♪ 1/8', 0.5], ['♪. Dot 1/8', 0.75],
    ['♩ 1/4', 1.0], ['♩. Dot 1/4', 1.5],
    ['𝅗𝅥 1/2', 2.0], ['𝅝 1/1', 4.0],
];

// Grid Configuration State
let audioBars = 2;
let audioRes = 0.25;       // Visual Snap Resolution
let audioNumSteps = 64;    // Calculated strictly on BASE_RES

let audioSteps = [];
let audioChannelPatches = [];
let activeNote = null;
let activeDuration = 1.0;
let audioStudioInitialized = false;
let audioLibraryLoaded = false;

function initAudioStudio() {
    if (!audioStudioInitialized) {
        audioStudioInitialized = true;

        for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
            audioSteps.push(new Array(audioNumSteps).fill(null));
            audioChannelPatches.push(JSEQ_PATCH_NAMES[c] || 'SELECT');
        }

        _buildNotePicker();
        _buildDurationPicker();
        _resizeGrid();
    }

    if (!audioLibraryLoaded) {
        loadAudioLibrary();
    }
}

function updateGridConfig() {
    audioBars = parseInt(document.getElementById('audioBarsInput').value) || 2;
    audioRes = parseFloat(document.getElementById('audioResInput').value) || 0.25;
    _resizeGrid();
}

function _resizeGrid() {
    audioNumSteps = Math.round((audioBars * 4) / BASE_RES);

    for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
        if (!audioSteps[c]) audioSteps[c] = [];
        audioSteps[c].length = audioNumSteps;

        for(let s = 0; s < audioNumSteps; s++) {
            if (audioSteps[c][s] === undefined) audioSteps[c][s] = null;
        }

        // Truncate notes that overshoot the new global timeline length
        for (let s = audioNumSteps - 1; s >= 0; s--) {
            const cell = audioSteps[c][s];
            if (cell && cell.note !== undefined) {
                if (s + cell.span > audioNumSteps) {
                    cell.span = audioNumSteps - s;
                    cell.duration = cell.span * BASE_RES;
                }
                break;
            }
        }
    }

    _buildGridHeader();
    const container = document.getElementById('channelRows');
    container.innerHTML = '';

    for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
        const row = document.createElement('div');
        row.className = 'channel-row';
        row.style.cssText = 'display: flex; flex-wrap: nowrap; align-items: center; margin-bottom: 6px;';

        const controls = document.createElement('div');
        controls.style.cssText = 'display: flex; gap: 5px; flex: 0 0 140px;';

        const lbl = document.createElement('div');
        lbl.className = 'channel-label';
        lbl.textContent = `Ch${c + 1}`;
        controls.appendChild(lbl);

        const sel = document.createElement('select');
        sel.className = 'channel-patch';
        sel.style.width = '90px';
        JSEQ_PATCH_NAMES.forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            if (name === audioChannelPatches[c]) opt.selected = true;
            sel.appendChild(opt);
        });
        sel.onchange = () => { audioChannelPatches[c] = sel.value; };
        controls.appendChild(sel);

        row.appendChild(controls);

        const grid = document.createElement('div');
        grid.id = `stepGrid_${c}`;
        grid.style.cssText = 'display: flex; flex-wrap: nowrap; gap: 2px;';
        row.appendChild(grid);
        container.appendChild(row);

        _renderChannel(c);
    }
}

function _buildGridHeader() {
    const header = document.getElementById('audioGridHeader');
    header.innerHTML = '';

    const spacer = document.createElement('div');
    spacer.style.flex = '0 0 148px';
    header.appendChild(spacer);

    const gridHeader = document.createElement('div');
    gridHeader.style.cssText = 'display: flex; gap: 2px;';

    // Draw the ruler based on the user's visual Snap setting
    const snapSteps = Math.round((audioBars * 4) / audioRes);
    const snapSpan = Math.round(audioRes / BASE_RES);

    for (let i = 0; i < snapSteps; i++) {
        const beatFloat = (i * audioRes);
        const isBeatStart = beatFloat % 1 === 0;

        const div = document.createElement('div');
        const w = snapSpan * BASE_WIDTH + (snapSpan - 1) * GAP;
        div.style.flex = `0 0 ${w}px`;
        div.style.fontSize = '0.7em';
        div.style.color = isBeatStart ? '#888' : '#444';
        div.style.textAlign = 'center';
        div.style.borderLeft = isBeatStart ? '1px solid #555' : '1px solid #222';
        div.textContent = isBeatStart ? Math.floor(beatFloat) + 1 : '';
        gridHeader.appendChild(div);
    }
    header.appendChild(gridHeader);
}

let audioTooltip = null;

function _getNoteFreq(noteName) {
    if (!noteName || noteName === '-') return 0;
    const semitones = { 'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11 };
    const m = noteName.match(/^([A-G]#?)(\d+)$/);
    if (!m) return 0;

    // Calculate standard MIDI index, then convert to Hz (A4 = 69 = 440Hz)
    const midi = (parseInt(m[2]) + 1) * 12 + semitones[m[1]];
    return (440.0 * Math.pow(2.0, (midi - 69) / 12.0)).toFixed(1);
}

function _showTooltip(e, text) {
    if (!audioTooltip) {
        audioTooltip = document.createElement('div');
        audioTooltip.style.position = 'absolute';
        audioTooltip.style.background = '#222';
        audioTooltip.style.color = '#ddd';
        audioTooltip.style.padding = '8px 12px';
        audioTooltip.style.borderRadius = '4px';
        audioTooltip.style.fontSize = '0.85em';
        audioTooltip.style.fontFamily = 'monospace';
        audioTooltip.style.pointerEvents = 'none'; // Prevents flickering
        audioTooltip.style.zIndex = '9999';
        audioTooltip.style.whiteSpace = 'pre';
        audioTooltip.style.border = '1px solid #555';
        audioTooltip.style.boxShadow = '0 4px 8px rgba(0,0,0,0.4)';
        document.body.appendChild(audioTooltip);
    }
    audioTooltip.textContent = text;
    audioTooltip.style.display = 'block';
    // Offset slightly so it doesn't block the cursor
    audioTooltip.style.left = (e.pageX + 15) + 'px';
    audioTooltip.style.top = (e.pageY + 15) + 'px';
}

function _hideTooltip() {
    if (audioTooltip) audioTooltip.style.display = 'none';
}

function _getNoteColor(noteName) {
    if (!noteName || noteName === '-') return { bg: '#444', border: '#666', text: '#999' };

    const semitones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const m = noteName.match(/^([A-G]#?)(\d+)$/);
    if (!m) return { bg: '#444', border: '#666', text: '#999' };

    const noteIdx = semitones.indexOf(m[1]);
    const octave = parseInt(m[2]);

    // Hue: Spread the 12 notes evenly around the 360° color wheel
    const hue = noteIdx * 30;

    // Lightness: Octave 2 = 35% (Dark), Octave 7 = 85% (Bright/Pastel)
    const lightness = 15 + (octave * 10);

    // High contrast text: Dark text for bright high notes, white text for dark low notes
    const textColor = lightness > 55 ? 'rgba(0,0,0,0.85)' : 'rgba(255,255,255,0.95)';

    return {
        bg: `hsl(${hue}, 80%, ${lightness}%)`,
        border: `hsl(${hue}, 80%, ${lightness - 15}%)`,
        text: textColor
    };
}

function _renderChannel(ch) {
    const gridEl = document.getElementById(`stepGrid_${ch}`);
    if (!gridEl) return;
    gridEl.innerHTML = '';

    const snapSpan = Math.round(audioRes / BASE_RES);

    for (let s = 0; s < audioNumSteps; ) {
        const cell = audioSteps[ch][s];
        if (cell && cell.covered) { s++; continue; }

        const btn = document.createElement('button');
        let span = 1;
        let isActive = false;
        let label = '—';

       if (cell && cell.note !== undefined) {
            span = cell.span;
            isActive = true;

            // Render dotted indicator if note aligns with standard dotted times
            let displayLabel = cell.note || '—';
            if (cell.note && (cell.duration === 0.75 || cell.duration === 1.5 || cell.duration === 3.0)) {
                displayLabel += ' •';
            }
            label = displayLabel;

            btn.className = 'step-btn active';

            // Apply the dynamic HSL colors
            const colors = _getNoteColor(cell.note);
            btn.style.background = colors.bg;
            btn.style.borderColor = colors.border;
            btn.style.color = colors.text;
            btn.style.fontWeight = 'bold';

            // Add a subtle text shadow so the labels pop against the colored background
            if (cell.note) {
                btn.style.textShadow = colors.text.includes('0,0,0')
                    ? '0px 1px 1px rgba(255,255,255,0.3)'
                    : '0px 1px 2px rgba(0,0,0,0.6)';
            }

            // --- NEW: Add Tooltip Hover Events ---
            if (cell.note) {
                const freq = _getNoteFreq(cell.note);
                const tooltipText = `Note: ${cell.note}\nFreq: ${freq} Hz\nDur:  ${cell.duration} Beats`;
                btn.onmousemove = (e) => _showTooltip(e, tooltipText);
                btn.onmouseleave = _hideTooltip;
            } else {
                const tooltipText = `Rest\nDur:  ${cell.duration} Beats`;
                btn.onmousemove = (e) => _showTooltip(e, tooltipText);
                btn.onmouseleave = _hideTooltip;
            }
        } else {
            // Group empty 1/32nd blocks into larger clickable "Snap" targets
            let nextBoundary = Math.ceil((s + 1) / snapSpan) * snapSpan;
            if (nextBoundary > audioNumSteps) nextBoundary = audioNumSteps;
            span = nextBoundary - s;

            // Stop grouping if we hit a note
            for (let k = 1; k < span; k++) {
                if (audioSteps[ch][s + k] && audioSteps[ch][s + k].note !== undefined) {
                    span = k;
                    break;
                }
            }
            btn.className = 'step-btn';
        }

        const w = span * BASE_WIDTH + (span - 1) * GAP;
        btn.style.flex = `0 0 ${w}px`;
        btn.style.height = '36px';
        btn.style.boxSizing = 'border-box';
        btn.style.overflow = 'hidden';
        btn.style.cursor = 'pointer';
        btn.textContent = label;

        const clickIndex = s;
        btn.onclick = () => _toggleStep(ch, clickIndex);

        gridEl.appendChild(btn);
        s += span;
    }
}

function _toggleStep(ch, s) {
    const cell = audioSteps[ch][s];

    if (cell && cell.note !== undefined && cell.note === activeNote && cell.duration === activeDuration) {
        for(let i=0; i<cell.span; i++) audioSteps[ch][s+i] = null;
        _renderChannel(ch);
        return;
    }

    const span = Math.min(Math.max(1, Math.round(activeDuration / BASE_RES)), audioNumSteps - s);

    for (let i = s - 1; i >= 0; i--) {
        const earlier = audioSteps[ch][i];
        if (earlier && earlier.note !== undefined) {
            if (i + earlier.span > s) {
                earlier.span = s - i;
                earlier.duration = earlier.span * BASE_RES;
                for(let k = s; k < i + earlier.span; k++) {
                    if(audioSteps[ch][k] && audioSteps[ch][k].covered) audioSteps[ch][k] = null;
                }
            }
            break;
        }
    }

    for (let i = s; i < s + span; i++) {
        const existing = audioSteps[ch][i];
        if (existing && existing.note !== undefined) {
            for(let k = i + 1; k < i + existing.span; k++) {
                if(audioSteps[ch][k] && audioSteps[ch][k].covered) audioSteps[ch][k] = null;
            }
        }

        if (i === s) {
            audioSteps[ch][i] = { note: activeNote, duration: span * BASE_RES, span: span };
        } else {
            audioSteps[ch][i] = { covered: true };
        }
    }

    _renderChannel(ch);
}

function _buildNotePicker() {
    const picker = document.getElementById('notePicker');
    picker.innerHTML = '';
    const restBtn = document.createElement('button');
    restBtn.className = 'note-pick-btn rest';
    restBtn.textContent = '— Rest';
    restBtn.onclick = () => _selectNote(null);
    picker.appendChild(restBtn);
    AUDIO_OCTAVES.forEach(oct => {
        AUDIO_NOTE_NAMES.forEach(n => {
            const noteName = n + oct;
            const btn = document.createElement('button');
            btn.className = 'note-pick-btn';
            btn.textContent = noteName;
            btn.id = `notePick_${noteName}`;
            btn.onclick = () => _selectNote(noteName);
            picker.appendChild(btn);
        });
    });
}

function _buildDurationPicker() {
    const picker = document.getElementById('durationPicker');
    picker.innerHTML = '';
    DURATION_OPTIONS.forEach(([label, beats]) => {
        const btn = document.createElement('button');
        btn.className = 'dur-btn' + (beats === activeDuration ? ' selected' : '');
        btn.textContent = label;
        btn.onclick = () => _selectDuration(beats, label, btn);
        picker.appendChild(btn);
    });
}

function _selectNote(noteName) {
    activeNote = noteName;
    document.getElementById('activeNoteLabel').textContent = noteName || '— Rest';
    document.querySelectorAll('.note-pick-btn').forEach(b => b.classList.remove('selected'));
    if (noteName) {
        const btn = document.getElementById(`notePick_${noteName}`);
        if (btn) btn.classList.add('selected');
    } else {
        document.querySelectorAll('.note-pick-btn.rest').forEach(b => b.classList.add('selected'));
    }
}

function _selectDuration(beats, label, clickedBtn) {
    activeDuration = beats;
    document.getElementById('activeDurLabel').textContent = label;
    document.querySelectorAll('.dur-btn').forEach(b => b.classList.remove('selected'));
    clickedBtn.classList.add('selected');
}

function audioClearAll() {
    for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
        audioSteps[c] = new Array(audioNumSteps).fill(null);
        _renderChannel(c);
    }
}

function _buildSequenceForChannel(ch) {
    let sequence = [];
    let accumulatedRest = 0;

    for (let s = 0; s < audioNumSteps; s++) {
        const cell = audioSteps[ch][s];
        if (!cell) {
            accumulatedRest += BASE_RES;
        } else if (cell.covered) {
            continue;
        } else if (cell.note !== undefined) {
            while (accumulatedRest > 0) {
                const chunk = Math.min(4.0, accumulatedRest);
                sequence.push(['-', chunk]);
                accumulatedRest -= chunk;
            }
            sequence.push([cell.note || '-', cell.duration]);
        }
    }

    while (accumulatedRest > 0) {
        const chunk = Math.min(4.0, accumulatedRest);
        sequence.push(['-', chunk]);
        accumulatedRest -= chunk;
    }
    return sequence;
}

function _buildPreviewPayload() {
    const bpm = parseInt(document.getElementById('audioBpm').value) || 120;
    const channels = [];
    for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
        channels.push({
            patch: audioChannelPatches[c],
            sequence: _buildSequenceForChannel(c)
        });
    }
    return { bpm, channels };
}

async function audioPreview() {
    try {
        const resp = await fetch('/api/synth/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_buildPreviewPayload()),
        });
        const data = await resp.json();
        if (resp.ok && data.status === 'success') {
            showStatus('audioStatus', '▶ Preview started on device', 'success');
        } else {
            showStatus('audioStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('audioStatus', 'Error: ' + e, 'error');
    }
}

async function audioStop() {
    browserStopAll();
    try {
        await fetch('/api/synth/stop', { method: 'POST' });
        showStatus('audioStatus', '■ Playback stopped', 'success');
    } catch (e) { }
}

function _noteToJseqIndex(noteName) {
    if (!noteName || noteName === '-') return 0;
    const semitones = { 'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11 };
    const m = noteName.match(/^([A-G]#?)(\d+)$/);
    if (!m) return 0;
    const midi = (parseInt(m[2]) + 1) * 12 + (semitones[m[1]] !== undefined ? semitones[m[1]] : 0);
    return midi + 1;
}

function _jseqIndexToNote(index) {
    if (index === 0) return null;
    const midi = index - 1;
    const octave = Math.floor(midi / 12) - 1;
    const semitones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    return semitones[midi % 12] + octave;
}

function _durationToJseqUnits(beats) {
    return Math.max(1, Math.min(255, Math.round(beats * 32)));
}

function _jseqUnitsToDuration(units) {
    return units / 32.0;
}

function _encodeJseq() {
    const bpm = parseInt(document.getElementById('audioBpm').value) || 120;
    const compiledChannels = [];
    let size = 8;

    for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
        const seq = _buildSequenceForChannel(c);
        compiledChannels.push(seq);
        size += 3 + seq.length * 2;
    }

    const buf = new ArrayBuffer(size);
    const view = new DataView(buf);
    let pos = 0;

    view.setUint8(pos++, 0x4A); view.setUint8(pos++, 0x53);
    view.setUint8(pos++, 0x45); view.setUint8(pos++, 0x51);
    view.setUint8(pos++, 1);
    view.setUint16(pos, bpm, true); pos += 2;
    view.setUint8(pos++, AUDIO_NUM_CHANNELS);

    for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
        const patchIdx = JSEQ_PATCH_NAMES.indexOf(audioChannelPatches[c]);
        view.setUint8(pos++, patchIdx >= 0 ? patchIdx : 0);

        const seq = compiledChannels[c];
        view.setUint16(pos, seq.length, true); pos += 2;

        for (let i = 0; i < seq.length; i++) {
            const step = seq[i];
            view.setUint8(pos++, step[0] === '-' ? 0 : _noteToJseqIndex(step[0]));
            view.setUint8(pos++, _durationToJseqUnits(step[1]));
        }
    }
    return buf;
}

function _bufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

async function audioSave() {
    const name = document.getElementById('audioSeqName').value.trim();
    if (!name) return showStatus('audioStatus', 'Please enter a sequence name', 'error');

    try {
        const base64Data = _bufferToBase64(_encodeJseq());
        const resp = await fetch(`/api/synth/save?name=${encodeURIComponent(name)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'text/plain' },
            body: base64Data,
        });
        const data = await resp.json();
        if (resp.ok) {
            showStatus('audioStatus', `💾 Saved to ${data.path}`, 'success');
            loadAudioLibrary(true);
        } else showStatus('audioStatus', 'Error: ' + data.error, 'error');
    } catch (e) {
        showStatus('audioStatus', 'Error: ' + e, 'error');
    }
}

async function audioLoad() {
    const select = document.getElementById('jseqSelect');
    const filename = select ? select.value : '';
    if (!filename) return showStatus('audioStatus', 'Please select a sequence to load', 'error');

    try {
        const resp = await fetch('/api/synth/load?name=' + encodeURIComponent(filename));
        if (!resp.ok) throw new Error(await resp.text());

        const buf = await resp.arrayBuffer();
        const view = new DataView(buf);
        let pos = 0;

        if (buf.byteLength < 8) throw new Error("File too small");
        if (view.getUint8(pos++) !== 0x4A || view.getUint8(pos++) !== 0x53 ||
            view.getUint8(pos++) !== 0x45 || view.getUint8(pos++) !== 0x51) {
            throw new Error("Invalid .jseq magic bytes");
        }

        const version = view.getUint8(pos++);
        document.getElementById('audioBpm').value = view.getUint16(pos, true); pos += 2;
        const numChannels = view.getUint8(pos++);

        let maxBeats = 4;
        let minDur = 0.25;
        const loadedChannels = [];

        for (let c = 0; c < numChannels; c++) {
            if (pos + 3 > buf.byteLength) {
                console.warn("JSEQ file truncated at channel header");
                break;
            }

            const patchName = JSEQ_PATCH_NAMES[view.getUint8(pos++)] || 'SELECT';
            const numSteps = view.getUint16(pos, true); pos += 2;

            let chanBeats = 0;
            const seq = [];

            for (let s = 0; s < numSteps; s++) {
                if (pos + 2 > buf.byteLength) {
                    console.warn(`File truncated at Ch ${c+1} Step ${s+1}.`);
                    break;
                }

                const noteIdx = view.getUint8(pos++);
                const dur = _jseqUnitsToDuration(view.getUint8(pos++));

                if (dur > 0 && dur < minDur) minDur = dur;
                chanBeats += dur;
                seq.push({ note: _jseqIndexToNote(noteIdx), dur });
            }
            if (chanBeats > maxBeats) maxBeats = chanBeats;
            loadedChannels.push({ patch: patchName, seq });
        }

        document.getElementById('audioBarsInput').value = Math.max(1, Math.ceil(maxBeats / 4));
        if (minDur <= 0.125) document.getElementById('audioResInput').value = 0.125;
        else if (minDur <= 0.25) document.getElementById('audioResInput').value = 0.25;
        else document.getElementById('audioResInput').value = 0.5;

        updateGridConfig();
        audioClearAll();

        for (let c = 0; c < loadedChannels.length; c++) {
            if (c >= AUDIO_NUM_CHANNELS) break;

            audioChannelPatches[c] = loadedChannels[c].patch;
            const patchSelect = document.querySelector(`#stepGrid_${c}`).parentElement.querySelector('select');
            if (patchSelect) patchSelect.value = loadedChannels[c].patch;

            let currentStep = 0;
            for (const item of loadedChannels[c].seq) {
                const span = Math.round(item.dur / BASE_RES);
                if (currentStep + span > audioNumSteps) break;

                if (item.note) {
                    audioSteps[c][currentStep] = { note: item.note, duration: item.dur, span: span };
                    for (let i = 1; i < span; i++) {
                        audioSteps[c][currentStep + i] = { covered: true };
                    }
                }
                currentStep += span;
            }
            _renderChannel(c);
        }

        document.getElementById('audioSeqName').value = filename.replace('.jseq', '');
        showStatus('audioStatus', '📂 Loaded ' + filename, 'success');

    } catch (e) {
        showStatus('audioStatus', 'Error loading sequence: ' + e.message, 'error');
    }
}

// --- Audio Library & Asset Playback ---

async function loadAudioLibrary(force = false) {
    if (audioLibraryLoaded && !force) return;
    try {
        const resp = await fetch('/api/audio/library');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();
        audioLibraryLoaded = true;

        // Populate tone select
        const toneSelect = document.getElementById('toneSelect');
        if (toneSelect) {
            toneSelect.innerHTML = '';
            if (data.tones && data.tones.length > 0) {
                data.tones.forEach(name => {
                    const opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = name;
                    toneSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No tones available';
                toneSelect.appendChild(opt);
            }
        }

        // Populate WAV select
        const wavSelect = document.getElementById('wavSelect');
        if (wavSelect) {
            wavSelect.innerHTML = '';
            if (data.wavs && data.wavs.length > 0) {
                data.wavs.forEach(filename => {
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = filename;
                    wavSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No WAV files found';
                wavSelect.appendChild(opt);
            }
        }

        // Populate JSEQ select
        const jseqSelect = document.getElementById('jseqSelect');
        if (jseqSelect) {
            jseqSelect.innerHTML = '';
            if (data.jseqs && data.jseqs.length > 0) {
                const defOpt = document.createElement('option');
                defOpt.value = '';
                defOpt.textContent = 'Select sequence...';
                jseqSelect.appendChild(defOpt);
                data.jseqs.forEach(filename => {
                    const opt = document.createElement('option');
                    opt.value = filename;
                    opt.textContent = filename;
                    jseqSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = 'No .jseq files found';
                jseqSelect.appendChild(opt);
            }
        }
    } catch (e) {
        // Reset flag so the user can retry by switching away and back to the tab
        audioLibraryLoaded = false;
        const toneSelect = document.getElementById('toneSelect');
        if (toneSelect) toneSelect.innerHTML = '<option value="">Error loading library</option>';
        const wavSelect = document.getElementById('wavSelect');
        if (wavSelect) wavSelect.innerHTML = '<option value="">Error loading library</option>';
        const jseqSelect = document.getElementById('jseqSelect');
        if (jseqSelect) jseqSelect.innerHTML = '<option value="">Error loading library</option>';
    }
}

async function playTone() {
    const select = document.getElementById('toneSelect');
    const name = select ? select.value : '';
    if (!name) {
        showStatus('toneStatus', 'Please select a tone', 'error');
        return;
    }
    const targetEl = document.querySelector('input[name="toneTarget"]:checked');
    const target = targetEl ? targetEl.value : 'synth';
    try {
        const resp = await fetch('/api/audio/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'tone', name, target }),
        });
        const data = await resp.json();
        if (resp.ok && data.status === 'success') {
            showStatus('toneStatus', `▶ Playing "${name}" on ${target}`, 'success');
        } else if (data.status === 'no_buzzer') {
            showStatus('toneStatus', 'Buzzer manager not connected', 'error');
        } else if (data.status === 'no_synth') {
            showStatus('toneStatus', 'Synth manager not connected', 'error');
        } else {
            showStatus('toneStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('toneStatus', 'Error: ' + e, 'error');
    }
}

async function playWav() {
    const select = document.getElementById('wavSelect');
    const filename = select ? select.value : '';
    if (!filename) {
        showStatus('wavStatus', 'Please select a WAV file', 'error');
        return;
    }
    try {
        const resp = await fetch('/api/audio/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'wav', filename }),
        });
        const data = await resp.json();
        if (resp.ok && data.status === 'success') {
            showStatus('wavStatus', `▶ Playing "${filename}"`, 'success');
        } else if (data.status === 'no_audio') {
            showStatus('wavStatus', 'Audio manager not connected', 'error');
        } else {
            showStatus('wavStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (e) {
        showStatus('wavStatus', 'Error: ' + e, 'error');
    }
}

// =====================================================================
// Browser Audio Emulator (Web Audio API)
// =====================================================================

let _webAudioCtx = null;
let _browserActiveNodes = [];
let _browserNoiseBuffer = null; // Shared noise buffer, generated once per AudioContext
let _browserPlayheadRaf = null; // requestAnimationFrame handle for the playback cursor

function _getAudioContext() {
    if (!_webAudioCtx || _webAudioCtx.state === 'closed') {
        _webAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
        _browserNoiseBuffer = null; // Invalidate cached buffer when context is recreated
    }
    if (_webAudioCtx.state === 'suspended') {
        _webAudioCtx.resume();
    }
    return _webAudioCtx;
}

// Maps JSEQ patch names to Web Audio oscillator types and ADSR parameters.
// ADSR values mirror the synthio Envelopes defined in synth_registry.py.
const BROWSER_PATCHES = {
    'RETRO_LEAD':  { type: 'square',   attack: 0.01,  decay: 0.0,  sustain: 0.8, release: 0.1,  attackLevel: 0.8 },
    'RETRO_BASS':  { type: 'triangle', attack: 0.01,  decay: 0.0,  sustain: 0.8, release: 0.1,  attackLevel: 0.8 },
    'RETRO_NOISE': { type: 'noise',    attack: 0.001, decay: 0.05, sustain: 0.0, release: 0.02, attackLevel: 0.6 },
    'BEEP':        { type: 'sine',     attack: 0.01,  decay: 0.0,  sustain: 1.0, release: 0.1,  attackLevel: 1.0 },
    'BEEP_SQUARE': { type: 'square',   attack: 0.01,  decay: 0.0,  sustain: 1.0, release: 0.1,  attackLevel: 1.0 },
    'PAD':         { type: 'triangle', attack: 0.5,   decay: 0.2,  sustain: 0.8, release: 0.5,  attackLevel: 0.8 },
    'PUNCH':       { type: 'sawtooth', attack: 0.005, decay: 0.1,  sustain: 0.6, release: 0.1,  attackLevel: 1.0 },
    'ALARM':       { type: 'sawtooth', attack: 0.01,  decay: 0.0,  sustain: 1.0, release: 0.1,  attackLevel: 1.0 },
    'SCANNER':     { type: 'triangle', attack: 0.01,  decay: 0.0,  sustain: 1.0, release: 0.1,  attackLevel: 1.0 },
    'CLICK':       { type: 'square',   attack: 0.001, decay: 0.05, sustain: 0.0, release: 0.05, attackLevel: 1.0 },
    'NOISE':       { type: 'noise',    attack: 0.01,  decay: 0.15, sustain: 0.0, release: 0.1,  attackLevel: 1.0 },
    'SELECT':      { type: 'square',   attack: 0.001, decay: 0.05, sustain: 0.0, release: 0.05, attackLevel: 1.0 },
};

/** Generate a shared noise AudioBuffer for the current AudioContext (created once). */
function _browserGetNoiseBuffer(audioCtx) {
    if (!_browserNoiseBuffer) {
        // 2 seconds of noise is enough to cover any single note duration at low BPM.
        const sampleRate = audioCtx.sampleRate;
        const frameCount = sampleRate * 2;
        _browserNoiseBuffer = audioCtx.createBuffer(1, frameCount, sampleRate);
        const data = _browserNoiseBuffer.getChannelData(0);
        for (let i = 0; i < frameCount; i++) {
            data[i] = Math.random() * 2 - 1;
        }
    }
    return _browserNoiseBuffer;
}

/**
 * Schedule a single note via Web Audio API.
 * Uses an OscillatorNode (or noise BufferSourceNode) routed through a
 * GainNode with ADSR automation for click-free attack and release.
 */
function _browserScheduleNote(audioCtx, freq, patchName, startTime, durationSec) {
    const patch = BROWSER_PATCHES[patchName] || BROWSER_PATCHES['BEEP'];
    const { type, attack, decay, sustain, release, attackLevel } = patch;
    const isNoise = (type === 'noise');
    const noteDuration = Math.max(durationSec, 0.01);
    const stopTime = startTime + noteDuration + release;

    const gainNode = audioCtx.createGain();
    gainNode.gain.setValueAtTime(0, startTime);
    gainNode.gain.linearRampToValueAtTime(attackLevel, startTime + attack);
    // Always schedule the decay endpoint to avoid a gain discontinuity (audible click)
    // even when decay === 0 (the ramp collapses to an instant step via setValueAtTime).
    const decayEnd = startTime + attack + Math.max(decay, 0);
    const sustainLevel = sustain * attackLevel;
    if (decay > 0) {
        gainNode.gain.linearRampToValueAtTime(sustainLevel, decayEnd);
    } else {
        gainNode.gain.setValueAtTime(sustainLevel, decayEnd);
    }
    const sustainEnd = startTime + noteDuration;
    gainNode.gain.setValueAtTime(sustainLevel, sustainEnd);
    gainNode.gain.linearRampToValueAtTime(0, stopTime);
    gainNode.connect(audioCtx.destination);

    if (isNoise) {
        const src = audioCtx.createBufferSource();
        // Reuse the shared noise buffer; loop it in case the note is longer than 2 s.
        src.buffer = _browserGetNoiseBuffer(audioCtx);
        src.loop = true;
        src.connect(gainNode);
        src.start(startTime);
        src.stop(stopTime);
        _browserActiveNodes.push(src);
    } else {
        const osc = audioCtx.createOscillator();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, startTime);
        osc.connect(gainNode);
        osc.start(startTime);
        osc.stop(stopTime);
        _browserActiveNodes.push(osc);
    }
    _browserActiveNodes.push(gainNode);
}

/** Semitone offsets from C for each note name, shared by note-name helpers. */
const _NOTE_SEMITONES = { 'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11 };

/** Convert a JSEQ note index (0 = rest, 1 = MIDI 0) to a frequency in Hz. */
function _jseqIndexToFreq(index) {
    if (!index || index === 0) return 0;
    const midi = index - 1;
    return 440.0 * Math.pow(2, (midi - 69) / 12.0);
}

/** Stop all scheduled browser audio nodes and close the AudioContext. */
function browserStopAll() {
    _browserStopPlayhead();
    _browserActiveNodes.forEach(node => {
        // Errors here are expected: nodes may have already finished naturally.
        try { node.stop ? node.stop() : node.disconnect(); } catch (_) {}
    });
    _browserActiveNodes = [];
    _browserNoiseBuffer = null;
    if (_webAudioCtx) {
        // Set to null synchronously to prevent _getAudioContext() from attempting
        // to resume a context that is in the middle of closing.
        const ctx = _webAudioCtx;
        _webAudioCtx = null;
        ctx.close();
    }
}

/**
 * Start an animationFrame loop that moves a vertical playhead across the sequencer
 * grid and auto-scrolls the container to keep the playhead in view.
 *
 * @param {AudioContext} audioCtx       - The active Web Audio context
 * @param {number}       scheduleOffset - audioCtx.currentTime at which slot 0 was scheduled
 * @param {number}       slotSec        - Duration of one slot (BASE_RES beats × beat length)
 * @param {number}       totalSteps     - Total number of 1/32nd slots in the sequence
 */
function _browserStartPlayhead(audioCtx, scheduleOffset, slotSec, totalSteps) {
    const inner = document.getElementById('audioGridInner');
    const scroller = document.getElementById('audioGridScroller');
    const grid0 = document.getElementById('stepGrid_0');
    if (!inner || !grid0) return;

    // Ensure the playhead element exists inside the relative-positioned inner div.
    let ph = document.getElementById('audioPlayhead');
    if (!ph) {
        ph = document.createElement('div');
        ph.id = 'audioPlayhead';
        ph.style.cssText = [
            'position:absolute',
            'top:0',
            'bottom:0',
            'width:2px',
            'background:rgba(255,200,0,0.85)',
            'pointer-events:none',
            'z-index:10',
            'border-radius:1px',
            'box-shadow:0 0 6px rgba(255,200,0,0.5)',
        ].join(';');
        inner.appendChild(ph);
    }
    ph.style.display = 'block';

    // Measure the pixel offset of the first step slot from the left edge of #audioGridInner.
    // grid0.offsetLeft is relative to its offset parent, which is the channel-row div; but
    // the channel-rows sit inside #audioGridInner with padding:10px and no additional offset,
    // so we walk up via offsetParent to accumulate the real left relative to #audioGridInner.
    let gridOffsetLeft = 0;
    let el = grid0;
    while (el && el !== inner) {
        gridOffsetLeft += el.offsetLeft;
        el = el.offsetParent;
    }
    const stepPx = BASE_WIDTH + GAP; // 16 px per 1/32nd slot

    function tick() {
        // Stop animating if the audio context has been closed (e.g. user pressed Stop).
        if (!_webAudioCtx || _webAudioCtx.state === 'closed') {
            _browserStopPlayhead();
            return;
        }

        const elapsed = _webAudioCtx.currentTime - scheduleOffset;
        const currentSlot = Math.floor(elapsed / slotSec);

        if (currentSlot >= totalSteps) {
            // Sequence has finished — hide the playhead and stop the loop.
            _browserStopPlayhead();
            return;
        }

        const left = gridOffsetLeft + currentSlot * stepPx;
        ph.style.left = left + 'px';

        // Auto-scroll to keep the playhead comfortably in view.
        if (scroller) {
            const margin = 120; // px from edge before scrolling kicks in
            const relLeft = left - scroller.scrollLeft;
            if (relLeft < margin) {
                scroller.scrollLeft = Math.max(0, left - margin);
            } else if (relLeft > scroller.clientWidth - margin) {
                scroller.scrollLeft = left - scroller.clientWidth + margin;
            }
        }

        _browserPlayheadRaf = requestAnimationFrame(tick);
    }

    _browserPlayheadRaf = requestAnimationFrame(tick);
}

/** Cancel the playhead animation and hide the playhead element. */
function _browserStopPlayhead() {
    if (_browserPlayheadRaf !== null) {
        cancelAnimationFrame(_browserPlayheadRaf);
        _browserPlayheadRaf = null;
    }
    const ph = document.getElementById('audioPlayhead');
    if (ph) ph.style.display = 'none';
}

/**
 * Play the current sequencer grid in the browser using Web Audio API.
 * Notes are pre-calculated and precisely scheduled against AudioContext.currentTime.
 */
function audioPreviewBrowser() {
    browserStopAll();

    const audioCtx = _getAudioContext();
    const bpm = parseInt(document.getElementById('audioBpm').value) || 120;
    const beatDuration = 60.0 / bpm;
    const slotSec = BASE_RES * beatDuration;
    const scheduleOffset = audioCtx.currentTime + 0.05;

    let hasNotes = false;

    for (let c = 0; c < AUDIO_NUM_CHANNELS; c++) {
        const patchName = audioChannelPatches[c] || 'BEEP';
        let cursor = scheduleOffset;

        for (let s = 0; s < audioNumSteps; s++) {
            const step = audioSteps[c][s];
            // Each array index occupies exactly BASE_RES beats regardless of note length.
            // Using step.duration (or activeDuration) here was wrong: covered-cell steps
            // have no .duration, causing cursor += NaN and silencing all subsequent notes.

            if (step && step.note && step.note !== '-') {
                const noteSec = step.duration * beatDuration;
                const freq = _jseqIndexToFreq(_noteToJseqIndex(step.note));
                if (freq > 0) {
                    _browserScheduleNote(audioCtx, freq, patchName, cursor, noteSec);
                    hasNotes = true;
                }
            }
            cursor += slotSec;
        }
    }

    if (hasNotes) {
        showStatus('audioStatus', '🔊 Playing in browser…', 'success');
        _browserStartPlayhead(audioCtx, scheduleOffset, slotSec, audioNumSteps);
    } else {
        showStatus('audioStatus', 'No notes to play — add some steps first', 'error');
    }
}

/**
 * Convert a note name (e.g. 'C4', 'A#3') to a frequency in Hz.
 * Returns 0 for unrecognised names (treated as rests).
 */
function _noteNameToFreq(noteName) {
    const m = noteName && noteName.match(/^([A-G]#?)(-?\d+)$/);
    if (!m) return 0;
    const midi = (parseInt(m[2]) + 1) * 12 + (_NOTE_SEMITONES[m[1]] !== undefined ? _NOTE_SEMITONES[m[1]] : 0);
    return 440.0 * Math.pow(2, (midi - 69) / 12.0);
}

/**
 * Fetch the tone sequence data from the device and play it in the browser.
 * The /api/audio/tone endpoint returns bpm, patch name, and the note sequence.
 */
async function playToneBrowser() {
    const select = document.getElementById('toneSelect');
    const name = select ? select.value : '';
    if (!name) {
        showStatus('toneStatus', 'Please select a tone', 'error');
        return;
    }
    browserStopAll();
    try {
        const resp = await fetch(`/api/audio/tone?name=${encodeURIComponent(name)}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        const audioCtx = _getAudioContext();
        const bpm = data.bpm || 120;
        const beatDuration = 60.0 / bpm;
        let cursor = audioCtx.currentTime + 0.05;
        const patchName = data.patch || 'BEEP';

        for (const [noteName, durationBeats] of (data.sequence || [])) {
            const freq = _noteNameToFreq(noteName);
            const durationSec = durationBeats * beatDuration;
            if (freq > 0) {
                _browserScheduleNote(audioCtx, freq, patchName, cursor, durationSec);
            }
            cursor += durationSec;
        }
        showStatus('toneStatus', `🔊 Playing "${name}" in browser`, 'success');
    } catch (e) {
        showStatus('toneStatus', 'Browser playback error: ' + e, 'error');
    }
}

/**
 * Fetch a WAV file from the device SD card and decode/play it in the browser
 * using the Web Audio API decodeAudioData pipeline.
 */
async function playWavBrowser() {
    const select = document.getElementById('wavSelect');
    const filename = select ? select.value : '';
    if (!filename) {
        showStatus('wavStatus', 'Please select a WAV file', 'error');
        return;
    }
    // Guard against path traversal: filenames come from the server's library listing
    // but we validate they contain no path separators as a defence-in-depth measure.
    if (filename.includes('..')) {
        showStatus('wavStatus', 'Invalid file path', 'error');
        return;
    }
    browserStopAll();
    const audioCtx = _getAudioContext();
    showStatus('wavStatus', '⏳ Fetching WAV…', 'success');
    try {
        const response = await fetch(`/api/files/download?path=${encodeURIComponent('/sd/' + filename)}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const arrayBuffer = await response.arrayBuffer();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);
        source.start();
        _browserActiveNodes.push(source);
        showStatus('wavStatus', `🔊 Playing "${filename}" in browser`, 'success');
    } catch (e) {
        showStatus('wavStatus', 'Browser playback error: ' + e, 'error');
    }
}

// =====================================================================
// HID Emulator
// =====================================================================
const HID_NUM_BUTTONS = 4;
let _hidBtnStates = new Array(HID_NUM_BUTTONS).fill(false);
let _hidEncoderPos = 0;
let _hidEncBtnPressed = false;

function _hidBuildButtonsStr() {
    return _hidBtnStates.map(v => v ? '1' : '0').join('');
}

async function _hidSend(payload) {
    try {
        const resp = await fetch('/api/hid/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sid: 'CORE', ...payload }),
        });
        const data = await resp.json();
        if (!resp.ok) {
            showStatus('hidStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        } else if (data.status === 'no_hid') {
            showStatus('hidStatus', 'HID manager not connected to web server', 'error');
        }
    } catch (e) {
        showStatus('hidStatus', 'Error: ' + e, 'error');
    }
}

function hidBtnPress(index) {
    if (_hidBtnStates[index]) return;
    _hidBtnStates[index] = true;
    document.getElementById('hidBtn' + index).classList.add('pressed');
    _hidSend({ buttons: _hidBuildButtonsStr() });
}

function hidBtnRelease(index) {
    if (!_hidBtnStates[index]) return;
    _hidBtnStates[index] = false;
    document.getElementById('hidBtn' + index).classList.remove('pressed');
    _hidSend({ buttons: _hidBuildButtonsStr() });
}

function hidEncoderStep(delta) {
    _hidEncoderPos += delta;
    document.getElementById('hidEncoderVal').textContent = _hidEncoderPos;
    _hidSend({ encoders: String(_hidEncoderPos) });
}

function hidEncoderReset() {
    _hidEncoderPos = 0;
    document.getElementById('hidEncoderVal').textContent = '0';
    _hidSend({ encoders: '0' });
}

function hidEncBtnPress() {
    if (_hidEncBtnPressed) return;
    _hidEncBtnPressed = true;
    document.getElementById('hidEncBtn').classList.add('pressed');
    _hidSend({ encoder_buttons: '1' });
}

function hidEncBtnRelease() {
    if (!_hidEncBtnPressed) return;
    _hidEncBtnPressed = false;
    document.getElementById('hidEncBtn').classList.remove('pressed');
    _hidSend({ encoder_buttons: '0' });
}

// =====================================================================
// Remote HID Interface (dynamic satellite topology)
// =====================================================================
const HID_PROFILES = {
    "CORE": {
        label: "CORE",
        color: "#4CAF50",
        buttons: [
            { label: "B1" }, { label: "B2" }, { label: "B3" }, { label: "B4" },
        ],
        latching_toggles: [],
        momentary_toggles: [],
        encoders: [{ label: "ENC" }],
    },
    "INDUSTRIAL": {
        label: "INDUSTRIAL",
        color: "#FF9800",
        buttons: [{ label: "BIG BTN" }],
        latching_toggles: [
            { label: "T1" }, { label: "T2" }, { label: "T3" }, { label: "T4" },
            { label: "T5" }, { label: "T6" }, { label: "T7" }, { label: "T8" },
            { label: "ARM" }, { label: "KEY" }, { label: "ROT A" }, { label: "ROT B" },
        ],
        momentary_toggles: [{ label: "MOM" }],
        encoders: [{ label: "ENC" }],
    },
};
HID_PROFILES["01"] = HID_PROFILES["INDUSTRIAL"];

const _hidRemoteState = {};
let _hidTopoHash = '';

async function _hidRemoteSend(sid, payload) {
    try {
        const resp = await fetch('/api/hid/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sid, ...payload }),
        });
        const data = await resp.json();
        if (!resp.ok) {
            showStatus('hidRemoteStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        } else if (data.status === 'no_hid') {
            showStatus('hidRemoteStatus', 'HID manager not connected', 'error');
        }
    } catch (e) {
        showStatus('hidRemoteStatus', 'Error: ' + e, 'error');
    }
}

function _buildHIDPanel(sid, typeName, profile, btnIndexStart, encIndexStart) {
    const panel = document.createElement('div');
    panel.className = 'hid-remote-panel';
    panel.style.borderColor = profile.color;

    const title = sid === 'CORE' ? 'CORE' : `SAT ${sid}`;
    const header = document.createElement('h3');
    header.innerHTML = `<span style="color:${profile.color};">${title}</span> <span style="font-weight:normal;font-size:0.8em;color:#888;">${typeName}</span>`;
    panel.appendChild(header);

    const state = _hidRemoteState[sid];

    // --- Buttons ---
    if (profile.buttons && profile.buttons.length > 0) {
        const section = document.createElement('div');
        section.className = 'hid-section';
        const h4 = document.createElement('h4');
        h4.textContent = 'Buttons';
        section.appendChild(h4);
        const grid = document.createElement('div');
        grid.className = 'hid-btn-grid';
        profile.buttons.forEach((btn, i) => {
            const absIdx = btnIndexStart + i;
            const b = document.createElement('button');
            b.className = 'hid-push-btn';
            b.id = `hidDynBtn_${absIdx}`;
            b.textContent = btn.label;
            const press = () => {
                if (state.buttons[i]) return;
                state.buttons[i] = true;
                b.classList.add('pressed');
                _hidRemoteSend(sid, { buttons: state.buttons.map(v => v ? '1' : '0').join('') });
            };
            const release = () => {
                if (!state.buttons[i]) return;
                state.buttons[i] = false;
                b.classList.remove('pressed');
                _hidRemoteSend(sid, { buttons: state.buttons.map(v => v ? '1' : '0').join('') });
            };
            b.addEventListener('mousedown', press);
            b.addEventListener('mouseup', release);
            b.addEventListener('mouseleave', release);
            b.addEventListener('touchstart', e => { e.preventDefault(); press(); }, { passive: false });
            b.addEventListener('touchend', release);
            b.addEventListener('touchcancel', release);
            grid.appendChild(b);
        });
        section.appendChild(grid);
        panel.appendChild(section);
    }

    // --- Latching Toggles ---
    if (profile.latching_toggles && profile.latching_toggles.length > 0) {
        const section = document.createElement('div');
        section.className = 'hid-section';
        const h4 = document.createElement('h4');
        h4.textContent = 'Toggles';
        section.appendChild(h4);
        const grid = document.createElement('div');
        grid.className = 'hid-toggle-grid';
        profile.latching_toggles.forEach((tog, i) => {
            const b = document.createElement('button');
            b.className = 'hid-toggle-btn';
            b.id = `hidDynTog_${sid}_${i}`;
            b.textContent = tog.label;
            if (state.toggles[i]) b.classList.add('active');
            b.addEventListener('click', () => {
                state.toggles[i] = !state.toggles[i];
                b.classList.toggle('active', state.toggles[i]);
                _hidRemoteSend(sid, { latching_toggles: state.toggles.map(v => v ? '1' : '0').join('') });
            });
            grid.appendChild(b);
        });
        section.appendChild(grid);
        panel.appendChild(section);
    }

    // --- Momentary Toggles ---
    if (profile.momentary_toggles && profile.momentary_toggles.length > 0) {
        const section = document.createElement('div');
        section.className = 'hid-section';
        const h4 = document.createElement('h4');
        h4.textContent = 'Momentary';
        section.appendChild(h4);
        profile.momentary_toggles.forEach((tog, i) => {
            const wrap = document.createElement('div');
            wrap.style.cssText = 'display:flex; gap:5px; align-items:center; margin-bottom:5px;';
            const lbl = document.createElement('span');
            lbl.style.cssText = 'color:#b0b0b0; font-size:0.85em; min-width:40px;';
            lbl.textContent = tog.label;
            const mkMomBtn = (dir, label) => {
                const b = document.createElement('button');
                b.className = 'hid-enc-step-btn';
                b.textContent = label;
                const press = () => {
                    state.momentary[i] = dir;
                    _hidRemoteSend(sid, { momentary_toggles: state.momentary.join('') });
                };
                const release = () => {
                    state.momentary[i] = 'C';
                    _hidRemoteSend(sid, { momentary_toggles: state.momentary.join('') });
                };
                b.addEventListener('mousedown', press);
                b.addEventListener('mouseup', release);
                b.addEventListener('mouseleave', release);
                b.addEventListener('touchstart', e => { e.preventDefault(); press(); }, { passive: false });
                b.addEventListener('touchend', release);
                b.addEventListener('touchcancel', release);
                return b;
            };
            wrap.appendChild(lbl);
            wrap.appendChild(mkMomBtn('U', '▲'));
            wrap.appendChild(mkMomBtn('D', '▼'));
            section.appendChild(wrap);
        });
        panel.appendChild(section);
    }

    // --- Encoders ---
    if (profile.encoders && profile.encoders.length > 0) {
        const section = document.createElement('div');
        section.className = 'hid-section';
        const h4 = document.createElement('h4');
        h4.textContent = 'Encoders';
        section.appendChild(h4);
        profile.encoders.forEach((enc, i) => {
            const absIdx = encIndexStart + i;
            const encWrap = document.createElement('div');
            encWrap.style.cssText = 'margin-bottom:10px;';
            const encLabel = document.createElement('div');
            encLabel.style.cssText = 'color:#b0b0b0; font-size:0.85em; margin-bottom:4px;';
            encLabel.textContent = enc.label;
            const controls = document.createElement('div');
            controls.className = 'hid-encoder-controls';
            const display = document.createElement('div');
            display.className = 'hid-encoder-display';
            display.id = `hidDynEnc_${absIdx}`;
            display.textContent = state.encoders[i];
            const step = (delta) => {
                state.encoders[i] += delta;
                display.textContent = state.encoders[i];
                _hidRemoteSend(sid, { encoders: state.encoders.map(String).join(':') });
            };
            const mkStepBtn = (delta, label) => {
                const b = document.createElement('button');
                b.className = 'hid-enc-step-btn';
                b.textContent = label;
                b.addEventListener('click', () => step(delta));
                return b;
            };
            const resetBtn = document.createElement('button');
            resetBtn.className = 'hid-enc-step-btn';
            resetBtn.style.fontSize = '0.7em';
            resetBtn.textContent = 'RST';
            resetBtn.addEventListener('click', () => {
                state.encoders[i] = 0;
                display.textContent = '0';
                _hidRemoteSend(sid, { encoders: state.encoders.map(String).join(':') });
            });
            controls.appendChild(mkStepBtn(-5, '«'));
            controls.appendChild(mkStepBtn(-1, '−'));
            controls.appendChild(display);
            controls.appendChild(mkStepBtn(1, '+'));
            controls.appendChild(mkStepBtn(5, '»'));
            controls.appendChild(resetBtn);
            // Encoder button
            const encBtnWrap = document.createElement('div');
            encBtnWrap.className = 'hid-enc-btn-wrap';
            const encBtn = document.createElement('button');
            encBtn.className = 'hid-enc-push-btn';
            encBtn.id = `hidDynEncBtn_${absIdx}`;
            encBtn.textContent = 'ENC BTN';
            const encPress = () => {
                if (state.encBtns[i]) return;
                state.encBtns[i] = true;
                encBtn.classList.add('pressed');
                _hidRemoteSend(sid, { encoder_buttons: state.encBtns.map(v => v ? '1' : '0').join('') });
            };
            const encRelease = () => {
                if (!state.encBtns[i]) return;
                state.encBtns[i] = false;
                encBtn.classList.remove('pressed');
                _hidRemoteSend(sid, { encoder_buttons: state.encBtns.map(v => v ? '1' : '0').join('') });
            };
            encBtn.addEventListener('mousedown', encPress);
            encBtn.addEventListener('mouseup', encRelease);
            encBtn.addEventListener('mouseleave', encRelease);
            encBtn.addEventListener('touchstart', e => { e.preventDefault(); encPress(); }, { passive: false });
            encBtn.addEventListener('touchend', encRelease);
            encBtn.addEventListener('touchcancel', encRelease);
            encBtnWrap.appendChild(encBtn);
            encWrap.appendChild(encLabel);
            encWrap.appendChild(controls);
            encWrap.appendChild(encBtnWrap);
            section.appendChild(encWrap);
        });
        panel.appendChild(section);
    }

    return panel;
}

// =====================================================================
// Hardware Topology Visualizer
// =====================================================================
// Constants and state are declared near the top of this file alongside
// the telemetry variables to avoid temporal dead zone errors.

/** Return the canvas-space centre of a topology node.
 *  index 0 = Core, 1..N = satellites in sorted order.
 *  xOffset shifts the whole chain horizontally (used to centre within the canvas). */
function _topoNodePos(index, canvasWidth, xOffset = 0) {
    return {
        x: _TOPO_ORIGIN_X + index * _TOPO_H_STEP + xOffset,
        y: _TOPO_H / 2,
    };
}

/** Compute the required internal canvas width for the current satellite set. */
function _topoCanvasWidth(sidCount) {
    return Math.max(300, _TOPO_ORIGIN_X + (sidCount + 1) * _TOPO_H_STEP);
}

/** Draw one node (Core or Satellite) on the canvas context. */
function _topoDrawNode(ctx, x, y, topLabel, bottomLabel, isCore, isOnline) {
    const r = _TOPO_NODE_R;

    // Glow
    if (isCore || isOnline) {
        const glow = ctx.createRadialGradient(x, y, r * 0.4, x, y, r * 1.8);
        glow.addColorStop(0, isCore ? 'rgba(33,150,243,0.25)' : 'rgba(76,175,80,0.18)');
        glow.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.beginPath();
        ctx.arc(x, y, r * 1.8, 0, Math.PI * 2);
        ctx.fillStyle = glow;
        ctx.fill();
    }

    // Circle fill
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = isCore ? '#0d2744' : (isOnline ? '#0d2a0d' : '#1e1010');
    ctx.strokeStyle = isCore ? '#2196F3' : (isOnline ? '#4CAF50' : '#555');
    ctx.lineWidth = 3;
    ctx.fill();
    ctx.stroke();

    // Primary label (top line inside circle)
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = isCore ? '#90CAF9' : (isOnline ? '#90EE90' : '#777');
    ctx.font = 'bold 12px monospace';
    const hasBottom = bottomLabel != null && bottomLabel !== '';
    ctx.fillText(topLabel, x, y - (hasBottom ? 8 : 0));

    // Secondary label (bottom line inside circle)
    if (hasBottom) {
        ctx.font = '10px monospace';
        ctx.fillStyle = isCore ? '#5b9bd5' : (isOnline ? '#5a9a5a' : '#555');
        ctx.fillText(bottomLabel, x, y + 8);
    }

    // Subtitle below node (type name) is rendered by the caller after invoking _topoDrawNode.
}

/** Render the full topology canvas, including any active pulses. */
function _topoRender() {
    const canvas = document.getElementById('topoCanvas');
    if (!canvas) return;

    const sids = Object.keys(_topoSatData).sort();

    // Always match the internal buffer to the element's rendered CSS width so
    // there is a 1:1 pixel mapping and circles stay circular (no bitmap stretch).
    const cssW = Math.round(canvas.getBoundingClientRect().width) || 600;
    const contentW = _topoCanvasWidth(sids.length);
    const w = Math.max(contentW, cssW);
    if (canvas.width !== w) canvas.width = w;

    // Horizontal offset to centre the chain in the available space.
    const xOff = Math.max(0, Math.floor((w - contentW) / 2));
    _topoXOff = xOff;

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, w, _TOPO_H);

    // --- Connection lines (Core→Sat[0]→Sat[1]→…) ---
    // Each segment i connects node i (Core=0 or satellite) to node i+1.
    // The colour is determined by the satellite at the far end (sids[i]).
    for (let i = 0; i < sids.length; i++) {
        const from = _topoNodePos(i, w, xOff);
        const to = _topoNodePos(i + 1, w, xOff);
        const sat = _topoSatData[sids[i]];
        const online = sat && sat.active;

        ctx.strokeStyle = online ? '#1e4d1e' : '#2a2a2a';
        ctx.lineWidth = 4;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(from.x + _TOPO_NODE_R, from.y);
        ctx.lineTo(to.x - _TOPO_NODE_R, to.y);
        ctx.stroke();
    }

    // --- Pulse animations (data flow: satellite → core) ---
    const now = Date.now();
    const PULSE_DURATION = 1100; // ms
    _topoPulses = _topoPulses.filter(p => now - p.ts < PULSE_DURATION);

    _topoPulses.forEach(pulse => {
        const sidIdx = sids.indexOf(pulse.sid);
        if (sidIdx < 0) return;

        const progress = (now - pulse.ts) / PULSE_DURATION;
        // Pulse animates directly from the satellite node to the Core node.
        // A true hop-by-hop animation would require tracking intermediate positions;
        // direct travel is visually clear and cheaper to compute.
        const from = _topoNodePos(sidIdx + 1, w, xOff);
        const to = _topoNodePos(0, w, xOff);

        const px = from.x + (to.x - from.x) * progress;
        const py = from.y + (to.y - from.y) * progress;

        const alpha = 1 - progress * 0.5;
        const grad = ctx.createRadialGradient(px, py, 0, px, py, 12);
        grad.addColorStop(0, `rgba(76,175,80,${alpha})`);
        grad.addColorStop(0.5, `rgba(76,175,80,${alpha * 0.5})`);
        grad.addColorStop(1, 'rgba(76,175,80,0)');
        ctx.beginPath();
        ctx.arc(px, py, 12, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
    });

    // --- Core node ---
    const corePos = _topoNodePos(0, w, xOff);
    _topoDrawNode(ctx, corePos.x, corePos.y, 'CORE', null, true, true);

    // Subtitle below Core
    ctx.font = '10px monospace';
    ctx.fillStyle = '#2a6090';
    ctx.textAlign = 'center';
    ctx.fillText('CORE', corePos.x, corePos.y + _TOPO_NODE_R + 15);

    // --- Satellite nodes ---
    sids.forEach((sid, i) => {
        const pos = _topoNodePos(i + 1, w, xOff);
        const sat = _topoSatData[sid];
        const online = sat && sat.active;
        const typeLabel = (sat && sat.type) ? sat.type : '??';
        _topoDrawNode(ctx, pos.x, pos.y, `SAT`, sid, false, online);

        // Type subtitle below node
        ctx.font = '10px monospace';
        ctx.fillStyle = online ? '#3a6a3a' : '#444';
        ctx.textAlign = 'center';
        ctx.fillText(typeLabel, pos.x, pos.y + _TOPO_NODE_R + 15);
    });

    // Empty state message
    if (sids.length === 0) {
        ctx.font = '11px monospace';
        ctx.fillStyle = '#555';
        ctx.textAlign = 'center';
        ctx.fillText('No satellites detected', w / 2, _TOPO_H / 2);
    }

    // Keep animation loop alive while pulses remain
    if (_topoPulses.length > 0) {
        _topoRafId = requestAnimationFrame(_topoRender);
    } else {
        _topoRafId = null;
    }
}

/** Find which node (if any) lies under canvas-space point (mx, my).
 *  Returns 'CORE', a satellite SID string, or null. */
function _topoHitTest(mx, my, canvasWidth) {
    const sids = Object.keys(_topoSatData).sort();
    const corePos = _topoNodePos(0, canvasWidth, _topoXOff);
    if (Math.hypot(mx - corePos.x, my - corePos.y) <= _TOPO_NODE_R) return 'CORE';
    for (let i = 0; i < sids.length; i++) {
        const pos = _topoNodePos(i + 1, canvasWidth, _topoXOff);
        if (Math.hypot(mx - pos.x, my - pos.y) <= _TOPO_NODE_R) return sids[i];
    }
    return null;
}

/** Convert a mouse event to canvas-space coordinates (accounts for CSS scaling). */
function _topoEventCoords(canvas, e) {
    const rect = canvas.getBoundingClientRect();
    return {
        mx: (e.clientX - rect.left) * (canvas.width / rect.width),
        my: (e.clientY - rect.top) * (canvas.height / rect.height),
    };
}

/** Attach click and hover listeners to the topology canvas (once). */
function _topoInitListeners() {
    if (_topoInitialized) return;
    _topoInitialized = true;

    const canvas = document.getElementById('topoCanvas');
    if (!canvas) return;

    canvas.addEventListener('click', function (e) {
        const { mx, my } = _topoEventCoords(canvas, e);
        const hit = _topoHitTest(mx, my, canvas.width);
        if (!hit) return;

        if (hit === 'CORE') {
            // Scroll to top of System tab (already active)
            window.scrollTo({ top: 0, behavior: 'smooth' });
            return;
        }

        // Navigate to HID tab and scroll to the satellite's panel
        const hidTabBtn = document.querySelector('.tab[onclick="showTab(\'hid\')"]');
        if (hidTabBtn) {
            hidTabBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        }
        // Delay allows the browser to complete the tab-switch DOM update before
        // attempting to scroll to the target panel header.
        const TAB_SWITCH_DELAY_MS = 120;
        setTimeout(() => {
            const allHeaders = document.querySelectorAll('#hidDynamicContainer h3');
            for (const h of allHeaders) {
                if (h.textContent.includes(hit)) {
                    h.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    break;
                }
            }
        }, TAB_SWITCH_DELAY_MS);
    });

    canvas.addEventListener('mousemove', function (e) {
        const { mx, my } = _topoEventCoords(canvas, e);
        const hit = _topoHitTest(mx, my, canvas.width);
        canvas.style.cursor = hit ? 'pointer' : 'default';
    });

    canvas.addEventListener('mouseleave', function () {
        canvas.style.cursor = 'default';
    });
}

/** Main entry point called from updateTelemetryUI.
 *  Updates satellite state, spawns a pulse for each active satellite, then redraws. */
function drawTopologyMap(satellites) {
    _topoSatData = satellites || {};
    _topoInitListeners();

    // Spawn a data-flow pulse for every active satellite on each telemetry update.
    // Throttle so we don't flood the pulse list on rapid consecutive calls.
    const PULSE_SPAWN_THROTTLE_MS = 400;
    const now = Date.now();
    Object.keys(_topoSatData).forEach(sid => {
        if (_topoSatData[sid].active) {
            const lastSpawn = _lastPulseSpawn[sid] || 0;
            if (now - lastSpawn > PULSE_SPAWN_THROTTLE_MS) {
                _topoPulses.push({ sid, ts: now });
                _lastPulseSpawn[sid] = now;
            }
        }
    });

    // Cancel any in-flight RAF and start a fresh render pass
    if (_topoRafId !== null) cancelAnimationFrame(_topoRafId);
    _topoRafId = null;
    _topoRender();
}

function rebuildHIDInterface(satellites) {
    const container = document.getElementById('hidDynamicContainer');
    if (!container) return;

    // Sort active satellite entries by ID for stable, backend-matching order
    const satEntries = Object.entries(satellites || {})
        .filter(([, sat]) => sat.active)
        .sort(([a], [b]) => a.localeCompare(b));

    // Build topology hash to avoid unnecessary DOM redraws
    const topoHash = 'CORE_1' + satEntries.map(([sid, sat]) => `-${sat.type || 'UNKNOWN'}_${sid}`).join('');

    if (_hidTopoHash === topoHash) return;
    _hidTopoHash = topoHash;
    container.innerHTML = '';

    let btnIndex = 0;
    let encIndex = 0;

    // CORE panel (always present)
    const coreProfile = HID_PROFILES['CORE'];
    if (!_hidRemoteState['CORE']) {
        _hidRemoteState['CORE'] = {
            buttons: new Array(coreProfile.buttons.length).fill(false),
            toggles: [],
            momentary: [],
            encoders: new Array(coreProfile.encoders.length).fill(0),
            encBtns: new Array(coreProfile.encoders.length).fill(false),
        };
    }
    container.appendChild(_buildHIDPanel('CORE', 'CORE', coreProfile, btnIndex, encIndex));
    btnIndex += coreProfile.buttons.length;
    encIndex += coreProfile.encoders.length;

    // Satellite panels
    for (const [sid, sat] of satEntries) {
        const typeName = sat.type || 'UNKNOWN';
        const profile = HID_PROFILES[typeName];
        if (!profile) {
            const placeholder = document.createElement('div');
            placeholder.className = 'hid-remote-panel';
            placeholder.innerHTML = `<h3 style="color:#888;">SAT ${sid}</h3><p style="color:#666;font-size:0.85em;">Unknown type: ${typeName}</p>`;
            container.appendChild(placeholder);
            continue;
        }
        if (!_hidRemoteState[sid]) {
            _hidRemoteState[sid] = {
                buttons: new Array(profile.buttons.length).fill(false),
                toggles: new Array(profile.latching_toggles.length).fill(false),
                momentary: new Array(profile.momentary_toggles.length).fill('C'),
                encoders: new Array(profile.encoders.length).fill(0),
                encBtns: new Array(profile.encoders.length).fill(false),
            };
        }
        container.appendChild(_buildHIDPanel(sid, typeName, profile, btnIndex, encIndex));
        btnIndex += profile.buttons.length;
        encIndex += profile.encoders.length;
    }

    // Keep the gamepad unit selector in sync with the current topology.
    _gpRefreshTargetOptions();
}

// =====================================================================
// Virtual Gamepad
// =====================================================================
// Button → HID action mapping.
// Each entry maps a gamepad control ID to a function (sid, state) that
// performs the appropriate _hidRemoteSend call.
//
// D-Pad:
//   UP/DOWN  → momentary toggle index 0 (U / D)
//   LEFT/RIGHT → encoder index 0 delta (−1 / +1)
// Action buttons:
//   A → button index 0, B → button index 1
//   X → button index 2, Y → button index 3
// Centre:
//   SELECT → encoder button index 0
//   START  → button index 3 (B4 on CORE) or last available button

let _gamepadInitialized = false;

// Track which pointer IDs are currently held on each button element.
// Enables proper multi-touch: each finger gets its own pointerId.
const _gpPointers = {};   // { elementId: Set<pointerId> }

function _gpAddPointer(elId, pid) {
    if (!_gpPointers[elId]) _gpPointers[elId] = new Set();
    _gpPointers[elId].add(pid);
}

function _gpRemovePointer(elId, pid) {
    if (_gpPointers[elId]) _gpPointers[elId].delete(pid);
}

function _gpHeld(elId) {
    return _gpPointers[elId] && _gpPointers[elId].size > 0;
}

/** Return the currently selected target SID from the toolbar dropdown. */
function _gpTargetSid() {
    const sel = document.getElementById('gamepadTargetSelect');
    return sel ? sel.value : 'CORE';
}

/** Send an error/success notice to the gamepad status bar. */
function _gpShowStatus(msg, type) {
    showStatus('gamepadStatus', msg, type);
}

/** Convenience: send HID update for the selected target and catch errors. */
async function _gpSend(payload) {
    const sid = _gpTargetSid();
    if (!_hidRemoteState[sid]) {
        _gpShowStatus('No HID state for ' + sid + '. Connect to Telemetry first.', 'error');
        return;
    }
    try {
        await _hidRemoteSend(sid, payload);
    } catch (e) {
        _gpShowStatus('Send error: ' + e, 'error');
    }
}

/** Attach pointerdown/up/cancel listeners to a button for multi-touch press/release. */
function _gpBindButton(el, onPress, onRelease) {
    const elId = el.id;

    el.addEventListener('pointerdown', e => {
        e.preventDefault();
        el.setPointerCapture(e.pointerId);
        _gpAddPointer(elId, e.pointerId);
        if (_gpPointers[elId].size === 1) {
            el.classList.add('pressed');
            onPress();
        }
    });

    const up = e => {
        _gpRemovePointer(elId, e.pointerId);
        if (!_gpHeld(elId)) {
            el.classList.remove('pressed');
            onRelease();
        }
    };

    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
}

/** Populate the target-unit dropdown from the current _hidRemoteState. */
function _gpRefreshTargetOptions() {
    const sel = document.getElementById('gamepadTargetSelect');
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '';
    const sids = Object.keys(_hidRemoteState);
    if (sids.length === 0) {
        const opt = document.createElement('option');
        opt.value = 'CORE';
        opt.textContent = 'CORE (not connected)';
        sel.appendChild(opt);
        return;
    }
    sids.forEach(sid => {
        const opt = document.createElement('option');
        opt.value = sid;
        opt.textContent = sid === 'CORE' ? 'CORE' : 'SAT ' + sid;
        sel.appendChild(opt);
    });
    if (sids.includes(prev)) sel.value = prev;
}

/** One-time setup of gamepad controls. Safe to call multiple times. */
function initGamepad() {
    _gpRefreshTargetOptions();

    if (_gamepadInitialized) return;
    _gamepadInitialized = true;

    // ---- D-Pad ----
    const dpadUp    = document.getElementById('gpDpadUp');
    const dpadDown  = document.getElementById('gpDpadDown');
    const dpadLeft  = document.getElementById('gpDpadLeft');
    const dpadRight = document.getElementById('gpDpadRight');

    // UP/DOWN → momentary toggle index 0
    _gpBindButton(dpadUp,
        () => {
            const sid = _gpTargetSid();
            const st = _hidRemoteState[sid];
            if (!st || !st.momentary.length) return;
            st.momentary[0] = 'U';
            _gpSend({ momentary_toggles: st.momentary.join('') });
        },
        () => {
            const sid = _gpTargetSid();
            const st = _hidRemoteState[sid];
            if (!st || !st.momentary.length) return;
            st.momentary[0] = 'C';
            _gpSend({ momentary_toggles: st.momentary.join('') });
        }
    );

    _gpBindButton(dpadDown,
        () => {
            const sid = _gpTargetSid();
            const st = _hidRemoteState[sid];
            if (!st || !st.momentary.length) return;
            st.momentary[0] = 'D';
            _gpSend({ momentary_toggles: st.momentary.join('') });
        },
        () => {
            const sid = _gpTargetSid();
            const st = _hidRemoteState[sid];
            if (!st || !st.momentary.length) return;
            st.momentary[0] = 'C';
            _gpSend({ momentary_toggles: st.momentary.join('') });
        }
    );

    // LEFT/RIGHT → encoder index 0 delta
    _gpBindButton(dpadLeft,
        () => {
            const sid = _gpTargetSid();
            const st = _hidRemoteState[sid];
            if (!st || !st.encoders.length) return;
            st.encoders[0]--;
            _gpSend({ encoders: st.encoders.map(String).join(':') });
        },
        () => {}
    );

    _gpBindButton(dpadRight,
        () => {
            const sid = _gpTargetSid();
            const st = _hidRemoteState[sid];
            if (!st || !st.encoders.length) return;
            st.encoders[0]++;
            _gpSend({ encoders: st.encoders.map(String).join(':') });
        },
        () => {}
    );

    // ---- Action buttons ----
    // A→btn0, B→btn1, X→btn2, Y→btn3
    const actionMap = [
        ['gpBtnA', 0],
        ['gpBtnB', 1],
        ['gpBtnX', 2],
        ['gpBtnY', 3],
    ];
    actionMap.forEach(([elId, btnIdx]) => {
        const el = document.getElementById(elId);
        if (!el) return;
        _gpBindButton(el,
            () => {
                const sid = _gpTargetSid();
                const st = _hidRemoteState[sid];
                if (!st || btnIdx >= st.buttons.length) return;
                st.buttons[btnIdx] = true;
                _gpSend({ buttons: st.buttons.map(v => v ? '1' : '0').join('') });
            },
            () => {
                const sid = _gpTargetSid();
                const st = _hidRemoteState[sid];
                if (!st || btnIdx >= st.buttons.length) return;
                st.buttons[btnIdx] = false;
                _gpSend({ buttons: st.buttons.map(v => v ? '1' : '0').join('') });
            }
        );
    });

    // ---- SELECT / START ----
    const selectBtn = document.getElementById('gpSelectBtn');
    const startBtn  = document.getElementById('gpStartBtn');

    // SELECT → encoder button 0 press
    if (selectBtn) {
        _gpBindButton(selectBtn,
            () => {
                const sid = _gpTargetSid();
                const st = _hidRemoteState[sid];
                if (!st || !st.encBtns.length) return;
                st.encBtns[0] = true;
                _gpSend({ encoder_buttons: st.encBtns.map(v => v ? '1' : '0').join('') });
            },
            () => {
                const sid = _gpTargetSid();
                const st = _hidRemoteState[sid];
                if (!st || !st.encBtns.length) return;
                st.encBtns[0] = false;
                _gpSend({ encoder_buttons: st.encBtns.map(v => v ? '1' : '0').join('') });
            }
        );
    }

    // START → button 3 (B4 on CORE) or first available button
    if (startBtn) {
        _gpBindButton(startBtn,
            () => {
                const sid = _gpTargetSid();
                const st = _hidRemoteState[sid];
                if (!st || !st.buttons.length) return;
                const idx = Math.min(3, st.buttons.length - 1);
                st.buttons[idx] = true;
                _gpSend({ buttons: st.buttons.map(v => v ? '1' : '0').join('') });
            },
            () => {
                const sid = _gpTargetSid();
                const st = _hidRemoteState[sid];
                if (!st || !st.buttons.length) return;
                const idx = Math.min(3, st.buttons.length - 1);
                st.buttons[idx] = false;
                _gpSend({ buttons: st.buttons.map(v => v ? '1' : '0').join('') });
            }
        );
    }

/** Pulse momentary toggle at index idx in direction dir ('U' or 'D') for durationMs, then release. */
function _gpPulseMomentary(sid, idx, dir, durationMs = 120) {
    const st = _hidRemoteState[sid];
    if (!st || idx >= st.momentary.length) return;
    st.momentary[idx] = dir;
    _gpSend({ momentary_toggles: st.momentary.join('') });
    setTimeout(() => {
        st.momentary[idx] = 'C';
        _gpSend({ momentary_toggles: st.momentary.join('') });
    }, durationMs);
}

// ---- Macro buttons ----
    // Macros fire a specific HID payload and briefly highlight.
    const MACROS = {
        // E-Stop: pulse the guarded toggle (latching index 8) and the big button (button 0)
        estop: sid => {
            const st = _hidRemoteState[sid];
            if (!st) return;
            if (st.toggles.length > 8) {
                st.toggles[8] = !st.toggles[8];
                _gpSend({ latching_toggles: st.toggles.map(v => v ? '1' : '0').join('') });
            } else if (st.buttons.length > 0) {
                st.buttons[0] = true;
                _gpSend({ buttons: st.buttons.map(v => v ? '1' : '0').join('') });
                setTimeout(() => {
                    st.buttons[0] = false;
                    _gpSend({ buttons: st.buttons.map(v => v ? '1' : '0').join('') });
                }, 120);
            }
        },
        // Vanguard Override: pulse momentary toggle 0 UP (EMP bomb / override action)
        vanguard_override: sid => { _gpPulseMomentary(sid, 0, 'U'); },
        // EMP Bomb: same as Vanguard Override impulse (momentary 0 up)
        emp: sid => { _gpPulseMomentary(sid, 0, 'U'); },
        // Stasis Field: pulse momentary toggle 0 DOWN (secondary action)
        stasis: sid => { _gpPulseMomentary(sid, 0, 'D'); },
        // Encoder reset: set encoder 0 back to 0
        enc_reset: sid => {
            const st = _hidRemoteState[sid];
            if (!st || !st.encoders.length) return;
            st.encoders[0] = 0;
            _gpSend({ encoders: st.encoders.map(String).join(':') });
        },
    };

    document.querySelectorAll('.gamepad-macro-btn').forEach(btn => {
        const macro = btn.dataset.macro;
        if (!MACROS[macro]) return;
        btn.addEventListener('pointerdown', e => {
            e.preventDefault();
            const sid = _gpTargetSid();
            MACROS[macro](sid);
            btn.classList.add('fired');
            setTimeout(() => btn.classList.remove('fired'), 300);
        });
    });
}

// =====================================================================
// Layout Configurator
// =====================================================================
let currentLayoutData = {};

async function loadLayout() {
    try {
        const response = await fetch('/api/config/layout');
        const data = await response.json();
        currentLayoutData = data;
        renderLayoutUI();
    } catch (error) {
        showStatus('layoutStatus', 'Error loading layout: ' + error, 'error');
    }
}

function renderLayoutUI() {
    const controls = document.getElementById('layoutControls');
    const canvas = document.getElementById('layoutCanvasContainer');

    controls.innerHTML = '<h3 style="margin-bottom: 15px; color: #4CAF50;">Offsets</h3>';

    // Reset canvas but keep the CORE block
    canvas.innerHTML = '<div style="position: absolute; top: calc(50% - 64px); left: calc(50% - 64px); width: 128px; height: 128px; background: rgba(0, 150, 255, 0.1); border: 2px solid #0096FF; display: flex; align-items: center; justify-content: center; color: #0096FF; font-weight: bold; font-size: 0.85em; z-index: 10; box-sizing: border-box;">CORE (0,0)</div>';

    // Merge saved offsets with live satellites to get a complete list of IDs
    const allSids = new Set([...Object.keys(currentLayoutData.offsets || {}), ...Object.keys(currentLayoutData.live || {})]);

    if (allSids.size === 0) {
        controls.innerHTML += '<em style="color:#666;">No satellites configured or connected.</em>';
        return;
    }

    Array.from(allSids).sort((a,b) => Number(a)-Number(b)).forEach(sid => {
        const saved = (currentLayoutData.offsets || {})[sid] || { offset_x: 0, offset_y: 0 };
        const live = (currentLayoutData.live || {})[sid] || { active: false, type: 'OFFLINE/UNKNOWN' };

        const badgeClass = live.active ? 'online' : 'offline';
        const badgeText = live.active ? 'ONLINE' : 'OFFLINE';

        // Render Input Controls
        const row = document.createElement('div');
        row.style.cssText = 'margin-bottom: 15px; padding: 15px; background: #1a1a1a; border: 1px solid #333; border-radius: 4px;';
        row.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <strong style="color: #e0e0e0;">SAT ${sid} <span style="font-weight:normal; color:#888; font-size:0.85em;">(${live.type})</span></strong>
                <span class="sat-badge ${badgeClass}">${badgeText}</span>
            </div>
            <div style="display: flex; gap: 15px;">
                <div style="flex: 1;">
                    <label style="font-size: 0.8em;">X Offset:</label>
                    <input type="number" id="layout_x_${sid}" value="${saved.offset_x}" oninput="updateCanvasPreview('${sid}')">
                </div>
                <div style="flex: 1;">
                    <label style="font-size: 0.8em;">Y Offset:</label>
                    <input type="number" id="layout_y_${sid}" value="${saved.offset_y}" oninput="updateCanvasPreview('${sid}')">
                </div>
            </div>
        `;
        controls.appendChild(row);

        // Render Virtual Canvas Block
        const satBox = document.createElement('div');
        satBox.id = `canvas_sat_${sid}`;
        // Assuming standard 8x16 matrices for satellites (64px by 128px visual scale)
        satBox.style.cssText = 'position: absolute; width: 64px; height: 128px; background: rgba(255, 152, 0, 0.15); border: 2px dashed #FF9800; display: flex; align-items: center; justify-content: center; color: #FF9800; font-weight: bold; font-size: 0.85em; transition: top 0.1s ease, left 0.1s ease; box-sizing: border-box;';
        satBox.innerHTML = `SAT ${sid}`;
        canvas.appendChild(satBox);

        // Position immediately based on loaded values
        updateCanvasPreview(sid);
    });
}

function updateCanvasPreview(sid) {
    const xInput = document.getElementById(`layout_x_${sid}`);
    const yInput = document.getElementById(`layout_y_${sid}`);
    if (!xInput || !yInput) return;

    const x = parseInt(xInput.value) || 0;
    const y = parseInt(yInput.value) || 0;

    const satBox = document.getElementById(`canvas_sat_${sid}`);
    if (satBox) {
        const scale = 8; // 1 LED pixel = 8 CSS pixels
        // Calculate position relative to the Core's origin point
        satBox.style.left = `calc(50% - 64px + ${x * scale}px)`;
        satBox.style.top = `calc(50% - 64px + ${y * scale}px)`;
    }
}

async function saveLayout() {
    const payload = {};
    const inputs = document.querySelectorAll('[id^="layout_x_"]');

    inputs.forEach(xInput => {
        const sid = xInput.id.split('_')[2];
        const yInput = document.getElementById(`layout_y_${sid}`);
        payload[sid] = {
            x: parseInt(xInput.value) || 0,
            y: parseInt(yInput.value) || 0
        };
    });

    try {
        const response = await fetch('/api/config/layout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            showStatus('layoutStatus', 'Layout saved to config & applied live!', 'success');
        } else {
            const data = await response.json();
            showStatus('layoutStatus', 'Error: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        showStatus('layoutStatus', 'Error: ' + error, 'error');
    }
}
