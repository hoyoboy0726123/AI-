(function(){
"use strict";
var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
var STORE_KEY = "so101-sop-progress-v1";

/* ---------- storage (per viewer, optional) ---------- */
function loadState(){ try{ return JSON.parse(localStorage.getItem(STORE_KEY) || "{}"); }catch(e){ return {}; } }
function saveState(s){ try{ localStorage.setItem(STORE_KEY, JSON.stringify(s)); }catch(e){} }

/* ---------- table of contents + progress ---------- */
function buildToc(){
  var toc = document.getElementById("toc");
  if(!toc) return;
  var groups = document.querySelectorAll("main .part");
  groups.forEach(function(part){
    var g = document.createElement("li");
    g.className = "grp";
    g.textContent = part.getAttribute("data-toc") || "";
    toc.appendChild(g);
    part.querySelectorAll(".step").forEach(function(step){
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + step.id;
      var code = step.querySelector(".code");
      var h = step.querySelector("h3");
      var sp = document.createElement("span");
      sp.textContent = code ? code.textContent : "";
      a.appendChild(sp);
      a.appendChild(document.createTextNode(h ? h.textContent : step.id));
      a.setAttribute("data-step", step.id);
      li.appendChild(a);
      toc.appendChild(li);
    });
  });
  var links = toc.querySelectorAll("a[data-step]");
  if("IntersectionObserver" in window){
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if(en.isIntersecting){
          links.forEach(function(l){ l.classList.toggle("on", l.getAttribute("data-step") === en.target.id); });
        }
      });
    }, {rootMargin:"-20% 0px -70% 0px"});
    document.querySelectorAll("main .step").forEach(function(s){ io.observe(s); });
  }
}
function initChecks(){
  var state = loadState();
  var boxes = document.querySelectorAll(".check input[type=checkbox]");
  boxes.forEach(function(b){
    if(state[b.id]) b.checked = true;
    b.addEventListener("change", function(){
      var s = loadState(); s[b.id] = b.checked; saveState(s); refresh();
    });
  });
  function refresh(){
    ["A","B","C"].forEach(function(ph){
      var all = document.querySelectorAll('.part[data-phase="'+ph+'"] .check input');
      var done = 0; all.forEach(function(b){ if(b.checked) done++; });
      var m = document.querySelector('[data-meter="'+ph+'"]');
      var l = document.querySelector('[data-meter-label="'+ph+'"]');
      if(m) m.style.width = (all.length ? (100*done/all.length) : 0) + "%";
      if(l) l.textContent = done + " / " + all.length + " 完成";
    });
    document.querySelectorAll("#toc a[data-step]").forEach(function(a){
      var st = document.getElementById(a.getAttribute("data-step"));
      var b = st && st.querySelector(".check input");
      a.classList.toggle("done", !!(b && b.checked));
    });
  }
  refresh();
}

/* ---------- copy buttons ---------- */
function initCopy(){
  document.querySelectorAll(".codeblk").forEach(function(blk){
    var btn = blk.querySelector("[data-copy]");
    var pre = blk.querySelector("pre");
    if(!btn || !pre) return;
    btn.addEventListener("click", function(){
      var txt = pre.innerText;
      function ok(){ btn.textContent = "已複製"; setTimeout(function(){ btn.textContent = "複製"; }, 1600); }
      function fallback(){
        var r = document.createRange(); r.selectNodeContents(pre);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
        btn.textContent = "已選取，請按 Ctrl+C";
        setTimeout(function(){ btn.textContent = "複製"; }, 2400);
      }
      try{
        if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(txt).then(ok, fallback); }
        else fallback();
      }catch(e){ fallback(); }
    });
  });
}

