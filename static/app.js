let isSimulationRunning = false;
let pollingInterval = null;
let lastLogCount = 0;

async function startSimulation() {
    if (isSimulationRunning) return;
    isSimulationRunning = true;
    
    document.getElementById('start-btn').textContent = "Simulation Running...";
    document.getElementById('start-btn').style.opacity = '0.7';

    try {
        await fetch('/api/simulation/start', { method: 'POST' });
        // Start polling for state every second
        if (!pollingInterval) {
            pollingInterval = setInterval(fetchState, 1000);
        }
    } catch (e) {
        console.error("Failed to start simulation:", e);
    }
}

async function fetchState() {
    try {
        const response = await fetch('/api/state');
        const data = await response.json();
        
        updateInventory(data.inventory);
        updateQueue(data.queue);
        updateLogs(data.logs);
        
        if (data.simulation_status === "ended" && isSimulationRunning) {
            isSimulationRunning = false;
            document.getElementById('start-btn').textContent = "Start Simulation";
            document.getElementById('start-btn').style.opacity = '1';
            
            // Show new comprehensive summary modal
            showSummary(data.simulation_summary);
            
            // Send request to reset backend state to idle so popup doesn't re-trigger
            await fetch('/api/simulation/reset', { method: 'POST' });
            
        } else if (data.simulation_status === "running") {
            isSimulationRunning = true;
            document.getElementById('start-btn').textContent = "Simulation Running...";
            document.getElementById('start-btn').style.opacity = '0.7';
        } else if (data.simulation_status === "idle" && isSimulationRunning) {
            isSimulationRunning = false;
            document.getElementById('start-btn').textContent = "Start Simulation";
            document.getElementById('start-btn').style.opacity = '1';
        }
    } catch (e) {
        console.error("Failed fetching state:", e);
    }
}

function updateInventory(inventory) {
    const grid = document.getElementById('inventory-grid');
    grid.innerHTML = '';
    
    // Sort roughly to keep things stable
    inventory.sort((a,b) => a.id.localeCompare(b.id));

    inventory.forEach(item => {
        // Just arbitrarily making 4* threshold the "max" for progress bar
        const maxCapacity = item.threshold * 5; 
        const percentage = Math.max(0, Math.min((item.qty / maxCapacity) * 100, 100));
        const score = item.qty / item.threshold;
        
        let statusClass = 'success';
        if (score < 1.0) statusClass = 'warning';
        if (score < 0.2) statusClass = 'danger';

        const card = document.createElement('div');
        card.className = 'stock-card';
        card.innerHTML = `
            <h3>${item.product_name}</h3>
            <div class="sku">${item.id.replace('stock:WH-ALPHA:', '')}</div>
            <div class="progress-bg">
                <div class="progress-fill ${statusClass}" style="width: ${percentage}%"></div>
            </div>
            <div class="stats">
                <span>Qty: ${item.qty}</span>
                <span style="color:var(--text-muted)">Th: ${item.threshold}</span>
            </div>
        `;
        grid.appendChild(card);
    });
}

function updateQueue(queue) {
    const list = document.getElementById('queue-list');
    list.innerHTML = '';
    
    if (queue.length === 0) {
        list.innerHTML = '<div style="color:var(--text-muted)">Queue is empty</div>';
    }
    
    queue.forEach(item => {
        const isCritical = item.score < 0.2;
        const qItem = document.createElement('div');
        qItem.className = `queue-item ${isCritical ? 'critical' : ''}`;
        qItem.innerHTML = `
            <span>${item.sku}</span>
            <strong>Score: ${item.score.toFixed(2)}</strong>
        `;
        list.appendChild(qItem);
    });
}

function updateLogs(logs) {
    const container = document.getElementById('logs-container');
    
    // Simple way to just append newly found logs
    if (logs.length > lastLogCount) {
        const newLogs = logs.slice(lastLogCount);
        newLogs.forEach(log => {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            
            // Format type safely
            const safeType = log.type ? log.type : 'UNKNOWN';
            
            entry.innerHTML = `
                <span class="log-time">[${log.time}]</span> 
                <span class="log-type ${safeType}">${safeType.padEnd(16, ' ')}</span> 
                <span class="log-msg">${log.message}</span>
            `;
            container.appendChild(entry);
        });
        lastLogCount = logs.length;
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
    }
}

