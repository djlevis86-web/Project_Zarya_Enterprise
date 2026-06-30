# UI Smoke Report

| User | Route | URL | Status | OK | Notes |
|---|---|---|---:|---:|---|
| public | `login` | `/` | 200 | True | app_css=True; layout_marker=True; server_error=False; location=None |
| admin | `dashboard` | `/dashboard/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `profile` | `/profile/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `invoice_list` | `/invoices/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `upload_invoice` | `/invoices/upload/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `upload_batches` | `/invoices/uploads/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `payment_schedule` | `/invoices/payment-schedule/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `payment_registry` | `/invoices/payment-registry/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `counterparty_directory` | `/invoices/counterparties/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `ocr_queue` | `/invoices/ocr-queue/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `system_dashboard` | `/system/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `audit:audit_log_list` | `/audit/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| admin | `user_admin_list` | `/users/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `dashboard` | `/dashboard/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `profile` | `/profile/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `invoice_list` | `/invoices/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `upload_invoice` | `/invoices/upload/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `upload_batches` | `/invoices/uploads/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `payment_schedule` | `/invoices/payment-schedule/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `payment_registry` | `/invoices/payment-registry/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `counterparty_directory` | `/invoices/counterparties/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `ocr_queue` | `/invoices/ocr-queue/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| finance | `system_dashboard` | `/system/` | 302 | True | app_css=False; layout_marker=False; server_error=False; location=/dashboard/?next=/system/ |
| finance | `audit:audit_log_list` | `/audit/` | 302 | True | app_css=False; layout_marker=False; server_error=False; location=/dashboard/?next=/audit/ |
| finance | `user_admin_list` | `/users/` | 302 | True | app_css=False; layout_marker=False; server_error=False; location=/dashboard/?next=/users/ |
| uploader | `dashboard` | `/dashboard/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| uploader | `profile` | `/profile/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| uploader | `invoice_list` | `/invoices/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| uploader | `upload_invoice` | `/invoices/upload/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| uploader | `upload_batches` | `/invoices/uploads/` | 200 | True | app_css=True; layout_marker=False; server_error=False; location=None |
| uploader | `payment_schedule` | `/invoices/payment-schedule/` | 403 | True | app_css=False; layout_marker=False; server_error=False; location=None |
| uploader | `payment_registry` | `/invoices/payment-registry/` | 403 | True | app_css=False; layout_marker=False; server_error=False; location=None |
| uploader | `counterparty_directory` | `/invoices/counterparties/` | 302 | True | app_css=False; layout_marker=False; server_error=False; location=/admin/login/?next=/invoices/counterparties/ |
| uploader | `ocr_queue` | `/invoices/ocr-queue/` | 403 | True | app_css=False; layout_marker=False; server_error=False; location=None |
| uploader | `system_dashboard` | `/system/` | 302 | True | app_css=False; layout_marker=False; server_error=False; location=/dashboard/?next=/system/ |
| uploader | `audit:audit_log_list` | `/audit/` | 302 | True | app_css=False; layout_marker=False; server_error=False; location=/dashboard/?next=/audit/ |
| uploader | `user_admin_list` | `/users/` | 302 | True | app_css=False; layout_marker=False; server_error=False; location=/dashboard/?next=/users/ |
