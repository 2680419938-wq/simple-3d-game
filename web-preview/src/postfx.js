// 后处理：Bloom（只让高亮区域发光）+ 供光柱用的场景深度图（软粒子式遮挡）。
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

export function createPostFX(renderer, scene, camera, opts = {}) {
  const buf = renderer.getDrawingBufferSize(new THREE.Vector2());
  const rt = new THREE.WebGLRenderTarget(buf.x, buf.y, {
    type: THREE.HalfFloatType, samples: 4, depthBuffer: true,
  });
  const composer = new EffectComposer(renderer, rt);
  const renderPass = new RenderPass(scene, camera);
  composer.addPass(renderPass);
  // 场景 pass 之后立刻取一次 renderer.info，供 HUD 读（后面 bloom/output pass 会重置它）
  const info = { triangles: 0, calls: 0 };
  const baseRender = renderPass.render.bind(renderPass);
  renderPass.render = (r, wb, rb, dt, mask) => {
    baseRender(r, wb, rb, dt, mask);
    info.triangles = r.info.render.triangles;
    info.calls = r.info.render.calls;
  };
  const bloom = new UnrealBloomPass(
    new THREE.Vector2(buf.x, buf.y),
    opts.strength ?? 0.60, opts.radius ?? 0.55, opts.threshold ?? 0.70
  );
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  // 光柱的软遮挡：把场景深度渲到一张半分辨率 RT（只写深度，不写颜色）
  const depthScale = opts.depthScale ?? 0.5;
  const depthTexture = new THREE.DepthTexture(1, 1);
  const depthRT = new THREE.WebGLRenderTarget(1, 1, { depthTexture, depthBuffer: true });
  const depthMat = new THREE.MeshBasicMaterial({ colorWrite: false });
  const depth = { texture: depthTexture, res: new THREE.Vector2(1, 1), near: camera.near, far: camera.far };

  function syncSize() {
    const s = renderer.getDrawingBufferSize(new THREE.Vector2());
    const w = Math.max(1, Math.floor(s.x * depthScale));
    const h = Math.max(1, Math.floor(s.y * depthScale));
    if (depthRT.width !== w || depthRT.height !== h) depthRT.setSize(w, h);
    depth.res.set(s.x, s.y);          // gl_FragCoord 空间（与 composer 主渲染目标一致）
    depth.near = camera.near;
    depth.far = camera.far;
  }

  function renderDepth() {
    syncSize();
    const prevMask = camera.layers.mask;
    camera.layers.set(0);             // 跳过 layer1 的光柱/雾片自身
    scene.overrideMaterial = depthMat;
    renderer.setRenderTarget(depthRT);
    renderer.clear(true, true, true);
    renderer.render(scene, camera);
    renderer.setRenderTarget(null);
    scene.overrideMaterial = null;
    camera.layers.mask = prevMask;
  }

  function resize() {
    composer.setPixelRatio(renderer.getPixelRatio());
    composer.setSize(window.innerWidth, window.innerHeight);
    syncSize();
  }

  resize();

  return {
    depth,
    bloom,
    info,
    setEnabled(on) { bloom.enabled = on; },
    renderDepth,
    render() { composer.render(); },
    resize,
  };
}