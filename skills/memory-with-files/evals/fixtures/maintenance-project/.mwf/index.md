# Memory index

Generated: 2026-08-27
Schema version: 1

Read this file and `handoff.md` before loading detailed records.

## Global active memory

No records yet.

## Routed active memory

| ID | Type | Status | Summary | Scope | Path |
|---|---|---|---|---|---|
| INC-20260827-001 | incident | resolved | Use LibreOffice headless when Pandoc drops embedded objects. | file_types=.docx; tools=pandoc, libreoffice; operations=conversion; keywords=embedded objects | `incidents/inc-20260827-001-preserve-objects-with-libreoffice.md` |
| INC-20260827-002 | incident | resolved | LibreOffice headless avoids Pandoc object loss in legacy reports. | paths=reports/legacy/**; file_types=.docx; tools=pandoc, libreoffice; operations=conversion | `incidents/inc-20260827-002-legacy-docx-conversion-workaround.md` |
| PREF-20260827-001 | preference | stable | Prefer Pandoc for project document conversion. | tools=pandoc; operations=conversion | `preferences/pref-20260827-001-prefer-pandoc-for-document-conversion.md` |
| PREF-20260827-002 | preference | stable | Never use Pandoc for reports containing embedded objects. | file_types=.docx; tools=pandoc; operations=conversion; keywords=embedded objects | `preferences/pref-20260827-002-do-not-use-pandoc-for-embedded-object-reports.md` |

## Pending candidates

No candidates pending.

## Pending review

- Candidates: 0
- Inbox items: 2
