-- 中职MySQL教学案例：仅操作独立教学库attendance_demo。
-- 在MySQL客户端中按顺序、选中语句执行。虚构数据，不连接真实项目库。
USE attendance_demo;
-- 前置：students表存在，且001号学生已录入。
-- 若两张新表已存在，先检查结构，不要重复CREATE。
CREATE TABLE attendance_sessions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_date DATE NOT NULL,
  title VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE attendance_records (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_id INT NOT NULL,
  student_id INT NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'pending',
  UNIQUE (session_id, student_id),
  FOREIGN KEY (session_id)
    REFERENCES attendance_sessions(id),
  FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DESCRIBE attendance_sessions;
DESCRIBE attendance_records;

-- 以下为教师演示；同一客户端连接中依次执行。
INSERT INTO attendance_sessions (session_date, title)
VALUES ('2026-11-23', '上午第1次点名');
SET @demo_session_id = LAST_INSERT_ID();
SELECT id INTO @demo_student_id FROM students WHERE student_number = '001';
INSERT INTO attendance_records (session_id, student_id)
VALUES (@demo_session_id, @demo_student_id);
SELECT * FROM attendance_records;
-- 本教学版未加入status的CHECK约束，后续需完善合法值校验。
