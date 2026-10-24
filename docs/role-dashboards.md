# Role dashboards

Signed-in users enter at `/dashboard`. The API reports available roles at `GET /api/v1/dashboard/roles/`, and the frontend opens the preferred workspace in this order: platform admin, clinic, doctor, patient. People with more than one role can switch workspaces using the dashboard tabs.

| Workspace | URL | Current data and actions |
|---|---|---|
| Patient | `/dashboard/patient` | Featured next visit, up to six other bookings, payment and refund details, upcoming and support counts, booking and nearby clinic shortcuts. |
| Doctor | `/dashboard/doctor` | Own profile and registration status, clinic affiliations, upcoming appointment count. Patient identities are not included. |
| Clinic | `/dashboard/clinic` | Today's appointment counts and first 20 bookings for a selected accessible clinic, in that clinic's timezone. This screen is read only. |
| Platform operations | `/dashboard/admin` | Aggregate counts and role-scoped queues for provider review, support, finance, appointments, and delivery. Superusers also manage staff access and view the operations audit trail. |

Every dashboard API requires authentication. The doctor API checks for a DoctorProfile, the clinic API checks for an active organization membership and an available clinic, and the operations dashboard requires a superuser or an active operations grant. Each operations API checks the specific grant again. A clinic ID outside the user's accessible organizations returns 404. A regular Django staff account is not automatically a platform administrator. The patient API only reads appointments belonging to the signed-in patient.

## Patient overview

The dashboard prioritizes the next visit, with the doctor, clinic, full appointment date and time, booking reference, status, and payment options together. A sidebar provides booking, nearby clinic, and account shortcuts. Other bookings appear below with expandable payment details. New patients see a booking prompt. The layout uses BYdoc's green palette, stacks on smaller screens, and supports keyboard navigation.

`GET /api/v1/dashboard/patient/` returns `next_appointment` as the earliest future confirmed or checked-in booking, or `null` when none exists. This query covers all the patient's bookings, so the next visit cannot be hidden by the six-record limit. `appointments` contains up to six other bookings ordered by appointment date descending; it excludes the featured visit. Dates are displayed in the browser's timezone.

Verification: dashboard API regression tests, frontend typecheck and production build, and Chrome DevTools review of populated and empty states. Layout checks cover 320, 768, 1024, and 1440 pixels. The populated dashboard's Lighthouse snapshot scored 100 for accessibility with no failed audits.

The current membership model grants access to an organization, not to individual clinic assignments within a multi-clinic organization. Owners and managers can see their organization's clinics. Receptionists in organizations with more than one clinic cannot access the clinic dashboard until clinic-specific staff assignments are implemented. Doctor profile editing and receptionist actions still need separate permissions and screens.

See [admin operations](admin-operations.md) for staff roles, decisions, and audit behavior.
