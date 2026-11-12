DragonMan 标准角色包（dragon-man-final）
==========================================

三件文件，都是 glTF 2.0 二进制 .glb，直接拖进 Unity / Unreal / three.js / Blender(导入 glTF) 即可。

1) DragonMan_Std_TPose.glb  10,281,104 B   标准 T-Pose，含 Idle_Lively 待机动画
2) DragonMan_Std_APose.glb   9,898,092 B   标准 A-Pose（双臂下倾 45°），无动画，适合绑装备/改模
3) DragonMan_Std_Walk.glb   10,372,644 B   Idle_Lively + Walk 两段动画（游戏用这个）

规格
- 骨骼：70 个关节，24 根手指骨（每指 3 节），命名全部 Mixamo 风格（mixamorig: 前缀），
  可直接与 Mixamo 动画重定向；无 jaw / eye / brow 骨，无 shape key。
- 尺寸与坐标：1 单位 = 1 米，站立身高 2.010 m；面向 +Z，Y 轴向上；
  轴心 = 双脚踝水平中点，落在世界原点 (0,0)，脚底 y = 0。
- 网格：DragonMan_Body 等 7 个网格，4 个材质，12 张 JPEG 贴图（内嵌）。
  三角面：TPose / APose 58,852，Walk 57,800（删掉了会穿地的护膝甲片）。
- 动画：Idle_Lively 121 帧，Walk 33 帧 / 1.0667 s / 首末帧一致可循环；
  逐帧最低顶点 ≥ 0（Walk 最差 +0.15 mm，Idle 最差 +3.8 mm），不穿地。
- 关节过渡：膝、肩、肘、腕、髋、颈、腰共 13 处补了过渡几何与权重渐变，
  手指 24 个关节全部加了指节袖套，弯曲 0/30/60/90° 无破洞。

注意
- 根节点 DragonMan_Rig 带 scale 1.5（Blender 导出的历史遗留），世界尺寸已正确，
  引擎里若按节点局部数值硬算位移需要乘/除 1.5，直接播放动画不受影响。
- 版权：原始模型 "Dragon men Character for game" by ohmmi5955，CC-BY 4.0，
  商用请保留署名。
