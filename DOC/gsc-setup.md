# Google Search Console — Setup Checklist

PrismRAG is now primarily a **pip library** (`prismrag-patch`). The static site at `prismrag.insightits.com` should emphasize PyPI install and [prismrag-lib.html](https://prismrag.insightits.com/prismrag-lib.html).

Product copy source: [INFO.md](../INFO.md).

---

## 1. Add property

**URL prefix:**

```
https://prismrag.insightits.com
```

## 2. Verify ownership

DNS TXT or HTML file — see GSC instructions.

## 3. Submit sitemap

```
sitemap.xml
```

Full URL: `https://prismrag.insightits.com/sitemap.xml`

## 4. Request indexing (priority URLs)

- `https://prismrag.insightits.com/`
- `https://prismrag.insightits.com/prismrag-lib.html`
- `https://prismrag.insightits.com/whitepaper.html`

## 5. Target keywords (2026 pivot)

Focus on **library + open source**, not SaaS signup:

- `prismrag-patch pip install`
- `RAG category bleed`
- `taxonomy grounded RAG python`
- `graph RAG client defined mapping`
- `pgvector category projection`

## 6. Structured data

Ensure `SoftwareApplication` schema lists:

- `downloadUrl`: https://pypi.org/project/prismrag-patch/
- `offers`: Free / Apache-2.0 (not SaaS tiers)

Update `web/index.html` schema when copy changes.

## 7. PyPI backlink

PyPI project should link to GitHub and https://prismrag.insightits.com/prismrag-lib.html

---

## Note on hosted API

SaaS API endpoints are retired. Do not index `/register.html`, `/playground.html` as primary conversion paths unless you restore hosting. Library docs and whitepaper remain valid.