/* ---------- downloads (zip bundles) ---------- */
function initDownloads(){
  var btns = document.querySelectorAll("[data-download]");
  if(!btns.length) return;
  var dlPromise = (window.claude && typeof window.claude.use === "function") ? window.claude.use("downloads") : Promise.resolve(null);
  btns.forEach(function(btn){
    var msg = btn.parentElement.querySelector(".msg");
    btn.addEventListener("click", function(){
      btn.disabled = true;
      if(msg) msg.textContent = "準備檔案中…";
      dlPromise.then(function(dl){
        if(!dl){ throw {code:"unavailable"}; }
        return fetch(btn.getAttribute("data-download")).then(function(r){
          if(!r.ok) throw {code:"fetch"};
          return r.blob();
        }).then(function(blob){
          return dl.save({filename: btn.getAttribute("data-filename"), data: blob});
        });
      }).then(function(){
        if(msg) msg.textContent = "已交給瀏覽器下載。";
      }).catch(function(err){
        var c = err && err.code;
        if(msg){
          if(c === "declined") msg.textContent = "你取消了下載。";
          else if(c === "rate_limited") msg.textContent = "已經有一個下載視窗開著，請先處理它。";
          else msg.textContent = "這個檢視模式不能下載。請在 claude.ai 開啟本頁，或改用下方 GitHub 連結與程式碼複製。";
        }
      }).then(function(){ btn.disabled = false; });
    });
  });
}

