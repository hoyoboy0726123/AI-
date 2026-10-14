// Render assembly steps from assets/asm/assembly.json with three.js in headless Chromium.
// usage: node src/tools/asm_render.js src/tools/asm_render_jobs.json  (needs playwright; LIB = folder with three, see README)   jobs: [{arm, upto, sub?, view:[x,y,z], focus:'all'|'new', out}]
const { chromium } = require('playwright'); const fs = require('fs');
const path = require('path'); const ROOT = path.resolve(__dirname, '../..'); const LIB = process.env.LIB || ROOT + '/.work/npmcheck/lib';
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const W = parseInt(process.env.W || '960', 10), H = parseInt(process.env.H || '720', 10);
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on('pageerror', e => console.log('pageerror', e.message));
  page.on('console', m => console.log('console', m.text()));
  await page.setContent('<html><body style="margin:0;background:transparent"></body></html>');
  await page.addScriptTag({ content: fs.readFileSync(LIB + '/three/build/three.min.js', 'utf8') });
  await page.addScriptTag({ content: fs.readFileSync(LIB + '/three/examples/js/loaders/STLLoader.js', 'utf8') });
  const asm = JSON.parse(fs.readFileSync(ROOT + '/assets/asm/assembly.json', 'utf8'));
  const meshes = {};
  for (const a of Object.values(asm.arms)) for (const p of Object.values(a.parts)) meshes[p.mesh] = fs.readFileSync(ROOT + '/assets/asm/' + p.mesh + '.stl').toString('base64');
  await page.evaluate(({ asm, meshes, W, H }) => {
    const geos = {};
    for (const [k, b64] of Object.entries(meshes)) {
      const bin = atob(b64); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
      const g = new THREE.STLLoader().parse(u.buffer); g.computeVertexNormals(); geos[k] = g;
    }
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setSize(W, H); renderer.setClearColor(0x000000, 0);
    window.__render = (job) => {
      const arm = asm.arms[job.arm];
      const order = []; arm.steps.forEach((s, si) => s.subs.forEach((sub, ui) => sub.parts.forEach(p => order.push({ p, si, ui }))));
      const scene = new THREE.Scene();
      scene.add(new THREE.HemisphereLight(0xffffff, 0x50605a, 0.95));
      const key = new THREE.DirectionalLight(0xffffff, 0.75); key.position.set(job.view[0] * 2 + 1, job.view[1] * 2 - 1, 3); scene.add(key);
      const fill = new THREE.DirectionalLight(0xffffff, 0.3); fill.position.set(-2, 2, 1); scene.add(fill);
      const root = new THREE.Group(); scene.add(root);
      const boxAll = new THREE.Box3(), boxNew = new THREE.Box3();
      for (const o of order) {
        if (o.si > job.upto) continue;
        const isNew = o.si === job.upto && (job.sub == null || o.ui === job.sub);
        const later = o.si === job.upto && job.sub != null && o.ui > job.sub;
        if (later) continue;
        const part = arm.parts[o.p];
        const color = isNew ? (part.motor ? 0x6b4a10 : 0xf2a51a) : (part.motor ? 0x3a3f3d : 0xb9c7c0);
        const ghost = !isNew && !!job.ghost; const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.55, metalness: part.motor ? 0.15 : 0.03, transparent: ghost, opacity: ghost ? 0.35 : 1 });
        const mesh = new THREE.Mesh(geos[part.mesh], mat);
        const m = new THREE.Matrix4(); m.fromArray(part.m); mesh.matrixAutoUpdate = false; mesh.matrix.copy(m);
        root.add(mesh);
        const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geos[part.mesh], 40), new THREE.LineBasicMaterial({ color: isNew ? 0x5a3a00 : 0x2a3530, transparent: true, opacity: isNew ? 0.55 : 0.3 }));
        edges.matrixAutoUpdate = false; edges.matrix.copy(m); root.add(edges);
        mesh.updateMatrixWorld(true);
        const bb = new THREE.Box3().setFromObject(mesh); boxAll.union(bb); if (isNew) boxNew.union(bb);
      }
      const box = (job.focus === 'new' && !boxNew.isEmpty()) ? boxNew : boxAll;
      const c = new THREE.Vector3(), size = new THREE.Vector3(); box.getCenter(c); box.getSize(size);
      const cam = new THREE.PerspectiveCamera(26, W / H, 1, 10000); cam.up.set(0, 0, 1);
      const d = new THREE.Vector3(...job.view).normalize();
      const rad = Math.max(size.length() / 2, job.focus === 'new' ? 45 : 60) * (job.pad || 1.0);
      const dist = rad / Math.sin((cam.fov * Math.PI / 180) / 2) * 0.95;
      cam.position.copy(c).add(d.multiplyScalar(dist)); cam.lookAt(c); cam.near = dist / 20; cam.far = dist * 10; cam.updateProjectionMatrix();
      renderer.render(scene, cam);
      return renderer.domElement.toDataURL(job.out.endsWith('.webp') ? 'image/webp' : 'image/png', 0.86);
    };
  }, { asm, meshes, W, H });
  for (const job of jobs) {
    const url = await page.evaluate(j => window.__render(j), job);
    fs.writeFileSync(path.resolve(ROOT, job.out), Buffer.from(url.split(',')[1], 'base64'));
    console.log('rendered', job.out);
  }
  await browser.close();
})();
