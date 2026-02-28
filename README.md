# RoboResilience Protocol v0.1

> **10天，从ABC对比实验到机器人分层恢复系统**  
> 一个18岁高三学生的机器人故障恢复工程实验

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[![Status](https://img.shields.io/badge/Status-WIP%20(Research%20Prototype)-orange)]() 

⚠️ **研究原型声明**：本项目为概念验证阶段，代码仅供参考，**完整复现文档将在后续整理**。当前展示以视频和现场演示为主。

## 项目演进

### Phase 0: 初始化策略研究（已完成）
**Phase0文件结构**：
```text
Phase0_ABC/
├── README.md
├── REPORT.md                 #详细报告
├── abc_comparison(1).xlsx    #数据表格
├── reward_convergence.jpg    #奖励函数曲线                 
└── stand_up_reward.jpg       #高度变化曲线
```
**核心发现**：机器人必须从多支撑点姿态（跪姿，Level 2）开始学习站立，从平躺（Level 3）开始是绝境，从站立（Level 1）开始则是痉挛陷阱。

**关键数据**：
- A组（平躺）：-138 reward，无法建立支撑
- B组（跪姿）：-89 reward，功能性恢复（半站立）
- C组（站立）：-88 reward，动态扭曲/自踢

**README**：[Phase0_ABC/README.md](./Phase0_ABC/README.md)
**详细报告**：[Phase0_ABC/REPORT.md](./Phase0_ABC/REPORT.md)

### Phase 1: 分层恢复系统（已超预期完成）
**原计划**：优化B组（跪姿）实现完全站立  
**实际完成**：建立了**4级课程学习链条**（Crawl→Superhero→Double→Single→Stand），实现了从Level 3到Level 1的硬切换恢复系统。

**技术路径**：
- 课程学习（Curriculum Learning）：从四点支撑渐进到站立
- 硬切换状态机：4个独立策略，明确可审计的切换逻辑
- 可视化验证：头顶红绿灯实时显示当前故障等级（红→橙→黄→青→绿）

**Phase1文件结构**：
```text
Phase1_Stand/
├── checkpoints/                    # 策略检查点（核心资产）
│   ├── [crawl_to_superhero.pt](./checkpoints/crawl_to_superhero.pt)      # Level 3→2.5：四点支撑到超级英雄姿势
│   ├── [superhero_to_double.pt](./checkpoints/superhero_to_double.pt)    # Level 2.5→2：撤手进入双膝跪地
│   ├── [double_to_single.pt](./checkpoints/double_to_single.pt)          # Level 2→1.5：压缩弹簧到单膝
│   └── [single_to_stand.pt](./checkpoints/single_to_stand.pt)            # Level 1.5→1：爆发站立
│
├── [play_hierarchical.py](./play_hierarchical.py)                        # 分层播放脚本（硬切换+红绿灯）
├── [taxonomy_v0.1.json](./taxonomy_v0.1.json)                            # 故障分类标准草案
└── README.md
```

## 为什么不使用端到端？

| 端到端（黑盒） | RoboResilience（白盒） |
|---|---|
| 流畅但不可解释 | 僵硬但可审计 |
| 摔了不知道在哪一层失败 | 明确知道处于Level 2还是Level 3 |
| 需要海量数据 | 模块化，可独立调试 |

## 当前状态

**已实现**：从Level 3（Crawl）到Level 1（Stand）的硬切换恢复系统

**技术说明**：  
- 基于IsaacLab + RSL-RL框架开发
- 含自定义奖励函数与分层状态机逻辑
- 完整环境配置将在Phase 2整理发布

**Phase1观看演示**：[B站视频链接]（推荐，此处展示完整效果）
**播放脚本**：[Phase1_Stand/play_hierarchical.py](./Phase1_Stand/play_hierarchical.py)
**分类标准草案**：[Phase1_Stand/taxonomy_v0.1.json](./Phase1_Stand/taxonomy_v0.1.json)