/* ---------- 3D STL viewer ---------- */
function cssVar(name, fallback){
  var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
var viewers = [];
function initViewers(){
  var roots = document.querySelectorAll(".viewer[data-viewer]");
  if(!roots.length) return;
  if(!window.THREE || !THREE.STLLoader || !THREE.OrbitControls){
    roots.forEach(function(r){ var s = r.querySelector(".status"); if(s) s.textContent = "3D 檢視器載入失敗，請重新整理頁面。"; });
    return;
  }
  roots.forEach(function(root){
    var started = false;
    function start(){ if(started) return; started = true; viewers.push(makeViewer(root)); }
    if("IntersectionObserver" in window){
      var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if(e.isIntersecting){ start(); io.disconnect(); } }); }, {rootMargin:"200px"});
      io.observe(root);
    } else start();
  });
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  var recolor = function(){ viewers.forEach(function(v){ v.recolor(); }); };
  if(mq.addEventListener) mq.addEventListener("change", recolor);
  new MutationObserver(recolor).observe(document.documentElement, {attributes:true, attributeFilter:["data-theme"]});
}
function makeViewer(root){
  var vp = root.querySelector(".vp");
  var status = root.querySelector(".status");
  var metaName = root.querySelector("[data-meta=name]");
  var metaSize = root.querySelector("[data-meta=size]");
  var metaUse = root.querySelector("[data-meta=use]");
  var renderer = new THREE.WebGLRenderer({antialias:true, alpha:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  vp.appendChild(renderer.domElement);
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(32, 1, 0.1, 10000);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x556a60, 0.95));
  var key = new THREE.DirectionalLight(0xffffff, 0.75); key.position.set(1, 1.6, 1.2); scene.add(key);
  var rim = new THREE.DirectionalLight(0xffffff, 0.35); rim.position.set(-1.2, 0.4, -1); scene.add(rim);
  var controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  var loader = new THREE.STLLoader();
  var mesh = null, edges = null, visible = false, raf = 0;
  var cache = {};
  function material(){ return new THREE.MeshStandardMaterial({color: new THREE.Color(cssVar("--part", "#b9c9c1")), roughness:0.62, metalness:0.04}); }
  function resize(){
    var w = vp.clientWidth, h = vp.clientHeight;
    if(!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  function loop(){ raf = requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); }
  function setVisible(v){ visible = v; if(v && !raf) loop(); if(!v && raf){ cancelAnimationFrame(raf); raf = 0; } }
  if("ResizeObserver" in window) new ResizeObserver(resize).observe(vp); else window.addEventListener("resize", resize);
  if("IntersectionObserver" in window){
    new IntersectionObserver(function(es){ es.forEach(function(e){ setVisible(e.isIntersecting); }); }).observe(root);
  } else setVisible(true);
  resize();
  function show(btn){
    var file = btn.getAttribute("data-file");
    root.querySelectorAll(".parts button").forEach(function(b){ b.setAttribute("aria-pressed", b === btn ? "true" : "false"); });
    if(metaName) metaName.textContent = btn.getAttribute("data-label") || btn.textContent;
    if(metaUse) metaUse.textContent = btn.getAttribute("data-use") || "";
    status.textContent = "載入 3D 模型中…";
    var base = btn.getAttribute("data-base") || root.getAttribute("data-base") || "assets/stl/";
    var p = cache[file] || (cache[file] = fetch(base + encodeURIComponent(file)).then(function(r){ if(!r.ok) throw new Error(r.status); return r.arrayBuffer(); }).then(function(buf){ return loader.parse(buf); }));
    p.then(function(geo){
      if(mesh){ scene.remove(mesh); }
      if(!geo.attributes.normal) geo.computeVertexNormals();
      geo.computeBoundingBox();
      var bb = geo.boundingBox, size = new THREE.Vector3(); bb.getSize(size);
      var c = new THREE.Vector3(); bb.getCenter(c);
      mesh = new THREE.Mesh(geo, material());
      mesh.position.set(-c.x, -c.y, -c.z);
      var holder = new THREE.Group(); holder.add(mesh); holder.rotation.x = -Math.PI / 2;
      if(edges) scene.remove(edges);
      edges = holder; scene.add(holder);
      var r = Math.max(size.x, size.y, size.z) * 0.5;
      var d = r / Math.tan(camera.fov * Math.PI / 360) * 1.35;
      camera.near = d / 100; camera.far = d * 20; camera.updateProjectionMatrix();
      camera.position.set(d * 0.62, d * 0.55, d * 0.62);
      controls.target.set(0, 0, 0); controls.update();
      if(metaSize) metaSize.textContent = size.x.toFixed(0) + " × " + size.y.toFixed(0) + " × " + size.z.toFixed(0) + " mm";
      status.textContent = "";
      if(!raf && visible) loop();
      renderer.render(scene, camera);
    }).catch(function(){ status.textContent = "這個模型載入失敗，請用下方 GitHub 連結下載查看。"; });
  }
  root.querySelectorAll(".parts button").forEach(function(b){ b.addEventListener("click", function(){ show(b); }); });
  var first = root.querySelector(".parts button[aria-pressed=true]") || root.querySelector(".parts button");
  if(first) show(first);
  return { recolor: function(){ if(mesh){ mesh.material.color = new THREE.Color(cssVar("--part", "#b9c9c1")); } } };
}

/* ---------- SVG helpers ---------- */
var NS = "http://www.w3.org/2000/svg";
function E(tag, attrs, parent){
  var e = document.createElementNS(NS, tag);
  if(attrs) for(var k in attrs){ if(attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]); }
  if(parent) parent.appendChild(e);
  return e;
}
function T(parent, x, y, str, cls, anchor){
  var t = E("text", {x:x, y:y, "class":cls || "sv-t", "text-anchor":anchor || "middle"}, parent);
  t.textContent = str; return t;
}
function G(parent, attrs){ return E("g", attrs || {}, parent); }
function drawPath(el){ var L = el.getTotalLength ? el.getTotalLength() : 300; el.style.strokeDasharray = L + " " + L; return L; }
function tlDraw(tl, el, opts, pos){ var L = drawPath(el); tl.fromTo(el, {strokeDashoffset:L}, Object.assign({strokeDashoffset:0, duration:0.8, ease:"power1.inOut"}, opts || {}), pos); }
function pinRow(parent, x, y, labels, side, gap){
  var pts = {};
  labels.forEach(function(lb, i){
    var yy = y + i * (gap || 22);
    E("circle", {cx:x, cy:yy, r:4.5, fill:"var(--w-yellow)", stroke:"var(--ink)", "stroke-width":1}, parent);
    T(parent, side === "left" ? x + 10 : x - 10, yy + 4, lb, "sv-tw", side === "left" ? "start" : "end");
    pts[lb] = [x, yy];
  });
  return pts;
}
function curve(a, b, bend){
  var mx = (a[0] + b[0]) / 2;
  return "M" + a[0] + "," + a[1] + " C" + (mx + (bend||0)) + "," + a[1] + " " + (mx - (bend||0)) + "," + b[1] + " " + b[0] + "," + b[1];
}

