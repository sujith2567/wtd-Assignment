import os
import glob

def fix_file(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='replace')
    original = text

    # Try fixing double-encoded UTF-8 strings (where UTF-8 bytes were decoded as cp1252/latin1 and re-encoded)
    try:
        # Re-encode to latin1 to recover original raw bytes, then decode as utf-8
        recovered = text.encode('latin1').decode('utf-8')
        text = recovered
        print(f"[FIXED DOUBLE-ENCODING] {filepath}")
    except Exception as e:
        print(f"[INFO] Direct latin1 recovery skipped for {filepath}: {e}")

    # Specific replacements for remaining Mojibake artifacts
    replacements = [
        ('📂', '📂'),
        ('📄', '📄'),
        ('⚖️', '⚖️'),
        ('⚖️', '⚖️'),
        ('✏️', '✏️'),
        ('✏️', '✏️'),
        ('▲', '▲'),
        ('▼', '▼'),
        ('▲', '▲'),
        ('▼', '▼'),
        ('', ''),
        ('—', '—'),
        ('▼', '←'),
        ('...', '…'),
        ('', ''),
        ('â€', '—'),
    ]

    for bad, good in replacements:
        if bad in text:
            text = text.replace(bad, good)

    if text != original:
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print(f"[SAVED UTF-8] {filepath}")
    else:
        print(f"[CLEAN] {filepath}")

def main():
    files = glob.glob('frontend/src/**/*.jsx', recursive=True) + glob.glob('frontend/src/**/*.js', recursive=True)
    for f in files:
        fix_file(f)

if __name__ == '__main__':
    main()
