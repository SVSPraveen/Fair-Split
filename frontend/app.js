// Fair-Split Frontend Application Logic
// Configurable API base URL with LocalStorage persistence and in-UI settings panel
const DEFAULT_API_URL = window.API_BASE_URL || 'http://localhost:8000';
let API_BASE_URL = localStorage.getItem('fair_split_api_url') || DEFAULT_API_URL;

let selectedBase64Image = null;
let lastSplitResponse = null;

// Preset Scenarios Data
const SAMPLE_PRESETS = {
  R1: {
    description: "Three of us: Ravi, Neha, Sameer. Ravi had the cappuccino and sandwich, Neha had pasta and lime soda, Sameer had the brownie. Sameer paid.",
    title: "R1: Brew & Bite Cafe (Individual Items)"
  },
  R2: {
    description: "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid.",
    title: "R2: Tamarind Kitchen (Shared Dishes, Priya Paid)"
  },
  R3: {
    description: "Three of us: Ishaan, Meera, Rohit. We all shared the pizza, pasta, and garlic bread. Ishaan and Rohit shared the craft beer. Meera had the virgin mojito. Rohit paid.",
    title: "R3: The Daily Grind (Shared Food & Drinks)"
  },
  R4: {
    description: "Four of us: Dev, Nikhil, Anjali, Farah. Dev and Nikhil shared the chicken biryani. Anjali had veg biryani, Farah had mutton rogan josh. We all had raita and soft drinks. Anjali paid.",
    title: "R4: Spice Route (15% Proportional Discount)"
  }
};

// DOM Elements
const form = document.getElementById('split-form');
const fileInput = document.getElementById('receipt-file');
const dropzone = document.getElementById('dropzone');
const dropzonePrompt = document.getElementById('dropzone-prompt');
const previewArea = document.getElementById('preview-area');
const receiptPreview = document.getElementById('receipt-preview');
const previewFilename = document.getElementById('preview-filename');
const previewMeta = document.getElementById('preview-meta');
const removeFileBtn = document.getElementById('remove-file-btn');
const descriptionInput = document.getElementById('description-input');
const submitBtn = document.getElementById('submit-btn');

// Config & Settings Elements
const settingsToggleBtn = document.getElementById('settings-toggle-btn');
const apiConfigPanel = document.getElementById('api-config-panel');
const apiUrlInput = document.getElementById('api-url-input');
const saveApiUrlBtn = document.getElementById('save-api-url-btn');
const testApiHealthBtn = document.getElementById('test-api-health-btn');
const apiTestResult = document.getElementById('api-test-result');
const apiStatusBadge = document.getElementById('api-status-badge');

// Results & Copy Elements
const loadingIndicator = document.getElementById('loading-indicator');
const errorCard = document.getElementById('error-card');
const errorMessage = document.getElementById('error-message');
const resultsContainer = document.getElementById('results-container');
const copyTableBtn = document.getElementById('copy-table-btn');
const copySettleBtn = document.getElementById('copy-settle-btn');
const rawJsonViewer = document.getElementById('raw-json-viewer');

// Initialize API URL Input & Health Check
apiUrlInput.value = API_BASE_URL;
checkApiHealth(API_BASE_URL);

// Settings Panel Toggle
settingsToggleBtn.addEventListener('click', () => {
  apiConfigPanel.classList.toggle('hidden');
});

saveApiUrlBtn.addEventListener('click', () => {
  const newUrl = apiUrlInput.value.trim().replace(/\/+$/, '');
  if (!newUrl) return;
  API_BASE_URL = newUrl;
  localStorage.setItem('fair_split_api_url', newUrl);
  checkApiHealth(newUrl);
  apiTestResult.textContent = 'Saved!';
  apiTestResult.style.color = '#15803D';
  setTimeout(() => { apiTestResult.textContent = ''; }, 2500);
});

testApiHealthBtn.addEventListener('click', () => {
  const targetUrl = apiUrlInput.value.trim().replace(/\/+$/, '');
  checkApiHealth(targetUrl, true);
});

