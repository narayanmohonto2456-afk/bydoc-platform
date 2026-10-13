# Doctor and clinic applications

Applicants create a BYdoc account, verify its email, then open `/join`. A doctor enters the name on their medical registration, council or authority, registration number, and optional specialty. A clinic representative enters the responsible manager, clinic licence or registration authority and number, contact information, and address. Each applicant attests that the details are accurate and that they are entitled to submit them.

Submission **does not verify an identity or publish a listing**. The application is private and marked `pending`. The applicant can see its status from the same page. An applicant may submit corrected details after rejection; each submission and review decision remains a separate database record.

## Platform review

Only a platform superuser can review applications in Django admin. Open **Doctor applications** or **Clinic applications**, inspect the details, and independently confirm them against the relevant authority and applicant. Save a review note describing the evidence checked and decision. Then select the row and choose **Approve selected after saving review notes** or **Reject selected after saving review notes**. The reviewer cannot approve their own application. The review timestamp and reviewer are stored. Avoid putting patient or unnecessary personal information in review notes.

Doctor approval creates an active doctor profile and a registration marked verified with reviewer and timestamp. The doctor can access the doctor dashboard, but will not appear in public doctor search or accept online bookings until an active, verified clinic affiliation is set up separately. The optional specialty submitted by the doctor must be mapped to the reviewed specialty catalog by staff before it is published.

Clinic approval creates an active independent organization, active clinic, and active owner membership for the applicant. The clinic becomes visible in the public clinic directory. Before approval, check for a duplicate clinic or an applicant trying to claim an existing listing; the automatic approval path does not merge or transfer ownership. Contact support for existing-listing claims.

This workflow records registration details and human decisions. It does not claim government endorsement, automatic licence validation, or document inspection. Document upload remains off until private object storage, malware scanning, access auditing, and retention controls are available. Suspend questionable existing listings through the existing clinic, organization, doctor, and registration status controls.

## API

- `GET /api/v1/onboarding/doctor/` and `GET /api/v1/onboarding/clinic/`: the signed-in applicant's latest status.
- `POST` to the same paths: submit a new application after email verification. A pending application or existing doctor profile blocks another doctor submission.

The API ignores client-supplied review or publication state. The application decision is made only through the server-side admin review service. Existing public directory filters continue to require active clinic and organization records, verified doctor registration, and active doctor-clinic affiliation.
