# GitHub Pages — PrismRAG interactive demo

Mirror of PrismGuard’s Pages pattern.

After merge to `insightitsGit/prismrag` **main**:

1. **Settings → Pages**
2. **Source:** Deploy from branch `main`
3. **Folder:** `/docs`
4. Save

**Live demo URL:**

```
https://insightitsgit.github.io/prismrag/demo.html
```

Until Pages is enabled, open `docs/demo.html` locally or view the raw file on GitHub.

## Files

| File | Purpose |
|------|---------|
| `docs/demo.html` | Interactive terminal walkthrough + query chips (live smoke lines) |
| `docs/taxonomy-scorecard.md` | Self-serve scorecard · soft CTA **TAXONOMY** |
| `docs/.nojekyll` | Allow Pages to serve without Jekyll |

## Also run the real library smoke

```bash
cd examples/graph-rag-replacement
pip install -r requirements.txt
python demo_taxonomy_connection.py
```

https://github.com/insightitsGit/prismrag/tree/main/examples/graph-rag-replacement
