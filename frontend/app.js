// Fair-Split Frontend Application Logic
// Configurable API base URL with LocalStorage persistence and smart cloud host detection
const DEFAULT_API_URL = window.API_BASE_URL || (
  window.location.hostname === 'localhost' && window.location.port === '3000'
    ? 'http://localhost:8000'
    : window.location.origin
);
let API_BASE_URL = localStorage.getItem('fair_split_api_url') || DEFAULT_API_URL;

let selectedBase64Image = null;
let lastSplitResponse = null;

// Preset Scenarios Data (R1 - R11)
const SAMPLE_PRESETS = {
  R1: {
    description: "Three of us — Ravi, Neha, Sameer. Ravi had the cappuccino and the sandwich. Neha had the pasta and the lime soda. Sameer had the brownie. Sameer paid.",
    imageFile: "samples/R1.png",
    filename: "R1_brew_and_bite_cafe.png",
    title: "R1: Brew & Bite Café (3p • Official Spec)"
  },
  R2: {
    description: "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid.",
    imageFile: "samples/R2.png",
    filename: "R2_tamarind_kitchen.png",
    title: "R2: Tamarind Kitchen (4p • Official Spec)"
  },
  R3: {
    description: "Ishaan, Meera, Rohit. Pizza, pasta and garlic bread shared equally by all three. The two beers were Ishaan and Rohit only. The mojito was Meera's. Rohit paid.",
    imageFile: "samples/R3.png",
    filename: "R3_the_daily_grind.png",
    title: "R3: The Daily Grind (3p • Official Spec)"
  },
  R4: {
    description: "Dev and Nikhil each had a chicken biryani. Anjali had the veg biryani. Farah had the rogan josh. The raita and soft drinks were common to all four. We used a 15% off coupon. Anjali paid.",
    imageFile: "samples/R4.png",
    filename: "R4_spice_route.png",
    title: "R4: Spice Route (4p • Official Spec)"
  },
  R5: {
    description: "Two of us: Kavya and Deepak. We each had one chai. Deepak had the Vada Pav, and Kavya had the Banana Muffin. Kavya paid.",
    imageFile: "samples/R5.png",
    filename: "R5_filter_brew_cafe.png",
    title: "R5: Filter & Brew Cafe (2p)"
  },
  R6: {
    description: "Four of us: Rohan, Divya, Arjun, Preethi. Rohan and Arjun shared the Butter Chicken (2 portions). Divya had the Palak Paneer alone. We all shared the Garlic Naan (6 pcs), Laccha Paratha, and Jeera Rice. The Dahi Puri starter was shared by Divya and Preethi. Gulab Jamun was shared equally across all four. Rohan paid.",
    imageFile: "samples/R6.png",
    filename: "R6_spice_affair_receipt.png",
    title: "R6: Spice Affair (4p)"
  },
  R7: {
    description: "Three of us: Sundar, Lakshmi, Aditya. Sundar had a Paper Roast Dosa alone. Lakshmi had the Onion Uttapam and one Idli Vada Combo. Aditya had Ghee Pongal and the other Idli Vada Combo. We all shared the 2 Masala Dosas, 3 Filter Kaapis, and Sambar Vada. Lakshmi had the Mango Lassi alone. Aditya paid.",
    imageFile: "samples/R7.png",
    filename: "R7_dosa_plaza_receipt.png",
    title: "R7: Dosa Plaza (3p)"
  },
  R8: {
    description: "Five of us: Natasha, Marcus, Elena, Rahul, Simone. Marcus and Elena shared the 2 Grilled Tenderloins. Rahul had the Pan-Seared Salmon alone. Natasha and Simone shared the Truffle Risotto. All five shared the Amuse-Bouche, Burrata, Seared Scallops, and 3 Seasonal Sides. Natasha and Elena shared the 2 Tiramisus. Rahul had the Crème Brûlée alone. Sparkling water shared across all five. Freshly squeezed juice for Natasha and Marcus. Natasha paid.",
    imageFile: "samples/R8.png",
    filename: "R8_olive_vine_receipt.png",
    title: "R8: Olive & Vine Fine Dining (5p)"
  },
  R9: {
    description: "Five of us: Zara, Neel, Pooja, Farhan, Tina. Neel and Farhan had 2 Kingfisher Ultras each. Zara and Tina had the Signature Mojitos. Pooja had the Passion Fruit Cooler (non-alcoholic). Both Red Bulls were shared by Neel and Farhan. The Chicken Satay Skewers were shared between Zara, Pooja, and Tina. Truffle Fries shared by all five. Mezze Platter shared by Zara, Pooja, and Tina. Peri-Peri Burger was Farhan's. Margherita Flatbread shared by all five. Zara paid.",
    imageFile: "samples/R9.png",
    filename: "R9_sky_high_lounge_receipt.png",
    title: "R9: Sky High Lounge (5p)"
  },
  R10: {
    description: "Party of six: Vikram, Ananya, Kabir, Rhea, Siddharth, Tara. Vikram and Kabir shared the 3 pints of Craft IPA Beer. Ananya and Tara had the Mint Mojitos. Siddharth and Rhea shared the Smoked BBQ Pork Ribs and Crispy Calamari. All six of us shared the 2 Truffle Pizzas, Loaded Nachos, and Mineral Water. Ananya had the Caesar Salad. Rhea, Tara, and Vikram shared the 2 Chocolate Lava Cakes. Eco packaging shared by all. Vikram paid the entire bill.",
    imageFile: "samples/R10.png",
    filename: "R10_urban_brewery_complex.png",
    title: "R10: Urban Brewery (6p)"
  },
  R11: {
    description: "Birthday party for Arjun, 8 guests: Arjun, Meena, Prashant, Kavitha, Suresh, Divyanka, Roshan, Teja. Welcome Mocktail Shots were one per person (8 total) equally shared. Appetizer Platter (Veg) shared between Kavitha, Meena, Divyanka. Chicken Seekh Kebab shared by Arjun, Prashant, Suresh, Roshan. Mixed Seafood Grill Platter was Prashant and Roshan only. Mushroom Soup shared by all 8. Garden Fresh Salad shared by Kavitha, Meena, Divyanka (3 bowls). Grilled Lobster (Half) — one for Arjun, one for Prashant. Chicken en Papillote — Arjun, Suresh, Roshan. Truffle Risotto — Kavitha and Divyanka. Dal Bukhara, Assorted Breads, Biryani Station, and Dessert Platters shared across all 8. Petit Fours shared by Arjun and Meena only. Sparkling Water and OJ shared equally across all 8. Banquet Hall and Floral Decoration costs split equally across all 8. Cake Cutting charged once to Arjun. The advance deposit of ₹15,000 was paid by Meena already. Arjun is paying the balance today.",
    imageFile: "samples/R11.png",
    filename: "R11_grand_meridian_banquet.png",
    title: "R11: Hotel Banquet (8p)"
  },
  R12: {
    description: "We are four friends: Kabir, Tanya, Arjun, Sneha. We ate at Punjab Grill — 2 Butter Chickens, Dal Makhani, Garlic Naan, and Lassi. But the waiter handed us Table 9's bill by mistake which has Sushi and Ramen. This receipt is completely wrong and does not match our meal.",
    imageFile: "samples/R12.png",
    filename: "R12_mismatched_wrong_receipt.png",
    title: "R12: ⚠️ Wrong Receipt / Table Mismatch (Error Catch Test)"
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

const loadingIndicator = document.getElementById('loading-indicator');
const errorCard = document.getElementById('error-card');
const errorMessage = document.getElementById('error-message');
const resultsContainer = document.getElementById('results-container');
const rawJsonViewer = document.getElementById('raw-json-viewer');

const copyTableBtn = document.getElementById('copy-table-btn');
const copySettleBtn = document.getElementById('copy-settle-btn');
const shareWhatsAppBtn = document.getElementById('share-whatsapp-btn');

// API Settings Elements
const settingsToggleBtn = document.getElementById('settings-toggle-btn');
const apiConfigPanel = document.getElementById('api-config-panel');
const apiUrlInput = document.getElementById('api-url-input');
const saveApiUrlBtn = document.getElementById('save-api-url-btn');
const testApiHealthBtn = document.getElementById('test-api-health-btn');
const apiTestResult = document.getElementById('api-test-result');
const apiStatusBadge = document.getElementById('api-status-badge');

// Toast Element
const toastEl = document.getElementById('toast');

// Image Lightbox Modal Elements
const imageModal = document.getElementById('image-modal');
const modalBackdrop = document.getElementById('modal-backdrop');
const closeModalBtn = document.getElementById('close-modal-btn');
const modalCloseActionBtn = document.getElementById('modal-close-action-btn');
const modalFullImage = document.getElementById('modal-full-image');
const modalImageTitle = document.getElementById('modal-image-title');
const modalImageMeta = document.getElementById('modal-image-meta');
const previewThumbBtn = document.getElementById('preview-thumb-btn');
const viewFullImageBtn = document.getElementById('view-full-image-btn');
const viewReceiptFromResultsBtn = document.getElementById('view-receipt-from-results-btn');

function openImageModal() {
  const src = receiptPreview.src;
  if (!src) {
    showToast('No receipt image loaded yet.');
    return;
  }
  modalFullImage.src = src;
  modalImageTitle.textContent = previewFilename.textContent || 'Receipt Photo';
  modalImageMeta.textContent = previewMeta.textContent || 'High-Resolution View';
  imageModal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeImageModal() {
  imageModal.classList.add('hidden');
  document.body.style.overflow = '';
}

if (previewThumbBtn) previewThumbBtn.addEventListener('click', openImageModal);
if (viewFullImageBtn) viewFullImageBtn.addEventListener('click', (e) => { e.stopPropagation(); openImageModal(); });
if (viewReceiptFromResultsBtn) viewReceiptFromResultsBtn.addEventListener('click', openImageModal);
if (closeModalBtn) closeModalBtn.addEventListener('click', closeImageModal);
if (modalCloseActionBtn) modalCloseActionBtn.addEventListener('click', closeImageModal);
if (modalBackdrop) modalBackdrop.addEventListener('click', closeImageModal);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && imageModal && !imageModal.classList.contains('hidden')) {
    closeImageModal();
  }
});

