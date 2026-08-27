---
id: INC-20260827-001
type: incident
status: resolved
created: 2026-08-27
updated: 2026-08-27
summary: "Use LibreOffice headless when Pandoc drops embedded objects."
scope:
  paths: []
  file_types: [".docx"]
  components: []
  tools: ["pandoc", "libreoffice"]
  operations: ["conversion"]
  phases: []
  keywords: ["embedded objects"]
---

# Preserve objects with LibreOffice

## Problem and failed approach

Pandoc dropped embedded objects.

## Successful approach and verification

LibreOffice headless preserved them. Validation reopened the generated file and confirmed the objects remained.

## Applicability

This applies to legacy DOCX files with embedded objects. Pandoc remains acceptable for simple text-only documents.

## Invalid when

Re-evaluate after material converter upgrades or when object-preservation validation fails.
