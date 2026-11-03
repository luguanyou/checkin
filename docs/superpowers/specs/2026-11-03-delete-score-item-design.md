# 删除平时分项目

用户已确认实现：删除项目前确认同时永久删除学生积分及备注，并重新计算汇总。
沿用现有成绩写事务、教师所有权检查、归档只读、expected_version 乐观锁。
DELETE /api/v1/classes/{class_group_id}/scores/items/{item_id} 接收 expected_version，返回最新 ScoreBook。
事务中移除关联积分与班委项目授权，记录项目及积分删除前快照，保留历史审计。
前端仅成功后清理草稿和更新选中项目；失败保留草稿。取消确认不发请求。
