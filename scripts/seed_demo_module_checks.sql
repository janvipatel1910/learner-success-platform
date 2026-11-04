-- Demo module checks for the SkillPulse demo course.
-- Each module (VPC, S3) has a 5-question check. Learners need 80% (4 of 5)
-- to complete the module and unlock the next one. 3 attempts are allowed.
-- Original questions written for SkillPulse; not copied from any exam or course.
-- Idempotent: safe to run more than once. Running it on a database that still
-- has the old 1-question checks upgrades them in one transaction.
BEGIN;

-- Four new questions per module. The first question of each check
-- (62000000-...-0000-000000000001 and ...0002) comes from the base seed.
INSERT INTO questions (id, topic_id, question_text, question_type, options_json, correct_answer_json, explanation, difficulty, verified_source_id, status)
VALUES
    ('62000000-0000-0000-0002-000000000001', '41000000-0000-0000-0000-000000000001', 'A subnet has the CIDR block 10.0.1.0/24. How many IP addresses can you use for your own resources?', 'single_choice', '["256", "254", "251", "250"]', '["251"]', 'A /24 has 256 addresses, but AWS keeps 5 in every subnet (network address, VPC router, DNS, future use and broadcast), leaving 251.', 2, '60000000-0000-0000-0000-000000000001', 'published'),
    ('62000000-0000-0000-0002-000000000002', '41000000-0000-0000-0000-000000000001', 'You must block all traffic from one IP address to every instance in a subnet. What should you use?', 'single_choice', '["A deny rule in a security group", "A deny rule in the subnet''s network ACL", "A route table entry for that IP address", "A NAT gateway"]', '["A deny rule in the subnet''s network ACL"]', 'Security groups only have allow rules. Network ACLs can deny traffic, and they apply to the whole subnet.', 2, '60000000-0000-0000-0000-000000000001', 'published'),
    ('62000000-0000-0000-0002-000000000003', '41000000-0000-0000-0000-000000000001', 'A PostgreSQL database must accept connections only from the application servers. What is the best inbound rule for the database''s security group?', 'single_choice', '["Allow port 5432 from 0.0.0.0/0", "Allow all traffic from the VPC CIDR block", "Allow port 5432 from the internet gateway", "Allow port 5432 from the application servers'' security group"]', '["Allow port 5432 from the application servers'' security group"]', 'Referring to another security group allows only instances in that group, even when their IP addresses change. The other options are far wider than needed.', 3, '60000000-0000-0000-0000-000000000001', 'published'),
    ('62000000-0000-0000-0002-000000000004', '41000000-0000-0000-0000-000000000001', 'An office needs a private, dedicated network connection to AWS with steady performance, not a connection over the internet. Which service fits?', 'single_choice', '["AWS Site-to-Site VPN", "AWS Direct Connect", "VPC peering", "An internet gateway"]', '["AWS Direct Connect"]', 'Direct Connect is a dedicated private line to AWS. Site-to-Site VPN is encrypted but runs over the internet, so its performance can vary.', 2, '60000000-0000-0000-0000-000000000001', 'published'),
    ('62000000-0000-0000-0002-000000000011', '41000000-0000-0000-0000-000000000002', 'Versioning is turned on for a bucket. A user deletes an object without giving a version ID. What happens?', 'single_choice', '["Every version of the object is deleted permanently", "The request fails because versioning is on", "S3 adds a delete marker, and the earlier versions can still be restored", "Versioning is switched off for that object"]', '["S3 adds a delete marker, and the earlier versions can still be restored"]', 'With versioning, a simple delete only adds a delete marker. Removing the marker, or reading an earlier version, brings the object back.', 2, '60000000-0000-0000-0000-000000000001', 'published'),
    ('62000000-0000-0000-0002-000000000012', '41000000-0000-0000-0000-000000000002', 'Nobody knows how often a dataset will be read, and the pattern keeps changing. Which storage class moves objects between access tiers automatically?', 'single_choice', '["S3 Intelligent-Tiering", "S3 Standard-IA", "S3 One Zone-IA", "S3 Glacier Deep Archive"]', '["S3 Intelligent-Tiering"]', 'Intelligent-Tiering watches access and moves objects to cheaper tiers when they are not used, and back when they are, with no retrieval fees.', 2, '60000000-0000-0000-0000-000000000001', 'published'),
    ('62000000-0000-0000-0002-000000000013', '41000000-0000-0000-0000-000000000002', 'Which data is the best fit for S3 One Zone-IA?', 'single_choice', '["The only copy of customer invoices", "Copies of thumbnails that can be recreated from the originals", "Website images read thousands of times a day", "Records that must survive the loss of an Availability Zone"]', '["Copies of thumbnails that can be recreated from the originals"]', 'One Zone-IA keeps data in a single AZ, so it is cheaper but can be lost if that AZ fails. Use it only for infrequently read data you can recreate.', 3, '60000000-0000-0000-0000-000000000001', 'published'),
    ('62000000-0000-0000-0002-000000000014', '41000000-0000-0000-0000-000000000002', 'A company wants control over the keys that encrypt its S3 objects, and an audit record each time a key is used. Which encryption should it choose?', 'single_choice', '["SSE-S3", "Block Public Access", "S3 Object Lock", "SSE-KMS"]', '["SSE-KMS"]', 'SSE-KMS uses keys in AWS KMS, where you control key policies and every use of the key is logged in AWS CloudTrail. SSE-S3 keys are fully managed by S3.', 3, '60000000-0000-0000-0000-000000000001', 'published')
