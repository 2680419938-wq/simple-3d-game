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
- **调试参数**：`?pos=x,z` 指定落点、`?dist=`/`?pitch=`/`?yaw=`/`?fov=` 定视角、`?nolock=1` 关指针锁定（无头截图用）、`?jump=1&jd=<ms>` 自动起跳。

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
- **玩家攻击**：`J` 键。动作是 Mixamo「Mutant Punch」重定向到异形 CC 骨架上的一段真片段（源片 34 帧 @30 fps = 1.13 s，导出后取第 3–19 帧 = 0.67 s，播放 1.10 倍速 → 0.61 s），不再是「只有弧光的前冲」：
  ```bash
  blender -b --python AnimLib/alien_clip_add.py -- --fbx 'AnimSource/mutant_punch/Mutant Punch.fbx' \
          --name Attack --src dragon-man-final/Alien_Walk_Jump_2k.glb --out <out.glb> --inplace
  ```
  时间轴按片段自己的节奏对齐：源片第 11 帧（导出片段第 8 帧，`(8-3)/24 = 0.21 s ÷ 1.10` = **0.19 s**）右爪甩到最前——离髋 0.61 m、肩到掌 0.577 m（等于静止时的满伸长度，手臂是直的）→ `startup 0.19 / active 0.16 / recovery 0.26`，命中判定与身前那道斜向弧光（`vfx.slash`）都在这一刻触发。前冲 2.2 m/s 只跑 startup+active 两段，且**贴到僵尸身上就停**（角色与僵尸之间没有碰撞体，否则会冲进去穿模）。
  命中范围：前伸 1.9 m + 敌人半径、只打正面朝向点积 ≥ 0.35（±70°）；20 伤、冷却 0.30 s。攻击期间 locomotion 让出权重（`if (atkT > 0)` 跳过 `setAnim`），片段播完由 `setAnim(want, 0.18)` 混回走/跑/站。
- **为什么要裁帧 + 变速**：源片是「架势 → 甩臂掠过身前 → 慢慢收势」，尾巴占了 1/3 的时长（第 23 帧后基本回到起点），直接播会拖到没法打。只留第 3–19 帧再去掉长尾，1.10 倍速压到 0.61 s。逐帧量的是「肩到掌距离 + 掌相对髋的前后位移」：第 8 帧前后位移 0.61 m 且手臂满伸，是最前的一刻。
- **源 FBX 带蒙皮怎么办**：`Mutant Punch.fbx` 是 With Skin 下载（63 骨 + 3 个网格 + 4 张 2K 贴图）。`alien_clip_add.py` 在导入后先删掉除 mixamo 骨架外的所有对象，否则整套网格会被一起导进主 GLB；`inspect_fbx.py` 报「网格 3(7448 tri)」就是这个信号。
- **僵尸动作的连贯性（已修）**：四条症状与根因——
  1. **走路/跑步会「重置」**：烘出来的片段带着 Mixamo 根位移（走一个周期髋部前移 1.28 m、跑 2.30 m），播到最后一帧瞬移回起点。`stripRootDrift()` 按线性斜坡把净位移扣掉（左右摆动与上下起伏都留着），同时返回片段自己的「设计地速」（走 0.31 m/s、跑 2.75 m/s），播放速率取 `移动速度 / 设计地速` 对齐脚——原来的 `walkSpeed 1.25` 对 0.31 m/s 的片段是 4 倍打滑，现已降到 0.90 m/s（≈2.9 倍速播放）。没用 `crossFadeTo(..., warp=true)`：它会在淡入结束把 timeScale 覆回 1，脚又开始滑。
  2. **打几下就彻底不动**：攻击片段是 `LoopOnce + clampWhenFinished`，播完是 `paused` + 定格在末帧；而 `play()` 见到 `cur === name` 就直接 return，于是第二次起手只是把同一段已结束的 action 再 `play()` 一次——永远定格。现在 `play()` 对 once 片段判 `!isRunning()` 就 `reset()` 重播，并且攻击结束、贴脸等冷却时补播 `idle`，不留上一刀的定格姿势。
  3. **走来走去像卡带**：走/跑在 6 m 边界上、`idle/walk` 在 1.71 m 线上都会逐帧互切，而每次切换都 `reset()` 片段。现在走/跑之间留 5.5–7 m 滞回带，贴脸停步线在「已在走」时放宽到 1.43 m。
  4. **改成原地抽搐**：第 1 条修完后，GLB 里的走/跑变成疯狂抖动。根因是设计地速按 `Math.hypot(dx, dz)` 算的净位移——原始 FBX 里 Mixamo 的根位移落在髋骨轨道的 **z** 分量上，烘进 GLB 后髋骨朝向不同，同一段位移跑到轨道的 **y** 分量上，于是 `dz ≈ 0`、设计地速算成 2.7e-8 m/s，播放速率 `0.90 / 2.7e-8` 变成三千万倍速，每帧跳几百个循环。现在三个分量一起取模（`Math.hypot(dx, dy, dz)`），并把速率夹在 0.25–4 之间兜底；`test/enemyglb.mjs` 直接对 GLB 片段断言设计地速 0.31 / 2.75 m/s、`walkSpeed / 设计地速 < 4`、剥离后整周期髋部无单帧瞬移（循环接缝 2.7 cm）。
  前三条都在 `test/enemy.mjs` 留了回归（现 24 项）。修之前实测：连打时 515/720 帧动作停住、抖动带里 239 次逐帧切换、循环接缝处髋部每帧跳 124.2 cm；修完三项均为 0。