function showToast(message) {
  if (!toastEl) return;
  toastEl.textContent = message;
  toastEl.classList.remove('hidden');
  setTimeout(() => {
    toastEl.classList.add('hidden');
  }, 3000);
}

// -------------------------------------------------------------
// API Settings Panel Controller
// -------------------------------------------------------------
apiUrlInput.value = API_BASE_URL;

settingsToggleBtn.addEventListener('click', () => {
  apiConfigPanel.classList.toggle('hidden');
});

saveApiUrlBtn.addEventListener('click', () => {
  const newUrl = apiUrlInput.value.trim().replace(/\/+$/, '');
  if (!newUrl) return;
  API_BASE_URL = newUrl;
  localStorage.setItem('fair_split_api_url', newUrl);
  apiTestResult.textContent = 'Saved! Testing endpoint...';
  apiTestResult.style.color = 'var(--text-muted)';
  testApiHealth();
});

testApiHealthBtn.addEventListener('click', testApiHealth);

async function testApiHealth() {
  const targetUrl = apiUrlInput.value.trim().replace(/\/+$/, '');
  apiTestResult.textContent = 'Testing connection...';
  apiTestResult.style.color = 'var(--text-muted)';

  try {
    const res = await fetch(`${targetUrl}/health`);
    if (res.ok) {
      const data = await res.json();
      apiTestResult.textContent = `Connected! Status: ${data.status.toUpperCase()} (v${data.version})`;
      apiTestResult.style.color = 'var(--success-text)';
      apiStatusBadge.textContent = 'API: Online';
      apiStatusBadge.className = 'badge-online';
      showToast('API Connected Successfully! ✅');
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (err) {
    apiTestResult.textContent = `Failed to connect: ${err.message}`;
    apiTestResult.style.color = 'var(--danger-text)';
    apiStatusBadge.textContent = 'API: Offline';
    apiStatusBadge.className = 'badge-offline';
  }
}

// -------------------------------------------------------------
// Quick Phrase Helpers
// -------------------------------------------------------------
document.querySelectorAll('.helper-tag').forEach(btn => {
  btn.addEventListener('click', () => {
    const appendText = btn.dataset.append;
    const current = descriptionInput.value.trim();
    if (current) {
      descriptionInput.value = current + ' ' + appendText;
    } else {
      descriptionInput.value = appendText;
    }
    descriptionInput.focus();
    showToast(`Added: "${appendText}"`);
  });
});

// -------------------------------------------------------------
// Preset Scenarios Controller
// -------------------------------------------------------------
const sampleChips = document.querySelectorAll('.sample-chip');
sampleChips.forEach(chip => {
  chip.addEventListener('click', () => {
    sampleChips.forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    const sampleKey = chip.getAttribute('data-sample');
    loadSamplePreset(sampleKey);
  });
});

async function loadSamplePreset(key) {
  const preset = SAMPLE_PRESETS[key];
  if (!preset) return;

  descriptionInput.value = preset.description;

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
        submitBtn.disabled = false;
        hideError();
      };
      reader.readAsDataURL(blob);
    }
  } catch (err) {
    console.warn("Could not auto-load sample image:", err);
  }
}

