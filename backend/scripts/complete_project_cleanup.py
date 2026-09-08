import os
import glob
import re

# Comprehensive Mojibake mapping derived from inspection of UTF-8 -> CP1252 double encodings
MOJIBAKE_MAP = {
    '📂': '📂',
    '📄': '📄',
    '🌲': '🌲',
    '🔬': '🔬',
    '🔬': '🔬',
    '💡': '💡',
    '💡': '💡',
    '💡': '💡',
    '📑': '📑',
    '⚠️': '⚠️',
    '⚠️': '⚠️',
    '⚖️': '⚖️',
    '⚖️': '⚖️',
    '✏️': '✏️',
    '✏️': '✏️',
    '➕': '➕',
    '➕': '➕',
    '▲': '▲',
    '▼': '▼',
    '▲': '▲',
    '▼': '▼',
    '': '',
    '—': '—',
    '▼': '←',
    '...': '...',
    '': '',
    '×': '×',
    '≈': '≈',
    '▼‘': '▲',
    '▼': '▼',
}

def clean_content(text):
    # Fix specific known Mojibake byte representations
    # 1. Close button multiplication / cross sign
    text = text.replace('\xc3\u2014', '×')
    text = text.replace('×', '×')

    # 2. Isolation Forest Tree emoji
    text = text.replace('\xf0\u0178\u0152\xb2', '🌲')

    # 3. Warning emoji
    text = text.replace('\xe2\u0161\xa0\x8f', '⚠️')
    text = text.replace('\xe2\u0161\xa0', '⚠️')

    # 4. Bullet / Plus icon
    text = text.replace('\xe2\u017e\u2022', '➕')

    # 5. Microscope / Scoped AI icon
    text = text.replace('\xf0\u0178\u201d\xac', '🔬')

    # 6. Lightbulb icon
    text = text.replace('\xf0\u0178\u2019\xa1', '💡')

    # 7. Document icon
    text = text.replace('\xf0\u0178\u2014\u2018', '📄')

    # 8. Delta comparison arrows
    text = text.replace("'\u2190\u2018'", "'▲'")
    text = text.replace("'\u2190\u201c'", "'▼'")
    text = text.replace("'\xe2\u2030\u02c6'", "'≈'")

    # 9. Generic replacement table
    for bad, good in MOJIBAKE_MAP.items():
        text = text.replace(bad, good)

    return text

def process_file(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read()

    # Remove BOM if present
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]

    try:
        text = raw.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"[ERROR READING] {filepath}: {e}")
        return

    cleaned = clean_content(text)

    if cleaned != text or raw.startswith(b'\xef\xbb\xbf'):
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(cleaned)
        print(f"[REPAIRED] {filepath}")
    else:
        print(f"[CLEAN] {filepath}")

def main():
    skip_dirs = {'.git', 'node_modules', 'venv', '__pycache__', '.pytest_cache', 'dist', 'build', '.gemini'}
    target_files = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            if file.endswith(('.jsx', '.js', '.py', '.html', '.css', '.json')):
                target_files.append(os.path.join(root, file))

    for filepath in target_files:
        process_file(filepath)

if __name__ == '__main__':
    main()
