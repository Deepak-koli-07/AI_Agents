
======================================================
SECTION 0 — EVENT_TABLE SCHEMA
======================================================


### 0.1 event_table Schema (DuckDB)

The only table queried is event_table with these columns:

- event_date (STRING, format 'YYYY-MM-DD')  
- event_timestamp (TIMESTAMP)  
- session_id (STRING)  
- event_name (STRING)  
- event_value (FLOAT / DOUBLE)  
- engagement_time_ms (BIGINT)  
- scroll_depth_percent (FLOAT)  
- user_id (STRING)  
- user_type (STRING)  
- is_logged_in (BOOLEAN)  
- traffic_source (STRING)  
- traffic_medium (STRING)  
- traffic_campaign (STRING)  
- page_url (STRING)  
- page_path (STRING)  
- content_category (STRING)  
- content_id (STRING)  
- device_category (STRING)  
- os (STRING)  
- country (STRING)  
- city (STRING)  

No other columns exist.

### 0.2 Date Handling Rules

- event_date is stored as STRING → ALWAYS cast to DATE for comparisons:

  CAST(event_date AS DATE)

- “Last N days” pattern:

  CAST(event_date AS DATE)
  BETWEEN CURRENT_DATE - INTERVAL 'N' DAY AND CURRENT_DATE

- Avoid raw string date comparisons like:
  - event_date >= '2025-01-01'
  - event_date >= CURRENT_DATE   -- invalid (string vs date)

### 0.3 Percentage / Share Rules

- Percentage = part / whole
- Bases:
  - Users      → COUNT(DISTINCT user_id)
  - Sessions   → COUNT(DISTINCT session_id)
  - Events     → COUNT(*)

- Example: device share by users:

  COUNT(DISTINCT user_id) * 1.0
  / SUM(COUNT(DISTINCT user_id)) OVER () AS user_share

- Do not mix events, users, and sessions in the same percentage measure.

### 0.4 Safety / Guardrails (SQL)

- Only SELECT queries are allowed.
- No DML/DDL: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, MERGE, CREATE, REPLACE.
- Only query event_table.
- Always group by all non-aggregated columns.

Notes:
- No columns exist for age, income, salary, gender.
- Do NOT assume demographics.

## 0.5 `event_table` Schema (Single Source of Truth)

All analytics MUST use only this table: `event_table`.

It has **exactly** these columns.  
Do **NOT** invent new columns (e.g., `id`, `event_properties`, `params`, `sessions`, `users`) and do **NOT** use JSON operators (`->`, `->>`).

### 0.5.1 Time & Session

- `event_date` (VARCHAR, format `'YYYY-MM-DD'`)
  - Use for date filters.
  - Always cast for date math, e.g.:
    - `CAST(event_date AS DATE) BETWEEN CURRENT_DATE - INTERVAL '30' DAY AND CURRENT_DATE`

- `event_timestamp` (VARCHAR, format `'YYYY-MM-DD hh:mm:ss.SSSSSS'`)
  - Use when exact event time is needed.
  - Cast to TIMESTAMP if necessary:
    - `CAST(event_timestamp AS TIMESTAMP)`

- `session_id` (VARCHAR)
  - Session identifier: one user can have many sessions.

### 0.5.2 Event Details

- `event_name` (VARCHAR)  
  Allowed values (only these):
  - `'page_view'`
  - `'scroll'`
  - `'click_cta'`
  - `'subscription_start'`
  - `'video_play'`
  - `'search'`

  Typical funnel sequence:
  - `page_view → scroll → click_cta → subscription_start`

- `event_value` (DOUBLE)
  - Numeric value associated with the event.
  - In this dataset, e.g., `499.0` for monetized events like `subscription_start`.
  - Use `SUM(event_value)` or `AVG(event_value)` where relevant.

- `engagement_time_ms` (BIGINT)
  - Time spent on the page in milliseconds.

- `scroll_depth_percent` (DOUBLE, can be NULL)
  - Scroll depth in %, e.g. 20, 50, 80, 100.
  - Mostly relevant for `scroll` / `page_view`-type analysis.

### 0.5.3 User & Traffic

- `user_id` (VARCHAR)
  - Primary user identifier.
  - Use `COUNT(DISTINCT user_id)` for unique users.

- `user_type` (VARCHAR)
  - Values: `'new'`, `'returning'`, `'subscriber'`.

- `is_logged_in` (BOOLEAN)
  - `TRUE` or `FALSE`.

- `traffic_source` (VARCHAR)
  - Values: `'direct'`, `'google'`, `'facebook'`, `'instagram'`, `'referral'`.

- `traffic_medium` (VARCHAR)
  - Values: `'(not_set)'`, `'organic'`, `'social'`, `'referral'`.

- `traffic_campaign` (VARCHAR, can be NULL)
  - Examples: `'diwali_sale_2025'`, `'ipl_2025_push'`, `'summer_reading_drive'`, or NULL.