// Auto-load default R1 preset on first load
loadSamplePreset('R1');

// -------------------------------------------------------------
// File Upload & Base64 Conversion
// -------------------------------------------------------------
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
    selectedBase64Image = dataUrl.split(',')[1];

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
  dropzone.style.borderColor = '#CBD5E1';
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.style.borderColor = '#CBD5E1';
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    fileInput.files = e.dataTransfer.files;
    handleFileSelection(e.dataTransfer.files[0]);
  }
});

// -------------------------------------------------------------
// Form Submission & API Call
// -------------------------------------------------------------
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

let loadingTimerInterval = null;
let loadingStartTime = null;

function setLoading(isLoading) {
  const timerEl = document.getElementById('loading-timer');
  const subtextEl = document.getElementById('loading-subtext');
  const step1 = document.getElementById('step-pill-1');
  const step2 = document.getElementById('step-pill-2');
  const step3 = document.getElementById('step-pill-3');

  if (isLoading) {
    loadingIndicator.classList.remove('hidden');
    submitBtn.disabled = true;

    // Reset steps
    if (step1) { step1.className = 'step-pill active'; }
    if (step2) { step2.className = 'step-pill'; }
    if (step3) { step3.className = 'step-pill'; }
    if (subtextEl) { subtextEl.textContent = 'Scanning receipt layout, line items, and tax lines...'; }

    // Start timer & step progression
    loadingStartTime = Date.now();
    if (timerEl) timerEl.textContent = '0.0s';

    clearInterval(loadingTimerInterval);
    loadingTimerInterval = setInterval(() => {
      const elapsed = (Date.now() - loadingStartTime) / 1000;
      if (timerEl) timerEl.textContent = `${elapsed.toFixed(1)}s`;

      if (elapsed > 1.2 && elapsed <= 2.5) {
        if (step1) step1.className = 'step-pill completed';
        if (step2) step2.className = 'step-pill active';
        if (subtextEl) subtextEl.textContent = 'Cross-referencing food items with group members...';
      } else if (elapsed > 2.5) {
        if (step1) step1.className = 'step-pill completed';
        if (step2) step2.className = 'step-pill completed';
        if (step3) step3.className = 'step-pill active';
        if (subtextEl) subtextEl.textContent = 'Applying Largest Remainder Method for exact rupee settlement...';
      }
    }, 100);

  } else {
    clearInterval(loadingTimerInterval);
    loadingIndicator.classList.add('hidden');
    submitBtn.disabled = false;

    if (step1) step1.className = 'step-pill completed';
    if (step2) step2.className = 'step-pill completed';
    if (step3) step3.className = 'step-pill completed';
  }
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorCard.classList.remove('hidden');
  errorCard.scrollIntoView({ behavior: 'smooth' });
}