/* ---------- scene engine ---------- */
var SCENES = {};
function initScenes(){
  if(!window.gsap){
    document.querySelectorAll(".anim .ctrl").forEach(function(c){ c.innerHTML = '<span class="msg" style="font-size:13px;color:var(--ink-2)">動畫函式庫沒有載入，下面的步驟文字仍然完整。</span>'; });
  }
  document.querySelectorAll(".anim[data-scene]").forEach(function(fig){
    var name = fig.getAttribute("data-scene");
    var builder = SCENES[name];
    var svg = fig.querySelector("svg");
    if(!builder || !svg) return;
    var captions = Array.prototype.slice.call(fig.querySelectorAll("ol.steps li"));
    if(!window.gsap){ builder(svg, null, function(){}); return; }
    var tl = gsap.timeline({paused:true});
    var labels = [];
    builder(svg, tl, function(lbl){ labels.push(lbl); tl.addLabel(lbl); });
    var times = labels.map(function(l){ return tl.labels[l]; });
    function idxAt(t){ var i = 0; for(var k = 0; k < times.length; k++){ if(t >= times[k] - 1e-3) i = k; } return i; }
    function mark(i){ captions.forEach(function(li, k){ li.classList.toggle("on", k === i); }); }
    tl.eventCallback("onUpdate", function(){ mark(idxAt(tl.time())); });
    tl.progress(1).pause();
    mark(captions.length - 1);
    var cur = labels.length - 1;
    function seg(i){
      cur = Math.max(0, Math.min(labels.length - 1, i));
      var a = times[cur], b = cur + 1 < times.length ? times[cur + 1] : tl.duration();
      mark(cur);
      if(REDUCED){ tl.pause(); tl.seek(b - 0.001 > a ? b - 0.001 : b); mark(cur); }
      else tl.tweenFromTo(a, b);
    }
    var bPlay = fig.querySelector("[data-act=play]"), bPrev = fig.querySelector("[data-act=prev]"), bNext = fig.querySelector("[data-act=next]");
    if(bPlay) bPlay.addEventListener("click", function(){ if(REDUCED){ tl.progress(1); mark(captions.length - 1); } else tl.restart(); });
    if(bPrev) bPrev.addEventListener("click", function(){ seg(cur - 1); });
    if(bNext) bNext.addEventListener("click", function(){ seg(tl.progress() >= 0.999 ? 0 : cur + 1); });
    captions.forEach(function(li, k){
      li.setAttribute("tabindex", "0");
      li.addEventListener("click", function(){ seg(k); });
      li.addEventListener("keydown", function(e){ if(e.key === "Enter" || e.key === " "){ e.preventDefault(); seg(k); } });
    });
    if(!REDUCED && "IntersectionObserver" in window){
      var played = false;
      var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if(e.isIntersecting && !played){ played = true; tl.restart(); io.disconnect(); } }); }, {threshold:0.45});
      io.observe(fig);
    }
  });
}

