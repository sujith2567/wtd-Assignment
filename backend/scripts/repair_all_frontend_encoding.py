import glob
import os

def clean_file(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read()

    # 1. Remove UTF-8 BOM if present
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]

    text = raw.decode('utf-8', errors='replace')
    original = text

    # Map of all known Mojibake or broken replacement patterns
    mapping = [
        # Double-encoded emoji / symbols from cp1252 / latin1 decoding
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
        ('—', '—'),
        ('▼', '←'),
        ('...', '...'),
        ('', ''),
        ('', ''),

        # Replacement character fixes from corrupted text reads
        ("return ''", "return '—'"),
        ("Loading", "Loading..."),
        ("Loading…", "Loading..."),
        ("profileâ…", "profile..."),
        ("explainabilityâ…", "explainability..."),
        ("auditâ…", "audit..."),
        ("▲", "▲"),
        ("▼", "▼"),
        ("—", "—"),
        ("✏️", "✏️"),
        ("✏️", "✏️"),
        ("▼", "←"),

        # Double-encoded quote / dash artifacts
        ("&apos;", "'"),
        ("&quot;", '"'),
    ]

    for bad, good in mapping:
        text = text.replace(bad, good)

    if text != original or raw.startswith(b'\xef\xbb\xbf'):
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print(f"[REPAIRED] {filepath}")
    else:
        print(f"[CLEAN] {filepath}")

def main():
    files = glob.glob('frontend/src/**/*.jsx', recursive=True) + glob.glob('frontend/src/**/*.js', recursive=True)
    for f in files:
        clean_file(f)

if __name__ == '__main__':
    main()
