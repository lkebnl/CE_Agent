# Markdown to HTML Converter for FEMB QC Reports

## Description

This tool automatically converts FEMB QC test reports in Markdown format to professional scientific-style HTML reports.

## Key Features

- ✅ Automatic Markdown to HTML conversion
- ✅ Professional scientific-style CSS styling
- ✅ Responsive design with print support
- ✅ Preserves all original Markdown content and formatting
- ✅ Supports single-file and batch conversion

## Usage

### 1. Convert a single file

```bash
python3 QC_components/md_to_html_converter.py report_FEMB_123_t1_P_S0.md
```

### 2. Batch convert all reports in a directory

```bash
# Convert all report_FEMB_*.md files in the current directory
cd D:/data/temp  # navigate to the report directory
python3 /path/to/md_to_html_converter.py .
```

### 3. Convert a specified directory

```bash
python3 QC_components/md_to_html_converter.py /path/to/reports/directory
```

### 4. Run directly (convert current directory)

```bash
cd /path/to/reports
python3 /path/to/md_to_html_converter.py
```

## Output Files

- Input file: `report_FEMB_123_t1_P_S0.md`
- Output file: `report_FEMB_123_t1_P_S0.html` (auto-generated in the same directory)

## Integration into Test Workflow

Can automatically convert reports after testing is complete:

```python
# Add at the end of All_Report.py
from QC_components.md_to_html_converter import convert_md_to_html

# After generating the markdown report
fpmd = ... # path to markdown file
# Automatically convert to HTML
convert_md_to_html(fpmd)
```

## Style Features

- 🎨 Professional scientific-style design
- 📊 Optimized table display
- 🖼️ Auto-scaling image sizes
- 🔗 Clean link styling
- ✓/✗ Prominent pass/fail indicators
- 🖨️ Print-friendly layout

## Notes

- The original `.md` files will not be deleted or modified
- HTML files will overwrite existing files with the same name
- All standard Markdown syntax is supported
- Embedded HTML tags are preserved

## Requirements

- Python 3.x
- No additional dependencies required (uses standard library only)
