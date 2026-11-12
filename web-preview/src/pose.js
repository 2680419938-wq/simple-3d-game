
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const params = new URLSearchParams(location.search);
const view = params.get('view') || 'front';
const file = params.get('file') || '/DragonMan_Game.glb';
const tag = document.getElementById('tag');

const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c'), antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(1);
renderer.setClearColor(0x15181d);

const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xbfd4f0, 0x20242c, 1.5));
const d1 = new THREE.DirectionalLight(0xffffff, 2.6); d1.position.set(4, 8, 6); scene.add(d1);
const d2 = new THREE.DirectionalLight(0x93b4ff, 1.0); d2.position.set(-6, 3, -4); scene.add(d2);

const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
const aspect = innerWidth / innerHeight;

// vertical guide at the model origin (x=0,z=0) and a ground line
scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
  [new THREE.Vector3(0, -0.5, 0), new THREE.Vector3(0, 3.2, 0)]),
  new THREE.LineBasicMaterial({ color: 0x3ea6ff })));
const groundLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(
  [new THREE.Vector3(-7, 0, 0), new THREE.Vector3(7, 0, 0)]),
  new THREE.LineBasicMaterial({ color: 0x8b96a8 }));
scene.add(groundLine);

function frame(bb) {
  const cz = bb.getCenter(new THREE.Vector3());
  const h = bb.max.y - bb.min.y;
  const w = Math.max(bb.max.x - bb.min.x, bb.max.z - bb.min.z);
  const fr = Math.max(h, w / aspect) * 0.58;
  cam.left = -fr * aspect; cam.right = fr * aspect; cam.top = fr; cam.bottom = -fr;
  cam.updateProjectionMatrix();
  const d = 20;
  if (view === 'front') cam.position.set(cz.x, cz.y, cz.z + d);
  else if (view === 'back') cam.position.set(cz.x, cz.y, cz.z - d);
  else if (view === 'side') cam.position.set(cz.x + d, cz.y, cz.z);
  else cam.position.set(cz.x + d * 0.7, cz.y + d * 0.18, cz.z + d * 0.7);
  cam.lookAt(cz);
  groundLine.position.y = bb.min.y;
  tag.textContent = view.toUpperCase() + ' · rest pose (no animation) · ' + file.split('/').pop()
    + ' | bbox h=' + h.toFixed(2) + ' w=' + w.toFixed(2) + ' | feet y=' + bb.min.y.toFixed(3)
    + ' | guide = vertical through origin';
}

new GLTFLoader().load(file, (gltf) => {
  const m = gltf.scene;
  scene.add(m);
  m.updateMatrixWorld(true);
  const bb = new THREE.Box3().setFromObject(m);
  frame(bb);
  window.__ready = true;
}, undefined, (e) => { tag.textContent = 'load error ' + e.message; });

tag.textContent = 'loading ' + file.split('/').pop() + ' …';
(function loop() { requestAnimationFrame(loop); renderer.render(scene, cam); })();
