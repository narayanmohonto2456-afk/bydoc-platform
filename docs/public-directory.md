# Public clinic and doctor directory

The directory is available without signing in. It returns active clinics and active doctors with a current verified registration and at least one active affiliation at an active clinic in an active organization. Suspended or closed entries return 404 in detail views.

## Clinics

- `GET /api/v1/clinics/`
- `GET /api/v1/clinics/{clinic_id}/`

List filters: `q` (clinic name, locality, or district), `state`, `district`, and `wheelchair_accessible` (`true` or `false`). State and district match without regard to case.

## Doctors

- `GET /api/v1/doctors/`
- `GET /api/v1/doctors/{doctor_id}/`

List filters: `q` (doctor display name), `specialty` (active specialty slug), `language` (active language code), `clinic_id` (UUID), `state`, `district`, and `online_booking` (`true` or `false`). Location and online booking criteria apply to the same eligible clinic affiliation. Only eligible clinics appear in doctor responses. Fees belong to each displayed clinic affiliation and may be null.

Lists are ordered by name then ID and paginated at 20 per page. Use `page` and `page_size` (maximum 100). Invalid filter values return 400. Both lists may include doctors or clinics without open appointment slots; query the existing appointment slot endpoint for a particular clinic and date to check availability.
