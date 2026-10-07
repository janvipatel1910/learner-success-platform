# Validation Checklist

## Scope

This is a proposed test plan for the design. No AWS resources have been deployed, so none of these tests have been run. Use fictional accounts and documents if the design is implemented.

Record each test as **Not run**, **Pass**, or **Fail**. Add the test date and evidence before calling it complete.

## Public entry and network boundaries

- [ ] **HTTPS entry:** Open the application from the internet over HTTPS. Expected result: the application is reachable through the load balancer.
- [ ] **HTTP handling:** Try the HTTP address. Expected result: it redirects to HTTPS or refuses the connection.
- [ ] **Application isolation:** Check that application tasks have no public IP address. Expected result: users cannot connect directly to a task.
- [ ] **Database isolation:** Try to connect to the database from the public internet. Expected result: the connection fails.
- [ ] **Allowed database route:** Connect from the application security group to the database on its required port. Expected result: the connection is allowed.
- [ ] **Denied database route:** Try the database connection from an unrelated security group. Expected result: the connection is blocked.

## Identity and document access

- [ ] **Own document:** Sign in as a learner and open that learner's document through the application. Expected result: access is allowed.
- [ ] **Other learner's document:** Try to open another learner's document. Expected result: the application denies access.
- [ ] **Tutor access:** Sign in as an authorised tutor and open a document for an assigned learner. Expected result: access follows the cohort permissions.
- [ ] **Anonymous access:** Try to list the bucket and open a document without signing in. Expected result: both requests are denied.
- [ ] **Application role scope:** Try to access an object outside the application's approved bucket or prefix. Expected result: the IAM role is denied.

## Encryption and storage controls

- [ ] **Public access block:** Confirm S3 Block Public Access is enabled.
- [ ] **Transport security:** Try an insecure request to the bucket. Expected result: the bucket policy denies it.
- [ ] **Encryption at rest:** Confirm document objects use the approved KMS key.
- [ ] **Key permissions:** Confirm only approved application and recovery roles can use the key.
- [ ] **Versioning:** Upload a replacement for a fictional document. Expected result: the earlier version remains available.

## Recovery and audit

- [ ] **Select a version:** Find the known-good version ID for the fictional document.
- [ ] **Restore:** Copy that version back to the original object key. Expected result: the application serves the restored document.
- [ ] **Privacy after recovery:** Repeat the anonymous-access test. Expected result: the restored document remains private.
- [ ] **Audit record:** Review the audit log. Expected result: it records the recovery action without exposing document contents or credentials.

## Operational checks

- [ ] Confirm logs do not contain passwords, credentials, or document contents.
- [ ] Define log and document-version retention periods.
- [ ] Set a budget alert and review the main cost drivers before deployment.
- [ ] Agree recovery time and recovery point objectives, then test them in a non-production environment.

## Evidence record

For every test performed, record its ID, date, expected result, actual result, and a safe evidence link. Do not mark a proposed test as passed until it has actually been run.
