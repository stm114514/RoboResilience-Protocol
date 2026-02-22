# RoboResilience Protocol

**Phase 0: 初始化策略研究报告**

核心发现：机器人必须从多支撑点姿态（跪姿，Level 2）开始学习站立，从平躺（Level 3）开始是绝境，从站立（Level 1）开始则是痉挛陷阱。

**关键数据**：
- A组（平躺）：-138 reward，无法建立支撑
- B组（跪姿）：-89 reward，功能性恢复（半站立）
- C组（站立）：-88 reward，动态扭曲/自踢

**详细报告**：[REPORT.md](./REPORT.md)

**图表证据**：
![Reward Convergence](reward_convergence.jpg)
![Stand Up Reward](stand_up_reward.jpg)

**长期目标**：**长期目标：RoboResilience —— 定义机器人摔倒了该怎么爬起来的标准框架** (Towards a Taxonomy for Humanoid Fall Recovery)

## 参考
- HumanUP (RSS 2025)
- HiFAR (IROS 2025)
