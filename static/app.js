// --- HELPER FUNCTIONS ---

// Safely format external URLs to ensure absolute pathing
function formatUrl(rawUrl) {
    if (!rawUrl) return '#';
    const trimmed = rawUrl.trim();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
        return trimmed;
    }
    return `https://${trimmed}`;
}

// Convert ISO timestamps to relative time strings
function timeAgo(dateString) {
    if (!dateString) return '';
    const diffInMinutes = Math.floor((new Date() - new Date(dateString)) / 1000 / 60);
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) return `${diffInHours}h ago`;
    return `${Math.floor(diffInHours / 24)}d ago`;
}


// --- API FEED LOADERS ---

// Fetch & Render Breaking News (Left Column)
async function loadBreakingNews() {
    const container = document.getElementById('breakingNewsFeed');
    if (!container) return;

    try {
        const response = await fetch('/api/breaking-news');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        
        if (!data.articles || data.articles.length === 0) {
            container.innerHTML = '<p class="text-slate-400 text-xs">No headlines available.</p>';
            return;
        }

        container.innerHTML = ''; // Clear loading placeholder

        data.articles.forEach(article => {
            if (!article.url) return;

            const link = document.createElement('a');
            link.href = formatUrl(article.url); 
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.className = 'group block border-b border-sky-50 pb-3 p-2 rounded-lg hover:bg-sky-50/70 transition-all cursor-pointer no-underline';

            link.innerHTML = `
                <div class="flex items-center justify-between gap-2 mb-1">
                    <span class="bg-sky-100 group-hover:bg-sky-200 text-sky-800 text-[10px] font-bold px-1.5 py-0.5 rounded uppercase truncate max-w-[120px]">
                        ${article.source?.name || 'NEWS'}
                    </span>
                    <span class="text-slate-400 text-[10px]">${timeAgo(article.publishedAt)}</span>
                </div>
                <h4 class="font-semibold text-slate-800 group-hover:text-sky-600 transition-colors leading-snug line-clamp-2 text-sm">
                    ${article.title} ↗
                </h4>
            `;

            container.appendChild(link);
        });

    } catch (err) {
        console.error("Error loading breaking news:", err);
        container.innerHTML = '<p class="text-rose-400 text-xs">Failed to load breaking news.</p>';
    }
}

// Fetch & Render Visual News (Right Column)
async function loadVisualNews() {
    const container = document.getElementById('visualNewsFeed');
    if (!container) return;

    try {
        const response = await fetch('/api/visual-news');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        const articles = (data.articles || []).filter(a => a.urlToImage && a.url).slice(0, 3);

        if (articles.length === 0) {
            container.innerHTML = '<p class="text-slate-400 text-xs">No visual feed available.</p>';
            return;
        }

        container.innerHTML = ''; // Clear loading placeholder

        articles.forEach(article => {
            const link = document.createElement('a');
            link.href = formatUrl(article.url);
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.className = 'group block bg-white border border-sky-100 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all cursor-pointer no-underline';

            link.innerHTML = `
                <div class="relative h-36 bg-slate-100 overflow-hidden">
                    <img src="${article.urlToImage}" 
                         alt="News Thumbnail" 
                         class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" 
                         onerror="this.src='https://images.unsplash.com/photo-1585829365295-ab7cd400c167?auto=format&fit=crop&w=400&q=80'">
                    <div class="absolute top-2 left-2">
                        <span class="bg-slate-900/80 text-white text-[10px] font-bold px-2 py-0.5 rounded uppercase">
                            ${article.source?.name || 'UPDATE'}
                        </span>
                    </div>
                </div>
                <div class="p-4 space-y-2">
                    <h3 class="font-serif font-bold text-slate-900 leading-snug line-clamp-2 group-hover:text-sky-600 transition-colors">
                        ${article.title} ↗
                    </h3>
                    <p class="text-xs text-slate-500 line-clamp-2">
                        ${article.description || ''}
                    </p>
                    <div class="pt-2 border-t border-sky-50 text-[10px] text-slate-400 text-right">
                        <span>${timeAgo(article.publishedAt)}</span>
                    </div>
                </div>
            `;

            container.appendChild(link);
        });

    } catch (err) {
        console.error("Error loading visual news:", err);
        container.innerHTML = '<p class="text-rose-400 text-xs">Failed to load visual news.</p>';
    }
}


