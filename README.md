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
| 动作 E | `Crouch` 4.13 s（99 帧 @24 fps，Mixamo `Crouching.fbx` 重定向）——从站姿下蹲到低伏（髋部 1.07→0.53 m），片尾停住不循环；起身用 0.35 s 交叉淡出回 Idle |
| 动作 F | `CrouchWalk` 3.04 s（73 帧 @24 fps，Mixamo `Crouch Walk.fbx` 重定向）——蹲走；预览里只取 **49..73 帧（1.0 s）** 当循环：原片前 43 帧两脚位移 < 3 cm（几乎不动），真正的迈步在 49 帧之后，取错区间会看起来“腿不动”。支撑脚实测 0.44 m/16 帧 与 0.34 m/13 帧 → 蹲走速度取 0.8 m/s |
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
| `AnimLib/` | **素材验收**：`inspect_fbx.py`（丢进来的 Mixamo FBX 先过这一关：版本 7100+ / 帧率 / 骨架 / 动作时长 / 髋部水平漂移，判定能不能进管线）。**动作导入器**：`retarget_import.py`（Mixamo → 龙人）、`mixamo_retarget.py`（Mixamo → 异形 CC 骨架，含中立帧归一化/去根位移/逐帧贴地）、`style_run.py`（前倾/低头/收肘风格化）、`ground_run.py`（逐帧抬升防穿地）、`alien_jump_build.py`（重定向 Jumping.fbx → Idle/Walk/Jump 打包）、`alien_clip_add.py`（往主 GLB 追加任意 Mixamo 动作：中立帧/world 模式、根位移、整段+逐帧贴地、前倾风格化）、`zombiegirl_build.py`（Mixamo With Skin 角色 → 网页用敌人 GLB：贴图去重降 1K、烘 NLA 动作轨） |
| `web-preview/` | three.js 网页预览 + **玩法原型**（零依赖 `node tools/serve.mjs`）：动作播放、关卡碰撞、跳跃、收集，`test/` 下有 node 测试 |
| `dragon-men-rebuild/` | 龙人生成管线脚本（Blender Python） |
| `启动预览.cmd` | 一键起本地预览服务 |
| `同步到gitee.cmd` | 一键提交并推送 |

## 素材验收（Mixamo）

