/* ---------- step-by-step 3D assembly (official URDF poses) ---------- */
(function(){
"use strict";
var X = window.__SO101; if(!X) return;
var fetchAny = X.fetchAny, cssVar = X.cssVar, viewers = X.viewers, REDUCED = X.REDUCED;
var ASM = window.__SO101_ASM || null;
var ASM_NEW = 0xF2A51A, ASM_NEW_MOTOR = 0x9A6A12;

function initAsm(){
  var roots = document.querySelectorAll("figure[data-asm]");
  if(!roots.length || !ASM) return;
  if(!window.THREE || !THREE.STLLoader || !THREE.OrbitControls){
    roots.forEach(function(r){ var s = r.querySelector(".status"); if(s) s.textContent = "3D 檢視器載入失敗，請重新整理頁面。"; });
    return;
  }
  roots.forEach(function(root){
    var started = false;
    function start(){ if(started) return; started = true; var v = makeAsm(root); if(v) viewers.push(v); }
    if("IntersectionObserver" in window){
      var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if(e.isIntersecting){ start(); io.disconnect(); } }); }, {rootMargin:"200px"});
      io.observe(root);
    } else start();
  });
}

function makeAsm(root){
  var arm = ASM.arms[root.getAttribute("data-asm")];
  if(!arm) return null;
  var vp = root.querySelector(".vp"), status = root.querySelector(".status");
  var capStep = root.querySelector("[data-asm-step]"), capSub = root.querySelector("[data-asm-sub]");
  var subList = root.querySelector("ol.subs");
  var stepBtns = root.querySelectorAll("[data-step]");
  var renderer = new THREE.WebGLRenderer({antialias:true, alpha:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  vp.appendChild(renderer.domElement);
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(30, 1, 1, 20000);
  camera.up.set(0, 0, 1);  /* the URDF world is Z-up */
  scene.add(new THREE.HemisphereLight(0xffffff, 0x556a60, 0.95));
  var key = new THREE.DirectionalLight(0xffffff, 0.7); key.position.set(3.4, -4.2, 3); scene.add(key);
  var fill = new THREE.DirectionalLight(0xffffff, 0.3); fill.position.set(-2, 2, 1); scene.add(fill);
  var controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  var raf = 0, visible = false, tl = null, cur = -1, ready = false;
  function resize(){
    var w = vp.clientWidth, h = vp.clientHeight;
    if(!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  function loop(){ raf = requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); }
  function setVisible(v){ visible = v; if(v && !raf && ready) loop(); if(!v && raf){ cancelAnimationFrame(raf); raf = 0; } }
  if("ResizeObserver" in window) new ResizeObserver(resize).observe(vp); else window.addEventListener("resize", resize);
  if("IntersectionObserver" in window) new IntersectionObserver(function(es){ es.forEach(function(e){ setVisible(e.isIntersecting); }); }).observe(root);
  else setVisible(true);
  resize();

  function neutral(isMotor){ return new THREE.Color(isMotor ? cssVar("--bed", "#2B3330") : cssVar("--part", "#B9C9C1")); }

  /* parts in assembly order */
  var order = [];
  arm.steps.forEach(function(s, si){ s.subs.forEach(function(sub, ui){ sub.parts.forEach(function(p){ order.push({id:p, si:si, ui:ui}); }); }); });
  var objs = {};
  var loader = new THREE.STLLoader();
  var meshNames = {};
  Object.keys(arm.parts).forEach(function(k){ meshNames[arm.parts[k].mesh] = 1; });
  var geos = {};
  status.textContent = "載入 3D 組裝模型中…";
  Promise.all(Object.keys(meshNames).map(function(name){
    return fetchAny("assets/stl64/" + name + ".stl.txt").then(function(buf){ var g = loader.parse(buf); g.computeVertexNormals(); geos[name] = g; });
  })).then(function(){
    order.forEach(function(o){
      var part = arm.parts[o.id];
      var mat = new THREE.MeshStandardMaterial({color: neutral(part.motor), roughness:0.55, metalness: part.motor ? 0.15 : 0.03});
      var mesh = new THREE.Mesh(geos[part.mesh], mat);
      mesh.matrixAutoUpdate = false; mesh.matrix.fromArray(part.m);
      var g = new THREE.Group(); g.add(mesh); scene.add(g);
      g.updateMatrixWorld(true);
      var box = new THREE.Box3().setFromObject(mesh);
      objs[o.id] = {group:g, mesh:mesh, mat:mat, motor:part.motor, box:box, o:o};
    });
    ready = true; status.textContent = "";
    show(0, false);
    if(visible && !raf) loop();
  }).catch(function(){ status.textContent = "組裝模型載入失敗，請重新整理頁面。"; });

  function boxOf(ids){
    var b = new THREE.Box3();
    ids.forEach(function(id){ b.union(objs[id].box); });
    return b;
  }
  function frame(box, minR, animate, pad){
    var c = new THREE.Vector3(), size = new THREE.Vector3(); box.getCenter(c); box.getSize(size);
    var r = Math.max(size.length() / 2 * (pad || 1), minR);
    var dist = r / Math.sin(camera.fov * Math.PI / 360) * 0.8;
    var dir = camera.position.clone().sub(controls.target);
    if(dir.lengthSq() < 1) dir.set(1.2, -1.6, 0.9);
    dir.normalize();
    var to = c.clone().add(dir.multiplyScalar(dist));
    camera.near = dist / 30; camera.far = dist * 20; camera.updateProjectionMatrix();
    if(animate && window.gsap && !REDUCED){
      gsap.to(controls.target, {x:c.x, y:c.y, z:c.z, duration:0.9, ease:"power2.inOut"});
      gsap.to(camera.position, {x:to.x, y:to.y, z:to.z, duration:0.9, ease:"power2.inOut"});
    } else { controls.target.copy(c); camera.position.copy(to); controls.update(); }
  }
  function paint(ob, isNew){
    ob.mat.color = isNew ? new THREE.Color(ob.motor ? ASM_NEW_MOTOR : ASM_NEW) : neutral(ob.motor);
  }
  function setCaption(si, ui){
    var st = arm.steps[si];
    capStep.textContent = st.title;
    capSub.textContent = ui == null ? "新裝上的零件標成橘色。" : (ui + 1) + " / " + st.subs.length + "　" + st.subs[ui].text;
    if(subList){
      subList.querySelectorAll("li").forEach(function(li, i){ li.classList.toggle("on", ui === i); });
    }
  }
  function fillSubs(si){
    if(!subList) return;
    subList.innerHTML = "";
    arm.steps[si].subs.forEach(function(sub, i){
      var li = document.createElement("li"); li.textContent = sub.text;
      li.addEventListener("click", function(){ show(si, true, i); });
      subList.appendChild(li);
    });
  }

  /* si: step index, or -1 for the finished arm */
  function show(si, animate, fromSub){
    if(!ready) return;
    if(tl){ tl.kill(); tl = null; }
    cur = si;
    stepBtns.forEach(function(b){ b.setAttribute("aria-pressed", String(+b.getAttribute("data-step") === si)); });
    var all = si < 0;
    var newIds = [], doneIds = [];
    order.forEach(function(o){
      var ob = objs[o.id];
      ob.group.position.set(0, 0, 0); ob.mat.opacity = 1; ob.mat.transparent = false;
      var shown = all || o.si < si || (o.si === si && (fromSub == null || o.ui <= fromSub || animate));
      ob.group.visible = shown;
      paint(ob, !all && o.si === si);
      if(all || o.si < si) doneIds.push(o.id); else if(o.si === si) newIds.push(o.id);
    });
    if(all){
      capStep.textContent = "完成的手臂"; capSub.textContent = "這是校準時的中間姿勢：上臂朝上、前臂朝前。";
      if(subList) subList.innerHTML = "";
      frame(boxOf(doneIds), 60, animate, 1.1);
      return;
    }
    fillSubs(si);
    frame(boxOf(newIds), 55, animate, 1.3);
    if(!animate || !window.gsap || REDUCED){ setCaption(si, null); return; }
    var subs = arm.steps[si].subs, start = fromSub || 0;
    tl = gsap.timeline({delay:0.5});
    var placed = doneIds.slice();
    order.forEach(function(o){ if(o.si === si && o.ui < start) placed.push(o.id); });
    subs.forEach(function(sub, ui){
      if(ui < start) return;
      tl.call(function(){
        setCaption(si, ui);
        newIds.forEach(function(id){ paint(objs[id], sub.parts.indexOf(id) >= 0); });
      });
      var prevBox = placed.length ? boxOf(placed) : null;
      sub.parts.forEach(function(id, k){
        var ob = objs[id];
        var pc = new THREE.Vector3(); ob.box.getCenter(pc);
        var dir = new THREE.Vector3(0, 0, 1);
        if(prevBox){ var ac = new THREE.Vector3(); prevBox.getCenter(ac); dir = pc.clone().sub(ac); if(dir.lengthSq() < 1) dir.set(0, 0, 1); dir.normalize(); }
        var off = dir.multiplyScalar(70);
        ob.group.visible = false;
        tl.call(function(){ ob.group.visible = true; ob.mat.transparent = true; ob.mat.opacity = 0; ob.group.position.copy(off); }, null, k ? "<0.2" : ">");
        tl.to(ob.mat, {opacity:1, duration:0.45, ease:"power1.out"}, "<");
        tl.to(ob.group.position, {x:0, y:0, z:0, duration:1.0, ease:"power2.out"}, "<");
        tl.call(function(){ ob.mat.transparent = false; });
      });
      sub.parts.forEach(function(id){ placed.push(id); });
      tl.to({}, {duration: sub.parts.length ? 1.1 : 1.8});
    });
    tl.call(function(){ setCaption(si, null); newIds.forEach(function(id){ paint(objs[id], true); }); });
  }

  root.querySelectorAll("[data-step]").forEach(function(b){ b.addEventListener("click", function(){ show(+b.getAttribute("data-step"), true); }); });
  var act = function(name, fn){ var b = root.querySelector("[data-act=" + name + "]"); if(b) b.addEventListener("click", fn); };
  act("play", function(){ show(cur < 0 ? 0 : cur, true); });
  act("prev", function(){ show(Math.max(0, (cur < 0 ? arm.steps.length : cur) - 1), true); });
  act("next", function(){ show(cur < 0 ? 0 : Math.min(arm.steps.length - 1, cur + 1), true); });
  act("all", function(){ show(-1, true); });
  return { recolor: function(){ if(ready) order.forEach(function(o){ var ob = objs[o.id]; paint(ob, cur >= 0 && o.si === cur); }); } };
}

if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", initAsm); else initAsm();
})();
