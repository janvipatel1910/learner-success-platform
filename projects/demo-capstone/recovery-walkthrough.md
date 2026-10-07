# S3 Document Recovery Walkthrough

## Scenario

A tutor discovers that a learner's fictional file, `assignments/network-design.pdf`, was overwritten by an incorrect version. The bucket has S3 Versioning enabled.

This is a proposed procedure. No AWS recovery has been performed.

## Recovery procedure

1. Record the incident time, learner, exact object key, and the person reporting the problem. Do not include a real learner document in the project.
2. Confirm the request with an authorised tutor. Use the restricted recovery role; do not make the bucket or object public.
3. Find the object's versions and identify the last known good version ID. Confirm the object key and version before restoring anything.
4. Copy the approved prior version back to the original object key. In a versioned bucket, this creates a new current version and preserves the older versions.
5. Confirm the restored object still uses the required KMS encryption and remains covered by the private bucket policy.
6. Ask the tutor to open the document through the application. Confirm an authorised user can access it and an anonymous user cannot.
7. Record the operator, object key, restored version ID, reason, time, and verification result in the audit trail.

## Recovery success criteria

- The application serves the intended earlier document.
- The document remains private and encrypted.
- Earlier object versions remain available according to the retention policy.
- The recovery action is recorded without exposing document contents or credentials.

## Limitations

Recovery depends on the needed version still being retained and the recovery role and KMS key being available. Retention settings, approval steps, and recovery time objectives must be agreed and tested before production use.
