import os
import re

def find_missing_t_definitions(root_dir):
    ts_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.ts') or file.endswith('.tsx'):
                ts_files.append(os.path.join(root, file))

    suspicious_files = []
    
    # Regex to find 't.' followed by a property name, ensuring 't' is a whole word
    t_usage_pattern = re.compile(r'\bt\.[a-zA-Z]')
    
    # Regex to find 'useLanguage'
    use_language_pattern = re.compile(r'useLanguage')
    
    # Regex to find component props usage like 'props.t' or '{ t }' in args
    # This is a heuristic; direct prop usage might not need useLanguage
    # But usually we use useLanguage hook.
    
    for file_path in ts_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Skip if it's the translation definition file itself
            if 'locales/ru.ts' in file_path or 'locales/en.ts' in file_path:
                continue

            if t_usage_pattern.search(content):
                if not use_language_pattern.search(content):
                    # Check if 't' is defined as a function argument or prop (e.g. ({ t }) => )
                    # or const t = ...
                    if not re.search(r'const\s+t\s*=', content) and \
                       not re.search(r'let\s+t\s*=', content) and \
                       not re.search(r'var\s+t\s*=', content) and \
                       not re.search(r'[:,]\s*t\s*[:=,)]', content) and \
                       not re.search(r'function\s+\w+\s*\([^)]*t[^)]*\)', content):
                       
                       suspicious_files.append(file_path)
        except Exception as e:
            print(f"Could not read {file_path}: {e}")

    return suspicious_files

if __name__ == "__main__":
    root = "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/mapsparser-Replit-front/frontend/src"
    files = find_missing_t_definitions(root)
    print("Files using 't.' without obvious definition:")
    for f in files:
        print(f)