/* ===== scene: print ===== */
SCENES.print = function(svg, tl, step){
  E("rect", {x:0, y:0, width:680, height:340, fill:"transparent"}, svg);
  var bed = E("rect", {x:30, y:36, width:360, height:270, rx:8, "class":"sv-bed"}, svg);
  for(var i = 1; i < 6; i++) E("line", {x1:30 + i * 60, y1:40, x2:30 + i * 60, y2:302, stroke:"rgba(255,255,255,.08)"}, svg);
  T(svg, 210, 26, "列印平台 220 × 220 mm 以上", "sv-ts");
  var glue = E("rect", {x:44, y:50, width:332, height:242, rx:4, fill:"var(--w-blue)", opacity:0.22}, svg);
  var gauge = G(svg);
  E("rect", {x:60, y:66, width:84, height:58, rx:4, "class":"sv-part"}, gauge);
  E("rect", {x:76, y:80, width:52, height:30, rx:2, fill:"var(--bed)"}, gauge);
  T(gauge, 102, 140, "量規", "sv-ts");
  var servo = G(svg);
  E("rect", {x:76, y:80, width:52, height:30, rx:3, "class":"sv-servo"}, servo);
  T(servo, 102, 99, "STS3215", "sv-tw");
  var ok = G(svg);
  E("circle", {cx:150, cy:70, r:12, "class":"sv-accent"}, ok);
  E("path", {d:"M144,70 l4,5 l8,-9", stroke:"#fff", "stroke-width":3, fill:"none", "stroke-linecap":"round"}, ok);
  var parts = G(svg);
  var shapes = [
    "M178,70 h70 a10,10 0 0 1 10,10 v40 a10,10 0 0 1 -10,10 h-70 a10,10 0 0 1 -10,-10 v-40 a10,10 0 0 1 10,-10z",
    "M280,64 h80 v34 h-40 v40 h-40z",
    "M70,160 h120 a14,14 0 0 1 14,14 v30 a14,14 0 0 1 -14,14 h-120z",
    "M226,160 h134 v28 h-134z",
    "M226,204 h84 l40,30 h-124z",
    "M70,236 h60 v50 h-60z",
    "M150,240 h52 a26,26 0 0 1 0,46 h-52z"
  ];
  var partEls = shapes.map(function(d){ return E("path", {d:d, "class":"sv-part"}, parts); });
  var hatch = G(svg);
  for(var k = 0; k < 7; k++) E("line", {x1:236 + k * 16, y1:236, x2:236 + k * 16, y2:262, stroke:"var(--amber)", "stroke-width":3}, hatch);
  T(hatch, 290, 280, "支撐", "sv-ts");
  var nozzle = G(svg);
  E("path", {d:"M-12,-26 h24 v14 l-8,12 h-8 l-8,-12z", "class":"sv-metal"}, nozzle);
  var panel = G(svg);
  var rows = [["材料", "PLA+"], ["噴嘴／層高", "0.4 mm／0.2 mm"], ["填充", "15%"], ["支撐", "全部開啟"], ["斜面門檻", "45°"], ["水平螺絲孔", "不要支撐"]];
  E("rect", {x:410, y:36, width:250, height:270, rx:8, "class":"sv-box"}, panel);
  T(panel, 426, 64, "切片設定（官方建議）", "sv-t", "start");
  var rowEls = rows.map(function(r, i){ var g = G(panel); T(g, 426, 100 + i * 34, r[0], "sv-ts", "start"); T(g, 644, 100 + i * 34, r[1], "sv-tm", "end"); return g; });
  if(!tl) return;
  step("s1");
  tl.from(glue, {scaleX:0, transformOrigin:"0% 50%", duration:0.9, ease:"power1.inOut"});
  step("s2");
  tl.from(gauge, {opacity:0, duration:0.4});
  tl.from(servo, {y:-60, opacity:0, duration:0.7, ease:"bounce.out"});
  tl.from(ok, {scale:0, transformOrigin:"50% 50%", duration:0.35, ease:"back.out(2)"});
  step("s3");
  tl.from(rowEls, {opacity:0, x:12, stagger:0.12, duration:0.3});
  tl.set(nozzle, {x:180, y:70});
  partEls.forEach(function(p, i){
    var bb = {x:[178,280,70,226,226,70,150][i], y:[70,64,160,160,204,236,240][i]};
    tl.to(nozzle, {x:bb.x + 30, y:bb.y + 20, duration:0.18, ease:"none"});
    tl.from(p, {opacity:0, scaleY:0, transformOrigin:"50% 100%", duration:0.3}, "<");
  });
  tl.from(hatch, {opacity:0, duration:0.3});
  tl.to(nozzle, {x:350, y:30, duration:0.3});
  step("s4");
  tl.to(hatch, {y:30, opacity:0, duration:0.7, ease:"power2.in"});
  tl.to(hatch, {y:0, opacity:1, duration:0.01, delay:0.6});
  tl.set(hatch, {opacity:0});
};

