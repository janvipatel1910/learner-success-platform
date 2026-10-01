BEGIN;

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
                '62000000-0000-0000-0000-000000000001'::uuid,
                'Demo VPC Module Check'
            ),
            (
                '61000000-0000-0000-0000-000000000012'::uuid,
                '41000000-0000-0000-0000-000000000002'::uuid,
                '62000000-0000-0000-0000-000000000002'::uuid,
                'Demo S3 Module Check'
            )
        ) AS checks(assessment_id, topic_id, question_id, title)
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM questions AS q
            JOIN topics AS t ON t.id = q.topic_id
            WHERE q.id = item.question_id
              AND q.topic_id = item.topic_id
              AND q.status = 'published'
              AND q.question_type = 'single_choice'
              AND t.course_id =
                  '40000000-0000-0000-0000-000000000001'::uuid
        ) THEN
            RAISE EXCEPTION
                'Expected published demo question missing for %',
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
            1,
            100,
            3,
            'published',
            NOW()
        )
        ON CONFLICT (id) DO NOTHING;

        IF NOT EXISTS (
            SELECT 1 FROM assessments
            WHERE id = item.assessment_id
              AND course_id =
                  '40000000-0000-0000-0000-000000000001'::uuid
              AND title = item.title
              AND assessment_type = 'quiz'
              AND question_count = 1
              AND pass_percentage = 100
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
        VALUES (
            item.assessment_id, item.question_id, 1, 1
        )
        ON CONFLICT (assessment_id, question_id) DO NOTHING;

        IF (
            SELECT COUNT(*) FROM assessment_questions
            WHERE assessment_id = item.assessment_id
        ) <> 1 OR NOT EXISTS (
            SELECT 1 FROM assessment_questions
            WHERE assessment_id = item.assessment_id
              AND question_id = item.question_id
              AND sequence_number = 1
              AND marks = 1
        ) THEN
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