async function checkApiHealth(url, isManualTest = false) {
  if (isManualTest) apiTestResult.textContent = 'Testing /health...';
  try {
    const res = await fetch(`${url}/health`, { method: 'GET' });
    if (res.ok) {
      apiStatusBadge.className = 'badge-online';
      apiStatusBadge.textContent = url.includes('localhost') ? 'API: Local (200 OK)' : 'API: Live (200 OK)';
      if (isManualTest) {
        apiTestResult.textContent = 'Connected (200 OK)';
        apiTestResult.style.color = '#15803D';
      }
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (err) {
    apiStatusBadge.className = 'badge-offline';
    apiStatusBadge.textContent = 'API: Disconnected';
    if (isManualTest) {
      apiTestResult.textContent = `Unreachable: ${err.message}`;
      apiTestResult.style.color = '#B91C1C';
    }
  }
}

// Preset Scenario Chips Handler
document.querySelectorAll('.sample-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.sample-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');

    const sampleKey = chip.getAttribute('data-sample');
    if (SAMPLE_PRESETS[sampleKey]) {
      descriptionInput.value = SAMPLE_PRESETS[sampleKey].description;
      descriptionInput.focus();
    }
  });
});

// File Upload & Base64 Conversion
fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  handleFileSelection(file);
});

function handleFileSelection(file) {
  if (!file.type.startsWith('image/')) {
    showError('Please upload a valid image file (PNG, JPEG, WEBP).');
    return;
  }

  const reader = new FileReader();
  reader.onload = (event) => {
    const dataUrl = event.target.result;
    // Strip data-URI prefix (e.g. "data:image/png;base64,") for API payload
    selectedBase64Image = dataUrl.split(',')[1];

    // Show preview thumbnail and file size
    receiptPreview.src = dataUrl;
    previewFilename.textContent = file.name;
    const sizeKb = (file.size / 1024).toFixed(1);
    previewMeta.textContent = `${sizeKb} KB • ${file.type.split('/')[1].toUpperCase()}`;

    dropzonePrompt.classList.add('hidden');
    previewArea.classList.remove('hidden');
    hideError();
  };
  reader.onerror = () => {
    showError('Failed to read the receipt image file.');
  };
  reader.readAsDataURL(file);
}

removeFileBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  selectedBase64Image = null;
  fileInput.value = '';
  receiptPreview.src = '';
  previewArea.classList.add('hidden');
  dropzonePrompt.classList.remove('hidden');
});

// Drag & Drop
dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.style.borderColor = 'var(--primary)';
});

dropzone.addEventListener('dragleave', () => {
  dropzone.style.borderColor = 'var(--border-color)';
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.style.borderColor = 'var(--border-color)';
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    fileInput.files = e.dataTransfer.files;
    handleFileSelection(e.dataTransfer.files[0]);
  }
});