### 0.5.4 Content & Page

- `page_url` (VARCHAR)
  - Full URL: e.g. `https://news.com/finance/trouble`.

- `page_path` (VARCHAR)
  - Path only: e.g. `/finance/trouble`.

- `content_category` (VARCHAR)
  - Values: `'Entertainment'`, `'Finance'`, `'Education'`, `'Sports'`, `'Politics'`, `'Lifestyle'`, `'Business'`, `'Tech'`.

- `content_id` (VARCHAR)
  - Article ID like `'ART_47439'`.

### 0.5.5 Device & Geo

- `device_category` (VARCHAR)
  - Values: `'mobile'`, `'desktop'`, `'tablet'`.

- `os` (VARCHAR)
  - Values: `'iOS'`, `'Android'`, `'Windows'`, `'MacOS'`, `'Linux'`, `'iPadOS'`.

- `country` (VARCHAR)
  - Values: `'India'`, `'UK'`, `'UAE'`, `'Canada'`, `'USA'`.

- `city` (VARCHAR)
  - Many city names (e.g. `Lucknow`, `Ahmedabad`, `Bangalore`, …).

---

### 0.5.6 Schema Guardrails (Anti-Hallucination)

When writing SQL:

- ✅ Use only these columns from `event_table`.
- ❌ Never use columns like: `id`, `event_properties`, `params`, `events`, `sessions`, `users`, `event_time`, etc.
- ❌ Never use JSON syntax or operators: `->`, `->>`, `event_properties->>'page_url'`.
- ✅ For counts:
  - Total events: `COUNT(*)`
  - Unique users: `COUNT(DISTINCT user_id)`
  - Unique sessions: `COUNT(DISTINCT session_id)`


======================================================
SECTION 1 — FUNNEL ANALYSIS (ORDERED INTENT STEPS)
======================================================

## Purpose
Measure progression across a defined sequence of actions.

## Logic
1. Steps are ordered: step1 → step2 → step3 → ...
2. User qualifies for step N only if steps < N are completed.
3. Compute:
   - Users at each step
   - Step-to-step conversion = stepN / step(N-1)
   - Drop-off = difference between steps

## Notes
Funnels require:
- User-level aggregation
- Boolean flags per step
- Logical dependency across steps


======================================================
SECTION 2 — RETENTION / COHORT ANALYSIS
======================================================

## Purpose
Measure whether users come back after their first activity.

## Logic
1. Cohort = users grouped by first_event_date.
2. For each cohort, track activity on day 1, 7, 30, etc.
3. Metrics:
   - Retention rate = returning_users / cohort_size
   - Re-engagement patterns
   - Stickiness (DAU/MAU)

## Notes
Retention is best segmented by:
- device_category
- traffic_source
- user_type


======================================================
SECTION 3 — AGGREGATE USER JOURNEY (EVENT TRANSITIONS)
======================================================

## Purpose
Understand how users move between events (flow analysis).

## Logic
1. Sort events by timestamp.
2. Extract adjacent transitions: event_i → event_j.
3. Count transitions and compute:
   - transition_count
   - transition_percentage = count / total_from_event_i

## Notes
Use adjacent events ONLY, not all later events.


======================================================
SECTION 4 — SANKET FLOW ANALYSIS (FOR VISUAL JOURNEYS)
======================================================

## Purpose
Generate Sankey-ready edges showing flow volumes.

## Logic
1. Same as aggregate transitions.
2. Output columns:
   - source
   - target
   - value (transition_count)

## Notes
Used for UI/UX flow diagrams.


======================================================
SECTION 5 — SESSION ANALYSIS
======================================================

## Purpose
Evaluate depth and quality of each session.

## Logic
1. Group by session_id.
2. Compute:
   - session_duration
   - events_per_session
   - unique_pages
   - bounce_sessions (events = 1)

## Notes
Bounce rate = bounce_sessions / total_sessions.


======================================================
SECTION 6 — ACTIVE USERS (DAU, WAU, MAU)
======================================================

## Logic
- DAU = distinct user_id per day
- WAU = distinct user_id in last 7 days
- MAU = distinct user_id in last 30 days

## Notes
DAU/MAU ratio measures long-term engagement.


======================================================
SECTION 7 — CONTENT PERFORMANCE
======================================================

## Purpose
Evaluate content quality, engagement, and consumption.

## Key Metrics
- Unique viewers
- Total views
- Avg engagement_time_ms
- Avg scroll_depth_percent
- CTA engagement (click_cta / page_view)
- Dwell time
- Recirculation rate (next content visited)

## Notes
Segment by content_category.


======================================================
SECTION 8 — TRAFFIC SOURCE ANALYSIS
======================================================

## Purpose
Understand acquisition and conversion by channel.

## Metrics
- unique_users
- sessions
- avg_engagement
- conversion_rate
- bounce_rate

## Notes
Important distinction between:
- traffic_source
- traffic_medium
- traffic_campaign


