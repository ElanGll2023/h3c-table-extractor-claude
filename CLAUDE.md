---
name: h3c-table-extractor-claude
description: Claude Code skill for extracting H3C switch specifications. Use /skills in Claude Code to access.
---

# H3C Table Extractor (Claude Code Skill)

A Claude Code skill for extracting H3C network switch specifications from official website HTML tables.

## Status

⚠️ **Note**: This skill requires Claude Code to load it from the `.claude/skills/` directory.

## Installation

### Option 1: Project-level (may not work in all Claude Code versions)
```bash
cd your-project
cp -r h3c-table-extractor-claude .claude/skills/
```

### Option 2: Global (recommended)
```bash
mkdir -p ~/.claude/skills
cp -r h3c-table-extractor-claude ~/.claude/skills/
```

Then restart Claude Code:
```bash
# Exit Claude Code
# Restart
claude code
```

## Usage

Once loaded, use in Claude Code:
```
/skills
# Should show: h3c-table-extractor-claude

# Then use natural language:
"Extract H3C S5130 specifications from https://www.h3c.com/..."
```

## Alternative

If this skill doesn't load in Claude Code, use the standalone Python module:

**h3c-specs-extractor** - https://github.com/yourusername/h3c-specs-extractor

```python
from scripts.direct_extractor import extract_tables_direct
from crawler.html_fetcher import HTMLFetcher

url = "https://www.h3c.com/en/.../H3C_S5130S_EI/"
fetcher = HTMLFetcher(delay=1.0)
html = fetcher.fetch(url)
results = extract_tables_direct(html, url)
```

## License

MIT
