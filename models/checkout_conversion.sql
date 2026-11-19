with sessions as (
    select week_start, segment, session_id,
           max(case when event_type = 'checkout_started' then 1 else 0 end) as started,
           max(case when event_type = 'purchase' then 1 else 0 end) as purchased
    from {{ ref('product_events') }}
    group by week_start, segment, session_id
)
select week_start, segment, sum(started) as checkout_sessions,
       sum(started * purchased) as converted_sessions,
       sum(started * purchased)::double / nullif(sum(started), 0) as conversion_rate
from sessions
group by week_start, segment