// --- MAIN DOM INITIALIZATION & EVENT LISTENERS ---

function initApp() {
    // Load external API feeds
    loadBreakingNews();
    loadVisualNews();

    const checkerForm = document.getElementById('checkerForm');
    const newSearchBtn = document.getElementById('newSearchBtn');
    const submitBtn = document.getElementById('submitBtn');
    const btnText = document.getElementById('btnText');
    const loader = document.getElementById('loader');

    // 1. "New Search" Button Click Handler
    if (newSearchBtn) {
        newSearchBtn.addEventListener('click', (e) => {
            e.preventDefault();

            // Clear input textarea
            const textInput = document.getElementById('article_text');
            if (textInput) {
                textInput.value = '';
            }

            // Hide main results container
            const resultsContainer = document.getElementById('resultsContainer');
            if (resultsContainer) {
                resultsContainer.classList.add('hidden');
            }

            // Clear evidence content
            const evidenceList = document.getElementById('evidenceList');
            if (evidenceList) {
                evidenceList.innerHTML = '';
            }

            // Clear individual text output fields
            const elementsToClear = ['verdictBadge', 'confidenceScore', 'extractedClaim', 'summaryExplanation'];
            elementsToClear.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.textContent = '';
            });

            // Ensure Verify Claim button UI state is reset to default
            if (submitBtn) submitBtn.disabled = false;
            if (btnText) btnText.textContent = "Verify Claim";
            if (loader) loader.classList.add('hidden');

            // Focus and smooth scroll back to input area
            if (textInput) {
                textInput.focus();
                textInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    // 2. Fact Check Form Submission Handler
    if (checkerForm) {
        checkerForm.addEventListener('submit', async (e) => {
            e.preventDefault(); 
            
            const resultsContainer = document.getElementById('resultsContainer');
            const textInput = document.getElementById('article_text')?.value;

            if (!textInput || textInput.trim().length < 10) {
                alert("Please enter a claim with at least 10 characters.");
                return;
            }

            // UI Loading State on Verify Button
            if (submitBtn) submitBtn.disabled = true;
            if (btnText) btnText.textContent = "Analyzing & Verifying...";
            if (loader) loader.classList.remove('hidden');
            if (resultsContainer) resultsContainer.classList.add('hidden');

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: textInput })
                });

                if (!response.ok) {
                    throw new Error(`Server returned status ${response.status}`);
                }

                const data = await response.json();

                // Update UI dynamically
                if (document.getElementById('verdictBadge')) {
                    document.getElementById('verdictBadge').textContent = data.verdict;
                }
                if (document.getElementById('confidenceScore')) {
                    document.getElementById('confidenceScore').textContent = `${(data.confidence_score * 100).toFixed(1)}%`;
                }
                if (document.getElementById('extractedClaim')) {
                    document.getElementById('extractedClaim').textContent = `"${data.extracted_claim}"`;
                }
                if (document.getElementById('summaryExplanation')) {
                    document.getElementById('summaryExplanation').textContent = data.summary_explanation;
                }

                // Render evidence cards
                const evidenceList = document.getElementById('evidenceList');
                if (evidenceList) {
                    evidenceList.innerHTML = '';

                    (data.evidence_breakdown || []).forEach(item => {
                        const card = document.createElement('div');
                        card.className = 'bg-[#f2f7fc] border border-sky-100 p-4 rounded-lg space-y-2';
                        card.innerHTML = `
                            <div class="flex items-center justify-between text-xs">
                                <span class="font-bold">${item.nli_label}</span>
                                <a href="${item.source_url}" target="_blank" rel="noopener noreferrer" class="text-indigo-600 hover:underline">Link</a>
                            </div>
                            <p class="text-xs text-slate-700 italic">"${item.snippet}"</p>
                        `;
                        evidenceList.appendChild(card);
                    });
                }

                if (resultsContainer) {
                    resultsContainer.classList.remove('hidden');
                }

            } catch (err) {
                alert(`Verification failed: ${err.message}`);
            } finally {
                if (submitBtn) submitBtn.disabled = false;
                if (btnText) btnText.textContent = "Verify Claim";
                if (loader) loader.classList.add('hidden');
            }
        });
    }
}

// Single initialization entry point
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}