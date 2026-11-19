with expected(week_start, segment, checkout_sessions, converted_sessions, conversion_rate) as (
    values (date '2026-11-02', 'mobile', 2, 1, 0.5),
           (date '2026-11-09', 'mobile', 2, 0, 0.0),
           (date '2026-11-09', 'desktop', 1, 1, 1.0)
),
actual as (select * from {{ ref('checkout_conversion') }}),
unexpected as (select * from actual except select * from expected),
missing as (select * from expected except select * from actual)
select * from unexpected
union all
select * from missing
