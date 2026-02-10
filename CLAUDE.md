---
name: h3c-table-extractor-claude
description: |
  Claude Code skill for extracting H3C switch specifications from HTML tables.
  Handles hardware specs, software features, performance metrics, and protocol compliance.
  Supports encoding fix, merged cells, and filtering of removable components.
---

# H3C Table Extractor (Claude Code Skill)

Extract H3C network switch specifications from official website HTML tables.

## Features

- ✅ **Hardware Specs** - Ports, power, fans, dimensions, weight
- ✅ **Software Features** - VLAN, routing, security features
- ✅ **Performance Metrics** - MAC table, VLAN table, routing table, ACL rules
- ✅ **Protocol Compliance** - IEEE standards, RFC protocols
- ✅ **POE Support** - POE/POE+/POE++ power and port counts
- ✅ **Encoding Fix** - Auto-fix `Ã` → `×`, `Âµ` → `µ`, etc.
- ✅ **Merged Cells** - Handle rowspan/colspan
- ✅ **Smart Filtering** - Skip removable components, power models

## Installation

### Option 1: Project-level
```bash
cd your-project
mkdir -p .claude/skills
cp -r h3c-table-extractor-claude .claude/skills/
```

### Option 2: Global (recommended)
```bash
mkdir -p ~/.claude/skills
cp -r h3c-table-extractor-claude ~/.claude/skills/
```

Restart Claude Code after installation.

## Usage

### Via /skills command
```
/skills
# Select: h3c-table-extractor-claude

# Then ask:
"Extract H3C S5130 specifications from https://www.h3c.com/en/..."
```

### Direct Python execution (recommended)
Claude Code can also execute Python directly:

```python
import sys
sys.path.insert(0, '/path/to/h3c-table-extractor-claude')

from scripts.direct_extractor import extract_tables_direct
from scripts.html_fetcher import HTMLFetcher

url = "https://www.h3c.com/en/Products_and_Solutions/InterConnect/Switches/Products/Campus_Network/Access/S5130/H3C_S5130S_EI/"
fetcher = HTMLFetcher(delay=1.0)
html = fetcher.fetch(url)
results = extract_tables_direct(html, url)

# Filter switch models
models = {k: v for k, v in results.items() if k.startswith('S5130')}
print(f"Extracted {len(models)} models")
```

## Extracted Fields

### Hardware Specifications
| Field | Description |
|-------|-------------|
| `交换容量` | Switching capacity (Gbps) |
| `包转发率` | Packet forwarding rate (Mpps) |
| `1000Base-T端口数` | Gigabit Ethernet ports count |
| `SFP端口数` | SFP fiber ports |
| `SFP+端口数` | SFP+ 10G ports |
| `QSFP+端口数` | QSFP+ 40G ports |
| `电源槽位数` | Power supply slots |
| `风扇数量` | Fan count (or "Fanless") |
| `Console口` | Console port |
| `USB口` | USB port |
| `管理网口` | Management port |
| `尺寸` | Dimensions (W×D×H) |
| `重量` | Weight |
| `功耗` | Power consumption |
| `输入电压` | Input voltage |
| `MTBF` | Mean time between failures |
| `工作温度` | Operating temperature |

### Software Features
| Field | Description |
|-------|-------------|
| `软件特性` | Software features summary (VLAN, routing, security) |

### Performance Metrics
| Field | Description |
|-------|-------------|
| `MAC地址表` | MAC address table size |
| `VLAN表项` | VLAN table entries |
| `路由表项` | Routing table entries |
| `ARP表项` | ARP entries |
| `ACL规则数` | ACL rules count |

### Protocol Compliance
| Field | Description |
|-------|-------------|
| `支持协议` | Supported protocols (IEEE, RFC) |

### POE (if supported)
| Field | Description |
|-------|-------------|
| `POE总功率` | Total POE power budget |
| `POE端口数(802.3af)` | POE ports (15.4W) |
| `POE+端口数(802.3at)` | POE+ ports (30W) |
| `POE++端口数(60W)` | POE++ ports (60W) |
| `POE++端口数(90W)` | POE++ ports (90W) |

## Table Types Handled

1. **Multi-model hardware tables** - Standard spec tables with model columns
2. **POE tables** - Power consumption and POE port distribution
3. **Software feature tables** - VLAN, routing, security features
4. **Performance tables** - MAC, VLAN, routing table sizes
5. **Protocol tables** - IEEE standards and RFC compliance

## Encoding Fixes

Automatically fixes common encoding issues:
- `Ã` → `×` (multiplication sign)
- `Âµ` → `µ` (micro sign)
- `Â°` → `°` (degree sign)
- `â¤` → `≤` (less than or equal)
- `â¥` → `≥` (greater than or equal)

## Filtered Content

Automatically skips:
- Removable power supply models (PSR150-A1-GL, etc.)
- Board support indicators (是否支持)
- Filler panel information
- Transceiver part numbers (unless specifically requested)

## Batch Extraction Example

```python
urls = {
    'S5130': 'https://www.h3c.com/en/.../H3C_S5130S_EI/',
    'S5590': 'https://www.h3c.com/en/.../H3C_S5590-EI/',
    'S6520': 'https://www.h3c.com/en/.../H3C_S6520X-EI/',
}

all_data = {}
for series, url in urls.items():
    html = HTMLFetcher(delay=1.5).fetch(url)
    results = extract_tables_direct(html, url)
    models = {k: v for k, v in results.items() if k.startswith('S')}
    all_data.update(models)
    print(f"{series}: {len(models)} models")

# Export
import pandas as pd
df = pd.DataFrame.from_dict(all_data, orient='index')
df.to_excel('h3c_switches.xlsx')
```

## Alternative: Standalone Python Module

For use outside Claude Code:

**h3c-specs-extractor** - https://github.com/ElanGll2023/h3c-specs-extractor

```bash
git clone https://github.com/ElanGll2023/h3c-specs-extractor.git
pip install -r h3c-specs-extractor/requirements.txt
```

## Version

Version: 1.0.0
Last Updated: 2026-02-10
Compatible with: Claude Code

## License

MIT
