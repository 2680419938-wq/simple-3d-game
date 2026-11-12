# web-preview · three.js 第三人称验证

用途：把 `dragon-men-game` 交付的三个 GLB 丢进实时渲染器，验证资产在真实引擎条件下是否成立
（比例、朝向、材质、动画、LOD 档位、第三人称相机），不是游戏本体。

## 跑起来

```
cd web-preview
pnpm install
pnpm dev            # http://localhost:5199
```

## 操作

- `WASD` / 方向键：移动（相机相对方向）
- `Shift`：跑（6 m/s），松开为走（2.2 m/s）
- 鼠标左键拖拽：转视角；滚轮：拉近拉远

## URL 参数（截图/证据用）

| 参数 | 作用 |
|---|---|
| `?demo=walk` | 自动前进，输出 WALK 状态 |
| `?demo=run` | 自动奔跑 |
| `?lod=1` / `?lod=2` | 装载 LOD1 / LOD2 替换 LOD0 |

## 已验证

- `DragonMan_Game.glb` / `_LOD1` / `_LOD2` 三个文件都能加载、播放 `Idle_Lively`（4.03s）、阴影正常
- 朝向 +Z、脚底 y=0、站立身高 2.010 m（旧版 2.7 m 是卷起尾巴的顶端），导入即站立在地面，无需改坐标系或缩放
- 角色移动时模型朝移动方向转身（`Object3D.lookAt` 系 +Z 语义，与资产朝向一致）
- LOD0 53,012 三角 / LOD2 11,655 三角（HUD 里 tri 数是渲染三角形数，含阴影 pass，约为面数 ×2）

## 已知限制（不是 bug，是这版验证的范围）

- **只有 Idle 动画**：走/跑是位移驱动，没有 walk/run 动作，所以腿是滑的（这也是当前资产最大的缺口）
- **没有物理**：地面是平面，没有重力、碰撞、斜坡、台阶
- **尾巴挡镜头**：尾巴向 -Z 伸 1.6m、整体占地约 2.5 × 2.7m，默认相机（后左 3/4、距离 4.9m、俯角 15°）
  在转身时会被尾巴扫到画面；正式第三人称相机需要更高、更远，或加弹簧臂碰撞
- 没有 LOD 自动切换、没有后处理、没有动画状态机（`AnimationMixer` 直接播单条 clip）

截图：`shot-idle.png` / `shot-run.png` / `shot-lod2.png`（Edge headless，1600×900，SwiftShader 软渲染）