/* ===== scene: chain (servo daisy chain) ===== */
SCENES.chain = function(svg, tl, step){
  var board = G(svg);
  E("rect", {x:24, y:226, width:120, height:70, rx:6, "class":"sv-pcb"}, board);
  T(board, 84, 258, "驅動板", "sv-tw");
  T(board, 84, 276, "Bus Servo", "sv-tw");
  var psu = G(svg);
  E("rect", {x:24, y:150, width:84, height:44, rx:6, "class":"sv-box"}, psu);
  T(psu, 66, 177, "電源", "sv-t");
  var pc = G(svg);
  E("rect", {x:170, y:244, width:96, height:56, rx:5, "class":"sv-box"}, pc);
  E("rect", {x:160, y:300, width:116, height:7, rx:3, "class":"sv-box"}, pc);
  T(pc, 218, 278, "電腦", "sv-t");
  var pPower = E("path", {d:"M66,194 C66,210 70,214 70,226", "class":"w w-red"}, svg);
  var pUsb = E("path", {d:"M144,262 C152,262 158,272 170,272", "class":"w w-blue"}, svg);
  var pos = [[330,262],[330,200],[410,128],[520,128],[590,128],[640,170]];
  var names = ["1 肩部旋轉","2 肩部抬升","3 手肘","4 手腕俯仰","5 手腕旋轉","6 夾爪"];
  E("path", {d:"M300,300 h80", "class":"sv-ink"}, svg);
  E("path", {d:"M330,262 L330,200 L410,128 L640,128", "class":"sv-thin", "stroke-width":14, stroke:"var(--part)", opacity:0.7}, svg);
  var motors = pos.map(function(p, i){
    var g = G(svg);
    E("rect", {x:p[0] - 22, y:p[1] - 16, width:44, height:32, rx:4, "class":"sv-servo"}, g);
    T(g, p[0], p[1] + 5, "ID " + (i + 1), "sv-tw");
    T(g, p[0], p[1] - 24, names[i], "sv-ts");
    return g;
  });
  var d = "M144,240 C230,240 250,262 308,262";
  var wires = [E("path", {d:d, "class":"w w-black"}, svg)];
  for(var i = 0; i < pos.length - 1; i++){
    var a = pos[i], b = pos[i + 1];
    wires.push(E("path", {d:"M" + (a[0] + (i===0?0:0)) + "," + (a[1] - 16) + " C" + a[0] + "," + (a[1] - 40) + " " + b[0] + "," + (b[1] + 40) + " " + b[0] + "," + (b[1] + 16), "class":"w w-black"}, svg));
  }
  motors.forEach(function(m){ svg.appendChild(m); });
  var pulse = E("circle", {r:5, fill:"var(--w-yellow)", stroke:"var(--ink)", "stroke-width":1, opacity:0}, svg);
  if(!tl) return;
  step("s1");
  tl.from([board, psu, pc], {opacity:0, y:10, stagger:0.15, duration:0.4});
  tlDraw(tl, pPower, {duration:0.5});
  tlDraw(tl, pUsb, {duration:0.5});
  step("s2");
  tl.from(motors, {opacity:0, scale:0.6, transformOrigin:"50% 50%", stagger:0.12, duration:0.3});
  step("s3");
  wires.forEach(function(w){ tlDraw(tl, w, {duration:0.35}); });
  step("s4");
  tl.set(pulse, {opacity:1});
  wires.forEach(function(w){
    var L = w.getTotalLength();
    var o = {t:0};
    tl.to(o, {t:1, duration:0.28, ease:"none", onUpdate:function(){ var pt = w.getPointAtLength(o.t * L); pulse.setAttribute("cx", pt.x); pulse.setAttribute("cy", pt.y); }});
  });
  tl.to(pulse, {opacity:0, duration:0.2});
};

