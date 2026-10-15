# Role dashboards

Signed-in users enter at `/dashboard`. The API reports available roles at `GET /api/v1/dashboard/roles/`, and the frontend opens the preferred workspace in this order: platform admin, clinic, doctor, patient. People with more than one role can switch workspaces using the dashboard tabs.

| Workspace | URL | Current data and actions |
|---|---|---|
| Patient | `/dashboard/patient` | Own appointment records, upcoming count, open support count, account settings link. |
| Doctor | `/dashboard/doctor` | Own profile and registration status, clinic affiliations, upcoming appointment count. Patient identities are not included. |
| Clinic | `/dashboard/clinic` | Today's appointment counts and first 20 bookings for a selected accessible clinic, in that clinic's timezone. This screen is read only. |
| Platform operations | `/dashboard/admin` | Aggregate counts and role-scoped queues for provider review, support, finance, appointments, and delivery. Superusers also manage staff access and view the operations audit trail. |

Every dashboard API requires authentication. The doctor API checks for a DoctorProfile, the clinic API checks for an active organization membership and an available clinic, and the operations dashboard requires a superuser or an active operations grant. Each operations API checks the specific grant again. A clinic ID outside the user's accessible organizations returns 404. A regular Django staff account is not automatically a platform administrator. The patient API only reads appointments belonging to the signed-in patient.

The current membership model grants access to an organization, not to individual clinic assignments within a multi-clinic organization. Owners and managers can see their organization's clinics. Receptionists in organizations with more than one clinic cannot access the clinic dashboard until clinic-specific staff assignments are implemented. Doctor profile editing and receptionist actions still need separate permissions and screens.

See [admin operations](admin-operations.md) for staff roles, decisions, and audit behavior.