function hideError() {
  errorCard.classList.add('hidden');
  errorMessage.textContent = '';
}

// -------------------------------------------------------------
// Render Results
// -------------------------------------------------------------
function renderResults(data) {
  // 0. KPI Stats Cards
  const statGrandTotal = document.getElementById('stat-grand-total');
  const statPersonSum = document.getElementById('stat-person-sum');
  const statDinerCount = document.getElementById('stat-diner-count');
  const statPayerName = document.getElementById('stat-payer-name');
  const statReconSub = document.getElementById('stat-recon-sub');

  statGrandTotal.textContent = `₹${data.grand_total.toFixed(2)}`;
  statPersonSum.textContent = `₹${data.reconciliation.sum_of_person_totals.toFixed(2)}`;
  statDinerCount.textContent = (data.per_person || []).length;
  statPayerName.textContent = data.paid_by || 'Not Specified';

  const isMatch = data.reconciliation && data.reconciliation.matches_bill;
  statReconSub.textContent = isMatch ? 'Exact Zero-Drift Match' : 'Discrepancy Flagged';

  // 1. Confidence Banner
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

  // 2. Reconciliation Status Banner
  const reconciliationBanner = document.getElementById('reconciliation-banner');
  const reconIcon = document.getElementById('recon-icon');
  const reconTitle = document.getElementById('recon-title');
  const reconSubtitle = document.getElementById('recon-subtitle');

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

  // 3. Settle Up Section
  const paidByName = document.getElementById('paid-by-name');
  const settleUpList = document.getElementById('settle-up-list');
  paidByName.textContent = data.paid_by || 'Not Specified';
  settleUpList.innerHTML = '';

  if (data.settle_up && data.settle_up.length > 0) {
    data.settle_up.forEach((t) => {
      const li = document.createElement('li');
      li.className = 'settle-up-item';
      
      const fromInitial = (t.from || t.from_person || 'U').charAt(0).toUpperCase();
      const toInitial = (t.to || t.to_person || 'P').charAt(0).toUpperCase();

      li.innerHTML = `
        <div class="settle-left">
          <div class="avatar-circle">${fromInitial}</div>
          <span class="settle-text">
            <strong>${escapeHtml(t.from || t.from_person)}</strong>
            <span class="transfer-arrow"> ➔ </span>
            <strong>${escapeHtml(t.to || t.to_person)}</strong>
          </span>
        </div>
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

  // 4. Per Person Table
  const splitTableBody = document.getElementById('split-table-body');
  splitTableBody.innerHTML = '';
  const payer = data.paid_by ? data.paid_by.trim().toLowerCase() : null;

  data.per_person.forEach((person) => {
    const tr = document.createElement('tr');
    const isPayer = payer && person.name.trim().toLowerCase() === payer;
    if (isPayer) tr.className = 'is-payer-row';

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

  // 5. Assumptions & Flags
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

  // 6. Money Flow Diagram (Mermaid)
  renderMoneyFlowDiagram(data);

  // 7. Raw JSON Inspector
  rawJsonViewer.textContent = JSON.stringify(data, null, 2);

  // Reveal results with smooth scroll
  resultsContainer.classList.remove('hidden');
  resultsContainer.scrollIntoView({ behavior: 'smooth' });
}

/**
 * Builds and renders a Mermaid flowchart showing the settle-up money flow.
 */
async function renderMoneyFlowDiagram(data) {
  const container = document.getElementById('mermaid-diagram');
  if (!container) return;
  container.innerHTML = '';

  const payer = data.paid_by;
  const settleUp = data.settle_up || [];
  const perPerson = data.per_person || [];

  if (!payer || settleUp.length === 0) {
    let def = 'graph LR\n';
    def += '  BILL(["🧾 Bill Total\\n₹' + data.grand_total.toFixed(0) + '"])\n';
    perPerson.forEach((p, i) => {
      const nodeId = 'P' + i;
      def += `  ${nodeId}(["👤 ${p.name}\\n₹${p.total.toFixed(0)}"])\n`;
      def += `  BILL --> ${nodeId}\n`;
      def += `  style ${nodeId} fill:#EEF2FF,color:#3730A3,stroke:#6366F1,stroke-width:2px\n`;
    });
    def += '  style BILL fill:#FEF3C7,color:#92400E,stroke:#F59E0B,stroke-width:2px\n';
    await _renderMermaid(container, def);
    return;
  }

  let def = 'graph LR\n';
  const payerSafe = payer.replace(/[^a-zA-Z0-9]/g, '_');
  def += `  ${payerSafe}(["💳 ${payer}\\n Paid ₹${data.grand_total.toFixed(0)}"])\n`;
  def += `  style ${payerSafe} fill:#ECFDF5,color:#065F46,stroke:#10B981,stroke-width:2.5px\n`;

  settleUp.forEach((t, i) => {
    const fromSafe = (t.from || t.from_person || '').replace(/[^a-zA-Z0-9]/g, '_');
    const fromName = t.from || t.from_person || 'Person';
    const toSafe = (t.to || t.to_person || payer).replace(/[^a-zA-Z0-9]/g, '_');
    const amt = typeof t.amount === 'number' ? t.amount : parseFloat(t.amount);

    def += `  ${fromSafe}(["👤 ${fromName}"])\n`;
    def += `  ${fromSafe} -->|"₹${amt.toFixed(0)}"| ${toSafe}\n`;
    def += `  style ${fromSafe} fill:#EEF2FF,color:#3730A3,stroke:#6366F1,stroke-width:2px\n`;
  });

  await _renderMermaid(container, def);
}