// Initial fetch immediately
fetchState();
if (!pollingInterval) {
    pollingInterval = setInterval(fetchState, 1000);
}

// Logic for Add/Delete Items and Database View
async function addItem() {
    const name = document.getElementById('add-name').value;
    const qty = parseInt(document.getElementById('add-qty').value);
    
    if (!name || isNaN(qty)) {
        alert("Please enter a valid name and quantity.");
        return;
    }
    
    try {
        await fetch('/api/item', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, quantity: qty })
        });
        document.getElementById('add-name').value = '';
        document.getElementById('add-qty').value = '';
        fetchState();
    } catch (e) {
        console.error("Error adding item:", e);
    }
}

async function deleteItem() {
    const name = document.getElementById('del-name').value;
    if (!name) return;
    
    try {
        await fetch(`/api/item/${encodeURIComponent(name)}`, { method: 'DELETE' });
        document.getElementById('del-name').value = '';
        fetchState();
    } catch (e) {
        console.error("Error deleting item:", e);
    }
}

let currentDbData = null;

async function showDatabase() {
    document.getElementById('db-modal').style.display = 'block';
    
    try {
        const response = await fetch('/api/database');
        currentDbData = await response.json();
        // Reset tabs and set inventory as default
        switchDbTab('inventory');
    } catch (e) {
        console.error("Failed fetching database:", e);
    }
}

function closeDatabase() {
    document.getElementById('db-modal').style.display = 'none';
}

function switchDbTab(tabName, eventObj) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (!eventObj && btn.textContent.toLowerCase() === tabName) {
            btn.classList.add('active');
        }
    });

    if (eventObj) {
        eventObj.target.classList.add('active');
    }
    
    const container = document.getElementById('db-view-container');
    if (!currentDbData) return;
    
    let html = '<table class="db-table">';
    const data = currentDbData[tabName];
    
    if (!data || data.length === 0) {
        container.innerHTML = '<p>No records found.</p>';
        return;
    }
    
    // Headers
    const keys = Object.keys(data[0]);
    html += '<thead><tr>';
    keys.forEach(k => html += `<th>${k}</th>`);
    html += '</tr></thead><tbody>';
    
    // Rows
    data.forEach(row => {
        html += '<tr>';
        keys.forEach(k => html += `<td>${row[k] !== null && row[k] !== undefined ? row[k] : ''}</td>`);
        html += '</tr>';
    });
    

    html += '</tbody></table>';
    container.innerHTML = html;
}

function showSummary(summaryData) {
    document.getElementById('summary-modal').style.display = 'block';
    const container = document.getElementById('summary-view-container');
    
    if (!summaryData || Object.keys(summaryData).length === 0) {
        container.innerHTML = '<p>No data recorded for this simulation run.</p>';
        return;
    }
    
    let html = '<table class="db-table">';
    html += '<thead><tr><th>SKU</th><th>Product Name</th><th>Initial Stock</th><th>Quantity Shipped</th><th>Times Reordered</th><th>Final Stock</th></tr></thead><tbody>';
    
    for (const [sku, stats] of Object.entries(summaryData)) {
        let shipped = 0;
        let reordered = 0;
        
        if (stats.events) {
            stats.events.forEach(ev => {
                if (ev.includes("Shipped")) {
                    const match = ev.match(/Shipped (\d+)/);
                    if (match) shipped += parseInt(match[1]);
                } else if (ev.includes("ALERT TRIGGERED")) {
                    reordered += 1;
                }
            });
        }
        
        html += `<tr>
            <td>${sku}</td>
            <td>${stats.name}</td>
            <td>${stats.initial}</td>
            <td>${shipped}</td>
            <td>${reordered}</td>
            <td style="color:var(--accent);font-weight:bold;">${stats.final}</td>
        </tr>`;
    }
    html += '</tbody></table>';
    container.innerHTML = html;
}

function closeSummary() {
    document.getElementById('summary-modal').style.display = 'none';
}

