// Fair-Split Frontend Application Logic
// Configurable API base URL with LocalStorage persistence and in-UI settings panel
const DEFAULT_API_URL = window.API_BASE_URL || 'http://localhost:8000';
let API_BASE_URL = localStorage.getItem('fair_split_api_url') || DEFAULT_API_URL;

let selectedBase64Image = null;
let lastSplitResponse = null;

// Preset Scenarios Data
const SAMPLE_PRESETS = {
  R1: {
    description: "Two of us: Kavya and Deepak. We each had one chai. Deepak had the Vada Pav, and Kavya had the Banana Muffin. Kavya paid.",
    imageFile: "samples/R1.png",
    filename: "R1_filter_brew_cafe.png",
    title: "R1: Filter & Brew Cafe"
  },
  R2: {
    description: "Four of us: Rohan, Divya, Arjun, Preethi. Rohan and Arjun shared the Butter Chicken (2 portions). Divya had the Palak Paneer alone. We all shared the Garlic Naan (6 pcs), Laccha Paratha, and Jeera Rice. The Dahi Puri starter was shared by Divya and Preethi. Gulab Jamun was shared equally across all four. Rohan paid.",
    imageFile: "samples/R2.png",
    filename: "R2_spice_affair_receipt.png",
    title: "R2: Spice Affair"
  },
  R3: {
    description: "Three of us: Sundar, Lakshmi, Aditya. Sundar had a Paper Roast Dosa alone. Lakshmi had the Onion Uttapam and one Idli Vada Combo. Aditya had Ghee Pongal and the other Idli Vada Combo. We all shared the 2 Masala Dosas, 3 Filter Kaapis, and Sambar Vada. Lakshmi had the Mango Lassi alone. Aditya paid.",
    imageFile: "samples/R3.png",
    filename: "R3_dosa_plaza_receipt.png",
    title: "R3: Dosa Plaza"
  },
  R4: {
    description: "Five of us: Natasha, Marcus, Elena, Rahul, Simone. Marcus and Elena shared the 2 Grilled Tenderloins. Rahul had the Pan-Seared Salmon alone. Natasha and Simone shared the Truffle Risotto. All five shared the Amuse-Bouche, Burrata, Seared Scallops, and 3 Seasonal Sides. Natasha and Elena shared the 2 Tiramisus. Rahul had the Crème Brûlée alone. Sparkling water shared across all five. Freshly squeezed juice for Natasha and Marcus. Natasha paid.",
    imageFile: "samples/R4.png",
    filename: "R4_olive_vine_receipt.png",
    title: "R4: Olive & Vine Fine Dining"
  },
  R5: {
    description: "Five of us: Zara, Neel, Pooja, Farhan, Tina. Neel and Farhan had 2 Kingfisher Ultras each. Zara and Tina had the Signature Mojitos. Pooja had the Passion Fruit Cooler (non-alcoholic). Both Red Bulls were shared by Neel and Farhan. The Chicken Satay Skewers were shared between Zara, Pooja, and Tina. Truffle Fries shared by all five. Mezze Platter shared by Zara, Pooja, and Tina. Peri-Peri Burger was Farhan's. Margherita Flatbread shared by all five. Zara paid.",
    imageFile: "samples/R5.png",
    filename: "R5_sky_high_lounge_receipt.png",
    title: "R5: Sky High Lounge Rooftop Bar"
  },
  R6: {
    description: "Party of six: Vikram, Ananya, Kabir, Rhea, Siddharth, Tara. Vikram and Kabir shared the 3 pints of Craft IPA Beer. Ananya and Tara had the Mint Mojitos. Siddharth and Rhea shared the Smoked BBQ Pork Ribs and Crispy Calamari. All six of us shared the 2 Truffle Pizzas, Loaded Nachos, and Mineral Water. Ananya had the Caesar Salad. Rhea, Tara, and Vikram shared the 2 Chocolate Lava Cakes. Eco packaging shared by all. Vikram paid the entire bill.",
    imageFile: "samples/R6.png",
    filename: "R6_urban_brewery_complex.png",
    title: "R6: Urban Brewery Feast (10 Items, Multi-Tax, Discount, 6-Person Group)"
  },
  R7: {
    description: "Birthday party for Arjun, 8 guests: Arjun, Meena, Prashant, Kavitha, Suresh, Divyanka, Roshan, Teja. Welcome Mocktail Shots were one per person (8 total) equally shared. Appetizer Platter (Veg) shared between Kavitha, Meena, Divyanka. Chicken Seekh Kebab shared by Arjun, Prashant, Suresh, Roshan. Mixed Seafood Grill Platter was Prashant and Roshan only. Mushroom Soup shared by all 8. Garden Fresh Salad shared by Kavitha, Meena, Divyanka (3 bowls). Grilled Lobster (Half) — one for Arjun, one for Prashant. Chicken en Papillote — Arjun, Suresh, Roshan. Truffle Risotto — Kavitha and Divyanka. Dal Bukhara, Assorted Breads, Biryani Station, and Dessert Platters shared across all 8. Petit Fours shared by Arjun and Meena only. Sparkling Water and OJ shared equally across all 8. Banquet Hall and Floral Decoration costs split equally across all 8. Cake Cutting charged once to Arjun. The advance deposit of ₹15,000 was paid by Meena already. Arjun is paying the balance today.",
    imageFile: "samples/R7.png",
    filename: "R7_grand_meridian_banquet.png",
    title: "R7: The Grand Meridian Hotel Banquet (19 Items, Dual-Slab GST, Advance Deposit, 8 Persons)"
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

// Preset Scenario Chips Handler (Loads both description & receipt image)
document.querySelectorAll('.sample-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.sample-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');

    const sampleKey = chip.getAttribute('data-sample');
    loadSamplePreset(sampleKey);
  });
});