丢进 `D:\浏览器·\` 之前先确认这几项，否则白下：

| 项 | 要求 | 为什么 |
| --- | --- | --- |
| Format | FBX Binary | 管线只认 FBX；glTF 也行但要另写导入 |
| Skin | 动作 Without Skin / 角色 With Skin | 动作套现有骨架，角色要网格贴图 |
| FPS | 24（30 也接受） | 管线按时间重采样到 24 |
| Keyframe Reduction | none | 减帧会毁掉攻击动作的起始相位 |
| In Place | 有根位移的动作（walk/run/冲刺攻击）**勾上** | 省掉后期去根位移，游戏里位移由代码驱动 |
| FBX 版本 | 7100+ | Blender 5.x 打不开 6100 这类老格式 |

下载后先跑验收：

```
blender -b --python AnimLib/inspect_fbx.py -- "D:\浏览器·\xxx.fbx"
```

输出形如 `OK standing walk forward.fbx v7700 24fps 骨37(mixamorig:) 网格0 动作1` + `clip … 1.17s 原地`。版本过低会直接 `FAIL`（打包资源包里常见）。

## 快速上手

**看模型**：双击 `启动预览.cmd`，浏览器打开 http://127.0.0.1:5199/
带参数（`?glb=/Alien_Walk_Jump_2k.glb` 换模型、`?lod=1|2` 切龙人 LOD、`?yaw=45&pitch=10&dist=4` 定视角、`?jump=1` 自动起跳）。
按键：WASD 移动、Shift 跑（真 Run，5.3 m/s）、**空格跳跃**、**C 蹲下/起身**、**R 重开**、鼠标左键拖动转视角、滚轮缩放。
蹲下后仍可移动（`CrouchWalk`，0.9 m/s），按一下 C 又站起来；蹲下时不能跳。

**进引擎**：把 `dragon-man-final/Alien_Walk_Jump_2k.glb` 拖进 Unity / Unreal / Godot / Blender。
12 万三角、12 个材质、96 蒙皮骨、六个动作（Walk / Idle / Jump / Run / Crouch / CrouchWalk）。龙人用 `DragonMan_Std_Walk.glb`（70 骨、5.9 万三角）。

## 场景：晨雾森林（默认）

游戏跑在你自己做的那片森林里（`D:/ai/数据分析/blender-mcp/forest_birds2.blend` → `dragon-man-final/Forest_Morning.glb`）。

- 原 Blender 场景 113 个网格 / 185 万三角 / 全程序化材质（Bark 噪波、Leaf+Grass 顶点色、体积雾），无法直接当游戏资源，
  管线是：删灯光相机与体积雾网格 → **Draco 压缩导出**（33.4 MB → **4.7 MB**）→ three.js 里重建光照。
- 光照按原场景参数复现：低角度晨光（sun_elevation 0.175 → 太阳仰角约 10°，长投影）、`FogExp2` 0.024 的冷灰雾、
  天空穹顶用 `ShaderMaterial` 做水平渐变（地平 #dcd8cb → 天顶 #8fb0c8，太阳方向加暖色辉光）、曝光 0.94。
- 材质按名字重映射（原材质是节点程序化的，glTF 只剩名字）：Bark 深褐、Ground 灰绿、GrassM 绿、Leaf 用自带顶点色
  `leafcol`（GLB 里是 COLOR_0）、BirdSil 近黑；体积雾 `MorningFog` 网格直接丢弃，改由 three.js 的 fog 代替。
- 碰撞：加载后遍历 `*_Br_` 枝干网格，取 y<1.3 m 的顶点算 XZ 包围盒当树干（45 棵，中位宽 1.17 m），玩家圆半径 0.55 m，
  所以贴着树走会被挡住；树林无高低差，站台逻辑不参与。
- 收集球改成绕原点两圈的 12 个点，点位不落在树干里。
- `?scene=arena` 可回到木箱场地测跳跃与踩台面。

### 大气与后处理

- **光柱软遮挡**（`web-preview/src/atmo.js` + `web-preview/src/postfx.js`）：12 根交叉面片光柱 + 3 层贴地雾片是自定义
  `ShaderMaterial`，片元着色器采样一张**半分辨率场景深度图**，用 `sceneDist` 与自身距离比较得到 `occ`——光柱被树干挡住就淡出，
  贴着树干前表面时逐渐显现（软粒子写法）。原来的光柱是贴纸式叠加，树干再亮也压不住它，所以看着假。
  深度图由一次 `overrideMaterial = MeshBasicMaterial({colorWrite:false})` 的 pass 渲出；光柱/雾片在 `camera.layers` 的
  layer 1 上，渲深度时 `camera.layers.set(0)` 排除掉它们自己。
- **Bloom**：`EffectComposer`（HalfFloat + 4× MSAA）+ `UnrealBloomPass(strength 0.60, radius 0.55, threshold 0.70)` + `OutputPass`。
  阈值 0.90 时几乎不出效果（>225 的像素只有个位数），0.55 时整帧洗白（mean 131.8 → 173.0），0.70 只有高光和收集球的边缘发光、
  整体均值不变。上一版屏幕空间 god rays（`godrays.js`）已删除：28 层径向累加会把远处雾一起点亮，代价换不来收益。
- **调色**：地平/雾由冷白改暖灰（`forest.js` 的 `SKY_HOR` #dcd8cb、`FOG` #c6c2b2），曝光 0.94，暗角由 `index.html` 的 `#vig` 叠。
- **亮度标定**：线性空间里加色比原来在 sRGB canvas 上直接加色亮约 4 倍，所以光柱/雾片的基准不透明度统一乘
  `ATMO_SCALE = 0.25`（`main.js:10`）；同机位实测 mean 121.9 vs 旧 117.8，观感对齐。
- **调试参数**：`?bloom=0` 关辉光、`?soft=0` 关软遮挡（此时深度采样退回全远纹理，光柱正常但不遮挡）、`?fogx=` 光柱强度倍数、
  `?bs=`/`?bt=` 辉光强度/阈值、`?sun=<秒>` 冻结太阳位置——太阳默认跟着 `performance.now()` 漂移，不冻结的话两次截图亮度不可比。

## 玩法原型（three.js，进行中）

20 × 20 的场地里**收集 12 个青色球**，左上角显示进度和计时，收满后显示通关时间，按 R 重开。

- **碰撞**：玩家按半径 0.55 m 的圆在 XZ 平面推挤，箱子侧面和边界墙都挡人；顶面高度单独算，所以能站上去，走出边缘会掉下来。
- **跳跃**：`JUMP_V = 5.4`、`GRAV = 16.3` → 顶点 0.85 m、滞空 0.65 s，和 Jump 动作的离地/落地帧对齐；起跳冲量在蓄力 0.38 s 之后才给，避免「动画还在下蹲、人已经飞了」。
- **可达性**：0 → 0.5 → 1.05 → 1.6 m 的梯级、0.45 / 0.9 / 1.35 m 三级台阶；跳一级的上限是 0.85 m，所以 12 个球全部拿得到（地面 6 个 + 台面 6 个）。
- **代码**：`web-preview/src/world.js`（关卡、碰撞、拾取、`stepVertical` 竖直积分）、`web-preview/src/main.js`（第三人称控制、动画状态机、重力）。
- **测试**：`cd web-preview && node test/world.mjs && node test/physics.mjs` —— 撞墙停在墙前、台面高度、拾取去重、跳跃顶点/滞空、走空掉落，11 + 5 项全通过。
- **调试参数**：`?pos=x,z` 指定落点、`?dist=`/`?pitch=`/`?yaw=` 定视角、`?jump=1&jd=<ms>` 自动起跳。

