# 简单 3d 游戏

一个可以直接进引擎的 3D 角色资产工程：Q 版龙人武士（DragonMan），标准 Mixamo 命名骨架、T/A-Pose 双版、
Idle / Run / Walk 三个动作、全身关节过渡几何，外加一个"把任意动作库的 FBX 套到这个角色上"的导入器。

角色素材来自 Sketchfab 的 *Dragon men Character for game*（作者 ohmmi5955，CC-BY 4.0），
本仓库做的是骨骼标准化、关节过渡、动作重定向与预览工具的工程化改造。

## 目录

| 路径 | 内容 |
| --- | --- |
| `dragon-man-final/` | **成品 GLB**（4 个）：T-Pose / A-Pose / Walk（含 Idle）/ 一个示例导入动作 |
| `AnimLib/` | **动作导入器**：把 Mixamo 等标准命名人形 FBX/BVH 重定向到本角色 |
| `web-preview/` | three.js 网页预览（Vite），能播动作、切 LOD |
| `dragon-men-rebuild/` | 生成管线脚本（Blender Python）：骨架改名、A-Pose、关节袖套、动作重定向、导出与验收 |
| `导入动作.cmd` | 一键导入：把 FBX 丢进 `AnimLib/in/` 双击即可 |
| `启动预览.cmd` | 一键起本地预览服务 |

## 快速上手

**看模型**：双击 `启动预览.cmd`，浏览器打开 http://127.0.0.1:5199/
带参数（`?demo=walk` 播走路、`?lod=1|2` 切 LOD、`?glb=/DragonMan_Std_Walk.glb` 换文件）。

**进引擎**：直接把 `dragon-man-final/DragonMan_Std_TPose.glb`（建模态）或 `DragonMan_Std_Walk.glb`（含 Idle+Walk）拖进
Unity / Unreal / Godot / Blender。70 根骨、4 个材质、12 张 JPEG 贴图、约 5.9 万三角。

**套动作**：
```
把 Mixamo 下载的 FBX（勾 In Place）放进 AnimLib\in\  ->  双击 导入动作.cmd
```
产物：`AnimLib\out\DragonMan_Std_<动作名>.glb`（含 Idle/Run/Walk + 新动作），
同时复制到 `dragon-man-final/` 与 `web-preview/public/`，命令行会打印预览地址。

## 角色指标（实测）

- 身高 2.010 m，脚底 y=0，轴心在双脚踝中点；面向 +Z，Y-up，1 单位 = 1 米
- 70 根骨，全部 Mixamo 命名（`mixamorig:` 前缀），含 4 指 × 3 节 × 左右 = 24 根指骨、12 根尾骨
- 身体 26,718 顶点 / 76 个网格岛（分件拼装资产），成品三角数 5.88 万，四档 LOD 到 1.16 万
- 动作：Idle 4.000 s / Walk 1.0667 s（33 帧）/ Run 0.600 s；逐帧蒙皮最低点 ≥ 0

## 已知限制

- 腿长 0.4548 m（身高的 22%），写实人类动作套进来会深蹲、步幅被压缩 —— 选步幅小、频率快的动作
- 手指/脚趾是刚性小岛，弯指节没有皮肤褶皱（资产结构，不是 rig 问题）
- 源动作里没有的骨不会被驱动：小指、眼、下颌；尾巴由程序摆动接管

## 许可

角色资产 CC-BY 4.0（© ohmmi5955，出处 Sketchfab），使用时请保留署名。详见 `LICENSE`。
