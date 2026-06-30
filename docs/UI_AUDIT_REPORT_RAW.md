# UI Audit Raw Report

Generated: 2026-06-30 15:45:50

## Git

```text
## feature-ui-audit-v1
?? scripts/ui_audit_project_v1.py

4956c09 (HEAD -> feature-ui-audit-v1, origin/develop, feature-name-v1, develop) Merge Jino passenger WSGI entrypoint
c6c3c7a Add Jino passenger WSGI entrypoint
b117863 Merge Jino deploy checklist
1a05d8f Add Jino deploy checklist
2a2e2d3 Merge Jino deploy prep
eb80f64 Prepare production settings for Jino deploy
987d681 Merge login page redesign
d6ea95e Redesign login page
```

## File summary

- HTML templates: 36
- CSS files: 38
- JS files: 3

## Templates

| File | Lines | Extends base | style attrs | `<style>` | inline `<script>` |
|---|---:|---:|---:|---:|---:|
| `audit/templates/audit/audit_log_list.html` | 159 | yes | 0 | 0 | 0 |
| `system/templates/system/backups.html` | 120 | yes | 0 | 0 | 0 |
| `system/templates/system/dashboard.html` | 340 | yes | 0 | 0 | 0 |
| `system/templates/system/maintenance.html` | 127 | yes | 0 | 0 | 0 |
| `system/templates/system/updates.html` | 138 | yes | 0 | 0 | 0 |
| `system/templates/system/versions.html` | 122 | yes | 0 | 0 | 0 |
| `templates/base.html` | 336 | no | 0 | 0 | 1 |
| `templates/components/sidebar.html` | 125 | no | 0 | 0 | 0 |
| `templates/components/topbar.html` | 36 | no | 0 | 0 | 0 |
| `templates/dashboard.html` | 450 | yes | 0 | 0 | 0 |
| `templates/invoices/counterparties_missing_requisites.html` | 261 | yes | 0 | 0 | 0 |
| `templates/invoices/counterparty_detail.html` | 542 | yes | 0 | 0 | 0 |
| `templates/invoices/counterparty_directory.html` | 389 | yes | 0 | 0 | 0 |
| `templates/invoices/counterparty_form.html` | 215 | yes | 0 | 0 | 0 |
| `templates/invoices/detail.html` | 925 | yes | 0 | 0 | 1 |
| `templates/invoices/edit_invoice.html` | 133 | yes | 0 | 0 | 0 |
| `templates/invoices/import_counterparties_1c.html` | 353 | yes | 0 | 0 | 0 |
| `templates/invoices/invoice_assign_counterparty.html` | 191 | yes | 1 | 0 | 0 |
| `templates/invoices/invoice_list.html` | 516 | yes | 0 | 0 | 0 |
| `templates/invoices/list.html` | 133 | yes | 0 | 0 | 0 |
| `templates/invoices/ocr_queue.html` | 340 | yes | 0 | 0 | 0 |
| `templates/invoices/payment_registry.html` | 891 | yes | 0 | 0 | 0 |
| `templates/invoices/payment_registry_detail.html` | 442 | yes | 0 | 0 | 0 |
| `templates/invoices/payment_registry_history.html` | 300 | yes | 0 | 0 | 0 |
| `templates/invoices/payment_schedule.html` | 390 | yes | 0 | 0 | 0 |
| `templates/invoices/unmatched_counterparties.html` | 240 | yes | 0 | 0 | 0 |
| `templates/invoices/upload.html` | 92 | yes | 0 | 0 | 0 |
| `templates/invoices/upload_batch_detail.html` | 383 | yes | 0 | 0 | 0 |
| `templates/invoices/upload_batches.html` | 166 | yes | 0 | 0 | 0 |
| `templates/invoices/upload_invoice.html` | 365 | yes | 0 | 0 | 1 |
| `templates/invoices/upload_result.html` | 338 | yes | 0 | 0 | 0 |
| `templates/login.html` | 159 | no | 0 | 0 | 0 |
| `templates/profile.html` | 152 | yes | 0 | 0 | 0 |
| `templates/reports/dashboard.html` | 85 | yes | 0 | 0 | 2 |
| `templates/users/user_admin_form.html` | 67 | yes | 0 | 0 | 0 |
| `templates/users/user_admin_list.html` | 154 | yes | 0 | 0 | 0 |

## CSS files