async function _renderMermaid(container, definition) {
  try {
    const id = 'mermaid-' + Date.now();
    const { svg } = await mermaid.render(id, definition);
    container.innerHTML = svg;
  } catch (e) {
    container.innerHTML = '<span style="color:#94a3b8;font-size:12px;">⚠️ Flow diagram unavailable for this result.</span>';
    console.warn('Mermaid render failed:', e);
  }
}

// -------------------------------------------------------------
// Copy & Share Handlers with Visual Feedback & Robust Fallback
// -------------------------------------------------------------
function copyToClipboard(text, successMsg, btnEl) {
  const originalHtml = btnEl ? btnEl.innerHTML : null;

  function onSuccess() {
    showToast(successMsg);
    if (btnEl) {
      btnEl.innerHTML = '<span>✅</span> Copied!';
      btnEl.style.borderColor = '#10B981';
      btnEl.style.color = '#059669';
      setTimeout(() => {
        if (originalHtml) btnEl.innerHTML = originalHtml;
        btnEl.style.borderColor = '';
        btnEl.style.color = '';
      }, 2000);
    }
  }

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(onSuccess).catch(() => {
      _fallbackCopy(text, onSuccess);
    });
  } else {
    _fallbackCopy(text, onSuccess);
  }
}

function _fallbackCopy(text, callback) {
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.style.position = "fixed";
  textArea.style.left = "-999999px";
  textArea.style.top = "-999999px";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  try {
    document.execCommand('copy');
    if (callback) callback();
  } catch (err) {
    console.error('Fallback copy failed', err);
    showToast('Failed to copy. Please copy manually.');
  }
  document.body.removeChild(textArea);
}

