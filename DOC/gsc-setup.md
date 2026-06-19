# Google Search Console — Setup Checklist

After the `[publish]` deploy, complete these steps in [Google Search Console](https://search.google.com/search-console).

## 1. Add property

Choose **URL prefix** (fastest):

```
https://prismrag.insightits.com
```

Or add **Domain** property for `insightits.com` if you want all subdomains covered (requires DNS TXT verification).

## 2. Verify ownership

**Option A — DNS (recommended for domain property)**

Add a TXT record at your DNS host (AWS Route 53 / Azure DNS):

```
Name:  @  (or insightits.com)
Type:  TXT
Value: google-site-verification=XXXXXXXX  (from GSC)
```

**Option B — HTML file (URL prefix)**

Download the verification file from GSC and place it in `web/` — it will be served at the site root after deploy.

## 3. Submit sitemap

In GSC → **Sitemaps** → enter:

```
sitemap.xml
```

Full URL: `https://prismrag.insightits.com/sitemap.xml`

## 4. Request indexing (optional, speeds first crawl)

GSC → **URL Inspection** → paste each high-priority URL → **Request indexing**:

- `https://prismrag.insightits.com/`
- `https://prismrag.insightits.com/whitepaper.html`
- `https://prismrag.insightits.com/prismrag-lib.html`

## 5. Verify rich results

Use [Rich Results Test](https://search.google.com/test/rich-results) on:

- `/` — expect `SoftwareApplication`, `FAQPage`, `Organization`
- `/whitepaper.html` — expect `TechArticle`

## 6. PyPI (separate from GSC)

After republishing `prismrag-patch` to PyPI, Google will pick up the Homepage link on:

```
https://pypi.org/project/prismrag-patch/
```

Republish command (from repo root, with PyPI token configured):

```powershell
cd prismrag_patch
python -m build
python -m twine upload dist/*
```

---

*Canonical domain: `https://prismrag.insightits.com`*
