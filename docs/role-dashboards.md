# Role dashboards

Signed-in users enter at `/dashboard`. The API reports available roles at `GET /api/v1/dashboard/roles/`, and the frontend opens the preferred workspace in this order: platform admin, clinic, doctor, patient. People with more than one role can switch workspaces using the dashboard tabs.

| Workspace | URL | Current data and actions |
|---|---|---|
| Patient | `/dashboard/patient` | Own appointment records, upcoming count, open support count, account settings link. |
| Doctor | `/dashboard/doctor` | Own profile and registration status, clinic affiliations, upcoming appointment count. Patient identities are not included. |
| Clinic | `/dashboard/clinic` | Today's appointment counts and first 20 bookings for a selected accessible clinic, in that clinic's timezone. This screen is read only. |
| Platform admin | `/dashboard/admin` | Aggregate account, doctor, clinic, verification, and support counts; link to Django admin for permitted operations. |

Every dashboard API requires a signed-in session. The doctor API checks for a DoctorProfile, the clinic API checks for an active organization membership and an available clinic, and the admin API requires a superuser. A clinic ID outside the user's accessible organizations returns 404. A regular Django staff account is not automatically a platform administrator. The patient API only reads appointments belonging to the signed-in patient.

The current membership model grants access to an organization, not to individual clinic assignments within a multi-clinic organization. Owners and managers can see their organization's clinics. Receptionists in organizations with more than one clinic cannot access the clinic dashboard until clinic-specific staff assignments are implemented. The dashboard does not yet provide patient booking, doctor profile editing, receptionist actions, or verification workflows. Those controls should be added with corresponding API permissions and tested at object level.
