# 实施步骤

1. 在 scores API、ScoresPage 及 API 合约测试补充删除、取消、失败和只读用例，并验证失败。
2. schemas/scores.py 定义删除请求；scores/router.py 和 service.py 复用写事务并清理积分和授权、记录审计。
3. resources.ts 新增 deleteItem；ScoreEditor.tsx 增加删除入口、确认与结果处理；历史中显示删除动作。
4. 运行成绩 API 测试、前端单元测试、构建及后端静态检查，检查 diff。