======================================================
SECTION 9 — DEVICE & OS ANALYSIS
======================================================

## Purpose
Compare behavior across device types and operating systems.

## Key Metrics
- user_share
- session_share
- engagement differences
- conversion differences

## Notes
Mobile vs Desktop often reveals UX issues.


======================================================
SECTION 10 — GEO ANALYSIS
======================================================

## Purpose
Understand regional performance.

## Metrics
- unique_users
- conversion
- engagement
- content preferences

## Notes
Geo segmentation improves personalization.


======================================================
SECTION 11 — LOGIN & USER TYPE ANALYSIS
======================================================

## Purpose
Compare anonymous vs logged-in vs subscriber behaviors.

## Metrics
- retention
- engagement depth
- conversion
- LTV signals


======================================================
SECTION 12 — PERCENTAGE-OF-TOTAL METRICS
======================================================

## Principles
1. Percentage = part / whole
2. Whole must be clearly defined: users? sessions? events?
3. Segment totals must sum to ~100%

## Common Mistakes
- Wrong denominator
- Mixing events with users
- Aggregating before grouping


======================================================
SECTION 13 — DISTRIBUTION ANALYSIS (ENGAGEMENT, SCROLL, VALUE)
======================================================

## Purpose
Understand shape/spread of continuous metrics.

## Logic
Compute:
- mean
- median
- percentile buckets (25th, 50th, 75th)
- histogram buckets (0–25%, 25–50%, etc.)

## Use Cases
- Scroll depth segmentation
- Engagement time distribution
- Revenue bucket analysis


======================================================
SECTION 14 — OUTLIER DETECTION
======================================================

## Purpose
Identify anomalous sessions, users, or content.

## Logic
Use:
- values > (mean + 3σ)
- top 1% or 0.1% thresholds
- extremely high engagement_time_ms
- suspiciously fast repeated events

## Notes
Useful for bot detection and data quality.


======================================================
SECTION 15 — BOT / INVALID TRAFFIC DETECTION
======================================================

## Signals
- extremely high event frequency
- identical timestamps
- impossible scroll patterns
- repeated session_ids
- events without page_views
- user_agents (if available)

## Logic
Flag users with unrealistic behavior.


======================================================
SECTION 16 — TIME-SERIES ANALYSIS
======================================================

## Purpose
Analyze metrics over time (daily, weekly, monthly).

## Logic
- Group by event_date
- Compute moving averages
- Detect spikes or drops

## Notes
Used for anomaly detection & forecasting foundations.


======================================================
SECTION 17 — SEARCH ANALYTICS
======================================================

## Purpose
Understand search behavior & performance.

## Metrics
- top queries
- searches per user
- CTR after search
- zero-results rate
- search-to-conversion rate


======================================================
SECTION 18 — ERROR ANALYTICS
======================================================

## Purpose
Identify where users encounter errors or dead ends.

## Logic
1. Filter event_name = 'error' or similar.
2. Group errors by page, device, OS.
3. Compute:
   - error_count
   - error_rate
   - sessions impacted


======================================================
SECTION 19 — CONVERSION RATE ANALYSIS
======================================================

## Purpose
Measure how users move from intent → action → conversion.

## Variants
- Micro conversions (click, scroll)
- Macro conversions (subscription_start)

## Metrics
- overall conversion rate
- conversion by segment
- conversion by journey path


======================================================
SECTION 20 — COHORT COMPARISON
======================================================

## Purpose
Compare different user groups.

## Examples
- new vs returning
- mobile vs desktop
- campaign A vs campaign B

## Metrics
- engagement
- conversion
- retention


======================================================
SECTION 21 — USER SCORING & ENGAGEMENT LEVELS
======================================================

## Purpose
Categorize users into engagement tiers.

## Sample Tiers
- Highly engaged
- Moderately engaged
- Low engaged
- Dormant

## Signals
- session frequency
- engagement_time_ms
- scroll depth
- content diversity


======================================================
SECTION 22 — LIFETIME VALUE (LTV) FOUNDATIONS
======================================================

## Purpose
Basic LTV signals from behavioral data.

## Signals
- subscription_start events
- engagement frequency
- retention curve
- content affinity


======================================================
SECTION 23 — A/B TEST ANALYSIS (BASIC)
======================================================

## Purpose
Compare performance of two variants.

## Metrics
- lift
- conversion difference
- significance (not computed in SQL)

## Logic
Group by experiment_variant.


======================================================
SECTION 24 — DATE FILTERING (STRING event_date)
======================================================

## Must cast to DATE:
CAST(event_date AS DATE)

## Valid patterns:
CAST(event_date AS DATE) >= CURRENT_DATE - INTERVAL 7 DAY
CAST(event_date AS DATE) BETWEEN DATE '2025-01-01' AND DATE '2025-01-31'

## Never compare string to DATE directly.


======================================================
END OF ANALYTICS PLAYBOOK
======================================================
