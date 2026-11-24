"""Build four self-contained, offline HTML teaching decks. Python standard library only."""
from pathlib import Path
from html import escape as e
import json

ROOT = Path(__file__).resolve().parent

def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{x}</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join(f'<td>{x}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def cards(*items):
    return '<div class="cards">'+''.join(f'<article class="card"><span class="card-no">{i:02}</span><h3>{a}</h3><p>{b}</p></article>' for i,(a,b) in enumerate(items,1))+'</div>'

def code(s):
    return '<div class="codebox"><button class="copy" type="button">复制 SQL</button><pre><code>'+e(s.strip())+'</code></pre></div>'

def call(s): return '<p class="callout">'+s+'</p>'
def answer(s): return '<details class="answer"><summary>展开参考答案</summary><div>'+s+'</div></details>'
def bullets(*s): return '<ul>'+''.join('<li>'+x+'</li>' for x in s)+'</ul>'
def split(a,b): return '<div class="split"><div>'+a+'</div><div>'+b+'</div></div>'
def quiz(q, options, correct, explanation):
    return '<div class="quiz"><h3>'+q+'</h3>'+''.join(f'<button type="button" data-correct="{str(i==correct).lower()}"><b>{chr(65+i)}</b> {e(o)}</button>' for i,o in enumerate(options))+'<p class="feedback" role="status" data-explanation="'+e(explanation,quote=True)+'"></p></div>'
def flow(*s): return '<div class="flow">'+'<span class="arrow">→</span>'.join('<div>'+x+'</div>' for x in s)+'</div>'
def slide(title, body, note, tag='认识与理解'):
    return dict(title=title,body=body,note=note,tag=tag)

STUDENT_DDL = """CREATE TABLE students (
  id INT PRIMARY KEY AUTO_INCREMENT,
  student_number VARCHAR(20) NOT NULL UNIQUE,
  name VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""
SEED = """INSERT INTO students (student_number, name)
VALUES ('001', '张晨'),
       ('002', '李悦'),
       ('003', '王浩'),
       ('004', '陈曦'),
       ('005', '刘洋');"""
SESSION_DDL = """CREATE TABLE attendance_sessions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_date DATE NOT NULL,
  title VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""
RECORD_DDL = """CREATE TABLE attendance_records (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_id INT NOT NULL,
  student_id INT NOT NULL,
  status VARCHAR(10) NOT NULL DEFAULT 'pending',
  UNIQUE (session_id, student_id),
  FOREIGN KEY (session_id)
    REFERENCES attendance_sessions(id),
  FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"""

lessons = []
lessons.append(dict(n=1, title='把点名册放进数据库',subtitle='先看懂数据，再开始写 SQL', goal='认识数据库、表、行和字段，完成一份点名数据设计单。',slides=[
slide('今天，从一张点名册开始', '<p class="lead">老师要记录：谁来了，谁没来，哪一天的课。</p>'+table(['学号','姓名','11 月 23 日'],[['001','张晨','出勤'],['002','李悦','缺勤'],['003','王浩','迟到']])+call('本节任务：把“我们要记什么”说清楚。'), '开场2分钟。全部姓名与学号均为虚构。先让学生描述日常点名步骤，不急着解释SQL。'),
slide('这 45 分钟，我们做什么', cards(('5 分钟','观察点名册，找出要保存的数据。'),('10 + 10 分钟','认识数据库概念，跟随教师观察客户端。'),('15 + 5 分钟','完成任务单，进行出口小测。')), '准备：已安装并启动的MySQL、可连接的图形客户端、投影。安装不占本节课时间。学生未准备好环境时，可两人一组观察演示。'),
slide('到了下周，问题出现了', cards(('找记录','怎样找到李悦上周的缺勤记录？'),('改资料','学号写错了，哪些地方需要修改？'),('做统计','这一周一共有几人次缺勤？'))+call('先说出问题，再选择保存数据的方式。'), '邀请学生说出用纸或Excel处理的步骤。说明Excel也能完成不少任务，数据库更适合结构化关联、共享与约束，不要把Excel说成不能统计。'),
slide('数据库，是有组织地保存数据',flow('数据库<br><small>attendance_demo</small>','数据表<br><small>students</small>','一条条学生记录')+cards(('数据库','一组相关数据的集合。'),('数据表','用固定结构保存同一类数据。'),('SQL','向数据库发出操作指令的语言。')), '用文件夹类比仅帮助入门，强调数据库不是把Excel文件放进一个目录。SQL不是数据库软件。'),
slide('一张表，横着看，竖着看',table(['id','student_number','name'],[['1','001','张晨'],['2','002','李悦'],['3','003','王浩']])+cards(('一行 = 一条记录','例如第 2 行描述李悦这个学生。'),('一列 = 一个字段','例如 name 列保存每个人的姓名。'),('表结构','字段名称、类型和约束组成的规则。')), '逐个指认：学生有几人？name列有几个值？表头不是学生记录。id与学号下一课深入。'),
slide('字段名，与字段里的值不同',split(table(['字段名','一个示例值'],[['student_number','001'],['name','张晨'],['session_date','2026-11-23']]),'<h3>把句子拆开</h3><p>“张晨的学号是 001。”</p>'+bullets('“姓名”是我们要记录的属性。','“张晨”是这个字段的一次具体取值。','字段名要稳定，数据值可以不同。')), '此处日期仅举例，不暗示日期属于学生表。教师提醒后面会决定每种字段应该放在哪张表。'),
slide('MySQL、客户端、SQL：谁做什么',flow('你<br><small>输入 SQL</small>','客户端<br><small>发送指令、显示结果</small>','MySQL 服务<br><small>保存和处理数据</small>')+call('关闭客户端，不代表数据库里的数据被删除。'), '演示客户端已有连接。不绑定具体工具，Navicat、Workbench或其他客户端均可。说明MySQL服务未启动时，即使客户端打开也可能连接失败。'),
slide('跟老师观察：第一次查询',code('SELECT 1 + 1 AS result;')+table(['result'],[['2']])+call('这是一条 SQL 指令。选中它，执行，观察结果区。'), '只要求观察或跟做，不要求背语法。先演示选中执行、分号、结果区和错误区。可提问：这个2是否已经永久保存成学生记录？答案：没有。', '教师演示'),
slide('判断：哪些是字段，哪些是值',quiz('下面哪一项适合作为“字段名”？',['张晨','姓名','001'],1,'姓名描述一种属性；张晨和001是具体的数据值。')+quiz('三名学生各占一行，这张表有几条学生记录？',['2 条','3 条','4 条，包含表头'],1,'表头描述结构，不计为学生记录。'), '先让学生举手，再点击选项反馈。选错后可重新选择。', '课堂互动'),
slide('本次案例，先缩小范围',cards(('一个班','暂不处理课程、教师账号与多个教学班。'),('几名学生','使用虚构的001—005号学生。'),('多次点名','后续要保存不同日期的出勤结果。'))+call('问题越明确，字段越容易设计。'), '教师进阶：真实项目含课程、教学班和名单关系。此处单班是教学边界，不是生产方案。先不把18张表展示给学生。'),
slide('试一试：设计一张学生资料卡', '<p class="lead">为“一个学生”选择需要长期保存的资料。</p>'+table(['候选信息','保留？为什么？'],[['学号','________'],['姓名','________'],['今天是否出勤','________'],['本周缺勤次数','________']])+answer('基础资料先保留学号和姓名。今天是否出勤属于某次点名；本周缺勤次数可由记录统计。本节只要求区分，不要求完成三表设计。'), '请学生先独立写3分钟，再同桌讨论。允许提出专业等额外字段，但要求说明用途。不要在学生动笔前展开答案。','学生任务 · 15 分钟'),
slide('完成你的第一张设计单',table(['对象','字段中文名','字段英文名','示例值'],[['学生','学号','student_number','001'],['学生','姓名','name','张晨'],['学生','你补充一项','________','________']])+bullets('必做：说清表、字段和记录分别是什么。','挑战：解释“今天迟到”为什么不能代表学生一直迟到。'), '验收不是英文拼写默写。让学生指着自己表中的一格说出对应字段与值。挑战题为第4课埋伏笔。','学生任务'),
slide('出口小测：用自己的话回答',quiz('MySQL 客户端主要用来做什么？',['发送操作指令并显示结果','代替所有数据库服务','保存每张纸质点名册的照片'],0,'客户端负责交互，真正处理数据的是MySQL服务。')+answer('口头补答：一行是一名学生的记录；一列是所有学生的一种属性；SQL是操作数据库的语言。'), '最后5分钟。随机请两人回答，再检查设计单。未掌握行列概念的学生下节先补1分钟。','检查理解'),
slide('下节课：让数据库按规则收名单', '<p class="lead">学号能重复吗？姓名可以不填吗？<br>数据库能帮我们检查吗？</p>'+flow('本节：说清要存什么','下节：决定怎么存','第 3 节：动手操作')+call('课后：完善学生资料卡，给每个字段写出两个示例值。'), '教师备课：对照项目models/teaching.py中的Student，观察student_number唯一约束。面试卡：字段设计应从业务含义、取值范围、约束出发。')
]))

lessons.append(dict(n=2,title='建立第一张学生表',subtitle='用字段和约束，表达数据的规则',goal='建立 students 表，解释字符类型、主键、非空和唯一。',slides=[
slide('今天，把设计单变成一张表', '<p class="lead">给每个字段选类型，给每条数据定规则。</p>'+cards(('学号','保留001这样的前导零，不能重复。'),('姓名','保存中文，必须填写。'),('内部编号','为每一行提供稳定的标识。')), '课前检查学生可连接独立教学MySQL。课程使用attendance_demo，与真实项目attendance库分开；不要使用生产库。'),
slide('目标与课堂节奏',cards(('回顾 · 5 分钟','分清字段、记录和字段值。'),('讲解与演示 · 20 分钟','字段类型、约束、建库建表。'),('练习与检查 · 20 分钟','建立学生表，观察结构与错误。')), '本节仅要求掌握INT、VARCHAR。DATE在第4节出现。类型比较、字符集细节放教师备注，不展开讲全类型体系。'),
slide('字段类型：规定可以保存什么',table(['类型','本课怎么用','示例'],[['INT','整数形式的内部编号','1、2、3'],['VARCHAR(20)','最多20个字符的学号','001、2026A01'],['VARCHAR(50)','最多50个字符的姓名','张晨']])+call('选类型，看数据的含义，不只看它长得像不像数字。'), 'VARCHAR(n)中的n表示最大字符数，不是“必须填满n位”。字节数与字符集有关，学生层不深入。'),
slide('学号 001，是一个数值吗',split('<div class="big-type">001</div><p>它用来识别人，而不是做加减。</p>',bullets('如果存成整数，001的数值就是1。','学号可能包含字母。','所以这里使用 VARCHAR(20)。'))+quiz('电话号码通常适合用哪类字段保存？',['字符型','用于计算的整数型','日期型'],0,'电话号码也是标识性文本，可能有前导零、区号或加号。'), '教师可用“001号储物柜”和“1个苹果”比较标识与数量。不要将所有数字外观信息一概判断为字符型，要看业务。'),
slide('id 与学号：两个不同角色',table(['id','student_number','name'],[['1','001','张晨'],['2','002','李悦']])+cards(('id：内部主键','数据库内部稳定地识别这一行。'),('学号：业务编号','教师和学生实际使用的编号。'),('为什么分开','学号更正时，内部关联仍可保持稳定。')), '教学用INT自增主键；真实项目使用应用生成的UUID。两种方案都需结合规模与业务解释，不把自增说成唯一标准。'),
slide('四条规则，让脏数据进不来',table(['写法','含义','用在哪里'],[['PRIMARY KEY','唯一、非空地标识一行','id'],['AUTO_INCREMENT','未指定编号时自动分配','id'],['NOT NULL','不能缺少该字段值','学号、姓名'],['UNIQUE','不允许相同值重复出现','学号']])+call('NOT NULL 不等于“不能输入空字符串”。姓名为空白还需要其他校验。'), '说明同名学生可能存在，不能把name设置为唯一。主键与学号唯一约束各有角色。'),
slide('先建库，再选择这个库',code('CREATE DATABASE IF NOT EXISTS attendance_demo\n  DEFAULT CHARACTER SET utf8mb4;\nUSE attendance_demo;')+flow('CREATE DATABASE<br><small>创建教学库</small>','USE<br><small>选择操作范围</small>','接着 CREATE TABLE')+call('每次打开新的查询窗口，先确认当前数据库。'), 'utf8mb4让库默认支持中文与完整Unicode字符。IF NOT EXISTS避免重复建库报错，不代表可以随意重复所有教学操作。','教师演示'),
slide('完整 SQL：建立学生表',code(STUDENT_DDL)+call('括号里定义字段，字段之间用英文逗号，整条语句用分号结束。'), '逐行运行前先完整读一遍：表名、字段、类型、约束、引擎、字符集。InnoDB后续支持外键与事务，此处只说明用途。','教师演示'),
slide('确认：表真的建好了吗',code('SHOW TABLES;\nDESCRIBE students;')+table(['Field','Type','Null','Key','Extra'],[['id','int','NO','PRI','auto_increment'],['student_number','varchar(20)','NO','UNI',''],['name','varchar(50)','NO','','']])+call('执行成功只是第一步，还要检查结构是否符合设计。'), 'MySQL不同版本显示格式可能略有不同，重点观察字段类型、Null、Key。SHOW TABLES结果应包含students。'),
slide('常见错误：先读错误，再修改',table(['看到的提示','先检查'],[['No database selected','有没有执行 USE attendance_demo;'],['Table already exists','是否已成功建表；先查看结构'],['SQL syntax error','英文括号、逗号、引号是否完整'],['连接失败','MySQL服务、地址、端口与账号是否正确']])+call('表已存在时，不要为了重试就直接删表。'), '不能仅凭中文错误概括判定原因。带学生定位错误语句和报错位置；已存在表结构正确即可继续。'),
slide('你的建表任务',bullets('必做：创建 attendance_demo 数据库并选择它。','建立 students 表：id、student_number、name。','运行 DESCRIBE，检查学号是否唯一、姓名是否非空。','挑战：在纸上设计一个可选专业字段，不必修改表。')+answer(code('USE attendance_demo;\nDESCRIBE students;')+'验收：3个字段；id为主键且自增；学号非空且唯一；姓名非空。'), '练习15分钟。提供02_students.sql作补救材料，但先让学生自己补全表结构。不要要求学生自行安装数据库。','学生任务 · 15 分钟'),
slide('判断规则：哪个设计更合理',quiz('两名学生可能都叫“张晨”，name 应设为 UNIQUE 吗？',['应该，同名就是同一个人','不应该，姓名不是可靠的唯一标识'],1,'学号用于业务识别，姓名允许重复。')+quiz('NOT NULL 能否自动禁止 name = 空字符串？',['能','不能'],1,'空字符串是一个已提供的值，与NULL不同。业务通常还要校验空白姓名。'), '可联系接口校验：数据库约束与应用校验互相补充。不要直接讲Pydantic代码。','检查理解'),
slide('把表结构讲给同桌听',table(['说明项','你的一句话'],[['学号为什么不用INT','________'],['id为什么是主键','________'],['UNIQUE阻止什么','________'],['NOT NULL阻止什么','________']])+call('验收标准：既能写出 SQL，也能说出每条规则的原因。'), '出口检查5分钟。教师进阶：实际项目学号VARCHAR(50)、姓名VARCHAR(100)，课堂缩短长度是教学选择，不要说成项目原字段。'),
slide('下节课：把五名学生录进去','<p class="lead">表结构准备好了。<br>接下来学习添加、查找和更正数据。</p>'+flow('结构：CREATE','数据：INSERT','查询：SELECT')+call('课后：保留本节数据库，记录自己的连接方式和表结构。'), '教师备课：对照SQLAlchemy Student模型与迁移文件。面试卡：为什么不能只依赖前端检查重复学号？并发请求可能同时通过前置查询，数据库唯一约束提供最后保障。')
]))

lessons.append(dict(n=3,title='录入、查找与更正学生',subtitle='让每一次 SQL 操作，都有明确的范围',goal='录入5名学生，按条件查询，并安全地更正一条姓名。',slides=[
slide('今天，你来管理这份学生名单',table(['学号','姓名'],[['001','张晨'],['002','李悦'],['003','王浩'],['004','陈曦'],['005','刘洋']])+call('课前状态：students 表已经建立，且尚未录入这五名学生。'), '教师先执行SELECT检查，不要重复运行插入。已有数据的学生可从查询开始。03_demo.sql为顺序演示，不能无脑整文件反复运行。'),
slide('一节课，掌握三种动作',cards(('添加 · INSERT','把五名学生加入名单。'),('查找 · SELECT','查看全部，或找到某个学生。'),('更正 · UPDATE','只修改选中的学生。'))+call('节奏：回顾5分钟 → 讲解10分钟 → 演示10分钟 → 练习15分钟 → 小测5分钟。'), 'DELETE仅作为教师提醒，不纳入本节学生必做；零基础45分钟优先掌握INSERT、SELECT、WHERE、UPDATE。'),
slide('添加一名学生：字段和值一一对应',code("INSERT INTO students (student_number, name)\nVALUES ('001', '张晨');")+flow('students<br><small>写入哪张表</small>','(student_number, name)<br><small>写入哪些字段</small>',"('001', '张晨')<br><small>对应的数据值</small>")+call('id 交给自增机制分配；字符串使用英文单引号。'), '这页单条插入与下一页批量插入是两种方案：课堂演示选择下一页完整五条，勿两页全部执行造成001重复。特别口头提醒。'),
slide('一次录入五名学生',code(SEED)+call('执行前先查表：如果已有001，不要再重复插入同一份名单。'), '实际演示从空表执行此页。受主键分配影响，id不保证永远连续，查询练习按学号定位。','教师演示'),
slide('查看全部，再选择需要的列',code('SELECT * FROM students;\n\nSELECT student_number, name\nFROM students\nORDER BY student_number;')+bullets('星号 * 表示所有列。','明确列名，可以只取需要的数据。','需要稳定顺序时，写出 ORDER BY。'), '不写ORDER BY不能保证展示顺序。SELECT只读数据，不会新增记录。SELECT *适合此处观察，实际接口应按需要选择字段。'),
slide('WHERE：把操作范围说清楚',code("SELECT student_number, name\nFROM students\nWHERE student_number = '002';")+table(['student_number','name'],[['002','李悦']])+call('先写“操作哪张表”，再想“要哪些行”。'), '让学生预测返回几行。学号有唯一约束，因此此条件最多匹配一人。字符串比较使用等号，不用双等号。'),
slide('名字里有“晨”的学生怎么找',code("SELECT student_number, name\nFROM students\nWHERE name LIKE '%晨%';")+cards(('%','匹配任意长度的字符。'),("'%晨%'",'查找姓名中包含“晨”的学生。'))+call('精确匹配用 =；本页用 LIKE 做包含查找。'), 'LIKE作为挑战示范，若学生主线未掌握可以略过。教师进阶：前置通配符查询通常不适合普通B-tree索引定位；此处不讲优化。'),
slide('更正姓名：先查，再改，再查',code("-- 1. 先确认目标\nSELECT * FROM students WHERE student_number = '003';\n-- 2. 更正王浩的姓名\nUPDATE students SET name = '王昊'\nWHERE student_number = '003';\n-- 3. 检查结果\nSELECT * FROM students WHERE student_number = '003';")+call('预期：003变为王昊，其余学生保持原值。'), '练习使用虚构改名场景。提醒WHERE唯一定位；在自动提交开启时执行后就会保存，本节不承诺可随意撤销，事务在后续课讲。','教师演示'),
slide('少了 WHERE，会发生什么',code("-- 只阅读，不执行！\nUPDATE students SET name = '王昊';")+quiz('这条 SQL 会修改哪些行？',['只修改003','修改所有学生','数据库一定会拒绝执行'],1,'无WHERE会匹配整张表；部分客户端的安全模式可能阻止，但不能依赖它。')+call('执行修改前，先用同样条件 SELECT 检查目标。'), '危险示例只供阅读，配套03_demo.sql不包含这条可执行语句。DELETE同样需要考虑范围，不在学生库做误删演示。'),
slide('如果数据库拒绝了你的操作',table(['现象','可能原因','检查办法'],[['Duplicate entry','学号重复','查询该学号是否已存在'],['Column cannot be null','必填字段被设为NULL','核对输入和值'],['查询不到结果','条件不匹配或选错库','检查学号、引号、当前库'],['修改影响0行','未匹配或值原本相同','执行SELECT确认结果']])+call('报错是线索。先看具体提示，再核对 SQL。'), '影响行数可能按客户端配置表示匹配或改变，不能仅靠0行判断是否失败。唯一约束错误也可能来自其他唯一字段，检查具体报错。'),
slide('轮到你：完成名单管理任务',bullets('① 查询学生表，确认共有五名学生。','② 只显示学号、姓名，并按学号排序。','③ 查询学号004的学生。','④ 把004的姓名更正为“陈希”，修改前后分别查询。','⑤ 挑战：找到姓名中包含“张”的学生。')+call('交付：SQL文本 + 查询结果。修改任务应只影响目标学生。'), '学生练习15分钟。不要直接展开下一页参考答案。已完成003演示修改不影响本任务。','学生任务 · 15 分钟'),
slide('核对答案：你改对人了吗',answer(code("SELECT student_number, name FROM students\nORDER BY student_number;\n\nSELECT * FROM students WHERE student_number = '004';\nUPDATE students SET name = '陈希'\nWHERE student_number = '004';\nSELECT * FROM students WHERE student_number = '004';\n\nSELECT * FROM students WHERE name LIKE '%张%';"))+table(['学号','预期姓名'],[['003','王昊（教师演示后）'],['004','陈希（学生任务后）']]), '验收学生实际结果，不只看复制的SQL。若没有执行教师改名演示，003仍是王浩也合理，明确区分任务前置条件。'),
slide('出口小测：预测 SQL 的结果',quiz("WHERE student_number = '002' 的作用是？",['选择002这名学生对应的行','选择第2列','把所有人的学号改为002'],0,'WHERE筛选行；SELECT后面的字段列表决定取哪些列。')+quiz('修改数据前，最值得先做的是？',['直接执行UPDATE','用相同WHERE条件查询确认','把WHERE删除'],1,'先确认目标，执行后再次查询核对。'), '学生独立回答后公布答案。要求学生说出SELECT和UPDATE的区别。','检查理解'),
slide('下一步：学生表能保存所有点名吗','<p class="lead">今天张晨出勤，明天张晨缺勤。<br>把 name 后面一直加日期列，行不行？</p>'+call('课后：画出两次点名的记录，思考哪些信息会重复。'), '教师备课：跟踪真实项目rosters/router.py → service.py → Student模型。面试卡：参数格式、业务规则和数据库约束分别在哪一层处理？')
]))

lessons.append(dict(n=4,title='从一张表到三张表',subtitle='用关系，保存每一次点名',goal='解释三表关系，补全点名场次表和考勤记录表的建表语句。',slides=[
slide('同一个学生，两次不同的结果',table(['学号','姓名','11 月 23 日','11 月 25 日'],[['001','张晨','出勤','缺勤'],['002','李悦','缺勤','出勤']])+call('问题：这两次结果，怎样长期、有规则地保存？'), '先复习学生表结构。单班案例，点名场次按“日期+标题”描述，不需要此时加入课程或班级外键。'),
slide('今天的任务：会拆，也会解释',cards(('看问题 · 5 分钟','每次点名都加列，会怎样？'),('设计与演示 · 20 分钟','辨认数据粒度，建立三表关系。'),('练习与检查 · 20 分钟','补全SQL，验证外键与重复约束。')), '学生第3课已完成名单。第4课仅建立结构并观察少量示例数据，不提前讲完第5课完整点名流程。'),
slide('方案一：每来一天，就加一列',table(['id','name','day_1123','day_1125','day_1127…'],[['1','张晨','present','absent','继续增加？']])+bullets('每次点名都要修改表结构。','查询一段时间的缺勤次数越来越麻烦。','同一天点名两次，还需要另想列名。')+call('日期应该成为数据值，而不是不断增加的字段名。'), '不讲所有范式定义。让学生用实际操作困难理解拆表动机，避免“宽表永远错误”的绝对说法，此处是持续增长的事件数据。'),
slide('方案二：每次复制学生姓名',table(['日期','标题','学号','姓名','状态'],[['2026-11-23','第1次点名','001','张晨','present'],['2026-11-25','第2次点名','001','张晨','absent']])+call('学生资料、点名活动、个人结果，混在了同一层。')+answer('改学生资料时容易漏改；同一次点名的日期和标题会在多名学生的行里重复。先分清每一行描述的对象。'), '历史快照是有目的的冗余，真实项目会保留姓名快照。此处先解释基础拆分；不要声称所有重复姓名都应该消除。'),
slide('分清三种“对象”',cards(('学生','一行描述一个人：001号张晨。'),('点名场次','一行描述一次活动：11月23日第1次点名。'),('考勤记录','一行描述一个结果：张晨在第1次点名中出勤。'))+call('设计一张表前，先说清“一行代表什么”。'), '数据粒度是本节最重要概念。请学生分别造一句话，确认记录表是一名学生在一次场次中的结果，不是学生的一生总状态。'),
slide('三表关系：两端的“一”，明细中的“多”','<div class="er"><article><h3>students</h3><p><b>PK</b> id</p><p>student_number · name</p></article><div class="er-link">1 → 多</div><article class="emphasis"><h3>attendance_records</h3><p><b>PK</b> id</p><p><b>FK</b> student_id</p><p><b>FK</b> session_id</p><p>status</p></article><div class="er-link">多 ← 1</div><article><h3>attendance_sessions</h3><p><b>PK</b> id</p><p>session_date · title</p></article></div>'+call('一个学生有多条考勤记录；一次点名也有多条考勤记录。'), '投影时用手指沿关系读：students.id被records.student_id引用；sessions.id被records.session_id引用。主表先建，引用它的表后建。'),
slide('场次表：保存“哪一次”',table(['字段','类型','用途'],[['id','INT 主键自增','内部场次标识'],['session_date','DATE 非空','点名日期'],['title','VARCHAR(50) 非空','例如上午第1次点名']])+code(SESSION_DDL), '同一天可有多次点名，不对session_date单独设置UNIQUE。title是教学简化字段，真实项目包含class_group_id、状态、开始完成时间等。'),
slide('记录表：保存“谁在这次怎么样”',table(['字段','类型','用途'],[['id','INT 主键自增','记录标识'],['session_id','INT 非空，外键','属于哪次点名'],['student_id','INT 非空，外键','是哪名学生'],['status',"VARCHAR(10)，默认pending",'这次点名的结果']])+call('pending 待点名 · present 出勤 · absent 缺勤 · leave 请假 · late 迟到'), '本教学DDL暂不加CHECK，状态仍可写入其他字符串，必须明确这一限制；真实项目通过CHECK与接口校验约束状态。默认值不等于合法值列表。'),
slide('两个外键，加一条不重复规则',code(RECORD_DDL)+call('UNIQUE(session_id, student_id)：同一次点名，同一个学生最多一条记录。'), 'SQL较长：先讲两条FOREIGN KEY再讲UNIQUE，强调联合唯一不是每列单独唯一。使用InnoDB；不添加级联删除，不关闭外键检查。','教师演示'),
slide('用三条数据，验证设计',code("INSERT INTO attendance_sessions (session_date, title)\nVALUES ('2026-11-23', '上午第1次点名');\nSET @demo_session_id = LAST_INSERT_ID();\nSELECT id INTO @demo_student_id\nFROM students WHERE student_number = '001';\nINSERT INTO attendance_records (session_id, student_id)\nVALUES (@demo_session_id, @demo_student_id);\nSELECT * FROM attendance_records;")+call('省略 status 时，应该看到默认值 pending。'), '教师演示页，SQL变量只需跟随观察，不作为学生考点。须在同一连接执行，先保证001存在。第一次示例只有一条记录，不代表完整名单初始化。','教师演示'),
slide('预测：哪些数据会被拒绝',quiz('重复插入相同的 session_id 和 student_id，会怎样？',['生成第二条正常记录','被联合唯一约束拒绝','覆盖原来的状态'],1,'普通INSERT不会自动覆盖，重复的组合会触发唯一约束错误。')+quiz('student_id 指向一个不存在的学生，会怎样？',['自动创建学生','被外键拒绝','自动当成缺勤'],1,'外键要求被引用的学生存在。非空规则还会阻止NULL。'), '预期失败语句在04_constraints_check.sql单独提供，逐条选中执行，避免脚本在第一次错误处中断后误判其他结果。'),
slide('动手：补全你自己的三表关系',bullets('① 画出三张表，为每张表写一句“一行代表什么”。','② 复制提供的04_relations.sql，在执行前解释两个外键。','③ 执行后用 DESCRIBE 检查两张新表。','④ 在纸上画出：2名学生、2次点名，全部点名后应有几条记录？','挑战：解释为什么不能单独限制 student_id 唯一。')+answer('必做：学生与记录是一对多；场次与记录是一对多。2人×2次，每人每次一条，共4条。student_id单独唯一会让一个学生只能有一条历史记录。'), '练习15分钟。前面建表成功的同学只检查，不重复CREATE。基础薄弱者使用完整脚本；进阶者从教师给的空白版补外键。','学生任务 · 15 分钟'),
slide('设计的理由，比背表名更重要',quiz('同一天可以点名两次，session_date 应单独设唯一吗？',['应该','不应该'],1,'日期不是一次点名的充分标识，场次id用来区分活动。')+answer('<p>为什么不把今天的状态直接放在students中？</p><p>因为状态属于“学生在某次点名中的结果”。只放一个状态会覆盖历史，无法同时表达不同日期的结果。</p>'), '出口小测5分钟。教师面试卡：关联查询取当前资料，历史快照保留当时信息；它们是不同业务要求，而非范式与冗余的简单对错。','检查理解'),
slide('四节课，已经走过的设计路线',flow('第1课<br>识别数据','第2课<br>建立规则','第3课<br>操作数据','第4课<br>表达关系')+call('接下来：为整班生成记录，完成一次点名，再查询缺勤名单。')+bullets('课后交付：三表关系图、建表SQL、结构检查结果。','口头说明：主键、外键、联合唯一各解决什么问题。'), '教师进阶路线：课堂3表 → 项目7张核心表 → 支撑与扩展表。对照models/attendance.py与modules/attendance/service.py阅读，补充事务、快照和版本校验。')
]))

CSS = r"""
:root{--ink:#152c34;--muted:#52676c;--paper:#f5f3eb;--teal:#006e64;--lime:#d9ed92;--line:#d6ddd6;--code:#152c34;--gold:#b86e20}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:'Microsoft YaHei','PingFang SC',system-ui,sans-serif}button,a{touch-action:manipulation}button{font:inherit;cursor:pointer}a{color:var(--teal)}:focus-visible{outline:3px solid #d17620;outline-offset:4px}header{height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 4vw;border-bottom:1px solid var(--line);font-size:14px;gap:20px}.brand{font-weight:800;letter-spacing:.06em;text-decoration:none;color:var(--ink)}.pill{background:var(--lime);border-radius:99px;padding:6px 14px;font-weight:700}.top-tools{display:flex;gap:8px;align-items:center}.tool{border:1px solid #b8c6bd;background:transparent;color:var(--ink);padding:7px 12px;border-radius:7px;font-size:13px}main{max-width:1500px;margin:auto}.slide{display:none;min-height:calc(100dvh - 132px);padding:28px 5vw 26px}.slide.active{display:flex;flex-direction:column;justify-content:center}.eyebrow{color:var(--teal);font-size:13px;font-weight:800;letter-spacing:.12em;margin:0 0 12px}.slide h1{font-size:clamp(34px,4.3vw,64px);line-height:1.18;letter-spacing:-.035em;margin:0 0 22px;max-width:1100px}.slide h2{font-size:clamp(27px,3vw,44px);line-height:1.3;margin:0 0 22px;letter-spacing:-.02em}.slide h3{font-size:clamp(18px,1.8vw,25px);margin:0 0 12px}.slide p,.slide li,.slide td,.slide th{font-size:clamp(17px,1.65vw,24px);line-height:1.65}.slide p{margin:0 0 16px}.lead{font-size:clamp(22px,2.8vw,38px)!important;line-height:1.55!important;max-width:1100px}.hero{position:relative}.hero:after{content:attr(data-number);position:absolute;right:5vw;top:30px;font-size:220px;color:#006e640b;font-weight:900;pointer-events:none}.hero .hero-num{font-size:16px;color:var(--teal);font-weight:bold;margin-bottom:25px}.hero .subtitle{color:var(--muted);max-width:850px}.hero-goal{border-left:4px solid var(--teal);padding:14px 20px;background:#fff9;max-width:950px;margin:20px 0}.hero-meta{display:flex;gap:14px;flex-wrap:wrap;font-size:15px;margin-top:15px}.hero-meta span{border:1px solid var(--line);border-radius:99px;padding:7px 13px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:20px;margin:8px 0 18px}.card{background:#fff9;border:1px solid var(--line);padding:22px;border-radius:12px}.card-no{display:block;color:var(--teal);font-size:13px;margin-bottom:17px;font-weight:bold}.card p{margin:0;color:var(--muted)}.table-wrap{overflow-x:auto;margin:8px 0 18px;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;background:#fff8;text-align:left}th{color:var(--teal);background:#e9eee5;font-weight:700}th,td{padding:10px 18px;border-bottom:1px solid var(--line)}tr:last-child td{border-bottom:0}.callout{border-left:4px solid var(--teal);padding:12px 20px;background:#e7eee4;margin:12px 0 0!important;font-size:clamp(17px,1.55vw,22px)!important}.codebox{position:relative;background:var(--code);border-radius:12px;margin:8px 0 18px}.codebox pre{margin:0;padding:38px 24px 20px;overflow:auto;color:#e6f2e8;font-size:clamp(14px,1.5vw,21px);line-height:1.6;tab-size:2}.codebox code{font-family:Consolas,'Courier New',monospace}.copy{position:absolute;right:12px;top:8px;font-size:12px;border:1px solid #66817c;border-radius:5px;background:#25423f;color:#fff;padding:3px 9px}.split{display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:center}.big-type{font-size:110px;color:var(--teal);font-weight:800}.flow{display:flex;align-items:stretch;gap:12px;margin:20px 0;flex-wrap:wrap}.flow>div{background:#fff9;border:1px solid var(--line);border-top:4px solid var(--teal);padding:23px 20px;border-radius:8px;font-size:clamp(18px,1.8vw,26px);flex:1;min-width:130px}.flow small{font-size:15px;color:var(--muted)}.arrow{align-self:center;color:var(--teal);font-size:24px}.answer{border:1px dashed #87a59a;border-radius:8px;padding:12px 18px;background:#fff7;margin:16px 0}.answer summary{cursor:pointer;font-size:18px;color:var(--teal);font-weight:bold}.answer>div{margin-top:14px;font-size:20px;line-height:1.7}.quiz{margin:10px 0 20px}.quiz>button{display:block;width:100%;text-align:left;background:#fff9;border:1px solid var(--line);border-radius:8px;padding:12px 18px;margin:8px 0;font-size:clamp(17px,1.55vw,22px);color:var(--ink)}.quiz button b{color:var(--teal);margin-right:12px}.quiz button.correct{background:#dceecf;border-color:#478047}.quiz button.wrong{background:#f9e4d6;border-color:#b66b36}.quiz .feedback{font-size:17px;margin:9px 0;min-height:0}.er{display:flex;align-items:center;gap:15px;margin:18px 0}.er article{background:#fff9;border:1px solid var(--line);border-radius:10px;padding:22px;flex:1;min-width:0}.er article.emphasis{border:2px solid var(--teal);background:#e7eee4;flex:1.25}.er h3{font-size:clamp(16px,1.7vw,23px);overflow-wrap:anywhere}.er p{font-size:17px;overflow-wrap:anywhere}.er b{font-size:12px;color:var(--teal);background:#d3e7d3;border-radius:4px;padding:3px}.er-link{color:var(--teal);white-space:nowrap;font-size:16px}.teacher-note{display:none;border-top:2px dashed #b59b69;padding:15px 20px;margin-top:24px;background:#fff3cf;color:#654b20;font-size:16px;line-height:1.7}.teacher-mode .teacher-note{display:block}.teacher-note b{display:block}footer{height:68px;display:flex;align-items:center;justify-content:space-between;gap:15px;padding:10px 4vw;border-top:1px solid var(--line);background:var(--paper)}.nav{display:flex;align-items:center;gap:14px}.nav button{border:1px solid var(--line);border-radius:8px;background:white;padding:8px 17px;color:var(--ink)}button:disabled{opacity:.35;cursor:default}.page-count{font-variant-numeric:tabular-nums;font-size:14px;min-width:60px;text-align:center}.hint{font-size:12px;color:var(--muted)}#progress{position:fixed;bottom:0;left:0;height:4px;background:var(--teal);transition:width .16s}dialog{border:1px solid var(--line);border-radius:15px;max-width:800px;width:90vw;max-height:85vh;padding:28px;background:var(--paper);color:var(--ink)}dialog::backdrop{background:#152c34a6}.toc-head{display:flex;justify-content:space-between;align-items:center}.toc-list{display:grid;gap:8px}.toc-list button{text-align:left;padding:12px;border:1px solid var(--line);border-radius:7px;background:white;color:var(--ink)}.toc-list button.current{border-color:var(--teal);background:#e0eddd}.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:var(--ink);color:white;border-radius:8px;padding:10px 18px;z-index:20}.hub{max-width:1200px;margin:55px auto;padding:0 25px}.hub h1{font-size:clamp(34px,5vw,64px);margin:18px 0;letter-spacing:-.04em}.hub .intro{font-size:21px;line-height:1.8;max-width:900px;color:var(--muted)}.hub-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:35px}.lesson-card{display:block;text-decoration:none;color:var(--ink);background:#fff9;border:1px solid var(--line);padding:28px;border-radius:14px}.lesson-card:hover{border-color:var(--teal);transform:translateY(-2px)}.lesson-card .n{font-size:13px;font-weight:bold;letter-spacing:.12em;color:var(--teal)}.lesson-card h2{font-size:27px}.lesson-card p{color:var(--muted);line-height:1.7}.hub aside{margin:28px 0;padding:22px;background:#e7eee4;border-radius:12px;line-height:1.9}.downloads{display:flex;gap:12px;flex-wrap:wrap;margin-top:15px}.downloads a{padding:10px 14px;border:1px solid var(--line);border-radius:7px;background:#fff8}.hub footer{padding:20px 0;height:auto}.hub code{font-family:Consolas,monospace}@media(max-width:800px){header{height:auto;min-height:64px;padding:12px 20px;flex-wrap:wrap}.slide{padding:24px 20px;min-height:calc(100dvh - 154px)}.split,.hub-grid{grid-template-columns:1fr}.er{flex-direction:column;align-items:stretch}.er-link{text-align:center}.hint,.header-label{display:none}.cards{gap:12px}.card{padding:18px}footer{padding:10px 16px}.top-tools{gap:5px}.tool{font-size:12px;padding:7px}.codebox pre{font-size:14px}.hero:after{font-size:140px}.slide h2{margin-bottom:18px}th,td{padding:9px 12px}.arrow{display:none}}@media print{@page{size:A4 landscape;margin:12mm}header,footer,#progress,dialog,.copy,.toast{display:none!important}.slide,.slide.active{display:block!important;min-height:0;page-break-after:always;break-after:page;padding:10px 20px}.slide:last-child{break-after:auto}.slide h1{font-size:40px}.slide h2{font-size:29px}.slide p,.slide li,.slide td,.slide th{font-size:16px;line-height:1.5}.codebox pre{font-size:14px;white-space:pre-wrap}.teacher-note{display:none!important}.hero:after{display:none}.slide .cards{gap:12px}.card{padding:14px}.answer{break-inside:avoid}.quiz button{font-size:16px}body{background:white;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""

CSS += r"""
@media screen and (min-width:801px) and (max-height:850px){.slide{padding-top:18px;padding-bottom:18px}.slide h2{font-size:34px;margin-bottom:16px}.eyebrow{margin-bottom:9px}.slide p,.slide li,.slide td,.slide th{font-size:20px;line-height:1.5}.slide p{margin-bottom:12px}th,td{padding:8px 16px}.card{padding:18px}.card-no{margin-bottom:12px}.cards{margin-bottom:12px}.callout{font-size:19px!important;padding:10px 16px}.codebox pre{font-size:18px;line-height:1.5;padding:32px 22px 16px}.quiz{margin:7px 0 13px}.quiz>button{font-size:19px;padding:9px 16px;margin:6px 0}.quiz h3{font-size:23px;margin-bottom:8px}.table-wrap{margin-bottom:12px}.answer{margin:12px 0;padding:10px 16px}}
"""

JS = r"""
const slides=[...document.querySelectorAll('.slide')];let current=0;
const count=document.querySelector('.page-count'), progress=document.querySelector('#progress');
function show(n){current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>{s.classList.toggle('active',i===current);s.inert=i!==current;});count.textContent=`${current+1} / ${slides.length}`;document.querySelector('#prev').disabled=current===0;document.querySelector('#next').disabled=current===slides.length-1;progress.style.width=`${(current+1)/slides.length*100}%`;history.replaceState(null,'',`#${current+1}`);document.querySelectorAll('.toc-list button').forEach((b,i)=>b.classList.toggle('current',i===current));window.scrollTo(0,0);}
const dialog=document.querySelector('dialog');document.querySelector('#toc').onclick=()=>dialog.showModal();document.querySelector('#close-toc').onclick=()=>dialog.close();
document.querySelectorAll('.toc-list button').forEach((b,i)=>b.onclick=()=>{show(i);dialog.close();});
document.querySelector('#prev').onclick=()=>show(current-1);document.querySelector('#next').onclick=()=>show(current+1);
document.querySelector('#notes').onclick=()=>{let on=document.body.classList.toggle('teacher-mode');document.querySelector('#notes').setAttribute('aria-pressed',on);};
document.querySelector('#fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{toast('浏览器未允许全屏，可尝试 F11。');}};
document.querySelector('#print').onclick=()=>window.print();
document.addEventListener('keydown',ev=>{if(dialog.open||ev.ctrlKey||ev.metaKey||ev.altKey||/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))return;if(ev.key===' '&&/BUTTON|SUMMARY|A/.test(document.activeElement.tagName))return;if(['ArrowRight','PageDown',' '].includes(ev.key)){ev.preventDefault();show(current+1);}if(['ArrowLeft','PageUp'].includes(ev.key)){ev.preventDefault();show(current-1);}if(ev.key==='Home'){ev.preventDefault();show(0);}if(ev.key==='End'){ev.preventDefault();show(slides.length-1);}});
window.addEventListener('hashchange',()=>show((Number(location.hash.slice(1))||1)-1));
function toast(text){const t=document.createElement('div');t.className='toast';t.setAttribute('role','status');t.textContent=text;document.body.append(t);setTimeout(()=>t.remove(),2200);}
document.querySelectorAll('.copy').forEach(b=>b.onclick=async()=>{const text=b.parentElement.querySelector('code').textContent;try{await navigator.clipboard.writeText(text);toast('SQL 已复制');}catch{const range=document.createRange();range.selectNodeContents(b.parentElement.querySelector('code'));const selection=getSelection();selection.removeAllRanges();selection.addRange(range);toast('代码已选中，请按 Ctrl+C 复制。');}});
document.querySelectorAll('.quiz button').forEach(b=>b.onclick=()=>{const q=b.closest('.quiz');q.querySelectorAll('button').forEach(x=>{x.classList.remove('correct','wrong');x.setAttribute('aria-pressed','false');});const ok=b.dataset.correct==='true';b.classList.add(ok?'correct':'wrong');b.setAttribute('aria-pressed','true');q.querySelector('.feedback').textContent=(ok?'✓ 回答正确。':'再想一想。')+q.querySelector('.feedback').dataset.explanation;});
show((Number(location.hash.slice(1))||1)-1);
"""

def write_deck(l):
    pages=[slide(l['title'],f'<p class="lead subtitle">{l["subtitle"]}</p><div class="hero-goal"><p>{l["goal"]}</p></div><div class="hero-meta"><span>中职 MySQL · 零基础</span><span>45 分钟</span><span>课堂考勤案例</span></div>', '使用方法：左右方向键翻页；目录跳转；教师备注默认隐藏；参考答案按需展开。课前准备MySQL服务与客户端，确认教学库独立。','本节课目标')]+l['slides']
    sections=[]
    for i,s in enumerate(pages):
        sections.append(f'<section class="slide {"hero" if i==0 else ""}" data-number="0{l["n"]}" aria-label="第{i+1}页：{e(s["title"],quote=True)}"><p class="eyebrow">LESSON 0{l["n"]} / {e(s["tag"])}</p><{"h1" if i==0 else "h2"}>{s["title"]}</{"h1" if i==0 else "h2"}>{s["body"]}<aside class="teacher-note"><b>教师备注 · 备课与面试延伸</b>{e(s["note"])}</aside></section>')
    toc=''.join(f'<button type="button">{i+1:02}　{e(s["title"])}</button>' for i,s in enumerate(pages))
    html=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>第{l['n']}次课 · {l['title']}</title><style>{CSS}</style></head><body><header><a class="brand" href="index.html">MYSQL / 课堂考勤案例</a><span class="pill header-label">第 {l['n']} 次课 · 45 分钟</span><div class="top-tools"><button class="tool" id="toc">目录</button><button class="tool" id="notes" aria-pressed="false">教师备注</button><button class="tool" id="fullscreen">全屏</button><button class="tool" id="print">打印</button></div></header><main>{''.join(sections)}</main><footer><span class="hint">← → 翻页 · Home / End 首尾页 · 答案按需展开</span><div class="nav"><button id="prev" aria-label="上一页">← 上一页</button><span class="page-count" role="status" aria-live="polite"></span><button id="next" aria-label="下一页">下一页 →</button></div></footer><div id="progress"></div><dialog aria-label="课件目录"><div class="toc-head"><h2>第 {l['n']} 次课 · 目录</h2><button class="tool" id="close-toc">关闭</button></div><div class="toc-list">{toc}</div></dialog><noscript>请启用浏览器JavaScript以使用翻页功能。</noscript><script>{JS}</script></body></html>'''
    (ROOT/f'lesson-{l["n"]:02}.html').write_text(html,encoding='utf-8')

for lesson in lessons: write_deck(lesson)
links=''.join(f'<a class="lesson-card" href="lesson-{l["n"]:02}.html"><span class="n">LESSON 0{l["n"]} · 45 MIN · 15 页</span><h2>{l["title"]}</h2><p>{l["goal"]}</p><strong>打开课件 →</strong></a>' for l in lessons)
downloads=''.join(f'<a href="sql/{f}" download>{label}</a>' for f,label in [('02_students.sql','第2课 · 建库建表'),('03_demo.sql','第3课 · 操作示例'),('04_relations.sql','第4课 · 三表结构'),('04_constraints_check.sql','第4课 · 约束验证')])
(ROOT/'index.html').write_text(f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MySQL课堂考勤案例 · 前四次课</title><style>{CSS}</style></head><body><div class="hub"><span class="pill">中职 MySQL · 项目案例课程</span><h1>从一张点名册，<br>走进数据库设计。</h1><p class="intro">四次课，沿着“识别数据 → 建立规则 → 操作数据 → 表达关系”学习。每次45分钟，包含演示、任务、参考答案和教师备注。</p><div class="hub-grid">{links}</div><aside><strong>上课前</strong><br>准备 MySQL 8 与可连接的客户端。课件可离线打开，SQL需在客户端执行。仅使用独立教学库 <code>attendance_demo</code>；全部学生资料均为虚构。<br>第2课建表，第3课从空学生表录入名单，第4课增加两张表。SQL按页、按语句运行，不要反复整文件执行。</aside><h2>配套 SQL</h2><div class="downloads">{downloads}</div><aside><strong>课件使用</strong><br>点击卡片开始；左右方向键翻页，目录跳页；“教师备注”显示讲稿及面试延伸；答案默认折叠。全屏按钮或F11进入投影模式。打印时展示全部页面，默认不含教师备注；需打印答案时，请先展开对应答案。<br>教学简化：单班、整数自增主键；真实项目使用UUID，另有课程、教学班、名单关系、权限与历史快照。</aside><footer><span>建议浏览器：Chrome / Edge · 无外部字体或网络依赖</span><a href="teacher-guide.txt">教师使用说明</a></footer></div></body></html>''',encoding='utf-8')

sqlroot=ROOT/'sql';sqlroot.mkdir(exist_ok=True)
intro='-- 中职MySQL教学案例：仅操作独立教学库attendance_demo。\n-- 在MySQL客户端中按顺序、选中语句执行。虚构数据，不连接真实项目库。\n'
(sqlroot/'02_students.sql').write_text(intro+"CREATE DATABASE IF NOT EXISTS attendance_demo DEFAULT CHARACTER SET utf8mb4;\nUSE attendance_demo;\n\n-- students已存在时先DESCRIBE检查，不要重复建表。\n"+STUDENT_DDL+'\n\nSHOW TABLES;\nDESCRIBE students;\n',encoding='utf-8')
(sqlroot/'03_demo.sql').write_text(intro+"USE attendance_demo;\n-- 前置：第2课已建表。先检查；以下五名学生应尚未录入。\nSELECT * FROM students;\n-- 已有这些学号时，跳过本次INSERT，不要重复执行。\n"+SEED+"\n\nSELECT student_number, name FROM students ORDER BY student_number;\nSELECT * FROM students WHERE student_number = '002';\nSELECT * FROM students WHERE name LIKE '%晨%';\n\n-- 教师演示：先查、再改、再查。\nSELECT * FROM students WHERE student_number = '003';\nUPDATE students SET name = '王昊' WHERE student_number = '003';\nSELECT * FROM students WHERE student_number = '003';\n\n-- 学生任务参考答案（先让学生独立完成）。\nSELECT * FROM students WHERE student_number = '004';\nUPDATE students SET name = '陈希' WHERE student_number = '004';\nSELECT * FROM students WHERE student_number = '004';\nSELECT * FROM students WHERE name LIKE '%张%';\n",encoding='utf-8')
(sqlroot/'04_relations.sql').write_text(intro+'USE attendance_demo;\n-- 前置：students表存在，且001号学生已录入。\n-- 若两张新表已存在，先检查结构，不要重复CREATE。\n'+SESSION_DDL+'\n\n'+RECORD_DDL+"\n\nDESCRIBE attendance_sessions;\nDESCRIBE attendance_records;\n\n-- 以下为教师演示；同一客户端连接中依次执行。\nINSERT INTO attendance_sessions (session_date, title)\nVALUES ('2026-11-23', '上午第1次点名');\nSET @demo_session_id = LAST_INSERT_ID();\nSELECT id INTO @demo_student_id FROM students WHERE student_number = '001';\nINSERT INTO attendance_records (session_id, student_id)\nVALUES (@demo_session_id, @demo_student_id);\nSELECT * FROM attendance_records;\n-- 本教学版未加入status的CHECK约束，后续需完善合法值校验。\n",encoding='utf-8')
(sqlroot/'04_constraints_check.sql').write_text(intro+"USE attendance_demo;\n-- 前置：在同一连接中已执行第4课演示，两个@变量仍有效。\n-- 这些语句故意失败，逐条选中执行，观察错误；不要作为初始化脚本。\n\n-- 预期：联合唯一约束报错（同一次点名同一名学生重复）。\nINSERT INTO attendance_records (session_id, student_id)\nVALUES (@demo_session_id, @demo_student_id);\n\n-- 预期：外键报错（本教学数据中不存在-1号学生）。\nINSERT INTO attendance_records (session_id, student_id)\nVALUES (@demo_session_id, -1);\n\n-- 预期：非空约束报错。\nINSERT INTO attendance_records (session_id, student_id)\nVALUES (@demo_session_id, NULL);\n",encoding='utf-8')

guide='''教师使用说明｜MySQL课堂考勤案例·前四次课

打开 index.html 选择课件。每份含封面及14页教学内容，共15页，4份共60页。
每次45分钟：回顾5、讲解10、演示10、练习15、检查5。内容可按班级基础略过挑战页。
课件全部自包含，不依赖网络；单独复制lesson文件也可投影，但返回导航需要index.html同目录。
SQL下载与说明文件需要整个文件夹一起复制。若浏览器打开SQL为文本，另存为本地即可。

课前环境
1. 学校机房预先准备MySQL 8、可连接的客户端，服务必须启动。
2. 使用独立教学库attendance_demo。不要在项目真实数据库中练习。
3. 第1课只演示SELECT 1+1，不依赖已有表。
4. 第2课执行sql/02_students.sql，建立空学生表。
5. 第3课先查表再录入五人。课件单条INSERT与批量INSERT是替代示例，不要都执行。
6. 第4课执行sql/04_relations.sql。SQL变量在同一连接有效，约束验证也用该连接。
7. 文件夹不提供自动删库重置。重复备课请新建其他独立教学库，并一致替换USE与建库名称。

投影操作
左右方向键或按钮翻页；Home/End到首尾页。目录可直接跳页。
教师备注默认隐藏，按钮开启后学生也能在投影上看到，建议备课时阅读。
参考答案折叠显示。选择题点击选项会解释原因，可重新作答。
复制SQL受浏览器权限限制时会选中代码，按Ctrl+C复制。
打印可导出全部页面；教师备注不打印。答案要先展开再打印。

课堂材料与验收
第1课：学生资料设计单；能区分行、列、字段值。
第2课：建表SQL与DESCRIBE结果；能解释学号字符型、主键、唯一与非空。
第3课：五名学生数据及带WHERE的修改；能按“先查再改再查”验证目标。
第4课：三表关系图及外键说明；能解释一行粒度与联合唯一。

教学简化与真实项目
课堂仅一个班：students、attendance_sessions、attendance_records。
课堂id为INT自增；真实项目主键为应用生成UUID，字段长度也不同。
课堂title是帮助识别场次的简化字段，不是当前真实模型的完整复刻。
课堂status默认pending，但未加入CHECK；默认值不会阻止写入非法状态。
真实项目另有users、courses、class_groups、enrollments等表，并保留考勤快照。
历史快照是有意保存当时资料；讲拆表时不要说所有重复数据都是错误。

教师进阶/面试备课位置（相对于仓库根目录）
第1、2课：api/src/attendance_api/models/teaching.py 与 models/base.py。
第3课：api/src/attendance_api/modules/rosters/router.py 与 service.py。
第4课：api/src/attendance_api/models/attendance.py 与 modules/attendance/service.py。
每次记录：业务问题、设计理由、代码位置、实验现象、方案限制。
能够解释：数据库约束与接口校验的区别；业务编号与主键的区别；外键与权限的区别。

验证范围
已通过浏览器离线打开、翻页、目录、教师备注、答案展开、选择题与打印显示检查。
当前环境无法连接本机MySQL，配套SQL未在MySQL实例中实跑。正式上课前请在独立教学库按顺序试讲一次。

维护
build_course.py为课件生成源，只用Python标准库。修改内容后运行python build_course.py。
'''
(ROOT/'teacher-guide.txt').write_text(guide,encoding='utf-8')
assert len(lessons)==4 and all(len(x['slides'])==14 for x in lessons)
print(json.dumps({'decks':4,'slides':60,'destination':str(ROOT)},ensure_ascii=False))