### 事件特效

三个事件各有反馈（`web-preview/src/vfx.js`，全部是程序化生成，没有额外贴图文件）：

- **拾取**：两圈地面扩散环（冷青 `0x9fe4ff` + 白色快闪）+ 球心一团上飘的细尘。环挂在**地面高度**、闪光挂在球的真实坐标，两者分开传参。
- **落地**：按落地竖直速度决定强度（`-impactVy / JUMP_V` 夹到 0.35..1.5）——环从 0.22 扩到 0.85+0.35·s、0.34 s 内淡出，暖土色 `0xd9c49a`（和拾取的冷光区分开），同时踢起 8–23 颗扬尘。
- **冲刺**：贴地拖尾条带（宽 1.15 m，尾部按弧长收窄 55%）+ 每 0.07 s 一撮脚步扬尘；速度掉到 `RUN_SPEED × 0.55` 以下后 0.5 s 内淡出。

实现要点：

- **条带朝向**：`side = tangent × up`（水平面片）。最初照搬参考实现的 `side = tangent × (camera - point)`（billboard），但本项目的追尾镜头几乎**沿切线**看，两者叉积趋零，条带退化成一条线、帧里完全看不见；改成水平面片后从背后就能看到两侧的尾迹。切线用中心差分、UV 按累计弧长参数化，点间距不均时不会被拉伸。
- **不在深度 pass 里**：光柱的软遮挡要靠半分辨率深度图，特效挂在 `camera.layers` 的 **layer 2**，深度 pass 用 `camera.layers.set(0)` 渲染时自然排除，否则地面光环会把自己写进深度图、把光柱挡掉。
- **池化**：环（10 个）/ 扬尘（120 颗）都是预分配 + `DynamicDrawUsage`，每帧只重写用到的那部分；拖尾是固定 48 段的三角条带，用 `setDrawRange` 控制绘制量，不新建几何体。
- **奔跑黑屏（已修）**：拖尾片元原本写 `pow(1.0 - vUv.x, 1.7)`，插值到条带边界会出现 `vUv.x = 1.0000001`，GLSL 里 `pow(负数, 小数)` 是 NaN；NaN 像素被 `UnrealBloomPass` 的低频 mip 抹开后与底图相加，得到整屏 NaN → 全黑。现在两处都 `clamp` 到 `[0,1]`：

  ```glsl
  float across = clamp(1.0 - abs(vSide), 0.0, 1.0);
  float along  = pow(clamp(1.0 - vUv.x, 0.0, 1.0), 1.7);
  float a      = clamp(across * across * along * uOpacity * 0.60, 0.0, 1.0);
  ```

  复现与二分方法：静止不黑、`?demo=run` 必黑 → `?bloom=0` 正常（说明是后处理链路）→ 逐个关特效定位到拖尾。证据图 `_shots/fx/CMP_black.png`（左：修复前全黑，右：修复后）。
