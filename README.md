# 简单 3d 游戏

一个可以直接进引擎的 3D 角色资产工程 + three.js 网页预览。

**当前主角**：异形（Alien）——12 万三角、189 根骨（96 根驱动骨 + 93 根 scaleCompensation 辅助骨）、
Reallusion Character Creator 标准人形骨架、**自带走路动作（10 个循环）+ 脚本生成的待机 + Mixamo 重定向的跳跃**，2K 贴图版 25.1 MB。

**历史资产**：Q 版龙人武士（DragonMan）——标准 Mixamo 命名骨架、T/A-Pose 双版、Idle / Run / Walk、
全身关节过渡几何、Mixamo 动作导入器。保留在 `dragon-man-final/` 与 `dragon-men-rebuild/` 不动。

## 异形主角（当前默认模型）

| 指标 | 数值 |
| --- | --- |
| 文件 | `dragon-man-final/Alien_Walk_Jump_2k.glb`（25.1 MB） |
| 原始素材 | `异形/character_alien_3d_model_by_oscar_creativo.glb`（437 MB，4K 贴图，仅本地保留，不进仓库） |
| 三角数 / 网格 | 120,818 三角 / 12 个 skinned mesh |
| 材质 / 贴图 | 12 个 PBR 材质，每个 BaseColor + ORM + Normal；导出时 4096 → 2048 WebP(q80) |
| 骨骼 | 189 根（`CC_Base_*` 命名 + `_scaleCompensation` 辅助骨），96 根参与蒙皮 |
| 动作 A | `Walk` 15.17 s = **10 个完整走路循环**（36.44 帧/循环 @24 fps，原地循环、无根位移） |
| 动作 B | `Idle` 3.00 s，脚本生成（脊柱呼吸 + 头部微摆 + 髋部 6 mm 起伏），腿部保持站立 |
| 动作 C | `Jump` 1.92 s（46 帧 @24 fps，Mixamo `Jumping.fbx` 重定向）——起跳蓄力 → 腾空收腿（髋部升 0.56 m）→ 落地缓冲，原地无根位移，逐帧贴地（最低点 0.002 m） |
| 动作 D | `Run` 0.542 s（13 帧 @24 fps，Mixamo `Fast Run.fbx` 重定向）——真冲刺循环：重心前压、膝抬高、双脚交替支撑，原地无根位移 |
| 步速 | 走：单脚支撑位移 0.50 m / 17–19 帧 → **0.66 m/s**；跑：支撑脚后退 0.22 m/帧 @24fps → **5.3 m/s**。预览里 `WALK_SPEED` / `RUN_SPEED` 与实测对齐，播放速率按真实速度反算，脚不打滑 |
| 朝向 / 单位 | 面向 +Z，Y-up，1 单位 = 1 米，脚底 y≈0（逐帧最低点 0.005 m） |

**关于那个动画**：素材自带的 15 秒动画原名 `6521517516544_TempMotion`，看着像待机，实测是走路——
双脚交替支撑、髋部起伏 3.7 cm、脚踝抬升 16 cm、髋部前后位移为 0（原地循环），10 个循环首尾相接。
所以直接当走路用，另用脚本生成了一个真正的待机（`异形/build_walk_idle.py`）。

**关于「跑步」**：`Run` 是 Mixamo `Fast Run` 重定向来的真冲刺循环（0.542 s / 2 步 = 3.7 步/秒，5.3 m/s）。
重定向用 `AnimLib/alien_clip_add.py --mode world`：**直接复制世界朝向**，因为源绑定是 T-pose、异形绑定是 A-pose，
按「相对绑定偏差」搬运会把这段静态差叠加成 68° 的固定偏移（手臂会甩到身后交叉）。
贴地分两步：先整段平移到「全片最低点 = 0.002 m」，再逐帧只抬升兜住个别穿地帧——不能逐帧压平，否则腾空相就没了。
预览里按住 Shift：`RUN_SPEED = 5.3` m/s，播放速率按 `speed / RUN_SPEED` 反算；
另外整身随速度前倾最多 8.6°（`LEAN_MAX = 0.15` rad，在 0.66→5.3 m/s 之间线性插值，走路时倾角为 0）。

**关于跳跃**：`AnimLib/alien_jump_build.py` 把 Mixamo 的 Jumping 动作重定向到 CC_Base 骨架，
逐帧把最低顶点抬到 ≥0.002 m（蓄力下蹲时最多抬 0.23 m，落地帧最低点 0.002 m），导出时保留 Idle / Walk / Jump 三条 action，
并清掉了导入时 Mixamo 的临时骨架与模型里的一颗无用 Icosphere。预览里按 **空格** 触发一次（timeScale 1.35）。

**为什么落地时手臂会交叉（已修）**：Mixamo 的绑定姿势是 **T-pose**（手臂水平），异形的绑定姿势是 **A-pose**（手臂下垂 68°），
而重定向公式 `D = P_m · (MWM · matrix_local)⁻¹` 会把「T→A 的放下量」当成动画内容逐帧施加一遍——
实测上臂恒偏 67.9°、前臂 68.9°，两只手因此甩到身后交叉。修法是**中立帧归一化**：
以源动作第一帧为中立帧，预先算 `DN = (P_m · base⁻¹)⁻¹`，烘焙时用 `D · DN` 只保留相对中立帧的运动。
这条已默认启用（`--no-neutral` 可关），所以任何 T-pose 源动作搬到 A-pose 目标上都不会再出现这种固定偏转。

