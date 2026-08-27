---
id: PREF-20260827-002
type: preference
status: stable
created: 2026-08-27
updated: 2026-08-27
summary: "Never use Pandoc for reports containing embedded objects."
scope:
  paths: []
  file_types: [".docx"]
  components: []
  tools: ["pandoc"]
  operations: ["conversion"]
  phases: []
  keywords: ["embedded objects"]
---

# Do not use Pandoc for embedded-object reports

Pandoc must not be used for reports containing embedded objects because it removes those objects. Use a preserving converter instead.
