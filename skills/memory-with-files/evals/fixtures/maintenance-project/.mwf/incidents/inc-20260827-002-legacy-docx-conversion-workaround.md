---
id: INC-20260827-002
type: incident
status: resolved
created: 2026-08-27
updated: 2026-08-27
summary: "LibreOffice headless avoids Pandoc object loss in legacy reports."
scope:
  paths: ["reports/legacy/**"]
  file_types: [".docx"]
  components: []
  tools: ["pandoc", "libreoffice"]
  operations: ["conversion"]
  phases: []
  keywords: []
---

# Legacy DOCX conversion workaround

## Problem and failed approach

The earlier Pandoc attempt lost embedded objects.

## Successful approach and verification

LibreOffice headless succeeded for reports under `reports/legacy`. A visual comparison confirmed layout preservation.

## Applicability

Retain the `reports/legacy/**` path scope when merging with related incident knowledge. Pandoc remains acceptable for simple text-only documents.

## Invalid when

Re-evaluate if later converter versions preserve embedded objects through another verified route.
