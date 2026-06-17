/* PrismRAG — Landing page interactions */

// ── Nav scroll effect ──────────────────────────────────────────────────────
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 20);
}, { passive: true });

// ── Code tab switcher ──────────────────────────────────────────────────────
const snippets = {
  Intake: `<span class="c-comment"># Send your mapping + data — PrismRAG does the rest</span>
<span class="c-keyword">POST</span> /api/prismrag/jobs

{
  <span class="c-key">"tenant_id"</span>: <span class="c-str">"your-tenant-uuid"</span>,
  <span class="c-key">"source_type"</span>: <span class="c-str">"file"</span>,
  <span class="c-key">"strategy"</span>: <span class="c-str">"mlp"</span>,
  <span class="c-key">"mapping"</span>: {
    <span class="c-key">"categories"</span>: [
      { <span class="c-key">"slug"</span>: <span class="c-str">"risk"</span>, <span class="c-key">"label"</span>: <span class="c-str">"Risk &amp; Compliance"</span> },
      { <span class="c-key">"slug"</span>: <span class="c-str">"growth"</span>, <span class="c-key">"label"</span>: <span class="c-str">"Growth &amp; Opportunity"</span> }
    ],
    <span class="c-key">"rules"</span>: [
      { <span class="c-key">"word"</span>: <span class="c-str">"volatility"</span>, <span class="c-key">"category_slug"</span>: <span class="c-str">"risk"</span> },
      { <span class="c-key">"word"</span>: <span class="c-str">"alpha"</span>, <span class="c-key">"category_slug"</span>: <span class="c-str">"growth"</span> }
    ]
  }
}`,
  Search: `<span class="c-comment"># Query your re-mapped knowledge graph</span>
<span class="c-keyword">POST</span> /api/prismrag/search

{
  <span class="c-key">"tenant_id"</span>: <span class="c-str">"your-tenant-uuid"</span>,
  <span class="c-key">"query"</span>: <span class="c-str">"quarterly risk exposure"</span>,
  <span class="c-key">"top_k"</span>: <span class="c-str">10</span>
}

<span class="c-comment">// Response — results reflect YOUR mapping, not statistics</span>
{
  <span class="c-key">"retrieval_mode"</span>: <span class="c-str">"graph_rag"</span>,
  <span class="c-key">"communities"</span>: [{ <span class="c-key">"label"</span>: <span class="c-str">"Risk &amp; Compliance"</span>, <span class="c-key">"weight"</span>: <span class="c-str">0.82</span> }],
  <span class="c-key">"hits"</span>: [
    { <span class="c-key">"chunk_text"</span>: <span class="c-str">"volatility exposure in Q3..."</span>,
      <span class="c-key">"category_slug"</span>: <span class="c-str">"risk"</span>, <span class="c-key">"score"</span>: <span class="c-str">0.94</span> }
  ]
}`
};

document.querySelectorAll('.code-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.code-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const snippet = document.querySelector('.code-snippet');
    if (snippet) snippet.innerHTML = snippets[tab.textContent.trim()] || '';
  });
});

// ── Intersection observer: fade-in sections ───────────────────────────────
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, { threshold: 0.08 });

document.querySelectorAll(
  '.step-card, .feature-card, .pricing-card, .compare-card'
).forEach(el => {
  el.style.opacity    = '0';
  el.style.transform  = 'translateY(24px)';
  el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
  observer.observe(el);
});

// ── Pricing: handle plan selection + Stripe redirect ─────────────────────
document.querySelectorAll('.plan-btn[data-plan]').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    const plan = btn.dataset.plan;
    if (!plan || plan === 'free') return;

    const token = localStorage.getItem('prismrag_token');
    if (!token) {
      window.location.href = `/register.html?plan=${plan}`;
      return;
    }

    btn.textContent = 'Redirecting…';
    btn.style.opacity = '0.7';

    try {
      const res = await fetch('/api/billing/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (data.redirect) window.location.href = data.redirect;
    } catch {
      btn.textContent = 'Try again';
      btn.style.opacity = '1';
    }
  });
});
