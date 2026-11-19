"""Generate scripts/seed_demo_mock_exam.sql: a 65-question timed mock exam.

The questions are original, written for SkillPulse at the AWS Solutions
Architect Associate (SAA-C03) level, and cover the two course modules.
Each question is checked here before any SQL is written, and the order of
answer options is shuffled with a fixed seed so the correct answer is not
always first, but the output is the same every time.

Run:  python scripts/generate_mock_exam.py
"""

import json
import random
from pathlib import Path

VPC = "41000000-0000-0000-0000-000000000001"
S3 = "41000000-0000-0000-0000-000000000002"
SOURCE = "60000000-0000-0000-0000-000000000001"
ASSESSMENT = "63000000-0000-0000-0000-000000000004"
COURSE = "40000000-0000-0000-0000-000000000001"
TITLE = "Mock Exam: VPC and S3"
OUTPUT = Path(__file__).resolve().parent / "seed_demo_mock_exam.sql"

# (topic, difficulty 1-5, question, [correct...], [wrong...], explanation)
QUESTIONS = [
    # ---------------- Networking and VPC (33) ----------------
    (VPC, 3,
     "A company's on-premises network uses 10.0.0.0/16. It is creating a VPC that will later connect to the office over a VPN. Which VPC CIDR block avoids an overlap?",
     ['172.16.0.0/16'],
     ['10.0.128.0/17', '10.0.0.0/8', '10.0.5.0/24'],
     '172.16.0.0/16 is a private range that does not overlap 10.0.0.0/16. The other three ranges all include addresses inside 10.0.0.0/16, which would break routing between the networks.'),
    (VPC, 2,
     'What is the largest IPv4 CIDR block you can assign to a VPC?',
     ['/16'],
     ['/8', '/24', '/28'],
     'A VPC IPv4 CIDR block can be between /16 (65,536 addresses) and /28 (16 addresses). /16 is the largest.'),
    (VPC, 1,
     'Which statement about subnets in Amazon VPC is correct?',
     ['Each subnet exists in exactly one Availability Zone.'],
     ['A subnet can span every Availability Zone in a Region.',
      'A subnet can span two Regions.',
      'A subnet is automatically shared with every VPC in the account.'],
     'A subnet always sits in a single Availability Zone. For high availability you create subnets in several AZs.'),
    (VPC, 2,
     'Web servers run in an Auto Scaling group and must keep working if one Availability Zone fails. What is the minimum subnet design?',
     ['Subnets in two or more Availability Zones, used by the Auto Scaling group'],
     ['One large subnet in a single Availability Zone, with a bigger instance type',
      'Two subnets in the same Availability Zone, with the group using both of them',
      'One subnet in each Region, connected with VPC peering'],
     'Because a subnet lives in one AZ, surviving an AZ failure needs subnets in at least two AZs and an Auto Scaling group that launches instances across them.'),
    (VPC, 3,
     'Instances in a private subnet cannot download updates. Their route table sends 0.0.0.0/0 to a NAT gateway, and the NAT gateway is in a public subnet. What is the most likely missing piece?',
     ["The public subnet's route table has no 0.0.0.0/0 route to an internet gateway."],
     ['The private instances need public IPv4 addresses.',
      'The NAT gateway must be moved into the private subnet.',
      "The private instances' security group must allow inbound traffic from the internet."],
     'A NAT gateway forwards traffic to the internet through the internet gateway, using the route table of the subnet it sits in. Without that route, outbound traffic has nowhere to go. Private instances do not need public IPs or inbound rules for this.'),
    (VPC, 3,
     'Which statement about a NAT gateway is correct?',
     ['It allows outbound connections from private instances, but not inbound ones from the internet.'],
     ['You attach a security group to the NAT gateway to control which instances can use it.',
      'It must be placed in a private subnet, next to the instances that use it.',
      'It lets internet users connect directly to instances in private subnets.'],
     'A NAT gateway only allows connections that start inside the VPC. You cannot attach security groups to it (network ACLs still apply), and it must be in a public subnet.'),
    (VPC, 3,
     'Instances that use IPv6 need outbound-only internet access over IPv6, with no inbound connections from the internet. What should you use?',
     ['An egress-only internet gateway'],
     ['A NAT gateway', 'A VPC peering connection', 'A virtual private gateway'],
     'An egress-only internet gateway is the IPv6 equivalent of NAT for outbound-only access. NAT gateways are for IPv4 traffic.'),
    (VPC, 2,
     'A security group has one inbound rule: allow TCP 22 from 203.0.113.10/32. What happens to an SSH connection attempt from 198.51.100.5?',
     ['It is denied, because traffic that no rule allows is denied.'],
     ['It is allowed, because the outbound rules allow all traffic.',
      'It is allowed if the network ACL allows it.',
      'It is denied only if a deny rule for 198.51.100.5 is added.'],
     'Security groups only have allow rules. Anything not explicitly allowed is denied, so no deny rule is needed.'),
    (VPC, 3,
     'A network ACL has rule 90: DENY all traffic from 198.51.100.0/24, and rule 100: ALLOW TCP 443 from 0.0.0.0/0. A client at 198.51.100.7 connects on port 443. What happens?',
     ['It is denied, because rule 90 is checked first and matches.'],
     ['It is allowed, because allow rules always win.',
      'It is allowed, because rule 100 is the higher number.',
      'Only the security group decides; network ACL rule order does not matter.'],
     'Network ACL rules are checked in number order, lowest first, and the first matching rule is applied. Rule 90 matches the client, so the traffic is denied.'),
    (VPC, 2,
     'Which TWO statements about security groups are correct? (Choose two.)',
     ['They are stateful: replies to allowed traffic are allowed automatically.',
      'A rule can use another security group as its source.'],
     ['They support explicit deny rules for blocking single IP addresses.',
      'Their rules are checked in number order, lowest number first.',
      'They apply to every instance in a subnet automatically.'],
     'Security groups are stateful, allow-only and attached to network interfaces. They can reference other security groups. Numbered rules and subnet-wide rules describe network ACLs.'),
    (VPC, 3,
     'Administrators need shell access to EC2 instances in private subnets without opening port 22 to the internet and without running a bastion host. What should they use?',
     ['AWS Systems Manager Session Manager'],
     ['An Elastic IP address on each instance',
      'A NAT gateway with port forwarding',
      "A VPC peering connection to the administrators' laptops"],
     'Session Manager connects through the SSM Agent over HTTPS, so no inbound ports, bastion hosts or SSH keys are needed, and sessions can be logged.'),
    (VPC, 2,
     'Gateway VPC endpoints are available for which TWO services? (Choose two.)',
     ['Amazon S3', 'Amazon DynamoDB'],
     ['Amazon SQS', 'AWS Systems Manager', 'Amazon EC2 API'],
     'Gateway endpoints exist only for Amazon S3 and DynamoDB. Most other services use interface endpoints (AWS PrivateLink).'),
    (VPC, 3,
     'Instances in private subnets must call the Amazon SQS API without using the internet or a NAT gateway. What should you create?',
     ['An interface VPC endpoint (AWS PrivateLink) for Amazon SQS'],
     ['A gateway VPC endpoint for Amazon SQS, added to the route table',
      'An internet gateway attached to the VPC',
      'An egress-only internet gateway for the private subnets'],
     'SQS is reached privately through an interface endpoint, which places network interfaces in your subnets. Gateway endpoints only support S3 and DynamoDB.'),
    (VPC, 4,
     'An interface endpoint for Amazon SQS was created, but instances still resolve the public SQS address and fail, because there is no NAT gateway. What is the most likely fix?',
     ['Turn on private DNS for the endpoint, with DNS support and hostnames on in the VPC.'],
     ['Attach an internet gateway so the public SQS address can be reached directly.',
      'Add a network ACL rule that denies the public SQS address range.',
      'Create a VPC peering connection to the VPC that hosts the SQS service.'],
     "With private DNS enabled, the normal SQS hostname resolves to the endpoint's private IP addresses inside the VPC. This needs the VPC's DNS support and DNS hostnames settings."),
    (VPC, 4,
     "A company runs a service behind a Network Load Balancer and wants to offer it privately to hundreds of customer VPCs. Customers' CIDR ranges may overlap, and the company must not expose its whole network. What is the best solution?",
     ['Publish the service as an AWS PrivateLink endpoint service'],
     ['Create a VPC peering connection with each customer',
      'Attach every customer VPC to one transit gateway',
      'Expose the service on the internet with an IP allow-list'],
     'PrivateLink exposes only one service, not whole networks, and works even when CIDR ranges overlap. Peering and Transit Gateway connect networks and need non-overlapping ranges.'),
    (VPC, 2,
     'Two VPCs both use the CIDR block 10.0.0.0/16. Can you connect them with VPC peering?',
     ['No. Peered VPCs must not have overlapping CIDR blocks.'],
     ['Yes, if the VPCs are in different Regions.',
      'Yes, after adding routes to both route tables.',
      'Yes, but traffic can only flow in one direction.'],
     'VPC peering does not support overlapping CIDR blocks. Plan non-overlapping address ranges before you need to connect networks.'),
    (VPC, 3,
     'A VPC peering connection was created and accepted, but instances in the two VPCs still cannot talk to each other. Which TWO things are most likely missing? (Choose two.)',
     ["Routes to the peer VPC's CIDR through the peering connection, on both sides",
      'Security group rules that allow traffic from the peer VPC'],
     ['An internet gateway attached to each VPC so the peered traffic can be routed',
      'A NAT gateway in each VPC to translate addresses between the two networks',
      "An AWS Direct Connect connection between the two VPCs' Regions"],
     'Peering needs routes on both sides and security group rules that allow the traffic. Peered traffic never uses internet gateways or NAT gateways.'),
    (VPC, 3,
     'A company has three VPCs and needs private connectivity between only two of them, at the lowest cost. What should it use?',
     ['A VPC peering connection'],
     ['AWS Transit Gateway',
      'AWS Direct Connect',
      'An AWS Site-to-Site VPN between the VPCs'],
     'VPC peering has no hourly charge, only data transfer, and is simplest for a single pair. Transit Gateway adds per-attachment hourly charges and is better for many VPCs.'),
    (VPC, 2,
     'A branch office needs an encrypted connection to a VPC by tomorrow, using its existing internet link. What is the best option?',
     ['AWS Site-to-Site VPN'],
     ['AWS Direct Connect', 'VPC peering', 'A gateway VPC endpoint'],
     'A Site-to-Site VPN can be set up quickly over the internet and is encrypted with IPsec. Direct Connect is a physical connection that takes much longer to provision.'),
    (VPC, 3,
     'A company sends critical traffic over a single AWS Direct Connect connection. What is the lowest-cost way to add a backup path?',
     ['Add an AWS Site-to-Site VPN as a backup connection'],
     ['Increase the bandwidth of the Direct Connect connection',
      'Add a NAT gateway',
      'Create a VPC peering connection to another Region'],
     'A Site-to-Site VPN over the internet is a common low-cost backup for Direct Connect. More bandwidth does not remove the single point of failure.'),
    (VPC, 4,
     "Traffic over AWS Direct Connect is not encrypted by default, but a company's policy requires encryption in transit. What can it do?",
     ['Run an IPsec VPN connection over the Direct Connect connection'],
     ['Turn on default encryption for its S3 buckets',
      'Add network ACL rules to the Direct Connect subnets',
      'Nothing, because Direct Connect encrypts all traffic automatically'],
     'Direct Connect is a private connection but not encrypted by default. Running a VPN over it (or using MACsec where supported) adds encryption in transit.'),
    (VPC, 2,
     'A team needs to see which source IP addresses are being rejected when they try to connect to an instance. Which feature should they use?',
     ['VPC Flow Logs'],
     ['AWS CloudTrail', 'AWS Config', 'AWS Trusted Advisor'],
     'VPC Flow Logs record IP traffic to and from network interfaces, including whether it was accepted or rejected. CloudTrail records API calls, not network traffic.'),
    (VPC, 3,
     'Which statement about VPC Flow Logs is correct?',
     ['They record traffic details such as IPs, ports and ACCEPT or REJECT, not packet contents.'],
     ['They record full packet contents so you can inspect application data later.',
      'They can block traffic that matches a rule, in the same way as a network firewall.',
      'They can only be turned on for public subnets that use an internet gateway.'],
     'Flow logs capture information about traffic, not payloads, and they do not affect traffic. They can be enabled for a VPC, a subnet or a network interface.'),
    (VPC, 1,
     'A server needs a fixed public IPv4 address that stays the same when the instance is stopped and started. What should you use?',
     ['An Elastic IP address'],
     ['The auto-assigned public IPv4 address',
      'A private IPv4 address',
      'A NAT gateway'],
     'An auto-assigned public IP changes after a stop and start. An Elastic IP address stays allocated to your account until you release it.'),
    (VPC, 3,
     "An internet-facing Application Load Balancer sends traffic to EC2 instances in private subnets. Where should the load balancer's subnets be?",
     ['In public subnets in at least two Availability Zones'],
     ['In the same private subnets as the instances, so traffic stays private',
      'In one public subnet only, because the load balancer scales automatically',
      'In any subnet, because load balancers do not use route tables'],
     'An internet-facing load balancer needs public subnets so clients can reach it, and needs at least two AZs. The targets can stay in private subnets.'),
    (VPC, 2,
     'Which statement about the default VPC is correct?',
     ['It has a public subnet in each AZ and an internet gateway already attached.'],
     ['It has private subnets only, and you must attach an internet gateway yourself.',
      'It has no subnets until you create them in each Availability Zone.',
      'It cannot be used to launch instances; it only holds default security groups.'],
     'The default VPC is ready to use: each AZ has a default subnet with a route to the attached internet gateway.'),
    (VPC, 3,
     'Instances in a custom VPC must receive public DNS hostnames. Which TWO VPC settings must be enabled? (Choose two.)',
     ['DNS hostnames', 'DNS resolution (DNS support)'],
     ['A NAT gateway', 'VPC Flow Logs', 'A VPC peering connection'],
     'Both DNS resolution and DNS hostnames must be turned on for instances with public IP addresses to get public DNS names.'),
    (VPC, 3,
     'A route table contains: 10.0.0.0/16 local; 10.1.0.0/16 to a peering connection; 0.0.0.0/0 to an internet gateway. Where is traffic to 10.1.5.9 sent?',
     ['To the peering connection, because the most specific matching route is used'],
     ['To the internet gateway, because the 0.0.0.0/0 route matches every destination',
      'It is dropped, because two routes match',
      'To the local route'],
     'Route tables use the longest prefix match. 10.1.0.0/16 is more specific than 0.0.0.0/0, so the peering connection is used.'),
    (VPC, 2,
     'Which statement about the local route in a VPC route table is correct?',
     ['It lets all subnets in the VPC reach each other, and it cannot be deleted.'],
     ['You must add it to the route table manually after creating each subnet.',
      'It only covers public subnets that have a route to an internet gateway.',
      'It sends traffic between subnets through the internet gateway.'],
     "Every route table has a local route for the VPC's CIDR, so subnets can always reach each other. Use security groups and network ACLs to limit that traffic."),
    (VPC, 2,
     'A new subnet is created and not explicitly associated with a route table. Which route table does it use?',
     ["The VPC's main route table"],
     ['None, so no traffic can leave the subnet',
      'A new, empty route table',
      "The default VPC's route table"],
     'Subnets without an explicit association use the main route table. Many teams keep the main table private and associate public subnets explicitly.'),
    (VPC, 3,
     'A company wants stateful inspection of all traffic entering and leaving its VPCs, including filtering by domain name. Which service should it use?',
     ['AWS Network Firewall'],
     ['Security groups only', 'VPC Flow Logs', 'Amazon Route 53 health checks'],
     'AWS Network Firewall is a managed firewall that supports stateful rules and domain filtering. Flow logs only record traffic, and security groups cannot filter by domain.'),
    (VPC, 2,
     'Internal services need DNS names that only resolve inside selected VPCs. What should you create?',
     ['An Amazon Route 53 private hosted zone associated with those VPCs'],
     ['A public hosted zone with records that only point to private IP addresses',
      'An Amazon CloudFront distribution in front of each service',
      'An Elastic IP address for each service, with a DNS record for each'],
     'A private hosted zone answers DNS queries only from the VPCs you associate with it.'),
    (VPC, 2,
     "A security group allows inbound HTTP (port 80) from anywhere, but the subnet's network ACL denies inbound port 80 from 0.0.0.0/0. What happens to HTTP requests from the internet?",
     ['They are blocked, because both the network ACL and the security group must allow the traffic.'],
     ['They are allowed, because security groups are stateful and remember the request.',
      "They are allowed, because the security group's allow rule overrides the network ACL.",
      'It depends only on the route table of the subnet.'],
     'Traffic must pass both layers. The network ACL is checked at the subnet boundary first, so its deny blocks the request before it reaches the instance.'),

    # ---------------- Storage and S3 (32) ----------------
    (S3, 1,
     'Which statement about S3 bucket names is correct?',
     ['Bucket names must be unique across all AWS accounts.'],
     ['Bucket names only need to be unique within your account.',
      'Bucket names only need to be unique within a Region.',
      'Bucket names can contain spaces and capital letters.'],
     'Bucket names share one global namespace, even though each bucket lives in a single Region.'),
    (S3, 1,
     'What is the largest size of a single object in Amazon S3?',
     ['5 TB'],
     ['5 GB', '160 GB', 'There is no limit'],
     'An object can be up to 5 TB. A single PUT request can upload up to 5 GB; larger objects need multipart upload.'),
    (S3, 2,
     'A 20 GB file must be uploaded to S3 quickly, and the upload must be able to continue if the network drops. What should you use?',
     ['Multipart upload'],
     ['A single PUT request', 'S3 Select', 'S3 Object Lock'],
     'Multipart upload sends parts in parallel and lets you retry only failed parts. A single PUT is limited to 5 GB.'),
    (S3, 2,
     'An application writes a new object to S3 and immediately reads it. What does the read return?',
     ['The new object, because S3 is strongly consistent for reads after writes'],
     ['Possibly an older version for a few minutes after the write',
      'A 404 error until the object has been copied to every Availability Zone',
      "Nothing until the bucket's index is rebuilt overnight"],
     'S3 is strongly consistent: once a write succeeds, all following reads return the new data.'),
    (S3, 2,
     'How is S3 Standard designed to protect your data?',
     ['For 11 nines of durability, by storing data across several Availability Zones'],
     ['By storing every object on one server in a single Availability Zone',
      'For 99.9% durability, by keeping two copies in one data centre',
      'Durability depends on how many buckets you spread the data across'],
     'S3 Standard keeps data across at least three AZs and is designed for 11 nines of durability.'),
    (S3, 3,
     'All requests to a bucket must use HTTPS. How do you enforce this?',
     ['Add a bucket policy that denies requests where aws:SecureTransport is false'],
     ['Turn on versioning so every request is recorded with a version ID',
      'Use SSE-S3 encryption, which also encrypts every request in transit',
      'Turn on Block Public Access for the bucket and for the whole account'],
     'The aws:SecureTransport condition key is false for plain HTTP requests, so an explicit deny on that condition blocks them. Encryption at rest does not control the transport.'),
    (S3, 4,
     'An IAM role in account B must read objects in a bucket owned by account A. Which TWO are required? (Choose two.)',
     ['A bucket policy in account A that allows the role from account B',
      'An IAM policy on the role in account B that allows s3:GetObject on the bucket'],
     ['Making the bucket public so that account B can read it without a policy',
      'Turning off Block Public Access on the bucket in account A',
      "Turning on versioning so account B can read the objects' versions"],
     "Cross-account access needs permission on both sides: the bucket policy trusts the other account's role, and the role's own policy allows the action."),
    (S3, 3,
     'Objects uploaded by another account are owned by that uploader, so the bucket owner cannot manage access to them. What is the recommended fix?',
     ["Set Object Ownership to 'Bucket owner enforced', which turns off ACLs"],
     ['Turn ACLs back on and grant the bucket owner full control on each upload',
      'Make the uploaded objects public so the bucket owner can read them',
      'Turn off default encryption so the bucket owner can open the objects'],
     "With 'Bucket owner enforced', the bucket owner owns every object and access is controlled only by policies. This is the default for new buckets."),
    (S3, 3,
     'A Lambda function only needs to read objects under the reports/ prefix of one bucket. Which permission follows least privilege?',
     ['Allow s3:GetObject on arn:aws:s3:::bucket-name/reports/*'],
     ['Allow s3:* on all resources',
      'Attach the AmazonS3FullAccess managed policy',
      'Allow s3:GetObject on every bucket in the account'],
     'Least privilege means only the needed action (GetObject) on only the needed resources (that prefix in that bucket).'),
    (S3, 3,
     'Users of a mobile app must upload photos directly to S3 for a short time, without having AWS credentials. What is the best approach?',
     ['The backend generates presigned URLs for uploads'],
     ["Allow public writes on the bucket for the app's users",
      'Put a long-term access key inside the app',
      'Turn on static website hosting for the bucket'],
     "A presigned URL lets someone perform one specific action until it expires, using the backend's permissions. Public write access and embedded keys are serious security risks."),
    (S3, 3,
     'Versioning is on, and storage costs keep rising because old versions build up. What is the best fix?',
     ['Add a lifecycle rule that expires noncurrent versions after some days'],
     ['Suspend versioning, which deletes the old versions automatically',
      "Turn versioning off completely and remove the bucket's history",
      'Turn on S3 Transfer Acceleration to move old versions faster'],
     'Lifecycle rules can expire noncurrent versions automatically. Suspending versioning does not delete existing versions, and versioning cannot be turned off once enabled.'),
    (S3, 3,
     'What happens when you suspend versioning on a bucket?',
     ['Existing versions are kept, and new objects get a null version ID.'],
     ['All earlier versions are deleted to save storage.',
      'Old versions are kept, but versioning can never be turned on again.',
      'All objects become locked until versioning is resumed.'],
     'Suspending stops creating new versions but keeps every existing version. You can turn versioning on again later.'),
    (S3, 3,
     'A company wants an extra safeguard so that permanently deleting an object version requires a multi-factor authentication code. What should it use?',
     ['MFA Delete on the versioned bucket'],
     ['Block Public Access on the bucket and the account',
      'SSE-KMS encryption with a customer managed key',
      'Requester Pays on the bucket'],
     "MFA Delete requires an MFA code to permanently delete a version or change the bucket's versioning state."),
    (S3, 4,
     'Records must be protected so that no user, including the root user, can delete them or shorten the retention period. Which S3 Object Lock setting meets this?',
     ['Compliance mode'],
     ['Governance mode',
      'Versioning without Object Lock',
      'A lifecycle expiration rule'],
     'In compliance mode nobody can delete the object or shorten its retention until it ends. Governance mode lets users with special permission override it.'),
    (S3, 3,
     'Lawyers need a specific object kept until a court case ends, but nobody knows when that will be. Which feature fits best?',
     ['An Object Lock legal hold'],
     ['Compliance-mode retention for 10 years', 'A lifecycle rule', 'MFA Delete'],
     'A legal hold protects an object with no end date until someone with permission removes it. Retention periods need a fixed date.'),
    (S3, 4,
     'Cross-Region Replication was set up today, but objects that already existed in the bucket were not copied. How can they be replicated?',
     ['Use S3 Batch Replication'],
     ['Wait, because replication copies existing objects within 24 hours',
      'Turn versioning off and on again',
      'Add a lifecycle transition rule'],
     'Replication rules only apply to new objects. S3 Batch Replication copies objects that existed before the rule was added.'),
    (S3, 3,
     'Log files must also be copied to a bucket in another account in the same Region, for a separate security team. What should you use?',
     ['S3 Same-Region Replication'],
     ['S3 Cross-Region Replication',
      'S3 Transfer Acceleration',
      'S3 Glacier Deep Archive'],
     'Same-Region Replication copies objects to another bucket in the same Region, including one in a different account.'),
    (S3, 4,
     'A company needs an SLA that 99.99% of new objects are replicated to another Region within 15 minutes. What should it turn on?',
     ['S3 Replication Time Control (RTC)'],
     ['S3 Transfer Acceleration', 'Multipart upload', 'S3 Intelligent-Tiering'],
     'Replication Time Control is designed to replicate 99.99% of objects within 15 minutes and is backed by an SLA, with metrics to track it.'),
    (S3, 2,
     'What is the minimum storage duration charge for S3 Standard-IA?',
     ['30 days'],
     ['90 days', '180 days', 'There is no minimum'],
     'Standard-IA charges for at least 30 days, even if the object is deleted sooner. It also has a retrieval fee per GB.'),
    (S3, 4,
     'An object stored in S3 Glacier Flexible Retrieval is deleted after 20 days. How is storage charged?',
     ['For the 90-day minimum storage duration'],
     ['For 20 days only', 'Nothing, because it was deleted early', 'For 180 days'],
     'Glacier Flexible Retrieval has a 90-day minimum, so early deletion is charged as if stored for 90 days. Glacier Deep Archive has a 180-day minimum.'),
    (S3, 2,
     'How long does a standard retrieval from S3 Glacier Deep Archive usually take?',
     ['Within 12 hours'],
     ['Milliseconds', '1 to 5 minutes', 'About 30 days'],
     'Deep Archive is the cheapest class, with standard retrievals within 12 hours (bulk within 48 hours).'),
    (S3, 4,
     'Archived files are almost never read, but now and then one is needed within a few minutes. Which option is the best fit?',
     ['S3 Glacier Flexible Retrieval, using expedited retrieval when needed'],
     ['S3 Glacier Deep Archive, using bulk retrieval when a file is needed',
      'S3 Glacier Deep Archive, using standard retrieval when a file is needed',
      'S3 One Zone-IA, moved by a lifecycle rule after 30 days'],
     'Expedited retrievals from Glacier Flexible Retrieval usually return data in 1 to 5 minutes. Deep Archive retrievals take hours.'),
    (S3, 3,
     'Which statement about S3 Intelligent-Tiering is correct?',
     ['It has no retrieval fees, but adds a small monitoring fee per object.'],
     ['It charges a retrieval fee for every GB read from the infrequent tier.',
      'It only moves objects between tiers if you also write lifecycle rules.',
      'It is only suitable for objects smaller than 128 KB.'],
     'Intelligent-Tiering moves objects between tiers automatically with no retrieval fees. Objects smaller than 128 KB are not monitored and stay in the frequent access tier.'),
    (S3, 1,
     'Product images are read by users many times every day. Which storage class should store them?',
     ['S3 Standard'],
     ['S3 Standard-IA', 'S3 Glacier Instant Retrieval', 'S3 One Zone-IA'],
     'Frequently read data belongs in S3 Standard. Infrequent access classes add retrieval fees that would cost more for data read every day.'),
    (S3, 2,
     'Which statement about encryption of new objects in S3 is correct?',
     ['New objects are encrypted at rest with SSE-S3 by default.'],
     ['New objects are unencrypted unless you turn encryption on.',
      'New objects must use AWS KMS keys.',
      'Only client-side encryption is supported.'],
     'Since January 2023, S3 applies SSE-S3 encryption to all new objects by default. You can choose SSE-KMS for more control.'),
    (S3, 4,
     'A bucket with a very high request rate uses SSE-KMS, and AWS KMS request costs are high. What is the best way to reduce them?',
     ['Turn on S3 Bucket Keys'],
     ['Turn on versioning', 'Turn off encryption', 'Turn on S3 Transfer Acceleration'],
     'S3 Bucket Keys create a bucket-level key that reduces requests from S3 to KMS, which can lower KMS costs a lot while keeping SSE-KMS.'),
    (S3, 3,
     "Data must be encrypted before it leaves the company's own servers, so AWS never receives it unencrypted. What should the company use?",
     ['Client-side encryption'],
     ['SSE-S3', 'SSE-KMS', 'Block Public Access'],
     'With client-side encryption, data is encrypted before upload. Server-side encryption happens after S3 receives the data.'),
    (S3, 3,
     'An auditor needs a record of who deleted which objects in a bucket. What should you turn on?',
     ['AWS CloudTrail data events for Amazon S3'],
     ['VPC Flow Logs for the subnets that use the bucket',
      'S3 Intelligent-Tiering monitoring reports',
      'AWS Budgets alerts for the bucket'],
     'CloudTrail data events record object-level API calls such as DeleteObject, including who made them and when.'),
    (S3, 3,
     'Users around the world upload large files to one bucket in eu-west-2, and uploads from far away are slow. What can improve upload speed?',
     ['S3 Transfer Acceleration'],
     ['S3 Standard-IA', 'Versioning', 'S3 One Zone-IA'],
     'Transfer Acceleration routes uploads through the nearest CloudFront edge location and then over the AWS network to the bucket.'),
    (S3, 2,
     'When a new image is uploaded to a bucket, a thumbnail must be created automatically. What is the best design?',
     ['An S3 event notification that invokes an AWS Lambda function'],
     ['A lifecycle rule that creates a thumbnail when each object is uploaded',
      'S3 Replication to a second bucket that resizes the images',
      'S3 Glacier Flexible Retrieval with expedited processing'],
     'S3 event notifications can trigger Lambda when objects are created, which is the standard serverless way to process uploads.'),
    (S3, 4,
     'A bucket must only be usable through one specific gateway VPC endpoint. How do you enforce this?',
     ['A bucket policy that denies requests unless aws:SourceVpce matches the endpoint ID'],
     ["A network ACL rule on the bucket that allows only the endpoint's subnet",
      'A security group attached to the bucket that allows only the VPC CIDR',
      'Turning on Block Public Access, which limits access to the VPC automatically'],
     'Buckets do not have security groups or network ACLs. A bucket policy condition on aws:SourceVpce limits access to requests that come through that endpoint.'),
    (S3, 3,
     'Data is rarely read after 90 days. Which TWO options can lower its storage cost automatically? (Choose two.)',
     ['A lifecycle rule moving objects to Glacier Flexible Retrieval after 90 days',
      'Storing the objects in S3 Intelligent-Tiering'],
     ['Turning on versioning so older copies are kept in the same storage class',
      'Turning on S3 Transfer Acceleration for downloads of older data',
      'Turning on Cross-Region Replication to a second bucket in S3 Standard'],
     'Lifecycle transitions and Intelligent-Tiering both move cold data to cheaper storage without manual work. Versioning and replication add storage, and Transfer Acceleration costs extra.'),
]