function showToast(message) {
  let toast = document.getElementById('fair-split-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'fair-split-toast';
    toast.className = 'fair-toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.classList.remove('show');
  }, 2600);
}

copyTableBtn.addEventListener('click', () => {
  if (!lastSplitResponse || !lastSplitResponse.per_person) {
    showToast('No calculation available to copy.');
    return;
  }
  let text = "Person\tSubtotal\tTax Share\tService Share\tDiscount Share\tTotal Payable\n";
  lastSplitResponse.per_person.forEach(p => {
    text += `${p.name}\t₹${p.subtotal.toFixed(2)}\t₹${p.tax_share.toFixed(2)}\t₹${p.service_share.toFixed(2)}\t₹${p.discount_share.toFixed(2)}\t₹${p.total.toFixed(2)}\n`;
  });
  copyToClipboard(text, '📊 Table copied to clipboard!', copyTableBtn);
});

copySettleBtn.addEventListener('click', () => {
  if (!lastSplitResponse || !lastSplitResponse.settle_up || lastSplitResponse.settle_up.length === 0) {
    showToast('No settle-up transfers available.');
    return;
  }
  let text = `💸 Fair-Split Settle-Up (Paid by ${lastSplitResponse.paid_by || 'Unknown'}):\n\n`;
  lastSplitResponse.settle_up.forEach(t => {
    text += `• ${t.from} pays ${t.to}: ₹${t.amount.toFixed(2)}\n`;
  });
  text += `\nTotal Bill: ₹${lastSplitResponse.grand_total.toFixed(2)}`;
  copyToClipboard(text, '📋 Settle-up summary copied!', copySettleBtn);
});

shareWhatsAppBtn.addEventListener('click', () => {
  if (!lastSplitResponse || !lastSplitResponse.settle_up || lastSplitResponse.settle_up.length === 0) {
    showToast('No settle-up transfers available.');
    return;
  }
  let text = `🧾 *Fair-Split Bill Settlement*\n`;
  text += `💰 *Total Bill:* ₹${lastSplitResponse.grand_total.toFixed(2)}\n`;
  text += `💳 *Paid by:* ${lastSplitResponse.paid_by || 'Unknown'}\n\n`;
  text += `*Direct Reimbursements:*\n`;
  lastSplitResponse.settle_up.forEach(t => {
    text += `👉 *${t.from}* pays *${t.to}*: ₹${t.amount.toFixed(2)}\n`;
  });
  text += `\n_Calculated with Fair-Split Engine_`;

  const waUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;
  window.open(waUrl, '_blank');
  showToast('Opening WhatsApp... 📱');
});

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
