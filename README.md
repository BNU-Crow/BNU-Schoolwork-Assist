# 北师大教务助手 BNU-Schoolwork-Assist (Deprecated)

不再维护 No long maintained



北师大教务助手     
Schoolwork Assistant for Beijing Normal University

使用`Python 3`。   
Using `Python 3`.    
   
需要第三方库`requests`、`PIL`和`pyexecjs`。   
3rd party libraries, `requests`, `PIL` and `pyexecjs` are required.   

> ~~学校内网登录近期偶尔又会跳转到老版登录界面，需要输入验证码，故引入PIL库，且登录流程复杂了一些。~~ 最近又好了，但该登录流程判断仍然保留。

## 声明 Declaration
最近貌似学校出现网络犯罪行为？好吧，我必须声明几点：   

1. 本助手没有对互联网和校园网中的任何网站进行任何形式的破坏和攻击；
2. 本助手的工作原理为通过对教务网的HTTP调试，找到各种操作的接口，并完全模拟浏览器提交过程，自动化查询、选课、评教、等一系列操作；
3. 为避免本助手使用泛滥，扩大学校关注，本助手短期内不会推广，保持无可视化界面的形式；
4. 本助手使用Python编写，需要自行配置运行环境，由于第3条所述原因，暂不公开简单的配置方法，请自行根据所述依赖库搭建环境；
5. 允许推广教务助手诞生的消息，但如果你会搭建运行环境并使用了，请尽量不要推广运行环境的配置方法。

I'm NOT CRACKER. I'm 3 good student. Thanks.

我不是骇客，我是三好学生，谢谢合作！

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
