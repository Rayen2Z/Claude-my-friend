/*
===============================================================================
  CHURN DERIVATION FROM MONTHLY CLIENT SNAPSHOTS (SAP BI)
===============================================================================
  Logic: A client is "churned" in month M if they were present in M-1 but
         absent in M. This avoids needing a dedicated churn flag column.

  CRITICAL: Clients who "upstream" (moved to VIP database) must NOT be
  labeled as churned. They are a positive outcome (client got richer).
  We use the VIP client list to exclude them from churn events.

  IMPORTANT: Adjust table/column names to match your SAP BI schema.
===============================================================================
*/

-- ============================================================================
-- STEP 0: Identify upstreamed clients (moved to VIP portfolio)
-- ============================================================================
-- Option A: If VIP team provides a list/table of clients they received
-- Option B: If there's a status flag in the client master table
-- Adjust the source to match what's available in your SAP BI environment.

WITH upstreamed_clients AS (
    -- OPTION A: Direct VIP client table (preferred — ask the VIP team)
    SELECT
        client_id,
        migration_date AS upstream_date  -- When they moved to VIP
    FROM
        your_schema.vip_client_migrations  -- << REPLACE with actual VIP table

    -- OPTION B: If no VIP table exists, use client master status field
    -- SELECT
    --     client_id,
    --     status_change_date AS upstream_date
    -- FROM your_schema.client_master
    -- WHERE client_segment = 'VIP'
    --   AND previous_segment IN ('Mainstream', 'Standard')

    -- OPTION C: If nothing exists, use NBI threshold as proxy
    -- (clients whose last-year NBI exceeded VIP eligibility threshold)
    -- SELECT client_id, MAX(transaction_date) AS upstream_date
    -- FROM your_schema.client_transactions
    -- GROUP BY client_id
    -- HAVING SUM(nbi_amount) > 50000  -- << VIP eligibility threshold
),

-- ============================================================================
-- STEP 1: Build a monthly client presence table
-- ============================================================================
-- This CTE extracts distinct active clients per month from your transaction
-- or account table. Adapt the source table and date column to your schema.

monthly_presence AS (
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
--         EXCLUDING upstreamed clients (they are NOT churned)
-- ============================================================================
-- This avoids false positives from clients who skip a month then return,
-- and critically, excludes clients who moved to the VIP portfolio.
confirmed_churn AS (
    SELECT
        ce.client_id,
        MIN(ce.churn_month) AS churn_month,
        ce.last_active_month
    FROM churn_events ce
    LEFT JOIN upstreamed_clients uc ON uc.client_id = ce.client_id
    WHERE ce.consecutive_absent_months >= 3  -- Adjust threshold as needed
      AND uc.client_id IS NULL               -- EXCLUDE upstreamed clients
    GROUP BY ce.client_id, ce.last_active_month
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
-- FINAL OUTPUT: Churn lookup table with upstream flag
-- ============================================================================
SELECT
    mp.client_id,
    mp.active_month,

    -- Client outcome classification (3-class)
    CASE
        WHEN uc.client_id IS NOT NULL THEN 'upstreamed'
        WHEN cc.churn_month IS NOT NULL THEN 'churned'
        WHEN sa.client_id IS NOT NULL AND cc.churn_month IS NULL THEN 'silent_attrition'
        ELSE 'active'
    END AS client_status,

    -- Binary churn flag (upstreamed = NOT churned)
    CASE
        WHEN cc.churn_month IS NOT NULL THEN 1
        ELSE 0
    END AS is_churned,

    -- Upstream flag (for analysis and exclusion)
    CASE
        WHEN uc.client_id IS NOT NULL THEN 1
        ELSE 0
    END AS is_upstreamed,

    cc.churn_month,
    cc.last_active_month,
    uc.upstream_date,

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
    upstreamed_clients uc
    ON uc.client_id = mp.client_id
LEFT JOIN
    silent_attrition sa
    ON sa.client_id = mp.client_id
    AND sa.snapshot_month = mp.active_month
ORDER BY
    mp.client_id, mp.active_month;
