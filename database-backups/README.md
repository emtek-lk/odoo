# Database backups

## odoo_2026-11-18_22-45-54.zip

Full backup (database dump + filestore) of the local development database `odoo`, taken 2026-11-18 22:45.

| | |
|---|---|
| Odoo | 20.0+e (Community + Enterprise) |
| PostgreSQL | 18.0 |
| Installed modules | 631 (15 custom, see below) |
| Size | 59.8 MB (dump.sql 84 MB, 1,836 filestore files) |
| SHA-256 | `dfa8473a595bcb391f024a6752ce5941a6f607385b94b05ec4c993ff028fb931` |

### What data it holds

**Odoo's own demo data** (all standard apps installed with demo data on):
292 contacts, 84 users, 9 companies, 73 sales orders, 20 purchase orders, 56 accounting entries,
29 employees, 44 CRM leads, 25 projects, 233 project tasks, 218 products.
The filestore includes the contact/employee photos, dashboards and menu icons (repaired from the earlier backups).

**Custom modules and their demo data** (all from `custom-addons/`):

| Module | Data loaded |
|---|---|
| `lms_institute`, `lms_demo_extra` | 20 courses, 78 lessons, 76 enrollments, instructors and students |
| `medical_base`, `medical_prescription`, `medical_lab`, `medical_portal`, `medical_demo`, `medical_demo_extra` | 7 institutions, 28 patients, 8 practitioners, 39 encounters, 33 prescriptions, 22 dispensings, 25 lab orders (39 results), 8 consents |
| `trace_base`, `trace_custody`, `trace_process`, `trace_public`, `trace_demo`, `trace_demo_extra` | 30 parties, 17 products, 158 batches, 897 events (hash-chained), 181 transfers, 38 processing runs, recalled batches and pending hand-overs |
| `apps_source_filter` | adds the Source filter to the Apps list; no data |

Demo logins have the login as the password (for example `med_doctor1`, `trace_green_valley`, `lms_student1`).

### Restore

1. Start Odoo with the same `addons_path` (Community, Enterprise and `custom-addons/`).
2. Open `/web/database/manager`, choose **Restore Database**, upload the zip, and enter the master password.
3. Log in with the original admin account.

### Handle with care

The dump contains user password hashes, Odoo's generated signing secrets (`database.secret`) and a real email address.
Keep this repository private, and restore it only on local or trusted machines.
