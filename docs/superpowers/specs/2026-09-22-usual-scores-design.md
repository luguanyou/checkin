# 平时成绩：基础分与表现积分

本设计根据本次对话及已审阅的 V4 交互图整理。用户已要求继续实现。

## 范围与规则

- 教师端新增“平时成绩”，按班级独立设置项目、基础分和系数；同一课程的不同班级可不同。
- 固定分类：作业 HOMEWORK、课堂表现 CLASSROOM、上机实验表现 LAB、其他 OTHER。每类可有多个具名项目，保留日期及说明。
- 每名学生每个项目保留一个当前积分及备注。支持 1、2、3、4、5 快捷录入、自定义小数和正负积分；重复录入是修改，不累计重复记录。另建项目可记录另一件课堂表现事件。
- 空值表示尚未评价，零表示已评价但没有积分。汇总计算将空值按 0 分计入，同时保留待评价计数和状态提示。服务端用 Decimal 保存、计算；最多四位小数，数据库可表达范围内不设业务积分上限。
- 基础分默认显示 70，可改为其他数值或留空；四类系数最初均留空，可分别设置非负系数，0 表示该类不参与总分。系数不要求合计为 100。
- 类别贡献 = 净积分之和 × 系数，不封顶、不保底。原始总分 = 基础分 + 四类贡献。最终成绩限制到 0～100，保留原始总分；展示及导出保留两位小数，内部精确累计后舍入。
- 基础分或任一系数未配置时仍允许录入，显示“规则待配置”，不生成正式总分。参与计算的项目尚未评价时显示“待评完整”，按 0 分生成当前汇总成绩并保留待评价提示。没有项目的类别净积分为 0；系数为 0 的类别不阻止汇总。
- 已移除学生的既有积分只读，恢复名单后允许录入。已移除后新建项目不影响其历史汇总；归档课程、班级整体只读，允许查看、导出。
- 考勤始终独立，不参与平时成绩；不录期末成绩，不乘总评的 40%。

## 页面

独立入口 `/scores`，课程班级快捷入口 `/scores?course_id=...&class_group_id=...`。页面支持课程、班级选择；项目录入、基础分与换算、成绩汇总三个页签。使用当前组件、绿色主题与响应式表格。项目可新建、编辑；已有项目保留，避免误删历史。

项目录入支持按分类选项目、全班快捷打分、备注及批量保存；切换班级、项目和离开前提示未保存修改。修改失败保留输入并提示重试；版本冲突需刷新并重新核对，禁止静默覆盖。

设置页按班保存基础分和四类系数。汇总由服务端计算，展示原始积分、类别贡献、原始总分及最终成绩。可查看单个学生的成绩变更记录。支持 CSV 和 XLSX 导出；规则未配置时可导出原始明细，正式汇总需规则完整，未评价成绩保持为空并写明状态。

## 数据与接口契约

成绩模块独立于考勤表和学生主表。新增设置、项目、积分记录表；积分绑定班级 enrollment_id。复用审计表保存前后值及操作者。所有写操作锁定班级并检查同一个 version，再在同一事务修改数据、写审计及增加版本；expected_version=0 用于初次保存，避免两个窗口互相覆盖。

统一前缀 `/api/v1/classes/{class_group_id}/scores`：

| 方法与后缀 | 输入 | 输出 |
| --- | --- | --- |
| GET 根路径 | 无 | ScoreBook |
| PUT /settings | expected_version, base_score, factors | ScoreBook |
| POST /items | expected_version, category, name, occurred_on, description | ScoreBook，201 |
| PATCH /items/{item_id} | expected_version, name, occurred_on, description | ScoreBook |
| PUT /items/{item_id}/records | expected_version, records: [{enrollment_id, points, note}] | ScoreBook |
| GET /history | enrollment_id 可选 | {items: ScoreHistory[]} |
| GET /export | format=csv或xlsx，kind=summary或details | 下载文件 |

Decimal JSON 均为字符串（请求也接受数值），留空为 null。除 GET 和导出外 body 拒绝额外字段。name 长度 1～120，description/note 最多 500。

```typescript
type ScoreCategory = 'HOMEWORK' | 'CLASSROOM' | 'LAB' | 'OTHER';
interface ScoreSettings {
  base_score: string | null;
  factors: Record<ScoreCategory, string | null>;
}
interface ScoreItem {
  id: string; category: ScoreCategory; name: string;
  occurred_on: string; description: string;
}
interface ScoreStudent {
  enrollment_id: string; student_id: string; student_number: string;
  student_name: string; enrollment_status: 'ACTIVE' | 'REMOVED';
}
interface ScoreRecord {
  id: string; item_id: string; enrollment_id: string;
  points: string | null; note: string; updated_at: string;
}
interface ScoreSummary {
  enrollment_id: string;
  categories: {category: ScoreCategory; points: string; contribution: string | null; pending: number}[];
  raw_score: string | null; final_score: string | null;
  status: 'READY' | 'RULES_PENDING' | 'RECORDS_PENDING';
}
interface ScoreBook {
  class_group: {id: string; name: string; status: 'ACTIVE' | 'ARCHIVED'};
  course: {id: string; name: string; status: 'ACTIVE' | 'ARCHIVED'};
  version: number; readonly: boolean; rules_ready: boolean;
  settings: ScoreSettings; items: ScoreItem[]; students: ScoreStudent[];
  records: ScoreRecord[]; summaries: ScoreSummary[];
}
interface ScoreHistory {
  id: string; action: string; actor_name: string; created_at: string;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
}
```

新项目创建时为活动成员建立积分行，积分取项目默认积分（未设置时为空，汇总按 0 计算）；新增成员在旧项目无行时使用项目默认积分，保存时新增记录。项目默认积分后续修改只影响项目配置，不覆盖已有学生记录。移除成员仅汇总已有记录，创建新项目不会为其新增空行。班级删除纳入成绩数据，确认文案说明成绩同时永久删除。

## 验证

后端验证分数精度、100 分总分边界、无类别限制、空值/零、规则缺失、系数为零、跨班隔离、教师权限、归档/移除只读、恢复、批量事务与版本冲突、审计、级联清理、迁移、导出公式防注入。前端验证 API 契约、快捷录入、规则编辑、错误保留输入、空态、只读及汇总导出。运行 TypeScript 构建、Vitest、Python 测试与静态检查，并做桌面和移动端浏览器验证。
