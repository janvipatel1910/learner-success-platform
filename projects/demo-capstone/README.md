# Secure Application and Document Storage

## Scenario

A training company needs an application with a private database and private storage for learner documents.

## Proposed architecture

```mermaid
flowchart TD
    User[User] --> ALB[Public application load balancer]
    ALB --> App[Application in private subnet]
    App --> DB[Database in private subnet]
    App --> S3[Private S3 bucket]
    App --> NAT[NAT gateway for outbound updates]
