BEGIN;

DO $$
DECLARE
    target_course UUID := '40000000-0000-0000-0000-000000000001';
    target_topic UUID := '41000000-0000-0000-0000-000000000002';
    project_id UUID := '65000000-0000-0000-0000-000000000011';
    project_title TEXT := 'Demo Capstone: Secure Application and Document Storage';
    project_brief TEXT := $brief$
Design a secure application architecture using the VPC and S3 concepts
covered in this demo course.

Scenario:
A small training company needs an application with a private database
and private storage for learner documents.

Submit:
1. An architecture diagram showing public and private subnets,
   routing, application access and private document storage.
2. A README explaining network boundaries, access permissions,
   encryption choices and how documents remain private.
3. A recovery walkthrough explaining how an overwritten document
   could be recovered using object versioning.
4. A validation checklist describing how you would test permitted
   access, denied access and document recovery.
5. A short explanation of your design limitations and cost assumptions.

Submission format:
Provide an HTTPS link to a GitHub repository or a shared document
that your assigned tutor can access. Include a short submission note.

This is a design-only demo capstone. AWS deployment is not required.
Use fictional data. Do not include credentials or real learner documents.

Review criteria:
- Clear architecture and network boundaries.
- Private storage and appropriate access controls.
- A coherent recovery procedure.
- Useful validation steps and clear documentation.

A tutor must review the evidence before approving the project.
Submitting a link does not automatically pass the project or issue
a certificate.
$brief$;
    requirements JSONB := '{
        "submission_type": "design_portfolio",
        "deployment_required": false,
        "required_artifacts": [
            "architecture_diagram",
            "design_readme",
            "recovery_walkthrough",
            "validation_checklist",
            "limitations_and_cost_assumptions"
        ]
    }'::jsonb;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM topics
        WHERE id = target_topic AND course_id = target_course
    ) THEN
        RAISE EXCEPTION 'Expected demo course/topic was not found.';
    END IF;

    INSERT INTO lab_tasks (
        id, course_id, topic_id, title, instructions,
        evidence_requirements, maximum_score, status
    )
    VALUES (
        project_id, target_course, target_topic, project_title,
        project_brief, requirements, 100, 'published'
    )
    ON CONFLICT (id) DO NOTHING;

    IF NOT EXISTS (
        SELECT 1 FROM lab_tasks
        WHERE id = project_id
          AND course_id = target_course
          AND topic_id = target_topic
          AND title = project_title
          AND instructions = project_brief
          AND evidence_requirements = requirements
          AND maximum_score = 100
          AND status = 'published'
    ) THEN
        RAISE EXCEPTION
            'Existing project differs from this demo definition; review it manually.';
    END IF;

    INSERT INTO course_final_projects (course_id, lab_task_id)
    VALUES (target_course, project_id)
    ON CONFLICT (course_id) DO NOTHING;

    IF NOT EXISTS (
        SELECT 1 FROM course_final_projects
        WHERE course_id = target_course AND lab_task_id = project_id
    ) THEN
        RAISE EXCEPTION 'This course already has a different final project.';
    END IF;
END
$$;

COMMIT;

SELECT
    l.title,
    l.status,
    l.maximum_score
FROM course_final_projects AS p
JOIN lab_tasks AS l ON l.id = p.lab_task_id
WHERE p.course_id = '40000000-0000-0000-0000-000000000001';
