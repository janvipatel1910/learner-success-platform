-- Demo module assignments: one written design task per module.
-- Original tasks written for SkillPulse; not copied from any exam or course.
-- Idempotent: safe to run more than once. Wording updates are applied.
BEGIN;

INSERT INTO module_assignments (id, course_id, topic_id, title, instructions, status)
VALUES
    (
        '66000000-0000-0000-0000-000000000001',
        '40000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000001',
        'Design a VPC for a web application',
        'A small company wants to run a web application on AWS. It has web '
        'servers, a PostgreSQL database, and the servers must download '
        'security updates from the internet. The site must keep working if one '
        'Availability Zone fails.' || E'\n\n' ||
        'In your own words (at least a short paragraph), describe your design:' || E'\n' ||
        '1. Which subnets you would create, in how many Availability Zones, and which are public or private.' || E'\n' ||
        '2. How users reach the web servers, and how the servers download updates without being reachable from the internet.' || E'\n' ||
        '3. The security group rules for the web servers and the database.' || E'\n' ||
        '4. One thing you would change if the company also needed to reach Amazon S3 privately.' || E'\n\n' ||
        'Optional: add an HTTPS link to a diagram (for example draw.io or a GitHub file).',
        'published'
    ),
    (
        '66000000-0000-0000-0000-000000000002',
        '40000000-0000-0000-0000-000000000001',
        '41000000-0000-0000-0000-000000000002',
        'Plan secure storage for learner documents',
        'A training company stores learner documents in Amazon S3: ID '
        'checks (kept for one year), course certificates (kept for ten years) '
        'and practice uploads (deleted after 90 days). Documents must never be '
        'public, and a file deleted by mistake must be recoverable.' || E'\n\n' ||
        'In your own words (at least a short paragraph), describe your plan:' || E'\n' ||
        '1. How you keep the bucket private and let a learner download their own certificate.' || E'\n' ||
        '2. How you recover a file deleted by mistake.' || E'\n' ||
        '3. Which storage class each type of document uses over time, and the lifecycle rules you would add.' || E'\n' ||
        '4. Which encryption you would choose, and why.' || E'\n\n' ||
        'Optional: add an HTTPS link to a diagram or a GitHub file with your plan.',
        'published'
    )
ON CONFLICT (id) DO UPDATE
SET title = EXCLUDED.title,
    instructions = EXCLUDED.instructions,
    updated_at = NOW()
WHERE module_assignments.title <> EXCLUDED.title
   OR module_assignments.instructions <> EXCLUDED.instructions;

DO $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM module_assignments AS a
        JOIN topics AS t ON t.id = a.topic_id AND t.course_id = a.course_id
        WHERE a.id IN (
            '66000000-0000-0000-0000-000000000001',
            '66000000-0000-0000-0000-000000000002'
        )
          AND a.status = 'published'
    ) <> 2 THEN
        RAISE EXCEPTION 'Expected 2 published demo assignments linked to their modules.';
    END IF;
END
$$;

COMMIT;

SELECT t.title AS module, a.title AS assignment, a.status
FROM module_assignments AS a
JOIN topics AS t ON t.id = a.topic_id
WHERE a.course_id = '40000000-0000-0000-0000-000000000001'
ORDER BY t.sequence_number;
