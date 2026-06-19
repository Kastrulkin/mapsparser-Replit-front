import os
import glob

locales_dir = 'frontend/src/i18n/locales'
files = glob.glob(os.path.join(locales_dir, '*.ts'))

for filepath in files:
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    indices = [i for i, line in enumerate(lines) if 'growthStages: {' in line]
    if len(indices) > 1:
        print(f"Fixing {filepath} (found {len(indices)} occurrences)...")
        # Keep the FIRST one on line indices[0]
        # Delete the SECOND one at indices[1]
        
        start_del = indices[1]
        
        # Determine the indentation of the start line
        start_line = lines[start_del]
        indentation = len(start_line) - len(start_line.lstrip())
        
        # Find the end of the block based on indentation
        # We look for a line that has the SAME indentation and verify it's a closing brace for this block
        # Or simple brace counting
        
        end_del = start_del 
        nesting = 0
        
        # Simply count braces starting from the start_del line
        for i in range(start_del, len(lines)):
            line = lines[i]
            nesting += line.count('{')
            nesting -= line.count('}')
            if nesting <= 0:
                end_del = i + 1
                break
        
        print(f"  Removing lines {start_del+1} to {end_del}")
        
        # Remove the lines
        # Note: if there's a comma after the closing brace, we keep it? 
        # Actually usually it's `},` or `}`. 
        # If we delete the whole block, we might leave a trailing comma or remove one.
        # But 'Duplicate key' implies it's in an object.
        # Let's verify if the PREVIOUS line has a comma if we remove this block.
        # Or if the remaining block needs a comma.
        # Usually it's fine.
        
        del lines[start_del:end_del]
        
        with open(filepath, 'w') as f:
            f.writelines(lines)
