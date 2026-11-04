"use strict";

// Study notes for each module, keyed by topic id.
// Written for the AWS Solutions Architect Associate (SAA-C03) level.
// To change the notes, edit this file and deploy; no database change is needed.
const courseContent = {
  "41000000-0000-0000-0000-000000000001": {
    title: "Networking and VPC",
    intro:
      "Amazon VPC is your own private network inside AWS. Almost every architecture " +
      "question in the exam starts here: where things live, what can reach them, " +
      "and how traffic gets in and out.",
    objectives: [
      "Explain VPCs, subnets, Availability Zones and route tables.",
      "Tell a public subnet from a private subnet, and explain why.",
      "Choose between an internet gateway, a NAT gateway and a VPC endpoint.",
      "Compare security groups with network ACLs.",
      "Pick the right way to connect several VPCs or an office network."
    ],
    lessons: [
      {
        title: "1. VPCs and subnets",
        points: [
          "A VPC lives in one AWS Region. You give it an IPv4 address range (a CIDR block), for example 10.0.0.0/16.",
          "A subnet is a smaller range inside the VPC, for example 10.0.1.0/24, and it always sits in exactly one Availability Zone (AZ).",
          "AWS keeps 5 addresses in every subnet for itself, so a /24 gives you 251 usable addresses, not 256.",
          "For high availability, put matching subnets in at least two AZs, so one AZ failing does not take your whole application down."
        ]
      },
      {
        title: "2. Route tables and gateways",
        points: [
          "Every subnet uses one route table. The route table decides where traffic goes.",
          "A subnet is public when its route table sends 0.0.0.0/0 to an internet gateway. The instance also needs a public IPv4 address or an Elastic IP.",
          "A private subnet has no route to the internet gateway. For outbound-only internet access (for updates), route 0.0.0.0/0 to a NAT gateway.",
          "A NAT gateway must sit in a public subnet, and it only protects one AZ. For resilience, create one NAT gateway per AZ.",
          "A gateway VPC endpoint lets private subnets reach Amazon S3 or DynamoDB without the internet or a NAT gateway, at no extra charge."
        ]
      },
      {
        title: "3. Security groups and network ACLs",
        points: [
          "A security group protects an instance (its network interface). It is stateful: if a request is allowed in, the reply is allowed out automatically.",
          "Security groups only have allow rules. Anything not allowed is denied.",
          "A network ACL protects a whole subnet. It is stateless, so you must allow the reply traffic too, usually on ephemeral ports 1024-65535.",
          "Network ACLs can allow and deny. Rules are checked in number order, lowest first, and the first match wins.",
          "Good practice: let one security group refer to another, for example the database group allows port 5432 only from the application group."
        ]
      },
      {
        title: "4. Connecting networks",
        points: [
          "VPC peering connects two VPCs privately. It is not transitive: if A peers with B and B with C, A still cannot reach C.",
          "Peered VPCs cannot have overlapping CIDR ranges, so plan address ranges early.",
          "AWS Transit Gateway is a central hub for many VPCs and on-premises networks. Choose it when peering would become a tangled mesh.",
          "AWS Site-to-Site VPN connects an office over the internet, encrypted. AWS Direct Connect is a private, dedicated line with steadier performance."
        ]
      }
    ],
    example: {
      title: "Worked example: a three-tier web application",
      text:
        "Put an Application Load Balancer in public subnets in two AZs. Put the web " +
        "servers in private subnets, reachable only from the load balancer's security " +
        "group. Put the database in separate private subnets, allowing only the web " +
        "servers' security group on the database port. Add one NAT gateway per AZ so " +
        "servers can download updates, and an S3 gateway endpoint for file storage."
    },
    traps: [
      "Security groups cannot deny traffic. If a question needs to block one IP address, think network ACL.",
      "A NAT gateway goes in a public subnet, never a private one.",
      "\"Public subnet\" is about the route table, not the IP range.",
      "VPC peering is not transitive. Many VPCs plus an office usually means Transit Gateway."
    ],
    activity:
      "Draw a VPC with public and private subnets in two AZs. Label the route tables, " +
      "the internet gateway, the NAT gateways and the security groups, then explain " +
      "how a request reaches a web server and how the server downloads an update.",
    links: [
      { label: "What is Amazon VPC?", url: "https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html" },
      { label: "Security groups", url: "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html" },
      { label: "Network ACLs", url: "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html" },
      { label: "NAT gateways", url: "https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html" }
    ]
  },

  "41000000-0000-0000-0000-000000000002": {
    title: "Storage and S3",
    intro:
      "Amazon S3 stores files (objects) in buckets. The exam tests how you keep data " +
      "private, how you recover from mistakes, and how you pick the cheapest storage " +
      "class that still meets the access needs.",
    objectives: [
      "Explain buckets, objects, keys and S3's durability.",
      "Secure a bucket with Block Public Access, IAM and bucket policies.",
      "Use versioning, replication and Object Lock to protect data.",
      "Choose the right storage class and automate moves with lifecycle rules."
    ],
    lessons: [
      {
        title: "1. Buckets and objects",
        points: [
          "A bucket lives in one Region, but its name must be unique across all of AWS.",
          "An object is a file plus its metadata, found by its key, for example reports/2026/october.pdf. One object can be up to 5 TB.",
          "S3 is designed for 99.999999999% (11 nines) durability by keeping copies across multiple AZs.",
          "S3 gives strong read-after-write consistency: as soon as a write succeeds, every read sees the new version."
        ]
      },
      {
        title: "2. Keeping data private",
        points: [
          "New buckets are private, with Block Public Access turned on. Leave it on unless the bucket really must be public.",
          "Control access with IAM policies (what a user or role can do) and bucket policies (who can use this bucket).",
          "Object ownership is set to \"bucket owner enforced\" by default, which turns off old-style ACLs. Use policies instead.",
          "To share one file for a short time, create a presigned URL instead of making anything public.",
          "New objects are encrypted at rest by default (SSE-S3). Use SSE-KMS when you need control over the keys and an audit trail of their use."
        ]
      },
      {
        title: "3. Protecting and recovering data",
        points: [
          "Versioning keeps every version of an object. Deleting adds a delete marker, so you can restore the previous version.",
          "Once versioning is turned on, it can only be suspended, not switched off.",
          "Replication copies objects to another bucket in the same Region or a different one. It needs versioning on both buckets.",
          "Object Lock stops objects being changed or deleted for a set time (write once, read many), which helps with legal and compliance rules."
        ]
      },
      {
        title: "4. Storage classes and lifecycle rules",
        points: [
          "S3 Standard: frequently used data. S3 Intelligent-Tiering: unknown or changing access patterns, moved automatically.",
          "S3 Standard-IA: used less than once a month but needed quickly. There is a retrieval fee and a 30-day minimum.",
          "S3 One Zone-IA: like Standard-IA but in one AZ only, so only for data you can recreate.",
          "S3 Glacier Instant Retrieval (milliseconds), Glacier Flexible Retrieval (minutes to hours) and Glacier Deep Archive (up to 12 hours, cheapest) are for archives.",
          "Lifecycle rules move objects to cheaper classes after a number of days, or delete old versions, without writing any code."
        ]
      }
    ],
    example: {
      title: "Worked example: private document storage",
      text:
        "Keep Block Public Access on. Add a bucket policy that denies requests not " +
        "using HTTPS. Turn on versioning, and add a lifecycle rule that moves old " +
        "versions to Glacier Flexible Retrieval after 30 days and deletes them after a " +
        "year. Encrypt with SSE-KMS, and let users download files through short-lived " +
        "presigned URLs."
    },
    traps: [
      "S3 is not inside your VPC. Private subnets reach it through a gateway endpoint.",
      "One Zone-IA is not for the only copy of important data.",
      "Replication needs versioning turned on in both buckets.",
      "\"Rarely accessed, needed within milliseconds\" points to Glacier Instant Retrieval; \"cheapest, can wait 12 hours\" points to Deep Archive."
    ],
    activity:
      "Design storage for a training company's learner documents. Decide who can read " +
      "and upload files, how you would recover a file deleted by mistake, and which " +
      "storage class each type of file should use after 30, 90 and 365 days.",
    links: [
      { label: "What is Amazon S3?", url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html" },
      { label: "Blocking public access", url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html" },
      { label: "Versioning", url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html" },
      { label: "Storage classes", url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html" },
      { label: "Lifecycle rules", url: "https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html" }
    ]
  }
};

// Builds the study notes for one module. Used by the learner workspace.
function renderStudyNotes(topicId, container) {
  const content = courseContent[topicId];
  if (!content) {
    container.append(element("p", "", "Study notes have not been published for this module yet."));
    return;
  }

  container.append(element("p", "study-intro", content.intro));

  const objectives = element("ul", "");
  content.objectives.forEach((text) => objectives.append(element("li", "", text)));
  container.append(element("h4", "", "By the end of this module you can"), objectives);

  content.lessons.forEach((lesson) => {
    const section = element("section", "study-lesson");
    const points = element("ul", "");
    lesson.points.forEach((text) => points.append(element("li", "", text)));
    section.append(element("h4", "", lesson.title), points);
    container.append(section);
  });

  const example = element("section", "study-example");
  example.append(element("h4", "", content.example.title), element("p", "", content.example.text));
  container.append(example);

  const traps = element("ul", "");
  content.traps.forEach((text) => traps.append(element("li", "", text)));
  const trapBox = element("section", "study-traps");
  trapBox.append(element("h4", "", "Common exam traps"), traps);
  container.append(trapBox);

  container.append(element("h4", "", "Practice activity"), element("p", "", content.activity));

  const links = element("ul", "study-links");
  content.links.forEach((link) => {
    const item = element("li", "");
    const anchor = element("a", "", link.label);
    anchor.href = link.url;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    item.append(anchor);
    links.append(item);
  });
  container.append(element("h4", "", "Read more in the AWS documentation"), links);
}
