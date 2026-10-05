# Validation Checklist

## Network

- [ ] Public users can reach only the application entry point.
- [ ] The database has no public route or public endpoint.
- [ ] Only the application security group can reach the database port.
- [ ] Private application servers use controlled outbound access.

## S3 access

- [ ] Anonymous users cannot list the bucket.
- [ ] Anonymous users cannot download objects.
- [ ] The application role can access only the required bucket prefix.
- [ ] Public access blocking is enabled.
- [ ] Encryption and versioning are enabled.

## Recovery

- [ ] An earlier object version exists after an overwrite.
- [ ] An authorised user can restore the chosen version.
- [ ] The restored document opens through the application.
- [ ] The recovery action is recorded.

## Operations

- [ ] No credentials or real learner documents are in the repository.
- [ ] Logs do not expose document contents.
- [ ] Retention, backup and lifecycle settings are documented.