## 目录

| 路径 | 内容 |
| --- | --- |
| `dragon-man-final/` | **成品 GLB**：异形 `Alien_Walk_Jump_2k.glb` + 龙人 T/A-Pose、Walk、Run |
| `异形/` | 异形原始 437 MB 素材（4K 原版，本地保留，不进仓库） |
| `AnimLib/` | **动作导入器**：`retarget_import.py`（Mixamo → 龙人）、`mixamo_retarget.py`（Mixamo → 异形 CC 骨架，含中立帧归一化/去根位移/逐帧贴地）、`style_run.py`（前倾/低头/收肘风格化）、`ground_run.py`（逐帧抬升防穿地）、`alien_jump_build.py`（重定向 Jumping.fbx → Idle/Walk/Jump 打包）、`alien_clip_add.py`（往主 GLB 追加任意 Mixamo 动作：中立帧/world 模式、根位移、整段+逐帧贴地、前倾风格化） |
| `web-preview/` | three.js 网页预览 + **玩法原型**（零依赖 `node tools/serve.mjs`）：动作播放、关卡碰撞、跳跃、收集，`test/` 下有 node 测试 |
| `dragon-men-rebuild/` | 龙人生成管线脚本（Blender Python） |
| `启动预览.cmd` | 一键起本地预览服务 |
| `同步到gitee.cmd` | 一键提交并推送 |

## 快速上手

**看模型**：双击 `启动预览.cmd`，浏览器打开 http://127.0.0.1:5199/
带参数（`?glb=/Alien_Walk_Jump_2k.glb` 换模型、`?lod=1|2` 切龙人 LOD、`?yaw=45&pitch=10&dist=4` 定视角、`?jump=1` 自动起跳）。
按键：WASD 移动、Shift 跑（真 Run，5.3 m/s）、**空格跳跃**、**R 重开**、鼠标左键拖动转视角、滚轮缩放。

**进引擎**：把 `dragon-man-final/Alien_Walk_Jump_2k.glb` 拖进 Unity / Unreal / Godot / Blender。
12 万三角、12 个材质、96 蒙皮骨、四个动作（Walk / Idle / Jump / Run）。龙人用 `DragonMan_Std_Walk.glb`（70 骨、5.9 万三角）。

## 玩法原型（three.js，进行中）

20 × 20 的场地里**收集 12 个青色球**，左上角显示进度和计时，收满后显示通关时间，按 R 重开。

- **碰撞**：玩家按半径 0.55 m 的圆在 XZ 平面推挤，箱子侧面和边界墙都挡人；顶面高度单独算，所以能站上去，走出边缘会掉下来。
- **跳跃**：`JUMP_V = 5.4`、`GRAV = 16.3` → 顶点 0.85 m、滞空 0.65 s，和 Jump 动作的离地/落地帧对齐；起跳冲量在蓄力 0.38 s 之后才给，避免「动画还在下蹲、人已经飞了」。
- **可达性**：0 → 0.5 → 1.05 → 1.6 m 的梯级、0.45 / 0.9 / 1.35 m 三级台阶；跳一级的上限是 0.85 m，所以 12 个球全部拿得到（地面 6 个 + 台面 6 个）。
- **代码**：`web-preview/src/world.js`（关卡、碰撞、拾取、`stepVertical` 竖直积分）、`web-preview/src/main.js`（第三人称控制、动画状态机、重力）。
- **测试**：`cd web-preview && node test/world.mjs && node test/physics.mjs` —— 撞墙停在墙前、台面高度、拾取去重、跳跃顶点/滞空、走空掉落，11 + 5 项全通过。
- **调试参数**：`?pos=x,z` 指定落点、`?dist=`/`?pitch=`/`?yaw=` 定视角、`?jump=1&jd=<ms>` 自动起跳。

## 角色指标（龙人，实测）

- 身高 2.010 m，脚底 y=0，轴心在双脚踝中点；面向 +Z，Y-up，1 单位 = 1 米
- 70 根骨，全部 Mixamo 命名（`mixamorig:` 前缀），含 4 指 × 3 节 × 左右 = 24 根指骨、12 根尾骨
- 成品三角数 5.88 万，四档 LOD 到 1.16 万
- 动作：Idle 4.000 s / Walk 1.0667 s（33 帧）/ Run 0.600 s
- 旧资产腿短（腿长仅身高 22%）是它看起来蹲着的原因，新主角换成正常比例人形后已不存在

## 同步

仓库：https://gitee.com/lilhand/simple-3d-game （仓库名「简单3d游戏」）

每改一次就推一次：双击 `同步到gitee.cmd`（或 `同步到gitee.cmd "改动说明"`）。
它做三件事：`git add -A` → 有变化就提交 → `git push gitee main`。

## 许可与署名

- **异形主角**：*Character Alien 3d model* by **Oscar Creativo**（Sketchfab），授权 **CC BY-NC 4.0**
  （署名 + 非商用）。出处：https://sketchfab.com/3d-models/character-alien-3d-model-by-oscar-creativo-d25e65efd50c4ba691e1d5dfa1551ccc
  本项目对该素材做了贴图降采样（4096→2048 WebP）与 GLB 重导出，**未减面**。
- **龙人（历史资产）**：*Dragon men Character for game* by ohmmi5955，CC-BY 4.0。

使用本项目时请保留以上两行署名。