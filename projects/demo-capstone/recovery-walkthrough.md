# S3 Document Recovery Walkthrough

1. A learner uploads `assignments/network-design.pdf`.
2. The application stores the document in a private S3 bucket.
3. S3 Versioning retains the previous object version.
4. If a newer upload overwrites the document, an authorised tutor identifies the last known good version.
5. The application restores that version as the current object.
6. The tutor verifies the restored document through the application.
7. The recovery action is recorded for auditing.
8. The bucket remains private throughout the process.

Production retention and lifecycle rules should be reviewed before launch. This is a design walkthrough; no AWS recovery was performed.
