-- 中职MySQL教学案例：仅操作独立教学库attendance_demo。
-- 在MySQL客户端中按顺序、选中语句执行。虚构数据，不连接真实项目库。
CREATE DATABASE IF NOT EXISTS attendance_demo DEFAULT CHARACTER SET utf8mb4;
USE attendance_demo;

-- students已存在时先DESCRIBE检查，不要重复建表。
CREATE TABLE students (
  id INT PRIMARY KEY AUTO_INCREMENT,
  student_number VARCHAR(20) NOT NULL UNIQUE,
  name VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SHOW TABLES;
DESCRIBE students;
