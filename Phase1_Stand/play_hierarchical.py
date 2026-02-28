# Copyright (c) 2022-2026, The Isaac Lab Project Developers
# SPDX-License-Identifier: BSD-3-Clause

"""RoboResilience Protocol - 4阶段分层恢复（带冷却时间防震荡）"""
import sys
sys.path.insert(0, r"E:\IsaacLab\scripts\reinforcement_learning\rsl_rl")
import argparse
import sys
from isaaclab.app import AppLauncher

import cli_args  # isort: skip

# ========== 4个策略路径 ==========
CHECKPOINT_PATHS = {
    "crawl": r"E:\IsaacLab\checkpoints\crawl_to_superhero.pt",
    "superhero": r"E:\IsaacLab\checkpoints\superhero_to_double.pt",
    "double": r"E:\IsaacLab\checkpoints\double_to_single.pt",
    "single": r"E:\IsaacLab\checkpoints\single_to_stand.pt"
}

parser = argparse.ArgumentParser(description="RoboResilience Hierarchical Play")
parser.add_argument("--video", action="store_true", default=False)
parser.add_argument("--video_length", type=int, default=1000)
parser.add_argument("--disable_fabric", action="store_true", default=False)
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--task", type=str, default=None)
parser.add_argument("--agent", type=str, default="rsl_rl_cfg_entry_point")
parser.add_argument("--seed", type=int, default=None)
parser.add_argument("--real-time", action="store_true", default=False)
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli, hydra_args = parser.parse_known_args()

if args_cli.video:
    args_cli.enable_cameras = True

sys.argv = [sys.argv[0]] + hydra_args
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import os
import time
import gymnasium as gym
import torch
from rsl_rl.runners import OnPolicyRunner

from isaaclab.envs import (
    DirectMARLEnv,
    DirectRLEnvCfg,
    ManagerBasedRLEnvCfg,
    multi_agent_to_single_agent,
)
from isaaclab.utils.dict import print_dict
from isaaclab_rl.rsl_rl import RslRlBaseRunnerCfg, RslRlVecEnvWrapper
import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils.hydra import hydra_task_config