def validate(questions):
    texts = set()
    counts = {VPC: 0, S3: 0}
    for number, (topic, difficulty, text, correct, wrong, explanation) in enumerate(
        questions, start=1
    ):
        where = f"Question {number}"
        assert topic in counts, where
        assert 1 <= difficulty <= 5, where
        assert text not in texts, f"{where} is a duplicate"
        texts.add(text)
        options = correct + wrong
        assert len(options) == len(set(options)), f"{where} repeats an option"
        if "(Choose two.)" in text:
            assert len(correct) == 2 and len(options) == 5, where
        else:
            assert len(correct) == 1 and len(options) == 4, where
        assert len(explanation) > 40, where
        counts[topic] += 1
    assert len(questions) == 65, f"Expected 65 questions, found {len(questions)}"
    return counts


def sql_text(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build() -> str:
    counts = validate(QUESTIONS)
    rows, links = [], []
    for number, (topic, difficulty, text, correct, wrong, explanation) in enumerate(
        QUESTIONS, start=1
    ):
        options = correct + wrong
        random.Random(number * 7919).shuffle(options)
        question_id = f"62000000-0000-0000-0003-{number:012d}"
        kind = "multiple_choice" if len(correct) > 1 else "single_choice"
        rows.append(
            "    ("
            + ", ".join([
                sql_text(question_id),
                sql_text(topic),
                sql_text(text),
                sql_text(kind),
                sql_text(json.dumps(options, ensure_ascii=False)),
                sql_text(json.dumps(correct, ensure_ascii=False)),
                sql_text(explanation),
                str(difficulty),
                sql_text(SOURCE),
                "'published'",
            ])
            + ")"
        )
        links.append(
            f"    ({sql_text(ASSESSMENT)}, {sql_text(question_id)}, {number}, 1)"
        )

    return f"""-- Demo mock exam: 65 timed questions across the VPC and S3 modules.
-- GENERATED by scripts/generate_mock_exam.py. Edit that file, not this one.
-- Original questions written for SkillPulse; not copied from any exam or course.
-- {counts[VPC]} Networking and VPC questions, {counts[S3]} Storage and S3 questions.
-- Idempotent: safe to run more than once.
BEGIN;

INSERT INTO questions (id, topic_id, question_text, question_type, options_json, correct_answer_json, explanation, difficulty, verified_source_id, status)
VALUES
{",\n".join(rows)}
ON CONFLICT (id) DO NOTHING;

INSERT INTO assessments (id, course_id, title, assessment_type, question_count, time_limit_minutes, pass_percentage, maximum_attempts, status, published_at)
VALUES ({sql_text(ASSESSMENT)}, {sql_text(COURSE)}, {sql_text(TITLE)}, 'mock_exam', 65, 130, 70, 3, 'published', NOW())
ON CONFLICT (id) DO NOTHING;

INSERT INTO assessment_questions (assessment_id, question_id, sequence_number, marks)
VALUES
{",\n".join(links)}
ON CONFLICT (assessment_id, question_id) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM assessments
        WHERE id = {sql_text(ASSESSMENT)}
          AND assessment_type = 'mock_exam'
          AND question_count = 65
          AND time_limit_minutes = 130
          AND pass_percentage = 70
          AND status = 'published'
    ) THEN
        RAISE EXCEPTION 'Mock exam configuration differs from the demo definition.';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM assessment_questions AS aq
        JOIN questions AS q ON q.id = aq.question_id
        WHERE aq.assessment_id = {sql_text(ASSESSMENT)}
          AND q.status = 'published'
          AND q.correct_answer_json <@ q.options_json
    ) <> 65 THEN
        RAISE EXCEPTION 'Mock exam must link 65 published questions with valid answers.';
    END IF;
END
$$;

COMMIT;

SELECT a.title, a.assessment_type, a.question_count, a.time_limit_minutes, a.pass_percentage,
       COUNT(*) FILTER (WHERE q.topic_id = {sql_text(VPC)}) AS vpc_questions,
       COUNT(*) FILTER (WHERE q.topic_id = {sql_text(S3)}) AS s3_questions
FROM assessments AS a
JOIN assessment_questions AS aq ON aq.assessment_id = a.id
JOIN questions AS q ON q.id = aq.question_id
WHERE a.id = {sql_text(ASSESSMENT)}
GROUP BY a.id;
"""


if __name__ == "__main__":
    OUTPUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUTPUT.name}")