| File | Lines | `!important` | hard colors | media queries | z-index | fixed/sticky |
|---|---:|---:|---:|---:|---:|---:|
| `static/css/app.css` | 59 | 0 | 0 | 0 | 0 | 0 |
| `static/css/base/animations.css` | 12 | 0 | 0 | 0 | 0 | 0 |
| `static/css/base/reset.css` | 48 | 0 | 0 | 0 | 0 | 0 |
| `static/css/base/typography.css` | 201 | 11 | 12 | 0 | 0 | 0 |
| `static/css/base/variables.css` | 93 | 0 | 34 | 0 | 0 | 0 |
| `static/css/components/alerts.css` | 13 | 0 | 1 | 0 | 0 | 0 |
| `static/css/components/badges.css` | 385 | 29 | 63 | 2 | 0 | 0 |
| `static/css/components/buttons.css` | 237 | 0 | 31 | 0 | 0 | 0 |
| `static/css/components/cards.css` | 509 | 32 | 42 | 0 | 0 | 1 |
| `static/css/components/filters.css` | 563 | 103 | 11 | 13 | 1 | 1 |
| `static/css/components/forms.css` | 437 | 31 | 31 | 1 | 0 | 0 |
| `static/css/components/modals.css` | 0 | 0 | 0 | 0 | 0 | 0 |
| `static/css/components/pagination.css` | 15 | 0 | 0 | 0 | 0 | 0 |
| `static/css/components/tables.css` | 929 | 1 | 18 | 3 | 0 | 0 |
| `static/css/features/legacy-migration.css` | 7 | 0 | 0 | 0 | 0 | 0 |
| `static/css/features/login-page.css` | 322 | 11 | 53 | 2 | 0 | 0 |
| `static/css/features/ocr.css` | 1045 | 2 | 84 | 8 | 1 | 1 |
| `static/css/features/partial-payments.css` | 297 | 26 | 52 | 0 | 0 | 0 |
| `static/css/features/sidebar-fixed-left.css` | 621 | 242 | 57 | 8 | 5 | 2 |
| `static/css/features/table-clean-baseline.css` | 1562 | 302 | 5 | 18 | 0 | 0 |
| `static/css/features/ui-polish-actions.css` | 237 | 27 | 0 | 3 | 0 | 0 |
| `static/css/features/ui-polish-badges.css` | 234 | 0 | 31 | 1 | 0 | 0 |
| `static/css/features/ui-polish-filters.css` | 576 | 33 | 17 | 7 | 0 | 0 |
| `static/css/features/users-roles.css` | 12 | 0 | 0 | 0 | 0 | 0 |
| `static/css/layout/shell.css` | 154 | 17 | 0 | 1 | 0 | 0 |
| `static/css/layout/sidebar.css` | 663 | 7 | 48 | 3 | 1 | 1 |
| `static/css/layout/topbar.css` | 193 | 0 | 20 | 2 | 1 | 1 |
| `static/css/pages/audit.css` | 246 | 92 | 31 | 2 | 0 | 0 |
| `static/css/pages/counterparties.css` | 289 | 1 | 7 | 2 | 0 | 0 |
| `static/css/pages/dashboard.css` | 843 | 63 | 26 | 7 | 0 | 0 |
| `static/css/pages/invoice-detail.css` | 65 | 0 | 1 | 0 | 0 | 0 |
| `static/css/pages/invoice-list.css` | 487 | 126 | 0 | 2 | 0 | 0 |
| `static/css/pages/payment-registry.css` | 1202 | 381 | 64 | 13 | 0 | 0 |
| `static/css/pages/payment-schedule.css` | 439 | 82 | 25 | 6 | 0 | 0 |
| `static/css/pages/profile.css` | 182 | 0 | 11 | 2 | 0 | 0 |
| `static/css/pages/system.css` | 113 | 0 | 8 | 0 | 0 | 0 |
| `static/css/style.css` | 6 | 0 | 0 | 0 | 0 | 0 |
| `static/src/input.css` | 1404 | 1 | 157 | 5 | 0 | 1 |

## app.css import order

| # | Import | Exists |
|---:|---|---:|
| 1 | `./base/variables.css` | yes |
| 2 | `./base/reset.css` | yes |
| 3 | `./base/typography.css` | yes |
| 4 | `./base/animations.css` | yes |
| 5 | `./layout/shell.css` | yes |
| 6 | `./layout/sidebar.css` | yes |
| 7 | `./layout/topbar.css` | yes |
| 8 | `./components/buttons.css` | yes |
| 9 | `./components/forms.css` | yes |
| 10 | `./components/tables.css` | yes |
| 11 | `./components/cards.css` | yes |
| 12 | `./components/badges.css` | yes |
| 13 | `./components/filters.css` | yes |
| 14 | `./components/pagination.css` | yes |
| 15 | `./components/modals.css` | yes |
| 16 | `./components/alerts.css` | yes |
| 17 | `./pages/dashboard.css` | yes |
| 18 | `./pages/invoice-list.css` | yes |
| 19 | `./pages/invoice-detail.css` | yes |
| 20 | `./pages/payment-schedule.css` | yes |
| 21 | `./pages/payment-registry.css` | yes |
| 22 | `./pages/counterparties.css` | yes |
| 23 | `./pages/profile.css` | yes |
| 24 | `./pages/system.css` | yes |
| 25 | `./pages/audit.css` | yes |
| 26 | `./features/partial-payments.css` | yes |
| 27 | `./features/ocr.css` | yes |
| 28 | `./features/users-roles.css` | yes |
| 29 | `./features/legacy-migration.css` | yes |
| 30 | `./features/table-clean-baseline.css` | yes |
| 31 | `./features/ui-polish-actions.css` | yes |
| 32 | `./features/ui-polish-badges.css` | yes |
| 33 | `./features/ui-polish-filters.css` | yes |
| 34 | `./features/sidebar-fixed-left.css` | yes |

## JS files

| File | Lines |
|---|---:|
| `postcss.config.js` | 6 |
| `static/js/sidebar-floating-highlight.js` | 98 |
| `tailwind.config.js` | 28 |

## Potential UI risks

### Templates without `{% extends %}`

- `templates/base.html`
- `templates/components/sidebar.html`
- `templates/components/topbar.html`

### Templates with inline styles

- `templates/invoices/invoice_assign_counterparty.html` — style attrs: 1, style tags: 0

## Static references in templates

| Template | Static file | Exists |
|---|---|---:|
| `templates/base.html` | `css/app.css` | yes |
| `templates/base.html` | `css/features/sidebar-fixed-left.css` | yes |
| `templates/base.html` | `js/sidebar-floating-highlight.js` | yes |
| `templates/invoices/detail.html` | `pdfjs/pdf.mjs` | yes |
| `templates/invoices/detail.html` | `pdfjs/pdf.worker.mjs` | yes |
| `templates/login.html` | `css/app.css` | yes |
| `templates/login.html` | `css/features/login-page.css` | yes |
