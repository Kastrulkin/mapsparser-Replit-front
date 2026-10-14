# OpenClaw contact-context compatibility patch

This release extends the installed OpenClaw `web_fetch`, using its existing HTML conversion on the **same fetched response**. It does not add a network client, a crawler, browser execution, paid fallback, contact-delivery permission or a second generator.

The original Readability result discarded contact/footer/navigation content: an offline fixture lost both the email and Contact link. The patched extraction retains bounded source contact snippets and Contact/About links ahead of the main content so `maxChars` cannot silently discard them. The normal external/untrusted-content wrapper remains outside this extraction. DNS pinning, redirect checks and Firecrawl handling are unchanged.

Patches:
- `web-fetch-utils.patch`: installed `/usr/lib/node_modules/openclaw/dist/agents/tools/web-fetch-utils.js`.
- `web-read.patch`: existing bridge `/root/openclaw_runtime/capabilities/outreach_mvp/web_read.py`; avoid rereading the canonical URL after slash redirects.
- `disabled-firecrawl-schema.patch`: installed `dist/config/zod-schema.agent-runtime.js` rejected the already-present `tools.web.fetch.firecrawl` setting at gateway restart. Accept **only** `{enabled:false}`; enabled=true and extra keys are rejected. No credentials or configuration values were changed.

Backups: `/root/openclaw_runtime/var/releases/outreach-20261014/` on OpenClaw host. Gateway: user service `openclaw-localos.service`; research bridge: system service `openclaw-outreach-mvp.service`. Both active after the compatibility fix.

Offline verification:

```
node test-contact-context.mjs file:///usr/lib/node_modules/openclaw/dist/agents/tools/web-fetch-utils.js
python3 test-web-read.py /root/openclaw_runtime/capabilities/outreach_mvp/web_read.py
```

A real **read-only**, model-free `invoke_fetch` of the reviewed DPauls page returned HTTP 200, its real public email, a Contact link, and Phuket content after the fix. This diagnostic did not write CRM records, qualify a prospect, create a draft or charge LocalOS credits. It is not end-to-end acceptance.

Installed-package updates can replace these compatibility files. Reconcile with the vendor version and rerun these checks after updates; do not silently turn on paid fallback or remove the bridge guard. Preserve current vendor files and use dry-run patch checks before applying or reverting. Read-only diagnostics must never print gateway tokens or service command lines.