async function loadSamplePreset(presetKey) {
  const preset = SAMPLE_PRESETS[presetKey];
  if (!preset) return;
  descriptionInput.value = preset.description;

  // Auto-fetch and load sample image into base64
  try {
    const res = await fetch(preset.imageFile);
    if (res.ok) {
      const blob = await res.blob();
      const reader = new FileReader();
      reader.onload = (event) => {
        const dataUrl = event.target.result;
        selectedBase64Image = dataUrl.split(',')[1];
        receiptPreview.src = dataUrl;
        previewFilename.textContent = preset.filename;
        const sizeKb = (blob.size / 1024).toFixed(1);
        previewMeta.textContent = `${sizeKb} KB • Sample Preset`;
        dropzonePrompt.classList.add('hidden');
        previewArea.classList.remove('hidden');
        hideError();
      };
      reader.readAsDataURL(blob);
    }
  } catch (err) {
    console.warn("Could not auto-load sample image:", err);
  }
}

// Auto-load default R2 preset on first load
loadSamplePreset('R2');

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
  
  if (file.size > 20 * 1024 * 1024) {
    showError('📁 The image is too large (over 20 MB). Please compress or take a screenshot of the receipt and try again.');
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
      const rawDetail = responseData.detail || responseData.message || JSON.stringify(responseData);
      throw new Error(_friendlyError(rawDetail, response.status));
    }

    lastSplitResponse = responseData;
    renderResults(responseData);
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      showError('Cannot reach the API server. Make sure the backend is running on ' + API_BASE_URL + ' and try again.');
    } else {
      showError(err.message);
    }
  } finally {
    setLoading(false);
  }
});

/**
 * Translates raw backend error messages into user-friendly, actionable text.
 */
