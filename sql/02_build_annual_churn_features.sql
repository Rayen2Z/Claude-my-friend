/*
===============================================================================
  BUILD ANNUAL CHURN FEATURES ALIGNED WITH CLV STRUCTURE
===============================================================================
  The CLV model has ONE ROW PER CLIENT PER YEAR with quarterly snapshot columns.
  This query builds the same structure for the retention sub-model.

  Output: One row per client per year with:
    - Quarterly activity indicators
    - Quarterly NBI aggregates
    - Churn flag (did the client churn within the NEXT year?)
    - Tenure at snapshot
    - Product counts per quarter
===============================================================================
*/

WITH client_quarterly_stats AS (
    SELECT
        client_id,
        YEAR(transaction_date) AS snapshot_year,
        -- Quarterly transaction counts
        SUM(CASE WHEN QUARTER(transaction_date) = 1 THEN 1 ELSE 0 END) AS n_transactions_q1,
        SUM(CASE WHEN QUARTER(transaction_date) = 2 THEN 1 ELSE 0 END) AS n_transactions_q2,
        SUM(CASE WHEN QUARTER(transaction_date) = 3 THEN 1 ELSE 0 END) AS n_transactions_q3,
        SUM(CASE WHEN QUARTER(transaction_date) = 4 THEN 1 ELSE 0 END) AS n_transactions_q4,

        -- Quarterly NBI
        SUM(CASE WHEN QUARTER(transaction_date) = 1 THEN nbi_amount ELSE 0 END) AS nbi_q1,
        SUM(CASE WHEN QUARTER(transaction_date) = 2 THEN nbi_amount ELSE 0 END) AS nbi_q2,
        SUM(CASE WHEN QUARTER(transaction_date) = 3 THEN nbi_amount ELSE 0 END) AS nbi_q3,
        SUM(CASE WHEN QUARTER(transaction_date) = 4 THEN nbi_amount ELSE 0 END) AS nbi_q4,

        -- Total annual NBI
        SUM(nbi_amount) AS nbi_annual,

        -- Quarterly product counts (distinct products used)
        COUNT(DISTINCT CASE WHEN QUARTER(transaction_date) = 1 THEN product_id END) AS n_products_q1,
        COUNT(DISTINCT CASE WHEN QUARTER(transaction_date) = 2 THEN product_id END) AS n_products_q2,
        COUNT(DISTINCT CASE WHEN QUARTER(transaction_date) = 3 THEN product_id END) AS n_products_q3,
        COUNT(DISTINCT CASE WHEN QUARTER(transaction_date) = 4 THEN product_id END) AS n_products_q4,

        -- Activity flags per quarter (was client active at all?)
        MAX(CASE WHEN QUARTER(transaction_date) = 1 THEN 1 ELSE 0 END) AS active_q1,
        MAX(CASE WHEN QUARTER(transaction_date) = 2 THEN 1 ELSE 0 END) AS active_q2,
        MAX(CASE WHEN QUARTER(transaction_date) = 3 THEN 1 ELSE 0 END) AS active_q3,
        MAX(CASE WHEN QUARTER(transaction_date) = 4 THEN 1 ELSE 0 END) AS active_q4,

        -- Quarters active (for activity trend)
        MAX(CASE WHEN QUARTER(transaction_date) = 1 THEN 1 ELSE 0 END)
        + MAX(CASE WHEN QUARTER(transaction_date) = 2 THEN 1 ELSE 0 END)
        + MAX(CASE WHEN QUARTER(transaction_date) = 3 THEN 1 ELSE 0 END)
        + MAX(CASE WHEN QUARTER(transaction_date) = 4 THEN 1 ELSE 0 END) AS quarters_active

    FROM
        your_schema.client_transactions
    WHERE
        YEAR(transaction_date) BETWEEN 2023 AND 2025
    GROUP BY
        client_id, YEAR(transaction_date)
),

-- Join with client demographics
client_info AS (
    SELECT
        client_id,
        date_of_birth,
        account_opening_date,
        segment,
        region
    FROM
        your_schema.client_master  -- << REPLACE with your client dim table
),

-- Derive churn target: did the client churn in the NEXT year?
-- Using the churn lookup from query 01
churn_target AS (
    SELECT
        client_id,
        YEAR(churn_month) AS churn_year
    FROM
        confirmed_churn  -- From query 01, or materialize as a table
)

SELECT
    cqs.client_id,
    cqs.snapshot_year,

    -- Demographics
    DATEDIFF(YEAR, ci.date_of_birth, CONCAT(cqs.snapshot_year, '-12-31')) AS age,
    DATEDIFF(MONTH, ci.account_opening_date, CONCAT(cqs.snapshot_year, '-12-31')) AS tenure_months,
    ci.segment,
    ci.region,

    -- Quarterly features (aligned with CLV structure)
    cqs.n_transactions_q1, cqs.n_transactions_q2,
    cqs.n_transactions_q3, cqs.n_transactions_q4,
    cqs.nbi_q1, cqs.nbi_q2, cqs.nbi_q3, cqs.nbi_q4,
    cqs.nbi_annual,
    cqs.n_products_q1, cqs.n_products_q2,
    cqs.n_products_q3, cqs.n_products_q4,
    cqs.active_q1, cqs.active_q2, cqs.active_q3, cqs.active_q4,
    cqs.quarters_active,

    -- Derived trend features
    (cqs.nbi_q4 - cqs.nbi_q1) AS nbi_trend_q4_vs_q1,
    CASE WHEN cqs.nbi_q1 > 0
         THEN (cqs.nbi_q4 - cqs.nbi_q1) / cqs.nbi_q1
         ELSE NULL
    END AS nbi_growth_rate,

    -- Activity decay: did activity decline across quarters?
    CASE
        WHEN cqs.active_q1 = 1 AND cqs.active_q2 = 1
             AND cqs.active_q3 = 1 AND cqs.active_q4 = 1 THEN 'stable'
        WHEN cqs.active_q1 = 1 AND cqs.active_q4 = 0 THEN 'declining'
        WHEN cqs.active_q1 = 0 AND cqs.active_q4 = 1 THEN 'increasing'
        ELSE 'irregular'
    END AS activity_pattern,

    -- TARGET: Did the client churn in the NEXT year?
    CASE
        WHEN ct.churn_year = cqs.snapshot_year + 1 THEN 1
        ELSE 0
    END AS churned_next_year

FROM
    client_quarterly_stats cqs
LEFT JOIN
    client_info ci ON ci.client_id = cqs.client_id
LEFT JOIN
    churn_target ct ON ct.client_id = cqs.client_id
ORDER BY
    cqs.client_id, cqs.snapshot_year;
