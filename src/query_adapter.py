import re
import logging
import datetime
import json

logger = logging.getLogger('db_adapter')

class QueryAdapter:
    """
    Adapter to bridge the gap between SQLite ('?') and PostgreSQL ('%s').
    Features:
    - Strict Parameter Count Check
    - String Literal Protection (don't replace ? inside quotes)
    - Type Casting for PostgreSQL compatibility
    """

    STRICT_MODE = True

    @staticmethod
    def adapt_query(query: str, params: tuple) -> str:
        """
        Translates SQLite query syntax to PostgreSQL syntax.
        Replace '?' with '%s', but ONLY if not inside a string literal.
        """
        # 1. Basic Mismatch Check
        # This is a naive count (includes ? in strings), but serves as a first sanity check.
        total_placeholders = query.count('?')
        if total_placeholders < len(params):
            # It's possible to hav FEWER ? if some params are unused (rare in raw SQL) or
            # more likely, ? are in comments/strings.
            pass 
        
        # 2. Strict Replacement logic
        # We need to tokenize the string to avoid replacing '?' inside 'strings'
        
        # Pattern to match:
        # 1. Single quoted strings: '[^']*' (handling escaped quotes is complex, simplified here)
        # 2. Double quoted strings: "[^"]*"
        # 3. The placeholder: \?
        
        # Note on SQL escaping: Postgres uses '' for escaped quote inside string.
        # Regex: '([^']|'')*'
        
        token_pattern = re.compile(r"('([^']|'')*')|(\"([^\"]|\"\")*\")|(\?)")
        
        new_query_parts = []
        param_index = 0
        last_pos = 0
        
        for match in token_pattern.finditer(query):
            # Add text between matches
            new_query_parts.append(query[last_pos:match.start()])
            
            group = match.group(0)
            
            if group == '?':
                # It's a placeholder -> replace
                new_query_parts.append('%s')
                param_index += 1
            else:
                # It's a string literal -> keep as is
                if '?' in group:
                    # Log warning or error
                    msg = f"Found '?' inside string literal: {group}. This is ambiguous but allowed in Strict Mode."
                    logger.debug(msg)
                new_query_parts.append(group)
                
            last_pos = match.end()
            
        new_query_parts.append(query[last_pos:])
        result_query = "".join(new_query_parts)
        
        # Final Strict Check
        if param_index != len(params):
             raise ValueError(f"QueryAdapter Error: Found {param_index} bind placeholders, but {len(params)} params provided. Query segment: {query[:50]}...")

        return result_query

    @staticmethod
    def adapt_params(params: tuple) -> tuple:
        """
        Casts parameters to PostgreSQL compatible types.
        """
        new_params = []
        for p in params:
            if isinstance(p, bool):
                # SQLite uses 0/1, Postgres uses True/False.
                # Psycopg2 handles Python types natively, so we ensure it's bool (not int 0/1)
                # But wait, if it comes from existing code it might be int (1) meaning True.
                # If we're not sure, we leave it. Postgres accepts 1 for boolean columns? No, it prefers 't'/'f' or true/false.
                # But python `True` is mapped to SQL `true`.
                new_params.append(p)
            elif isinstance(p, datetime.datetime):
                # Ensure it's not a string ISO if passed as object
                new_params.append(p)
            elif isinstance(p, dict) or isinstance(p, list):
                # If passing a dict to JSONB column, simple json dump string is safer 
                # unless using Json adapter. Let's dump to string for compatibility with TEXT columns as well
                new_params.append(json.dumps(p))
            else:
                new_params.append(p)
        return tuple(new_params)
