// One-click static server for the built preview (dist/).
// Usage: node tools\serve.mjs [--port 5199] [--root dist] [--no-open]
import { createServer } from 'node:http';
import { createReadStream, statSync, existsSync, copyFileSync, readdirSync } from 'node:fs';
import { extname, join, normalize, resolve } from 'node:path';
import { spawn } from 'node:child_process';

const argv = process.argv.slice(2);
const argOf = (name, def) => {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : def;
};
const ROOT = resolve(argOf('--root', join(import.meta.dirname, '..', 'dist')));
const START_PORT = Number(argOf('--port', process.env.PORT || 5199));
const OPEN = !argv.includes('--no-open') && !process.env.PREVIEW_NOOPEN;

// dist 里若是构建时缺少模型文件（或有人清过目录），从 dragon-man-final 补齐
const ASSET_SRC = resolve(ROOT, '..', '..', 'dragon-man-final');
function ensureAssets() {
  if (!existsSync(ASSET_SRC)) return;
  for (const f of readdirSync(ASSET_SRC)) {
    if (!f.toLowerCase().endsWith('.glb')) continue;
    const dst = join(ROOT, f);
    if (!existsSync(dst)) {
      copyFileSync(join(ASSET_SRC, f), dst);
      console.log('  + 补齐资源 ' + f);
    }
  }
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json',
  '.bin': 'application/octet-stream',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.wasm': 'application/wasm',
  '.hdr': 'application/octet-stream',
  '.ktx2': 'image/ktx2',
};

if (!existsSync(join(ROOT, 'index.html'))) {
  console.error('[x] 找不到 ' + join(ROOT, 'index.html'));
  console.error('    先在 web-preview 里构建：node node_modules\\vite\\bin\\vite.js build');
  process.exit(1);
}

function handler(req, res) {
  const url = decodeURIComponent((req.url || '/').split('?')[0]);
  let file = normalize(join(ROOT, url));
  if (!file.startsWith(ROOT)) {
    res.writeHead(403).end('forbidden');
    return;
  }
  try {
    if (statSync(file).isDirectory()) file = join(file, 'index.html');
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }).end('404 ' + url);
    return;
  }
  const type = MIME[extname(file).toLowerCase()] || 'application/octet-stream';
  const size = statSync(file).size;
  res.writeHead(200, {
    'content-type': type,
    'content-length': size,
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
  });
  if (req.method === 'HEAD') return res.end();
  createReadStream(file).on('error', () => res.destroy()).pipe(res);
}

ensureAssets();

function listen(port, triesLeft) {
  const server = createServer(handler);
  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE' && triesLeft > 0) {
      listen(port + 1, triesLeft - 1);
    } else {
      console.error('[x] 端口 ' + port + ' 不可用：' + err.message);
      process.exit(1);
    }
  });
  server.listen(port, '127.0.0.1', () => {
    const page = 'http://127.0.0.1:' + port + '/';
    console.log('');
    console.log('  龙人武士 · 网页预览已启动');
    console.log('  ' + page);
    console.log('  切换模型：' + page + '?glb=/DragonMan_Std_TPose.glb');
    console.log('  冻结某帧：' + page + '?freeze=0.5   切换视角：?yaw=45&pitch=10&dist=4');
    console.log('');
    console.log('  关闭这个窗口即停止服务。');
    console.log('');
    if (OPEN) spawn('cmd', ['/c', 'start', '', page], { detached: true, stdio: 'ignore' }).unref();
  });
}
listen(START_PORT, 20);