@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """Play with hierarchical policy switching."""
    
    agent_cfg: RslRlBaseRunnerCfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs
    env_cfg.seed = agent_cfg.seed
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    if args_cli.video:
        video_kwargs = {
            "video_folder": os.path.join("logs", "hierarchical_play", "videos"),
            "step_trigger": lambda step: step == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    dt = env.unwrapped.step_dt

    # 加载全部4个策略
    print("\n[INFO] Loading 4-phase hierarchical policies...")
    policies = {}
    policy_nns = {}
    
    for phase_name, ckpt_path in CHECKPOINT_PATHS.items():
        print(f"[INFO] Loading [{phase_name}] from: {ckpt_path}")
        
        if agent_cfg.class_name == "OnPolicyRunner":
            runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
        else:
            raise ValueError(f"Unsupported runner: {agent_cfg.class_name}")
            
        if not os.path.exists(ckpt_path):
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")
        runner.load(ckpt_path)
        
        policy = runner.get_inference_policy(device=env.unwrapped.device)
        policies[phase_name] = policy
        
        try:
            policy_nn = runner.alg.policy
        except AttributeError:
            policy_nn = runner.alg.actor_critic
        policy_nns[phase_name] = policy_nn
        
        print(f"[INFO] [{phase_name}] loaded.")

    # 从阶段1（Crawl）开始
    current_phase = "crawl"
    current_policy = policies[current_phase]
    current_policy_nn = policy_nns[current_phase]
    
    # # ========== 新增：阶段冷却时间（防止过快切换）==========
    # MIN_STEPS_PER_PHASE = {
    #     "crawl": 5,        # crawl至少运行50步才能切换（避免初始就切）
    #     "superhero": 10,   # superhero至少100步
    #     "double": 20,      # double至少100步
    #     "single": 0         # 最后一个阶段不限制
    # }
    # phase_step_count = 0  # 当前阶段已运行步数
    MIN_STEPS_PER_PHASE = {
        "crawl": 18,        # crawl至少运行50步才能切换（避免初始就切）
        "superhero": 20,   # superhero至少100步
        "double": 25,      # double至少100步
        "single": 0         # 最后一个阶段不限制
    }
    phase_step_count = 0  # 当前阶段已运行步数
    
    print(f"\n{'='*60}")
    print(f"Chain: Crawl → Superhero → Double-Kneel → Single-Kneel → Stand")
    print(f"Start: {current_phase} (冷却步数: {MIN_STEPS_PER_PHASE[current_phase]})")
    print(f"{'='*60}\n")

    obs = env.get_observations()
    
    # ========== 新增：获取动作维度 ==========
    action_dim = env.num_actions  # 通常是19
    print(f"[INFO] 动作维度: {action_dim}")
    
    # ========== 新增：头顶红绿灯小球 ==========
    from pxr import UsdGeom, Gf
    stage = env.unwrapped.scene.stage  # 获取USD舞台
    indicator_path = "/World/indicator_sphere"
    
    # 创建球体（如果已存在则先删除）
    if stage.GetPrimAtPath(indicator_path):
        stage.RemovePrim(indicator_path)
    
    sphere = UsdGeom.Sphere.Define(stage, indicator_path)
    sphere.CreateRadiusAttr(0.1)  # 半径8厘米
    
    # 创建Xform变换（控制位置）
    sphere_xform = UsdGeom.Xformable(sphere)
    translate_op = sphere_xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(0.0, 0.0, 1.5))  # 头顶上方1.3米（根据机器人高度调整）
    
    # 创建颜色属性（初始红色）
    color_attr = sphere.CreateDisplayColorAttr()
    color_attr.Set([Gf.Vec3f(1.0, 0.0, 0.0)])  # 红色：危险/初始
    
    print("[INFO] 头顶指示灯已创建（红色=初始）")
    
    # ========== 新增：初始姿态延迟1秒 ==========
    # print("\n" + "="*60)
    # print("初始姿态展示：物理稳定1秒...")
    # print("="*60)
    
    # for i in range(50):  # 50步 ≈ 1秒
    #     zero_action = torch.zeros(1, action_dim, device=env.device)
    #     obs, _, _, _ = env.step(zero_action)
    #     # 让球体跟随机器人（可选，如果机器人移动）
    #     try:
    #         robot = env.unwrapped.scene["robot"]
    #         robot_pos = robot.data.root_pos_w[0]
    #         translate_op.Set(Gf.Vec3d(0.0, 0.0, robot_pos[2].item() + 0.5))  # 跟随高度
    #     except:
    #         pass
            
    #     if i % 10 == 0:
    #         try:
    #             h = robot.data.root_pos_w[0, 2].item()
    #             print(f"  稳定中... 高度: {h:.3f}m")
    #         except:
    #             pass
    
    # print("开始执行策略！\n")
    # ========== 延迟结束 ==========

    timestep = 0
    
    # ========== 新增：动作混合参数 ==========
    BLEND_STEPS = 1.5  # 混合3步（约0.06秒，肉眼几乎无感但足够平滑）
    is_blending = False  # 是否正在混合中
    blend_counter = 0
    last_action = None  # 旧策略的最后一个动作
    next_action = None  # 新策略的第一个动作
    
    timestep = 0
    
    while simulation_app.is_running():
        start_time = time.time()
        
        with torch.inference_mode():
            # 获取高度
            try:
                robot = env.unwrapped.scene["robot"]
                height = robot.data.root_pos_w[0, 2].item()
                translate_op.Set(Gf.Vec3d(0.0, 0.0, height + 0.8))
            except:
                height = 0.0
            
            # 阶段步数计数
            if not is_blending:  # 只有在非混合期才计数（避免混合期也算作阶段运行时间）
                phase_step_count += 1
            
            # 检测是否需要切换（但不立即执行，先准备混合）
            should_switch = False
            new_phase_candidate = current_phase
            
            if phase_step_count >= MIN_STEPS_PER_PHASE[current_phase]:
                if current_phase == "crawl" and height < 0.50:
                    should_switch = True
                    new_phase_candidate = "superhero"
                elif current_phase == "superhero" and height > 0.555:
                    should_switch = True
                    new_phase_candidate = "double"
                elif current_phase == "double" and height < 0.58:
                    should_switch = True
                    new_phase_candidate = "single"
            
            # ========== 动作混合逻辑 ==========
            if is_blending:
                # 正在混合期：线性插值
                alpha = blend_counter / BLEND_STEPS  # 从0到1
                actions = alpha * next_action + (1.0 - alpha) * last_action
                blend_counter += 1
                
                # 混合结束，正式切换阶段
                if blend_counter > BLEND_STEPS:
                    is_blending = False
                    current_phase = new_phase_candidate  # 正式切换
                    current_policy = policies[current_phase]
                    current_policy_nn = policy_nns[current_phase]
                    phase_step_count = 0
                    if hasattr(current_policy_nn, 'reset'):
                        current_policy_nn.reset(torch.zeros(env.num_envs, dtype=torch.bool, device=env.device))
                    
                    # 切换完成后的颜色变化（如果需要）
                    if current_phase == "single":
                        color_attr.Set([Gf.Vec3f(0.0, 1.0, 0.0)])  # 绿色：成功！
                        print("  [指示灯] 青色 -> 绿色（站立成功！）")
            
            else:
                # 正常执行当前策略
                actions = current_policy(obs)
                last_action = actions.clone()  # 保存，可能用于下次混合
                
                # 检测是否需要开始混合（准备切换）
                if should_switch:
                    # 获取新策略的动作（用于混合）
                    next_action = policies[new_phase_candidate](obs)
                    is_blending = True
                    blend_counter = 0
                    
                    print(f"\n[STEP {timestep}] >>> 开始平滑过渡到: {new_phase_candidate} | 高度: {height:.3f}m")
                    
                    # 改变颜色（提前变色，表示开始过渡）
                    if new_phase_candidate == "superhero":
                        color_attr.Set([Gf.Vec3f(1.0, 0.5, 0.0)])  # 橙色
                    elif new_phase_candidate == "double":
                        color_attr.Set([Gf.Vec3f(1.0, 1.0, 0.0)])  # 黄色
                    elif new_phase_candidate == "single":
                        color_attr.Set([Gf.Vec3f(0.0, 1.0, 1.0)])  # 青色
            
            # 执行动作（无论是正常还是混合）
            obs, _, dones, _ = env.step(actions)
            
            if timestep % 50 == 0:
                status = "混合中" if is_blending else current_phase
                print(f"Step {timestep:4d} | {status:12s} | Height: {height:.2f}m | 阶段步数: {phase_step_count}")
            
            current_policy_nn.reset(dones)
            
        timestep += 1
        
        if args_cli.video and timestep == args_cli.video_length:
            break

        sleep_time = dt - (time.time() - start_time)
        if args_cli.real_time and sleep_time > 0:
            time.sleep(sleep_time)

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
