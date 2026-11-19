
// 森林场景：加载 Blender 导出的 Forest_Morning.glb，重建晨雾光照，并从枝干生成树干碰撞。
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';

const SKY_TOP = new THREE.Color(0x8fb0c8);
const SKY_HOR = new THREE.Color(0xd7dde0);
const FOG = new THREE.Color(0xbcc8cf);

function skyDome(sunDir) {
  const geo = new THREE.SphereGeometry(400, 32, 16);
  const mat = new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: {
      top: { value: SKY_TOP }, hor: { value: SKY_HOR }, sunDir: { value: sunDir.clone() },
    },
    vertexShader: 'varying vec3 vW; void main(){ vW = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
    fragmentShader: [
      'varying vec3 vW; uniform vec3 top; uniform vec3 hor; uniform vec3 sunDir;',
      'void main(){',
      '  float h = clamp(vW.y * 1.6, 0.0, 1.0);',
      '  vec3 c = mix(hor, top, pow(h, 0.85));',
      '  float s = pow(max(dot(normalize(vW), normalize(sunDir)), 0.0), 6.0);',
      '  c += vec3(1.0, 0.86, 0.68) * s * 0.35;',
      '  gl_FragColor = vec4(c, 1.0);',
      '}',
    ].join('\n'),
  });
  const m = new THREE.Mesh(geo, mat);
  m.frustumCulled = false;
  return m;
}

const MAT_COLOR = {
  Bark: 0x2f2a24, Ground: 0x5f6455, GrassM: 0x6f7c57, BirdSil: 0x0d0f12, Leaf: 0xffffff,
};

export function setupForestLook(scene, renderer) {
  const sunDir = new THREE.Vector3(-0.55, 0.22, -0.8).normalize();  // 低角度晨光（对应 sun_elevation 0.175）
  scene.background = null;
  scene.fog = new THREE.FogExp2(FOG.getHex(), 0.028);
  const sky = skyDome(sunDir);
  scene.add(sky);

  const sun = new THREE.DirectionalLight(0xffeccc, 2.35);
  sun.position.copy(sunDir).multiplyScalar(60);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  const sc = sun.shadow.camera;
  sc.left = -26; sc.right = 26; sc.top = 26; sc.bottom = -26; sc.near = 1; sc.far = 160;
  sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.04;
  scene.add(sun);
  scene.add(sun.target);

  const hemi = new THREE.HemisphereLight(0xbcccd8, 0x3c4234, 0.55);
  scene.add(hemi);
  renderer.toneMappingExposure = 0.98;
  return {
    sun, sunDir, sky,
    setSunDir(d) {
      sunDir.copy(d).normalize();
      if (sky.material.uniforms && sky.material.uniforms.sunDir) sky.material.uniforms.sunDir.value.copy(sunDir);
    },
  };
}

/** 树干碰撞：取每根枝干网格里 y<1.3 m 的顶点，算 XZ 包围盒 */
function trunkBoxes(root) {
  const boxes = [];
  const v = new THREE.Vector3();
  root.updateMatrixWorld(true);
  root.traverse((o) => {
    if (!o.isMesh || !/_Br_|Br_/.test(o.name)) return;
    const pos = o.geometry.attributes.position;
    let minx = 1e9, maxx = -1e9, minz = 1e9, maxz = -1e9;
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
      if (v.y > 1.3) continue;
      if (v.x < minx) minx = v.x;
      if (v.x > maxx) maxx = v.x;
      if (v.z < minz) minz = v.z;
      if (v.z > maxz) maxz = v.z;
    }
    if (minx > maxx) return;
    const w = maxx - minx, d = maxz - minz;
    if (w < 0.05 || d < 0.05) return;      // 退化网格（枝条末端）忽略
    boxes.push({ minx, maxx, minz, maxz, top: 4.0 });
  });
  return boxes;
}

export function loadForest(scene, url, onDone, onErr) {
  const draco = new DRACOLoader().setDecoderPath('/draco/');
  const loader = new GLTFLoader().setDRACOLoader(draco);
  loader.load(url, (gltf) => {
    const root = gltf.scene;
    const dropped = [];
    root.traverse((o) => {
      if (!o.isMesh) return;
      if (o.name === 'Fog' || (o.material && o.material.name === 'MorningFog')) { dropped.push(o); return; }
      o.castShadow = true;
      o.receiveShadow = true;
      o.frustumCulled = false;
      const name = (o.material && o.material.name) || '';
      const base = MAT_COLOR[name];
      const mat = new THREE.MeshStandardMaterial({
        color: base === undefined ? 0xb9bdb4 : base,
        roughness: name === 'Leaf' ? 0.62 : 0.9,
        metalness: 0,
        side: THREE.DoubleSide,
        vertexColors: !!o.geometry.attributes.color,
        transparent: false,
      });
      if (name === 'BirdSil') { mat.color.setHex(0x0d0f12); }
      o.material = mat;
      o.userData.forest = true;
    });
    for (const o of dropped) if (o.parent) o.parent.remove(o);
    scene.add(root);
    onDone({ root, boxes: trunkBoxes(root) });
  }, undefined, onErr);
}
