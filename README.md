# 北师大教务助手 BNU-Edu-Assistance
北师大教务助手     
BNU Education System Assistance

使用`Python 3`。   
Using `Python 3`.    
   
需要第三方库`requests`、`PIL`和`pyexecjs`。   
3rd party libraries, `requests`, `PIL` and `pyexecjs` are required.   

> ~~学校内网登录近期偶尔又会跳转到老版登录界面，需要输入验证码，故引入PIL库，且登录流程复杂了一些。~~ 最近又好了，但该登录流程判断仍然保留。

## 特性 Features

1. 登录统一身份认证系统    
Login through Unified Authentication System
2. 按开课计划查询课程   
Query planning courses
3. 查询公选课   
Query elective courses
4. 退选课程   
Cancel course
5. 选公选课   
Select elective course
6. 选开课计划课程   
Select planning course
7. 查询选课结果   
Query course selection result
8. 查询考试安排   
Query exams
9. 查询考试成绩   
Query scores
10. 评教   
Evaluate teachers
11. 批量评教   
Evaluate all teachers at one time
12. 提升用户交互体验   
Improve user interactive experience
13. 设计和实现选课策略   
Design and implement strategies to select courses

## 选课策略 Strategy
1. 通过开课计划和公共选修课列表加入需要选择的课程到愿望单   
Add wanted courses into wishlist
2. 先公选课后计划课程，依愿望单次序选课，间隔时间从1.2秒自适应递增   
Elective courses first, planning courses then. Ordered by wishlist.
3. 抢某一课程失败，重新加入队列等待下一轮，不在一门课吊死   
Add courses failing to be chosen into queue again, and wait for another turn.

## TODO

1. **实现可视化用户界面   
Implement visual user interface**