- **主角受击动作**：Mixamo「Zombie Reaction Hit」重定向到异形骨架（源片 53 帧 @24 fps = 2.17 s，取第 9–33 帧 = 1.0 s，播 1.9 倍速 → 0.53 s）：
  ```bash
  blender -b --python AnimLib/alien_clip_add.py -- --fbx 'AnimSource/hit_react/Zombie Reaction Hit.fbx' \
          --name Hurt --src dragon-man-final/Alien_Walk_Jump_2k.glb --out <out.glb> --inplace
  ```
  状态机优先级是 **attack > hurt > jump > locomotion**：受击时立刻交叉淡入（0.05 s），挥击中不打断（`atkT > 0` 时跳过受击片段，只扣血），片段播完用 `setAnim(want, 0.22)` 混回走/跑/站。受击期间不能出刀。
- **为什么受击必须加 `--inplace`**：这条动作在 Mixamo 页面勾了 In Place，实测**没去掉**——逐帧量 hips 从 y=0.01 漂到 0.80（向后退了 0.8 m），于是 `inspect_fbx.py` 的「原地」判定也漏掉了它（只看部分分量，别拿它当唯一依据）。`alien_clip_add.py` 的 `--inplace` 在算完 `TWN` 之后把根位移的 x/y 归零、保留竖直起伏；重定向后逐帧量 `CC_Base_Hip_02` 的水平漂移 = **0.000**，头高 1.746 → 1.580（第 25 帧弯到最低）→ 1.731。
- **受击与波次**：玩家 100 HP，被打 12 点、0.6 s 无敌帧（同时是受击片段的播放窗口）、归零回原点满血；一波清空 2.8 s 后刷下一波，最多 3 波（1/2/3/4 只）。
- **HUD**：游戏行变成 `HP 100 / 100 · 僵尸 1 · 第 1 波 · 收集 0 / 12 · 0.4 s`，被击倒时显示「被击倒 · 重生中」。
- **测试**：`node test/enemyglb.mjs`（14 项）验烘好的 GLB——根节点 scale 为 1、5 条 clip 齐全、每条 ≥150 条轨道、3 个网格拆成 7 个蒙皮图元共 7448 三角、rest pose 髋 1.08 m / 头 1.82 m，并且逐条播一遍确认躯干仍竖直（防「套错坐标系整个人躺倒」这类回归）。`node test/enemy.mjs`（16 项）走回退路径：骨数、占位体格高度与脚底、动作确实在驱动骨骼（手臂骨四元数与 rest pose 的夹角 > 0.05）、追击位移、20 伤存活 / 再 20 伤阵亡播 death、2.6 s 后隐藏。跑法与 `world.mjs`、`physics.mjs` 一样在 `web-preview` 下 `node test/xxx.mjs`。node 里 GLTFLoader 没有 DOM/ImageBitmap，测试先用 20 行把 GLB 的纹理解析掉再喂给它。
- **调试参数**：`?foe=x,z` 把第一只僵尸摆到指定坐标（截图用，默认在 `SPAWNS` 里）；`?atk=1` 自动连挥（HUD 额外显示 `cur / atkT / hit / 僵尸数`，用来验状态机）；`?noatk=1` 退回旧版「无片段，只有弧光 + 前冲」，专门拍前后对照；`?hurt=1` 每 0.6 s 循环播一次受击（扣 0 HP，截图用），配合 `&clip=hurt&freeze=<秒>` 可以定格看单帧。
- **贴图与过曝**：真贴图下敌人的受击闪白会整只过曝成橙色，`setFlash` 的 emissive 增量从 0.7 收到 0.34、强度从 1.6 收到 0.8、衰减从 4/s 提到 6/s（0.17 s），现在只是「亮一下」。
- **已知缺口**：主角借的是变异体的勾拳——手臂在胸前横扫、不是直线刺出，从正前方看会读成「双爪抱在胸前」，从追尾镜头看是「爪子扫过身前」；换更直的动作只需换 `--fbx` 与裁剪帧号。还没有关卡化（出生点/出口/开门条件）。
- **证据图**：`_shots/combat/CMP_hurt.png`（起手 / 头后甩 / 上身后仰 / 与僵尸同框四格）、`_shots/combat/CMP_attack.png`（上排旧 vs 新同机位，下排 4 个关键帧）、`_shots/combat/CMP_zombie.png`（占位体格 vs 真蒙皮网格）。