ON CONFLICT (id) DO NOTHING;

DO $$
DECLARE
    item RECORD;
BEGIN
    FOR item IN
        SELECT *
        FROM (
            VALUES
            (
                '61000000-0000-0000-0000-000000000011'::uuid,
                '41000000-0000-0000-0000-000000000001'::uuid,
                ARRAY[
                    '62000000-0000-0000-0000-000000000001',
                    '62000000-0000-0000-0002-000000000001',
                    '62000000-0000-0000-0002-000000000002',
                    '62000000-0000-0000-0002-000000000003',
                    '62000000-0000-0000-0002-000000000004'
                ]::uuid[],
                'Demo VPC Module Check'
            ),
            (
                '61000000-0000-0000-0000-000000000012'::uuid,
                '41000000-0000-0000-0000-000000000002'::uuid,
                ARRAY[
                    '62000000-0000-0000-0000-000000000002',
                    '62000000-0000-0000-0002-000000000011',
                    '62000000-0000-0000-0002-000000000012',
                    '62000000-0000-0000-0002-000000000013',
                    '62000000-0000-0000-0002-000000000014'
                ]::uuid[],
                'Demo S3 Module Check'
            )
        ) AS checks(assessment_id, topic_id, question_ids, title)
    LOOP
        IF (
            SELECT COUNT(*)
            FROM questions AS q
            JOIN topics AS t ON t.id = q.topic_id
            WHERE q.id = ANY (item.question_ids)
              AND q.topic_id = item.topic_id
              AND q.status = 'published'
              AND q.question_type = 'single_choice'
              AND t.course_id =
                  '40000000-0000-0000-0000-000000000001'::uuid
        ) <> 5 THEN
            RAISE EXCEPTION
                'Expected 5 published demo questions for %',
                item.title;
        END IF;

        INSERT INTO assessments (
            id, course_id, title, assessment_type,
            question_count, pass_percentage,
            maximum_attempts, status, published_at
        )
        VALUES (
            item.assessment_id,
            '40000000-0000-0000-0000-000000000001',
            item.title,
            'quiz',
            5,
            80,
            3,
            'published',
            NOW()
        )
        ON CONFLICT (id) DO UPDATE
        SET question_count = EXCLUDED.question_count,
            pass_percentage = EXCLUDED.pass_percentage,
            updated_at = NOW()
        -- Only touch the row when it changes, so the check version stays
        -- the same on repeat runs and learners mid-check are not affected.
        WHERE assessments.question_count <> EXCLUDED.question_count
           OR assessments.pass_percentage <> EXCLUDED.pass_percentage;

        IF NOT EXISTS (
            SELECT 1 FROM assessments
            WHERE id = item.assessment_id
              AND course_id =
                  '40000000-0000-0000-0000-000000000001'::uuid
              AND title = item.title
              AND assessment_type = 'quiz'
              AND question_count = 5
              AND pass_percentage = 80
              AND maximum_attempts = 3
              AND status = 'published'
        ) THEN
            RAISE EXCEPTION
                'Existing assessment differs from demo configuration: %',
                item.title;
        END IF;

        INSERT INTO assessment_questions (
            assessment_id, question_id, sequence_number, marks
        )
        SELECT item.assessment_id, ids.question_id, ids.position, 1
        FROM unnest(item.question_ids) WITH ORDINALITY
            AS ids(question_id, position)
        ON CONFLICT (assessment_id, question_id) DO NOTHING;

        IF (
            SELECT COUNT(*) FROM assessment_questions
            WHERE assessment_id = item.assessment_id
        ) <> 5 OR (
            SELECT COUNT(*)
            FROM assessment_questions AS aq
            JOIN unnest(item.question_ids) WITH ORDINALITY
                AS ids(question_id, position)
              ON ids.question_id = aq.question_id
             AND ids.position = aq.sequence_number
            WHERE aq.assessment_id = item.assessment_id
              AND aq.marks = 1
        ) <> 5 THEN
            RAISE EXCEPTION
                'Unexpected question configuration for %', item.title;
        END IF;

        INSERT INTO module_assessments (
            topic_id, course_id, assessment_id
        )
        VALUES (
            item.topic_id,
            '40000000-0000-0000-0000-000000000001',
            item.assessment_id
        )
        ON CONFLICT (topic_id) DO NOTHING;

        IF NOT EXISTS (
            SELECT 1 FROM module_assessments
            WHERE topic_id = item.topic_id
              AND assessment_id = item.assessment_id
        ) THEN
            RAISE EXCEPTION
                'Module already has a different assessment: %',
                item.title;
        END IF;
    END LOOP;
END
$$;

COMMIT;

SELECT
    t.title AS module,
    a.title AS assessment,
    a.question_count,
    a.pass_percentage,
    a.maximum_attempts
FROM module_assessments AS ma
JOIN topics AS t ON t.id = ma.topic_id
JOIN assessments AS a ON a.id = ma.assessment_id
WHERE ma.course_id = '40000000-0000-0000-0000-000000000001'
ORDER BY t.sequence_number;
