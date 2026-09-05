# Briefing TODO

webhook 에서 bot 으로 전환 준비

orders sync 흐름 Tech 문서 작성
- order/history(createdTime) vs closed-pnl(updatedTime) 이중 경로
- sync_missing_from_closed_pnl → new_orders → enrich → notify
- attach_position_context는 Order.all() 기준
