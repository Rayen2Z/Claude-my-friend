/*
===============================================================================
  CHURN DERIVATION FROM MONTHLY CLIENT SNAPSHOTS (SAP BI)
===============================================================================
  Logic: A client is "churned" in month M if they were present in M-1 but
         absent in M. This avoids needing a dedicated churn flag column.

  IMPORTANT: Adjust table/column names to match your SAP BI schema.
===============================================================================
*/

-- ============================================================================
-- STEP 1: Build a monthly client presence table
-- ============================================================================
-- This CTE extracts distinct active clients per month from your transaction
-- or account table. Adapt the source table and date column to your schema.

WITH monthly_presence AS (
    SELECT DISTINCT
        client_id,
        -- Truncate transaction/snapshot date to first of month
        DATE_TRUNC('month', transaction_date) AS active_month
    FROM
        your_schema.client_transactions  -- << REPLACE with your SAP BI table
    WHERE
        transaction_date >= '2022-01-01'  -- Go back far enough for tenure calc
        AND transaction_date <= CURRENT_DATE
),

-- ============================================================================
-- STEP 2: Generate a calendar spine (all months in range)
-- ============================================================================
calendar_months AS (
    SELECT DISTINCT DATE_TRUNC('month', transaction_date) AS cal_month
    FROM your_schema.client_transactions
    WHERE transaction_date >= '2022-01-01'
),

-- ============================================================================
-- STEP 3: Identify churn events (present in M-1, absent in M)
-- ============================================================================
churn_events AS (
    SELECT
        prev.client_id,
        prev.active_month                          AS last_active_month,
        cm.cal_month                               AS churn_month,
        -- Count consecutive absent months to distinguish temporary vs permanent
        ROW_NUMBER() OVER (
            PARTITION BY prev.client_id
            ORDER BY cm.cal_month
        ) AS consecutive_absent_months
    FROM
        monthly_presence prev
    INNER JOIN
        calendar_months cm
        ON cm.cal_month = ADD_MONTHS(prev.active_month, 1)
    LEFT JOIN
        monthly_presence curr
        ON curr.client_id = prev.client_id
        AND curr.active_month = cm.cal_month
    WHERE
        curr.client_id IS NULL  -- Client NOT present in next month
),

-- ============================================================================
-- STEP 4: Flag "confirmed" churn (absent for 3+ consecutive months)
-- ============================================================================
-- This avoids false positives from clients who skip a month then return.
confirmed_churn AS (
    SELECT
        client_id,
        MIN(churn_month) AS churn_month,
        last_active_month
    FROM churn_events
    WHERE consecutive_absent_months >= 3  -- Adjust threshold as needed
    GROUP BY client_id, last_active_month
),

-- ============================================================================
-- STEP 5: Detect "silent attrition" (H5 check)
-- ============================================================================
-- Clients who are technically active but NBI dropped to near-zero
silent_attrition AS (
    SELECT
        t.client_id,
        DATE_TRUNC('month', t.transaction_date) AS snapshot_month,
        SUM(t.nbi_amount) AS monthly_nbi
    FROM
        your_schema.client_transactions t
    INNER JOIN
        monthly_presence mp
        ON mp.client_id = t.client_id
        AND mp.active_month = DATE_TRUNC('month', t.transaction_date)
    GROUP BY
        t.client_id,
        DATE_TRUNC('month', t.transaction_date)
    HAVING
        SUM(t.nbi_amount) < 1.0  -- Near-zero NBI threshold (adjust)
)

-- ============================================================================
-- FINAL OUTPUT: Churn lookup table
-- ============================================================================
SELECT
    mp.client_id,
    mp.active_month,
    CASE
        WHEN cc.churn_month IS NOT NULL THEN 1
        ELSE 0
    END AS is_churned,
    cc.churn_month,
    cc.last_active_month,
    CASE
        WHEN sa.client_id IS NOT NULL AND cc.churn_month IS NULL THEN 1
        ELSE 0
    END AS is_silent_attrition
FROM
    monthly_presence mp
LEFT JOIN
    confirmed_churn cc
    ON cc.client_id = mp.client_id
    AND mp.active_month >= cc.last_active_month
LEFT JOIN
    silent_attrition sa
    ON sa.client_id = mp.client_id
    AND sa.snapshot_month = mp.active_month
ORDER BY
    mp.client_id, mp.active_month;
