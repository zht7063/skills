---
id: INC-20260827-001
type: incident
status: resolved
created: 2026-08-27
updated: 2026-08-27
summary: "Use LibreOffice headless because Pandoc drops embedded objects from legacy DOCX reports."
scope:
  paths: []
  file_types: [".docx"]
  components: []
  tools: ["pandoc", "libreoffice"]
  operations: ["conversion"]
  phases: []
  keywords: ["embedded objects"]
---

# Preserve embedded objects during DOCX conversion

## Problem and failed approach

Pandoc was a reasonable first attempt for document conversion, but inspection showed that it dropped embedded objects.

## Successful approach and verification

LibreOffice headless preserved the objects. The output was verified by reopening the converted document and checking the object count.

## Applicability

Use this recipe for legacy DOCX reports with embedded objects. Pandoc remains acceptable for simple text-only documents.

## Invalid when

Re-evaluate this recipe if the document has no embedded objects, the converter versions change materially, or validation no longer confirms object preservation.