### 技能特效（demo 移植）

技能视觉来自 [ThreeJSVFX-Demo](https://github.com/mohamedachrefelouafi)（MIT，见「许可与署名」）：33 个文件整块复制到 `web-preview/src/fx/`，并保持 demo 的相对目录层级，所以 import 路径一行都不用改。只搬了管线需要的部分（`abilities/` 10 个技能 + `materials/` 10 个材质 + `particles/` + `effects/` + `core/` + `gameplay/abilityProfiles.js`），demo 的 App / 编辑器 / 世界没有搬。

- **接线**：`web-preview/src/skills.js` 装配 demo 每个技能都要的共享服务（`ParticleEngine / LightPool / DecalSystem / FissureSystem / BurstSystem / CameraShake / ScreenFlash`），适配层 `Combat` 照抄 demo 的 `beginCast / onAbilityImpact / updateAbility / endCast` 语义，只把命中查询从 demo 的 EnemyManager 换成我们的僵尸数组（`_sphere` 与「点到线段距离 + 半径按 t 插值」的 `_line`），扣血走 `enemy.hurt()`。伤害取自 `fx/gameplay/abilityProfiles.js`：冰枪 80 / 雷枪 75，都是线形命中。
- **四个必须踩的坑**（缺一个效果就不出现）：
  1. `environment.registerShadowCasterWithPatch()` **不能是空实现**。demo 的 Environment 里它只做一件事——把补丁串到材质的 `onBeforeCompile` 上。我们一开始传了 no-op，结果 `createIceMaterial` 的整段补丁（体色、裂纹、边缘辉光、透明）全被丢掉，晶体渲染成不透明白塑料。现在按 demo 的 `patchOnBeforeCompile` 链式挂载，并给每个材质一个唯一的 `customProgramCacheKey`（three 默认用 `onBeforeCompile.toString()` 当键，两个闭包源码相同就会被合并成同一个程序）。
  2. 特效挂在 `LAYER.VFX`(1) 上，而 `camera.layers.enable(1)` 原来只写在 `useForest` 分支里 → 竞技场里闪电、粒子、地面贴花全部隐形。现在在 `main.js:31` 无条件打开。
  3. 所有特效材质的软边都靠 `softFade(frame.uSceneDepth, ...)`。本项目还没有打包深度的 prepass，`uSceneDepth` 为 null 时采样到 `(0,0,0,0)` → `unpackRGBAToDepth(0)=0` → 判成「被遮挡」→ alpha 恒为 0。占位贴图**必须解包出深度 1.0**：`DataTexture([255,0,0,0])` 刚好是 1.0；给 `[255,255,255,255]` 会算出 1.0039，`perspectiveDepthToViewZ` 翻成正数，软边又变成 0。
  4. 森林的 `FogExp2` 会把 10 m 外的特效洗成白色（demo 场景没有雾），所以每次 `cast` 之后对技能子树做一遍 `noFog()`。
- **技能池只有四个**：`ice 冰枪 / thunder 雷枪 / beam 光柱 / phoenix 凤凰`。另外六个逐个实测过：`void` 只有一条光带；`snare / glacier / meteor` 只出地面白烟、主体几何不出现（三者的 mesh 都 `frustumCulled = false` 且在 VFX 层，所以不是裁剪或层的问题，根因还没查）——暂不进池。
- **调试参数**：`?skill=<元素>` 进场自动放一次；`&skillhold=<秒>` 先按 60 Hz 手动推进到该相位再冻结（无头截图只能推进 0.4 s，靠它拍中段）；`?reach=<米>` 改距离；`?unlock=1` 直接填满四个槽；`?cards=2` 摆一张选卡界面；`?xp=<n>` 预置经验。
- **证据图**：`_shots/skills/CMP_skills.png`（冰枪命中 / 雷枪命中 / 森林冰枪 / 森林雷枪四格，其中两张 HUD 读 `僵尸 0 活` = 伤害真的结算了）、`_shots/skills/pg_cards.png`（升级选卡）、`pg_slots.png`（四槽 + 光柱）。

### 成长与技能槽（roguelite）

割草循环：**击杀 → 升级 → 抽 3 张卡 → 技能变强 / 解锁新技能 → 无限波次的僵尸**。逻辑在 `web-preview/src/progression.js`（纯数据层，不 import three，node 能直接测），`main.js` 只做接线，选卡界面是 `index.html` 里的 `#cards` 覆盖层。

- **等级**：升到下一级要 `needFor(level) = 6 + 2 × level` 个击杀（1 → 2 级 8 个），余量保留。**试玩按键**：`L` 直接升一级并弹卡、`K` 免费解锁下一个技能（不计击杀，随时可用）。升级时整个世界暂停（`update()` 直接 return），抽 3 张卡，按 `1 / 2 / 3` 或点鼠标选一张；一次多杀连升多级会排队，选完一张接着弹下一张。
- **技能槽**：4 个，起手只有冰枪，其余三个靠解锁卡。`1–4` 对应槽位，HUD 尾部按槽位显示 `[1] 冰枪 就绪 · [2] 雷枪 1.4s · [3] 空`，不用记哪个键对哪个技能；屏幕底部有常驻按键条（`index.html` 的 `#keys`）。
- **卡池**：解锁（**有空槽时必出至少一张**，否则技能永远凑不满）/ 单体伤害 +25% / 单体冷却 ×0.85 / 全体伤害 +12% / 全体冷却 ×0.90。满槽后不再出解锁卡，且**保证至少一张伤害卡**（避免连续抽到只有冷却的牌）。冷却乘子有下限 `CARD.minCooldown = 0.35`。
- **乘子怎么生效**：伤害乘子在 `cast()` 那一刻写进 `combat.dmgMul[element]`（`skills.js`），所以已经在飞的技能不会被之后的卡强化；冷却乘子直接乘在 `settings[element].cooldown` 上。
- **无限波次**：`spawnWave()` 每波 `min(2 + wave, 8)` 只、血量 `× (1 + 0.22 × (wave - 1))`（`enemy.js` 构造参数 `hpScale`），清场 2.2 s 后刷下一波——原来「最多 3 波」的上限已去掉。按 R 重开会连成长一起重置。
- **测试**：`node test/progression.mjs` 19 项全 PASS（升级余量、有空槽必出解锁卡、满槽不出解锁卡且必有伤害卡、乘子叠加与下限、卡面文案、`grantLevel` 只 +1 级）；原有 world 11 / physics 5 / enemy 24 / enemyglb 18 不变。
- **还没做的**：数值平衡（现在僵尸 30 HP、冰枪 80 伤，一张卡就秒）、更多卡种（范围 / 暴击 / 吸血 / 移速）、死亡结算（现在 HP 归零只是原地重生 1.4 s）。

### 视角与操控（已优化）

原来看起来「不方便」是三件事叠在一起：视野窄（fov 48）、必须按住左键才能转视角（松手就停）、贴着树干时镜头钻进树皮。全部在 `web-preview/src/main.js`：

- **视野** 48° → **60°**，追尾镜头下侧后方来的僵尸不再被切出画面。
- **指针锁定**：点画面即锁定鼠标，之后直接移动鼠标转视角，按 `Esc` 退出；没锁定前仍可按住左键拖拽（对截图/触摸也留了这条路）。`?nolock=1` 关掉锁定，自动化截图必须带它。
- **滚轮缩放**：`rig.dist` 2.2–10 m。
- **俯仰范围**放宽到 −0.22（略仰视）…1.15 rad，原来只能俯视，看不到远处的怪。
- **跑起来镜头自动拉远**：`dist + min(speed, 5) × 0.32`，冲刺时最多多 1.6 m。
- **遮挡避让**：从角色胸口沿相机方向打一条射线，打到树干/高箱体就把相机收到命中点前 0.12 m；缩立即生效（否则一帧就穿进树干），放回用 `dt × 2.5` 慢插值避免抖动。矮箱子（顶面 < 1.4 m）不参与——站上去时它的顶面不该把镜头顶到角色背上。
- **抖动**：技能镜头抖动（`skills.shakeRig`）叠在平滑后的基准位姿上，不参与插值，所以不会累积漂移。
- **代码/测试**：遮挡数学抽到 `web-preview/src/camera.js`（`rayBox` / `clearDistance`，纯函数不 import three），`node test/camera.mjs` 15 项全 PASS：空场不缩距离、树干在近面截断、超出视距忽略、矮箱子不挡、偏轴不挡、斜向命中、相机半径影响、起点在盒内返回 ~0、多树取最近、仰视越过矮树不挡。
- **软锁定（战斗镜头）**：站定不动或正在出手时，镜头缓缓转向 11 m 内最近的活僵尸；一按 WASD 就交还控制权（避免镜头替你拐弯）。手动转视角后 1.2 s 内完全不抢。权重按 `dt × 2.4` 爬升，转动速度上限 `2.6 rad/s × 权重`，走最短弧（`approachAngle`），因此是「跟过去」而不是「瞬移对准」。出手瞬间如果锁定的那只在 4 m 内，角色会先转向它再挥（`startAttack` 里的 `modelYaw`），不会朝空气挥。HUD 出现 `· 锁定` 表示正在生效。`?aim=<倍率>` 调快慢、`?noaim=1` 关掉、`?foes=<n>` 覆盖每波数量（截图摆位用）。注意无头 Edge 的 `--virtual-time-budget` 只推进 0.1–0.5 s 应用时间，拍对比图时用 `?aim=60` 让它在这么短的时间里收敛，实机是 2.6 rad/s。
- **证据图**：`_shots/skills/CMP_cam.png`（同一机位、同一场景，左 fov 48 右 fov 60）、`_shots/skills/CMP_aim.png`（同一机位，左无软锁定右有，僵尸在 90° 侧后方）。

### 音效（程序化合成）

原来整个项目里**一个音频文件都没有**（全仓 `*.mp3/ogg/wav/m4a/flac` 匹配 0 个，代码里也没有 `AudioContext`），技能、挥击、脚步全是静音的。现在补上，做法是**全部用 WebAudio 现场合成**，不引入任何音频素材：零授权风险、零体积、不依赖网络（本项目其它素材都要从 Mixamo 下来再烘，音效不必），也和「特效全程序化」的路线一致。

- **代码**：`web-preview/src/audio.js`。上半是纯数据 + 纯函数（`SOUNDS` 表、`castSound`/`impactSound` 映射、`attenuation`/`panFor`、`VOICES` 并发上限），可被 node 直接测；下半 `createAudio()` 懒建 `AudioContext`（浏览器自动播放策略：首次点击/按键才建），无 `AudioContext` 的环境（node、老浏览器）所有调用退化成空操作。
- **19 个音效**：`jump` `land` `step` `swing` `hit` `hurt` `die` `growl` `pickup` `levelup` `click` + `cast_{ice,thunder,beam,phoenix}` + `impact_{ice,thunder,beam,phoenix}`。声部用固定种子噪声（`noiseBuffer` 的 LCG）+ 正弦/三角/锯齿振荡器 + 包络拼：冰是高频 ring + 冷气扫 + 碎冰五连击，雷是噼啪 + 低频轰鸣，光柱是锯齿上升 + 带通，凤凰是火焰上扬噪声，受击用 210/233 Hz 微失谐出痛感，升级是 523/659/784/1046 琶音。
- **混音**：master(0.55) → `DynamicsCompressor`(−12 dB, 6:1) → 输出，留足余量。距离衰减 `1/(1+0.09d)`，声像 `clamp(dx/12, ±1)`（听者取相机位置与 yaw，右向量 `(cos yaw, −sin yaw)` 与 `update()` 里的 `right` 同式）。
- **防糊**：`VOICES` 给同名音效设并发上限（`land` 2 / `hit` 4 / `growl` 3 / `die` 4 / `step` 2 / `pickup` 3，其余 6）；同名最小间隔 `step` 0.06 s、其余 0.02 s，一屏僵尸同时倒地不会叠成噪音。
- **接线点**（全在 `main.js`）：起跳 `jump`、落地 `land`（`rate` 按落速 0.45–1.4）、脚步 `step`（间隔 `clamp(0.62 − speed×0.055, 0.22, 0.6)`）、挥击 `swing`、命中 `hit` + 击杀 `die`、玩家受击 `hurt`、僵尸咬人 `growl`、拾取 `pickup`、升级 `levelup`、选卡 `click`、施法 `castSound(element)`、技能命中 `impactSound(element)`。
- **音量平衡（实测峰值，同 play() 口径）**：`hit` 0.195 / `impact_thunder` 0.212 / `land` 0.164 / `cast_thunder` 0.174 最响，`jump` 0.069、`step` 0.035、`swing` 0.026 最轻——**频繁音故意压低**（脚步每 0.3 s 一次、挥击每 0.6 s 一次，和命中同响会很快听累）。全部 < 0.25，没有削波。调音时的两处修正：`jump` 原来比落地小 7 倍（起跳基本听不见，声部峰值 0.25 → 0.70）、`renderProbe` 原来漏乘 `SOUNDS.gain`（读数偏高，和实际混音口径不一致）。
- **操作**：`M` 静音（HUD 显示 `· 静音(M)`）；`?mute=1` 启动即静音。
- **验证**：`node test/audio.mjs` 11 项 PASS（每个音效 dur/gain 合法且 gain ≤ 0.7、四个元素的 cast/impact 都在、未知元素回落 `swing`/`hit`、衰减单调、声像夹紧、`panFor(6) = 0.5`、并发上限存在）。另外两个只给自动化用的参数：`?audioprobe=1` 用 `OfflineAudioContext` 把 19 个音效离线渲一遍，把时长/峰值/RMS 打到屏幕左上（`#probe`）；`?audiotest=1` 走真实 `play()` 路径打 `ready/state/played/rejected/live`。无头 Edge 里要加 `--autoplay-policy=no-user-gesture-required`，否则 `AudioContext` 一直是 `suspended`、探针读数全是 0。
- **证据**：`_shots/audio/final.png`（1000×760：19 行探针读数 + 右下 `audiotest ready=true state=running played=6 rejected=0`）。

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
- **技能特效**：*ThreeJSVFX-Demo* by **mohamedachrefelouafi**，授权 **MIT**（许可原文见 `web-preview/src/fx/LICENSE`）。`web-preview/src/fx/` 是该项目 `src/` 的部分文件逐字复制，本项目新增的只有接线层 `web-preview/src/skills.js`。

使用本项目时请保留以上两行署名。