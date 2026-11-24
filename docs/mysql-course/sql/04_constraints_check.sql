-- 中职MySQL教学案例：仅操作独立教学库attendance_demo。
-- 在MySQL客户端中按顺序、选中语句执行。虚构数据，不连接真实项目库。
USE attendance_demo;
-- 前置：在同一连接中已执行第4课演示，两个@变量仍有效。
-- 这些语句故意失败，逐条选中执行，观察错误；不要作为初始化脚本。

-- 预期：联合唯一约束报错（同一次点名同一名学生重复）。
INSERT INTO attendance_records (session_id, student_id)
VALUES (@demo_session_id, @demo_student_id);

-- 预期：外键报错（本教学数据中不存在-1号学生）。
INSERT INTO attendance_records (session_id, student_id)
VALUES (@demo_session_id, -1);

-- 预期：非空约束报错。
INSERT INTO attendance_records (session_id, student_id)
VALUES (@demo_session_id, NULL);
