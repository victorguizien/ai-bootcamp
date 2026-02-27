-- Example 1
WITH activity_avg_duration AS (
    SELECT
        s.activity_type,
        AVG(s.duration_minutes)::numeric(10,2) AS avg_session_duration_minutes
    FROM public.sessions AS s
    GROUP BY s.activity_type
)

SELECT
    activity_type,
    avg_session_duration_minutes
FROM activity_avg_duration
ORDER BY avg_session_duration_minutes DESC
LIMIT 1;

-- Example 2
WITH churned_subscriptions AS (
    SELECT
        DATE_TRUNC('month', s.end_date)::date AS churn_month,
        COUNT(*) AS churned_count
    FROM public.subscriptions AS s
    WHERE s.status IN ('canceled', 'expired')
        AND s.end_date IS NOT NULL
        AND s.end_date >= DATE_TRUNC('year', CURRENT_DATE)
        AND s.end_date < DATE_TRUNC('year', CURRENT_DATE) + INTERVAL '1 year'
    GROUP BY 1
)

SELECT
    churn_month,
    churned_count
FROM churned_subscriptions
ORDER BY churn_month;

-- Example 3
WITH latest_sub AS (
    SELECT DISTINCT ON (s.user_id)
        s.user_id,
        s."plan",
        s.start_date,
        s.end_date
    FROM public.subscriptions AS s
    WHERE s."plan" IN ('monthly', 'annual')
    ORDER BY s.user_id, s.start_date DESC
),
session_with_plan AS (
    SELECT
        se.session_id,
        CASE
            WHEN ls."plan" IS NOT NULL
                AND ls.start_date <= se.session_date::timestamp
                AND (ls.end_date IS NULL OR ls.end_date >= se.session_date::timestamp)
            THEN 'paying'
            ELSE 'free'
        END AS user_bucket,
        se.duration_minutes
    FROM public.sessions AS se
    LEFT JOIN latest_sub AS ls ON ls.user_id = se.user_id
)

SELECT
    user_bucket,
    AVG(duration_minutes)::numeric(10,2) AS avg_session_duration_minutes,
    COUNT(*) AS sessions
FROM session_with_plan
GROUP BY 1
ORDER BY user_bucket;



WITH latest_subscription AS (
    SELECT DISTINCT ON (s.user_id)
        s.user_id,
        s."plan",
        s.start_date
    FROM public.subscriptions s
    ORDER BY
        s.user_id,
        s.start_date DESC
),

user_plan_segment AS (
    SELECT
        u.user_id,
        COALESCE(ls."plan", 'free') AS "plan",
        CASE
            WHEN COALESCE(ls."plan", 'free') IN ('monthly', 'annual') THEN 'paying'
            ELSE 'free'
        END AS plan_segment
    FROM public.users u
    LEFT JOIN latest_subscription ls
        ON u.user_id = ls.user_id
),

session_metrics AS (
    SELECT
        ups.plan_segment,
        COUNT(*) AS total_sessions,
        COUNT(DISTINCT s.user_id) AS unique_users,
        AVG(s.duration_minutes)::numeric(10,2) AS avg_session_duration_minutes
    FROM public.sessions s
    INNER JOIN user_plan_segment ups
        ON s.user_id = ups.user_id
    GROUP BY
        ups.plan_segment
)

SELECT
    plan_segment,
    total_sessions,
    unique_users,
    avg_session_duration_minutes
FROM session_metrics
ORDER BY plan_segment;


-- Example 4
WITH user_month_sessions AS (
    SELECT
        s.user_id,
        DATE_TRUNC('month', s.session_date)::date AS month,
        COUNT(*) AS sessions_in_month
    FROM public.sessions s
    GROUP BY
        s.user_id,
        DATE_TRUNC('month', s.session_date)::date
),

user_month_with_prev AS (
    SELECT
        ums.user_id,
        ums.month,
        ums.sessions_in_month,
        LAG(ums.sessions_in_month) OVER (
            PARTITION BY ums.user_id
            ORDER BY ums.month
        ) AS prev_sessions_in_month
    FROM user_month_sessions ums
),

drops AS (
    SELECT
        user_id,
        month,
        prev_sessions_in_month,
        sessions_in_month,
        ROUND(
            (sessions_in_month::numeric / NULLIF(prev_sessions_in_month, 0))::numeric
        , 4) AS mom_ratio,
        ROUND(
            (1 - (sessions_in_month::numeric / NULLIF(prev_sessions_in_month, 0)))::numeric
        , 4) AS mom_drop_pct
    FROM user_month_with_prev
    WHERE prev_sessions_in_month IS NOT NULL
)

SELECT
    user_id,
    month,
    prev_sessions_in_month AS prev_month_sessions,
    sessions_in_month      AS current_month_sessions,
    mom_ratio,
    mom_drop_pct
FROM drops
WHERE prev_sessions_in_month > 0
  AND sessions_in_month < prev_sessions_in_month * 0.5
ORDER BY
    mom_drop_pct DESC,
    month DESC,
    user_id;