/* ===== arm drawing (side view) ===== */
function makeArm(parent, ox, oy, s){
  s = s || 1;
  var root = G(parent, {transform:"translate(" + ox + "," + oy + ") scale(" + s + ")"});
  E("rect", {x:-50, y:-6, width:100, height:16, rx:4, "class":"sv-part"}, root);
  E("rect", {x:-22, y:-46, width:44, height:42, rx:6, "class":"sv-servo"}, root);
  var upper = G(root);
  E("rect", {x:-10, y:-166, width:20, height:130, rx:9, "class":"sv-part"}, upper);
  E("circle", {cx:0, cy:-36, r:9, "class":"sv-metal"}, upper);
  var fore = G(upper);
  E("rect", {x:-2, y:-174, width:122, height:18, rx:8, "class":"sv-part"}, fore);
  E("circle", {cx:0, cy:-166, r:9, "class":"sv-metal"}, fore);
  var wrist = G(fore);
  E("rect", {x:112, y:-178, width:52, height:24, rx:6, "class":"sv-servo"}, wrist);
  E("circle", {cx:120, cy:-166, r:7, "class":"sv-metal"}, wrist);
  E("path", {d:"M164,-176 l34,6 v6 l-34,0z", "class":"sv-part"}, wrist);
  var jaw = G(wrist);
  E("path", {d:"M164,-156 l34,-2 v6 l-34,8z", "class":"sv-part"}, jaw);
  var st = {lift:0, elbow:0, wrist:0, jaw:0};
  function render(){
    upper.setAttribute("transform", "rotate(" + st.lift + " 0 -36)");
    fore.setAttribute("transform", "rotate(" + st.elbow + " 0 -166)");
    wrist.setAttribute("transform", "rotate(" + st.wrist + " 120 -166)");
    jaw.setAttribute("transform", "rotate(" + st.jaw + " 164 -152)");
  }
  render();
  return {root:root, state:st, render:render};
}

/* ===== scene: calibrate ===== */
SCENES.calibrate = function(svg, tl, step){
  T(svg, 20, 28, "側視圖", "sv-ts", "start");
  var arm = makeArm(svg, 200, 300, 1);
  var inset = G(svg);
  E("rect", {x:440, y:40, width:220, height:120, rx:8, "class":"sv-box"}, inset);
  T(inset, 550, 62, "俯視：肩部旋轉、手腕旋轉", "sv-ts");
  E("circle", {cx:500, cy:110, r:32, "class":"sv-thin"}, inset);
  var pan = E("line", {x1:500, y1:110, x2:532, y2:110, "class":"sv-accent-s"}, inset);
  E("circle", {cx:610, cy:110, r:26, "class":"sv-thin"}, inset);
  var roll = E("line", {x1:610, y1:110, x2:636, y2:110, "class":"sv-accent-s"}, inset);
  T(inset, 500, 156, "1 肩部旋轉", "sv-ts"); T(inset, 610, 156, "5 手腕旋轉", "sv-ts");
  var key = G(svg);
  E("rect", {x:500, y:220, width:120, height:56, rx:8, "class":"sv-box"}, key);
  T(key, 560, 254, "Enter", "sv-tm");
  T(svg, 560, 300, "依畫面提示按 Enter", "sv-ts");
  var label = T(svg, 200, 28, "", "sv-t", "start");
  var st = arm.state;
  st.lift = -28; st.elbow = 40; st.wrist = -50; arm.render();
  if(!tl){ st.lift = 0; st.elbow = 0; st.wrist = 0; arm.render(); return; }
  var r = arm.render;
  step("s1");
  tl.call(function(){ label.textContent = "所有關節轉到行程中間"; });
  tl.to(st, {lift:0, elbow:0, wrist:0, jaw:0, duration:1.2, ease:"power2.inOut", onUpdate:r});
  tl.fromTo(key, {scale:1}, {scale:0.92, transformOrigin:"50% 50%", duration:0.12, yoyo:true, repeat:1});
  step("s2");
  tl.call(function(){ label.textContent = "每個關節轉到兩端極限"; });
  tl.to(pan, {rotation:-120, svgOrigin:"500 110", duration:0.6}).to(pan, {rotation:120, svgOrigin:"500 110", duration:0.9}).to(pan, {rotation:0, svgOrigin:"500 110", duration:0.5});
  tl.to(st, {lift:-55, duration:0.6, onUpdate:r}).to(st, {lift:45, duration:0.9, onUpdate:r}).to(st, {lift:0, duration:0.5, onUpdate:r});
  tl.to(st, {elbow:-60, duration:0.6, onUpdate:r}).to(st, {elbow:75, duration:0.9, onUpdate:r}).to(st, {elbow:0, duration:0.5, onUpdate:r});
  tl.to(st, {wrist:-80, duration:0.5, onUpdate:r}).to(st, {wrist:80, duration:0.8, onUpdate:r}).to(st, {wrist:0, duration:0.4, onUpdate:r});
  tl.to(roll, {rotation:-150, svgOrigin:"610 110", duration:0.5}).to(roll, {rotation:150, svgOrigin:"610 110", duration:0.8}).to(roll, {rotation:0, svgOrigin:"610 110", duration:0.4});
  tl.to(st, {jaw:24, duration:0.4, onUpdate:r}).to(st, {jaw:0, duration:0.4, onUpdate:r});
  step("s3");
  tl.call(function(){ label.textContent = "完成後再按 Enter 存檔"; });
  tl.fromTo(key, {scale:1}, {scale:0.92, transformOrigin:"50% 50%", duration:0.12, yoyo:true, repeat:1});
};

