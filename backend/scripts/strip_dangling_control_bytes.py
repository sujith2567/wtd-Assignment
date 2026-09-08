import glob
import os
import re

# Regex to match non-standard control bytes / dangling Mojibake residual bytes
# \x80-\x9f, \xa0-\xa9, \u0160, \u0178, \u2018, \u2019 when attached to clean symbols
DANGLING_BYTES_PATTERN = re.compile(r'[\x7f-\x9f\xa4\u0160\u0178]')

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    original = text

    # Remove dangling byte characters
    cleaned = DANGLING_BYTES_PATTERN.sub('', text)

    # Specific string cleanups for perfect display
    cleaned = cleaned.replace('📂, Sections', '📂 Sections')
    cleaned = cleaned.replace('📂,. Upload', '📄 Upload')
    cleaned = cleaned.replace('📂 Upload Resume', '📄 Upload Resume')
    cleaned = cleaned.replace('📄‚ Sections', '📂 Sections')
    cleaned = cleaned.replace('📄\xa4', '📄')
    cleaned = cleaned.replace('📄\u0160', '📄')
    cleaned = cleaned.replace('⚖️  ', '⚖️ ')
    cleaned = cleaned.replace('✏️  ', '✏️ ')
    cleaned = cleaned.replace('← ', '← ')
    cleaned = cleaned.replace('←’ ', '')
    cleaned = cleaned.replace('←“ ', '')
    cleaned = cleaned.replace('←‘', '')

    if cleaned != original:
        with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
            f.write(cleaned)
        print(f"[CLEANED DANGLING BYTES] {filepath}")
    else:
        print(f"[PERFECT] {filepath}")

def main():
    for fn in glob.glob('frontend/src/*.jsx'):
        clean_file(fn)

if __name__ == '__main__':
    main()
