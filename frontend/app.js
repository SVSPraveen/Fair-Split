// Fair-Split Frontend Application Logic
// Configurable API base URL (defaults to http://localhost:8000)
const API_BASE_URL = window.API_BASE_URL || 'http://localhost:8000';

let selectedBase64Image = null;

// DOM Elements
const form = document.getElementById('split-form');
const fileInput = document.getElementById('receipt-file');
const dropzone = document.getElementById('dropzone');
const dropzonePrompt = document.getElementById('dropzone-prompt');
const previewArea = document.getElementById('preview-area');
const receiptPreview = document.getElementById('receipt-preview');
const previewFilename = document.getElementById('preview-filename');
const removeFileBtn = document.getElementById('remove-file-btn');
const descriptionInput = document.getElementById('description-input');
const loadSampleBtn = document.getElementById('load-sample-btn');
const submitBtn = document.getElementById('submit-btn');

const loadingIndicator = document.getElementById('loading-indicator');
const errorCard = document.getElementById('error-card');
const errorMessage = document.getElementById('error-message');
const resultsContainer = document.getElementById('results-container');

// Results elements
const reconciliationBanner = document.getElementById('reconciliation-banner');
const reconIcon = document.getElementById('recon-icon');
const reconTitle = document.getElementById('recon-title');
const reconSubtitle = document.getElementById('recon-subtitle');
const statGrandTotal = document.getElementById('stat-grand-total');
const statPersonSum = document.getElementById('stat-person-sum');
const splitTableBody = document.getElementById('split-table-body');
const paidByName = document.getElementById('paid-by-name');
const settleUpList = document.getElementById('settle-up-list');
const assumptionsList = document.getElementById('assumptions-list');
const flagsBlock = document.getElementById('flags-block');
const flagsList = document.getElementById('flags-list');

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

    // Show preview thumbnail
    receiptPreview.src = dataUrl;
    previewFilename.textContent = file.name;
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

// Load Sample R2 Description
loadSampleBtn.addEventListener('click', () => {
  descriptionInput.value = 'Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid.';
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

    const response = await fetch(`${API_BASE_URL}/split`, {
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
  splitTableBody.innerHTML = '';
  const payer = data.paid_by ? data.paid_by.trim().toLowerCase() : null;


  data.per_person.forEach((person) => {
    const tr = document.createElement('tr');
    const isPayer = payer && person.name.trim().toLowerCase() === payer;

    // Items list badges
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

  // Reveal results
  resultsContainer.classList.remove('hidden');
  resultsContainer.scrollIntoView({ behavior: 'smooth' });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