/* ===== scene: teleop ===== */
SCENES.teleop = function(svg, tl, step){
  T(svg, 150, 26, "主控臂 Leader：用手帶動", "sv-t");
  T(svg, 500, 26, "執行臂 Follower：跟著動", "sv-t");
  var L = makeArm(svg, 150, 250, 0.85);
  var F = makeArm(svg, 500, 250, 0.85);
  var hand = E("circle", {r:13, fill:"var(--amber)", opacity:0.85}, L.root);
  var pc = G(svg);
  E("rect", {x:290, y:268, width:90, height:50, rx:5, "class":"sv-box"}, pc);
  T(pc, 335, 298, "電腦", "sv-t");
  var u1 = E("path", {d:"M190,270 C240,300 260,292 290,292", "class":"w w-blue"}, svg);
  var u2 = E("path", {d:"M380,292 C420,292 440,300 460,270", "class":"w w-blue"}, svg);
  function place(){ var a = L.state; hand.setAttribute("cx", 180 - a.lift * 0.4); hand.setAttribute("cy", -166 - a.elbow * 0.6); }
  place();
  if(!tl) return;
  function both(){ L.render(); place(); }
  var lag = 0.18;
  step("s1");
  tlDraw(tl, u1, {duration:0.4}); tlDraw(tl, u2, {duration:0.4});
  step("s2");
  var poses = [{lift:-30, elbow:30, wrist:-20, jaw:20}, {lift:25, elbow:-40, wrist:40, jaw:0}, {lift:-10, elbow:55, wrist:-50, jaw:22}, {lift:0, elbow:0, wrist:0, jaw:0}];
  poses.forEach(function(p){
    tl.to(L.state, Object.assign({duration:0.9, ease:"power1.inOut", onUpdate:both}, p));
    tl.to(F.state, Object.assign({duration:0.9, ease:"power1.inOut", onUpdate:F.render}, p), "<" + lag);
  });
};

window.__SO101 = {E:E, T:T, G:G, tlDraw:tlDraw, pinRow:pinRow, curve:curve, SCENES:SCENES, makeArm:makeArm};

/* ---------- boot ---------- */
function boot(){
  buildToc(); initChecks(); initCopy(); initDownloads(); initViewers();
  if(window.__SO101_EXTRA) window.__SO101_EXTRA();
  initScenes();
}
if(document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
