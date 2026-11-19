
// 屏幕空间体积光（god rays）：先把场景渲到 RT，再朝太阳位置做带衰减的径向采样，
// 树木挡住的地方亮度低 -> 光柱天然被遮挡，比面片假光柱真实。
import * as THREE from 'three';

const VS = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';

const RAY_FS = [
  'uniform sampler2D tScene;',
  'uniform vec2 sunPos;',
  'uniform vec2 resolution;',
  'uniform float density;',
  'uniform float decay;',
  'uniform float weight;',
  'uniform float threshold;',
  'varying vec2 vUv;',
  'void main() {',
  '  vec2 stepv = (sunPos - vUv) * density / 28.0;',
  '  vec2 coord = vUv;',
  '  float illum = 0.0;',
  '  float d = 1.0;',
  '  for (int i = 0; i < 28; i++) {',
  '    coord += stepv;',
  '    vec3 c = texture2D(tScene, clamp(coord, 0.0, 1.0)).rgb;',
  '    float l = dot(c, vec3(0.299, 0.587, 0.114));',
  '    illum += max(l - threshold, 0.0) * d;',
  '    d *= decay;',
  '  }',
  '  gl_FragColor = vec4(vec3(illum * weight), 1.0);',
  '}',
].join('\n');

const COMP_FS = [
  'uniform sampler2D tScene;',
  'uniform sampler2D tRays;',
  'uniform float intensity;',
  'uniform vec3 tint;',
  'varying vec2 vUv;',
  'void main() {',
  '  vec3 c = texture2D(tScene, vUv).rgb;',
  '  float r = texture2D(tRays, vUv).r;',
  '  c += tint * r * intensity;',
  '  gl_FragColor = vec4(pow(max(c * 0.92, vec3(0.0)), vec3(0.4545)), 1.0);',
  '}',
].join('\n');

export function createGodRays(renderer, scene, camera) {
  const rt = new THREE.WebGLRenderTarget(1, 1, { type: THREE.UnsignedByteType });

  const rtRays = new THREE.WebGLRenderTarget(1, 1);


  const rayMat = new THREE.ShaderMaterial({
    vertexShader: VS, fragmentShader: RAY_FS, depthTest: false, depthWrite: false,
    uniforms: {
      tScene: { value: rt.texture }, sunPos: { value: new THREE.Vector2(0.5, 0.8) },
      resolution: { value: new THREE.Vector2(1, 1) }, density: { value: 1.0 },
      decay: { value: 0.94 }, weight: { value: 0.35 }, threshold: { value: 0.55 },
    },
  });
  const compMat = new THREE.ShaderMaterial({
    vertexShader: VS, fragmentShader: COMP_FS, depthTest: false, depthWrite: false,
    uniforms: {
      tScene: { value: rt.texture }, tRays: { value: rtRays.texture },
      intensity: { value: 0.22 }, tint: { value: new THREE.Color(0xfff1da) },
    },
  });
  const quad = new THREE.PlaneGeometry(2, 2);
  const rayScene = new THREE.Scene();
  const rayCam = new THREE.Camera();
  rayScene.add(new THREE.Mesh(quad, rayMat));
  const compScene = new THREE.Scene();
  compScene.add(new THREE.Mesh(quad, compMat));

  const sunWorld = new THREE.Vector3();
  let enabled = true;
  let baseIntensity = 0.22;

  return {
    setEnabled(v) { enabled = v; },
    setSunDir(dir, dist, focus) {
      sunWorld.copy(focus || new THREE.Vector3()).addScaledVector(dir, dist || 120);
    },
    setIntensity(v) { baseIntensity = v; compMat.uniforms.intensity.value = v; },
    setThreshold(v) { rayMat.uniforms.threshold.value = v; },
    resize() {
      const s = renderer.getSize(new THREE.Vector2());
      const w = Math.max(1, Math.floor(s.x * 0.75)), h = Math.max(1, Math.floor(s.y * 0.75));
      rt.setSize(w, h); rtRays.setSize(w, h);
      rayMat.uniforms.resolution.value.set(w, h);
    },
    render(cameraTarget) {
      if (!enabled) { renderer.setRenderTarget(null); renderer.render(scene, cameraTarget); return; }
      // 太阳方向的投影：在相机后方就不加光柱
      const p = sunWorld.clone().project(cameraTarget);
      const behind = p.z > 1 || p.z < -1 || Math.abs(p.x) > 3 || Math.abs(p.y) > 3;
      renderer.setRenderTarget(rt);
      renderer.render(scene, cameraTarget);
      rayMat.uniforms.sunPos.value.set(p.x * 0.5 + 0.5, p.y * 0.5 + 0.5);
      renderer.setRenderTarget(rtRays);
      renderer.render(rayScene, rayCam);
      compMat.uniforms.intensity.value = behind ? 0 : baseIntensity;
      renderer.setRenderTarget(null);
      renderer.render(compScene, rayCam);
    },
  };
}
