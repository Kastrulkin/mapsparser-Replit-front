"""Guarded single-module update; run from /opt/seo-app. No DB/provider calls."""
import argparse
import ast
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

EXPECTED = 'b591db1b5d99048afb7bfbefcb193651d0e4edf6b1b12de88581bdab4001c07d'
ASSETS = Path(__file__).parent
REPLACEMENTS = {
    '_load_content_plan_service_facts', '_build_content_brief_v1',
    '_content_brief_prompt_block', '_parse_content_candidates',
    '_unsupported_candidate_claims', '_score_content_candidate',
    '_content_generation_v2_prompt', 'UNSUPPORTED_CLAIM_PATTERNS',
}
ADDITIONS = {
    '_load_content_plan_service_sources', '_with_content_fact_sources',
    '_content_brief_fact_sources', '_strip_content_json_markdown', '_content_creative_warnings',
}
BEFORE = '''        business_facts["services"] = _load_content_plan_service_facts(
            cursor,
            str(item.get("business_id") or ""),
            limit=12,
        )'''
AFTER = '''        business_facts["service_sources"] = _load_content_plan_service_sources(
            cursor,
            str(item.get("business_id") or ""),
            limit=12,
        )
        business_facts["services"] = "\\n".join(f"- {source['fact']}" for source in business_facts["service_sources"])'''


def node_name(node):
    if isinstance(node, ast.FunctionDef):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return ''


def candidate_for(original):
    tree = ast.parse(original)
    release = (ASSETS / 'release_functions.py').read_text()
    release_nodes = {node_name(node): node for node in ast.parse(release).body if node_name(node)}
    current = {node_name(node): node for node in tree.body if node_name(node)}
    if not REPLACEMENTS.issubset(current) or ADDITIONS.intersection(current):
        raise RuntimeError('Unexpected production structure; no files changed')
    lines = original.splitlines(keepends=True)
    edits = []
    for name in REPLACEMENTS:
        node = current[name]
        replacement = ast.get_source_segment(release, release_nodes[name]) + '\n'
        edits.append((node.lineno - 1, node.end_lineno, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]
    candidate = ''.join(lines)
    helpers = '\n\n'.join(ast.get_source_segment(release, release_nodes[name]) for name in sorted(ADDITIONS))
    marker = 'def _load_content_plan_service_facts('
    candidate = candidate.replace(marker, helpers + '\n\n\n' + marker, 1)
    if candidate.count(BEFORE) != 1:
        raise RuntimeError('Generation call site changed; no files changed')
    candidate = candidate.replace(BEFORE, AFTER, 1)
    compile(candidate, 'content_plan_service.py', 'exec')
    # All unrelated top-level code and functions must remain identical.
    old_nodes = [ast.dump(node) for node in tree.body
                 if node_name(node) not in REPLACEMENTS | {'generate_draft_for_plan_item'}]
    new_nodes = [ast.dump(node) for node in ast.parse(candidate).body
                 if node_name(node) not in REPLACEMENTS | ADDITIONS | {'generate_draft_for_plan_item'}]
    if old_nodes != new_nodes:
        raise RuntimeError('Unrelated code changed; no files changed')
    return candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='/opt/seo-app/src/services/content_plan_service.py')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    target = Path(args.source)
    original_bytes = target.read_bytes()
    digest = hashlib.sha256(original_bytes).hexdigest()
    if digest != EXPECTED:
        raise SystemExit('Production changed since inspection; nothing installed')
    candidate = candidate_for(original_bytes.decode())
    result = {'before': digest, 'after': hashlib.sha256(candidate.encode()).hexdigest(),
              'installed': False, 'file': str(target)}
    if args.apply:
        if target != Path('/opt/seo-app/src/services/content_plan_service.py'):
            raise SystemExit('Apply is restricted to the canonical production file')
        backup = Path('/opt/seo-app/backups') / ('content-facts-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700)
        shutil.copy2(target, backup / target.name)
        staged = backup / 'candidate.py'
        staged.write_text(candidate)
        shutil.copystat(target, staged)
        if hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED:
            raise SystemExit('Concurrent source change; original retained')
        os.replace(staged, target)
        result.update(installed=True, backup=str(backup))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