function _friendlyError(detail, httpStatus) {
  if (typeof detail !== 'string') detail = JSON.stringify(detail);

  if (detail.includes('HEIC') || detail.includes('HEIF'))
    return '📱 iPhone HEIC format detected. Go to Settings → Camera → Formats → "Most Compatible" to save as JPEG, then re-upload.';

  if (detail.includes('too large') || detail.includes('20 MB'))
    return '📁 The image is too large (over 20 MB). Please take a screenshot of the receipt or compress the image before uploading.';

  if (detail.includes('does not appear to contain a bill') || detail.includes('No line items'))
    return '🖼️ No receipt found in the image. Please upload a clear photo of your restaurant bill, grocery receipt, or hand-written menu.';

  if (detail.includes('could not be read as an image'))
    return '⚠️ The file appears corrupted or is not a valid image. Please re-export or re-screenshot the receipt and try again.';

  if (detail.includes('timed out') || httpStatus === 504)
    return '⏱️ The AI took too long to read the receipt (>15s). Please try again — if the receipt is very complex, try cropping to just the items and total.';

  if (detail.includes('extraction failed') || detail.includes('parsing failed'))
    return '🤖 The AI could not understand the receipt format. Please check the image is well-lit and not blurry, then try again.';

  if (httpStatus === 429)
    return '🚦 Too many requests. Please wait a few seconds and try again.';

  if (httpStatus >= 500)
    return `🔧 Server error (${httpStatus}). The backend encountered an unexpected problem — please try again in a moment.`;

  return detail;
}


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

  // 5. Money Flow Diagram (Mermaid)
  renderMoneyFlowDiagram(data);

  // 6. Raw JSON Inspector
  rawJsonViewer.textContent = JSON.stringify(data, null, 2);

  // Reveal results
  resultsContainer.classList.remove('hidden');
  resultsContainer.scrollIntoView({ behavior: 'smooth' });
}

/**
 * Builds and renders a Mermaid flowchart showing the settle-up money flow.
 * For each person who owes the payer, draws an arrow: Person -->|₹amount| Payer
 * Color-codes: payer = green, debtors = purple, no-payer = neutral.
 */
async function renderMoneyFlowDiagram(data) {
  const container = document.getElementById('mermaid-diagram');
  if (!container) return;
  container.innerHTML = '';

  const payer = data.paid_by;
  const settleUp = data.settle_up || [];
  const perPerson = data.per_person || [];

  if (!payer || settleUp.length === 0) {
    // No payer — show a simple breakdown of totals per person
    let def = 'graph LR\n';
    def += '  BILL(["🧾 Bill Total\\n₹' + data.grand_total.toFixed(0) + '"])\n';
    perPerson.forEach((p, i) => {
      const nodeId = 'P' + i;
      const safe = p.name.replace(/[^a-zA-Z0-9]/g, '_');
      def += `  ${nodeId}(["👤 ${p.name}\\n₹${p.total.toFixed(0)}"])\n`;
      def += `  BILL --> ${nodeId}\n`;
    });
    def += '  style BILL fill:#4f46e5,color:#fff,stroke:#6366f1\n';
    await _renderMermaid(container, def);
    return;
  }

  // Build directed graph: each debtor → payer
  let def = 'graph LR\n';

  // Payer node
  const payerSafe = payer.replace(/[^a-zA-Z0-9]/g, '_');
  def += `  ${payerSafe}(["💳 ${payer}\\n Paid ₹${data.grand_total.toFixed(0)}"])\n`;
  def += `  style ${payerSafe} fill:#059669,color:#fff,stroke:#047857\n`;

  settleUp.forEach((t, i) => {
    const fromSafe = (t.from || t.from_person || '').replace(/[^a-zA-Z0-9]/g, '_');
    const fromName = t.from || t.from_person || 'Person';
    const toSafe = (t.to || t.to_person || payer).replace(/[^a-zA-Z0-9]/g, '_');
    const amt = typeof t.amount === 'number' ? t.amount : parseFloat(t.amount);

    def += `  ${fromSafe}(["👤 ${fromName}"])\n`;
    def += `  ${fromSafe} -->|"₹${amt.toFixed(0)}"| ${toSafe}\n`;
    def += `  style ${fromSafe} fill:#4f46e5,color:#fff,stroke:#6366f1\n`;
  });

  await _renderMermaid(container, def);
}

async function _renderMermaid(container, definition) {
  try {
    const id = 'mermaid-' + Date.now();
    const { svg } = await mermaid.render(id, definition);
    container.innerHTML = svg;
  } catch (e) {
    container.innerHTML = '<span class="mermaid-placeholder">⚠️ Flow diagram unavailable for this result.</span>';
    console.warn('Mermaid render failed:', e);
  }
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