// Form Submission
form.addEventListener('submit', async (e) => {
  e.preventDefault();

  if (!selectedBase64Image) {
    showError('Please select or upload a receipt image first.');
    return;
  }

  const description = descriptionInput.value.trim();
  if (!description) {
    showError('Please provide a dining description of who had what.');
    return;
  }

  setLoading(true);
  hideError();
  resultsContainer.classList.add('hidden');

  try {
    const payload = {
      receipt_base64: selectedBase64Image,
      description: description
    };

    const targetUrl = API_BASE_URL.replace(/\/+$/, '');
    const response = await fetch(`${targetUrl}/split`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const responseData = await response.json();

    if (!response.ok) {
      const errorDetail = responseData.detail || responseData.message || JSON.stringify(responseData);
      throw new Error(errorDetail);
    }

    lastSplitResponse = responseData;
    renderResults(responseData);
  } catch (err) {
    showError(`Error (${err.message})`);
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  if (isLoading) {
    loadingIndicator.classList.remove('hidden');
    submitBtn.disabled = true;
  } else {
    loadingIndicator.classList.add('hidden');
    submitBtn.disabled = false;
  }
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorCard.classList.remove('hidden');
}

function hideError() {
  errorCard.classList.add('hidden');
  errorMessage.textContent = '';
}

// Render Results
function renderResults(data) {
  // 0. Confidence Banner
  const confidenceBanner = document.getElementById('confidence-banner');
  const confidenceBadge = document.getElementById('confidence-badge');
  const confidenceTitle = document.getElementById('confidence-title');
  const confidenceSubtitle = document.getElementById('confidence-subtitle');
  const confidenceReasonsContainer = document.getElementById('confidence-reasons-container');
  const confidenceReasonsList = document.getElementById('confidence-reasons-list');

  const conf = data.confidence || { level: 'high', reasons: [] };
  const isHigh = conf.level === 'high';

  if (isHigh) {
    confidenceBanner.className = 'confidence-banner high';
    confidenceBadge.className = 'confidence-badge high';
    confidenceBadge.textContent = 'HIGH CONFIDENCE';
    confidenceTitle.textContent = 'Anti-Hallucination Verified';
    confidenceSubtitle.textContent = 'All mathematical self-checks passed, primary AI models used, and 100% of line items reconciled.';
    confidenceReasonsContainer.classList.add('hidden');
    confidenceReasonsList.innerHTML = '';
  } else {
    confidenceBanner.className = 'confidence-banner needs-review';
    confidenceBadge.className = 'confidence-badge needs-review';
    confidenceBadge.textContent = 'NEEDS REVIEW';
    confidenceTitle.textContent = 'Audit Flags or Discrepancies Detected';
    confidenceSubtitle.textContent = 'One or more edge conditions, unassigned items, or fallback models were triggered:';
    confidenceReasonsContainer.classList.remove('hidden');
    confidenceReasonsList.innerHTML = '';
    conf.reasons.forEach((r) => {
      const li = document.createElement('li');
      li.textContent = r;
      confidenceReasonsList.appendChild(li);
    });
  }

  // 1. Reconciliation Banner
  const reconciliationBanner = document.getElementById('reconciliation-banner');
  const reconIcon = document.getElementById('recon-icon');
  const reconTitle = document.getElementById('recon-title');
  const reconSubtitle = document.getElementById('recon-subtitle');
  const statGrandTotal = document.getElementById('stat-grand-total');
  const statPersonSum = document.getElementById('stat-person-sum');

  const isMatch = data.reconciliation && data.reconciliation.matches_bill;
  statGrandTotal.textContent = `₹${data.grand_total.toFixed(2)}`;
  statPersonSum.textContent = `₹${data.reconciliation.sum_of_person_totals.toFixed(2)}`;

  if (isMatch) {
    reconciliationBanner.className = 'reconciliation-banner';
    reconIcon.textContent = '✅';
    reconTitle.textContent = 'Bill Reconciled Exactly';
    reconSubtitle.textContent = 'Sum of individual totals matches bill grand total within tolerance.';
  } else {
    reconciliationBanner.className = 'reconciliation-banner warning';
    reconIcon.textContent = '⚠️';
    reconTitle.textContent = 'Reconciliation Discrepancy Detected';
    reconSubtitle.textContent = 'The sum of individual person totals does not match the printed grand total.';
  }

  // 2. Per Person Table
  const splitTableBody = document.getElementById('split-table-body');
  splitTableBody.innerHTML = '';
  const payer = data.paid_by ? data.paid_by.trim().toLowerCase() : null;

  data.per_person.forEach((person) => {
    const tr = document.createElement('tr');
    const isPayer = payer && person.name.trim().toLowerCase() === payer;

    const itemsHtml = person.items.map(item => `
      <span class="item-badge ${item.is_shared ? 'shared' : ''}">
        ${escapeHtml(item.name)} (₹${item.amount.toFixed(2)}${item.is_shared ? ' - shared' : ''})
      </span>
    `).join('');

    tr.innerHTML = `
      <td>
        <span class="person-name">${escapeHtml(person.name)}</span>
        ${isPayer ? '<span class="payer-badge">Payer</span>' : ''}
      </td>
      <td><div class="item-badge-list">${itemsHtml}</div></td>
      <td class="num-col">₹${person.subtotal.toFixed(2)}</td>
      <td class="num-col">₹${person.tax_share.toFixed(2)}</td>
      <td class="num-col">₹${person.service_share.toFixed(2)}</td>
      <td class="num-col">${person.discount_share > 0 ? '-₹' + person.discount_share.toFixed(2) : '₹0.00'}</td>
      <td class="num-col total-col">₹${person.total.toFixed(2)}</td>
    `;
    splitTableBody.appendChild(tr);
  });

  // 3. Settle Up Section
  const paidByName = document.getElementById('paid-by-name');
  const settleUpList = document.getElementById('settle-up-list');
  paidByName.textContent = data.paid_by || 'Not Specified';
  settleUpList.innerHTML = '';

  if (data.settle_up && data.settle_up.length > 0) {
    data.settle_up.forEach((t) => {
      const li = document.createElement('li');
      li.className = 'settle-up-item';
      li.innerHTML = `
        <span class="settle-text">
          <strong>${escapeHtml(t.from)}</strong> pays <strong>${escapeHtml(t.to)}</strong>
        </span>
        <span class="settle-amount">₹${t.amount.toFixed(2)}</span>
      `;
      settleUpList.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.className = 'settle-up-item';
    li.innerHTML = `<em>No debt settle-up instructions (no payer identified or bill paid individually).</em>`;
    settleUpList.appendChild(li);
  }

  // 4. Assumptions & Flags
  const assumptionsList = document.getElementById('assumptions-list');
  const flagsBlock = document.getElementById('flags-block');
  const flagsList = document.getElementById('flags-list');

  assumptionsList.innerHTML = '';
  if (data.assumptions && data.assumptions.length > 0) {
    data.assumptions.forEach(assump => {
      const li = document.createElement('li');
      li.textContent = assump;
      assumptionsList.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.innerHTML = '<em>No special assumptions made during parsing.</em>';
    assumptionsList.appendChild(li);
  }

  if (data.flags && data.flags.length > 0) {
    flagsBlock.classList.remove('hidden');
    flagsList.innerHTML = '';
    data.flags.forEach(flag => {
      const li = document.createElement('li');
      li.textContent = flag;
      flagsList.appendChild(li);
    });
  } else {
    flagsBlock.classList.add('hidden');
  }

  // 5. Raw JSON Inspector
  rawJsonViewer.textContent = JSON.stringify(data, null, 2);

  // Reveal results
  resultsContainer.classList.remove('hidden');
  resultsContainer.scrollIntoView({ behavior: 'smooth' });
}

// Copy Utilities
copyTableBtn.addEventListener('click', () => {
  if (!lastSplitResponse || !lastSplitResponse.per_person) return;
  let text = "Person\tSubtotal\tTax Share\tService Share\tDiscount Share\tTotal Payable\n";
  lastSplitResponse.per_person.forEach(p => {
    text += `${p.name}\t₹${p.subtotal.toFixed(2)}\t₹${p.tax_share.toFixed(2)}\t₹${p.service_share.toFixed(2)}\t₹${p.discount_share.toFixed(2)}\t₹${p.total.toFixed(2)}\n`;
  });
  navigator.clipboard.writeText(text).then(() => {
    const orig = copyTableBtn.textContent;
    copyTableBtn.textContent = 'Copied! ✓';
    setTimeout(() => { copyTableBtn.textContent = orig; }, 2000);
  });
});

copySettleBtn.addEventListener('click', () => {
  if (!lastSplitResponse || !lastSplitResponse.settle_up || lastSplitResponse.settle_up.length === 0) return;
  let text = `Settle-Up Reimbursements (Paid by ${lastSplitResponse.paid_by || 'Unknown'}):\n`;
  lastSplitResponse.settle_up.forEach(t => {
    text += `• ${t.from} pays ${t.to}: ₹${t.amount.toFixed(2)}\n`;
  });
  navigator.clipboard.writeText(text).then(() => {
    const orig = copySettleBtn.textContent;
    copySettleBtn.textContent = 'Copied! ✓';
    setTimeout(() => { copySettleBtn.textContent = orig; }, 2000);
  });
});

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
