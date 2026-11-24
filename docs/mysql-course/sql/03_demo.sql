-- 中职MySQL教学案例：仅操作独立教学库attendance_demo。
-- 在MySQL客户端中按顺序、选中语句执行。虚构数据，不连接真实项目库。
USE attendance_demo;
-- 前置：第2课已建表。先检查；以下五名学生应尚未录入。
SELECT * FROM students;
-- 已有这些学号时，跳过本次INSERT，不要重复执行。
INSERT INTO students (student_number, name)
VALUES ('001', '张晨'),
       ('002', '李悦'),
       ('003', '王浩'),
       ('004', '陈曦'),
       ('005', '刘洋');

SELECT student_number, name FROM students ORDER BY student_number;
SELECT * FROM students WHERE student_number = '002';
SELECT * FROM students WHERE name LIKE '%晨%';

-- 教师演示：先查、再改、再查。
SELECT * FROM students WHERE student_number = '003';
UPDATE students SET name = '王昊' WHERE student_number = '003';
SELECT * FROM students WHERE student_number = '003';

-- 学生任务参考答案（先让学生独立完成）。
SELECT * FROM students WHERE student_number = '004';
UPDATE students SET name = '陈希' WHERE student_number = '004';
SELECT * FROM students WHERE student_number = '004';
SELECT * FROM students WHERE name LIKE '%张%';