- **参数标定过程**：第一版环贴图渐变从 0.26 铺到 0.5，加色叠在灰白雾地上糊成一团白雾；收紧到 0.62 才开始透、0.84 达到 0.85 的窄亮环后才读得出「冲击环」的形状。扬尘的 alpha 也从 0.55 降到 0.30，否则落地像爆了个白球。
- **调试参数**：`?fx=land|pickup` 循环触发、`&fxhold=<秒>` 推进到指定相位后定格（无头截图对比用）、`?still=1` 冻结雾片漂移、`?demo=run` 自动冲刺。证据图 `_shots/fx/CMP_fx.png`。
- 条带朝向与弧长 UV 的思路来自 MIT 许可的 [achrefelouafi/LinearAbiltyCastingThreeJS](https://github.com/achrefelouafi/LinearAbiltyCastingThreeJS)（`src/effects/RibbonGeometry.js`），实现按本项目的事件循环重写。

### 战斗

僵尸动作来自 Mixamo「Scary Zombie Pack」（见上面素材验收），挑 5 条转存到 `web-preview/public/models/zombie/`：`idle / walk / run / attack / death`（FBX，共 1.49 MB）。敌人网格是另一份 Mixamo **With Skin** 下载的 `Zombiegirl W Kurniawan.fbx`（7700 版、63 骨——比动作多 36 根指骨、4 张 2048² 贴图已内嵌、Armature scale 0.01、整体高 2.038 m）。

- **烘焙成 GLB**：`blender -b --python AnimLib/zombiegirl_build.py` → `web-preview/public/models/zombie/zombiegirl.glb`（4.46 MB）。脚本做四件事：贴图按 filepath 去重、降到 1K；断开 Principled 的 Specular 输入（省掉 `KHR_materials_specular` 那张 1.3 MB 的贴图）；删掉模型自带的动作；把 5 条僵尸动作当作 **NLA 轨**挂到女僵尸骨架上一起导出，于是 GLB 里直接带 5 条 glTF animation（每条 189 通道 = 63 骨 × 3）。
- **为什么非要在 Blender 里烘**：three 直接读那份 FBX 得到的骨架，和 Blender 转出来的 GLB 骨架，**每根骨的局部坐标系不一样**（FBX 里 hips 的局部平移是 `(0, 92.5, 0)` 那套轴；转成 GLB 后是 `(0, -0.29, -107.59)`，因为 0.01 缩放和 -90° X 旋转落在 Armature 节点上）。把 FBX 里的 clip 直接套到 GLB 骨架上实测：髋部掉到 0.00、头到 -0.25 —— 整个人躺在地上。所以动作必须与骨架在同一个坐标系里生成，不能跨管线拼。
- **运行期加载**：`loadEnemyAssets()` 先读 GLB（`assets.scale = 1`，0.01 已经烘在 Armature 节点上）；读失败则退回旧路——无蒙皮 FBX 骨架 + `buildPuppet()` 用贴在骨段上的盒子拼的占位体格（`assets.scale = 0.01`）。指骨没有动作轨道，会保持绑定姿势。
- **为什么能直接用**：`three/addons/loaders/FBXLoader.js` 能读这些 FBX（37 根 `mixamorig` 骨，`obj.animations` 里就是动作），所以不需要 Blender 转 GLB。注意骨架单位是**厘米**（髋高 92.555），实例要整体 ×0.01；模型自身朝 +Z（左脚步在 +X 侧）。
- **数值**（`enemy.js` 的 `ENEMY`）：30 HP、走 1.25 m/s、跑 3.0 m/s、视野 15 m、攻击距离 1.9 m、12 伤、攻击冷却 1.6 s、死亡 2.6 s 后隐藏。僵尸攻击片段 2.62 s 太长，用 2× 速播到 1.31 s。
- **玩家挥击**：`J` 键，`startup 0.10 / active 0.12 / recovery 0.22` 三段；命中在 startup 结束那一帧判一次（前伸 1.9 m + 敌人半径、只打正面朝向点积 ≥ 0.35 即 ±70°），前冲 3.4 m/s 带碰撞；命中 20 伤、冷却 0.45 s。主角**还没有真正的攻击动画**，现在靠前冲 + 身前那道斜向弧光（`vfx.slash`）撑读感。
- **受击与波次**：玩家 100 HP，被打 12 点、0.6 s 无敌帧、归零回原点满血；一波清空 2.8 s 后刷下一波，最多 3 波（1/2/3/4 只）。
- **HUD**：游戏行变成 `HP 100 / 100 · 僵尸 1 · 第 1 波 · 收集 0 / 12 · 0.4 s`，被击倒时显示「被击倒 · 重生中」。
- **测试**：`node test/enemyglb.mjs`（14 项）验烘好的 GLB——根节点 scale 为 1、5 条 clip 齐全、每条 ≥150 条轨道、3 个网格拆成 7 个蒙皮图元共 7448 三角、rest pose 髋 1.08 m / 头 1.82 m，并且逐条播一遍确认躯干仍竖直（防「套错坐标系整个人躺倒」这类回归）。`node test/enemy.mjs`（16 项）走回退路径：骨数、占位体格高度与脚底、动作确实在驱动骨骼（手臂骨四元数与 rest pose 的夹角 > 0.05）、追击位移、20 伤存活 / 再 20 伤阵亡播 death、2.6 s 后隐藏。跑法与 `world.mjs`、`physics.mjs` 一样在 `web-preview` 下 `node test/xxx.mjs`。node 里 GLTFLoader 没有 DOM/ImageBitmap，测试先用 20 行把 GLB 的纹理解析掉再喂给它。
- **调试参数**：`?foe=x,z` 把第一只僵尸摆到指定坐标（截图用，默认在 `SPAWNS` 里）。
- **已知缺口**：主角攻击还是 stand-in（没有真正的挥击动画）；还没有关卡化（出生点/出口/开门条件）。

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