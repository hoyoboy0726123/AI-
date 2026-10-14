(function(){
"use strict";
var X = window.__SO101; if(!X) return;
var E = X.E, T = X.T, G = X.G, tlDraw = X.tlDraw, SC = X.SCENES;

/* ===== scene: weights (calibration with known weights) ===== */
SC.weights = function(svg, tl, step){
  var tool = G(svg);
  E("rect", {x:40, y:214, width:70, height:60, rx:5, "class":"sv-part"}, tool);
  T(tool, 75, 296, "固定座", "sv-ts");
  E("rect", {x:104, y:226, width:150, height:16, rx:3, "class":"sv-metal"}, tool);
  T(tool, 179, 262, "TAL221", "sv-ts");
  E("rect", {x:232, y:204, width:24, height:22, rx:3, "class":"sv-part"}, tool);
  var stack = G(svg);
  var wts = [{g:1, h:6, w:20}, {g:10, h:10, w:28}, {g:50, h:16, w:36}, {g:100, h:20, w:42}, {g:200, h:26, w:48}];
  var wEls = wts.map(function(w){
    var g = G(stack);
    E("rect", {x:244 - w.w / 2, y:204 - w.h, width:w.w, height:w.h, rx:3, "class":"sv-servo"}, g);
    T(g, 244, 204 - w.h / 2 + 4, w.g + "g", "sv-tw");
    g.style.opacity = 0;
    return g;
  });
  var disp = G(svg);
  E("rect", {x:40, y:40, width:200, height:70, rx:8, "class":"sv-box"}, disp);
  T(disp, 56, 64, "序列埠讀數", "sv-ts", "start");
  var val = T(disp, 224, 98, "0.0 g", "sv-big", "end");
  var ch = G(svg);
  var x0 = 340, y0 = 290, W = 300, H = 230;
  E("line", {x1:x0, y1:y0, x2:x0 + W, y2:y0, "class":"sv-thin"}, ch);
  E("line", {x1:x0, y1:y0, x2:x0, y2:y0 - H, "class":"sv-thin"}, ch);
  [0, 50, 100, 150, 200].forEach(function(v){
    var x = x0 + v / 200 * W, y = y0 - v / 200 * H;
    T(ch, x, y0 + 18, String(v), "sv-ts");
    T(ch, x0 - 8, y + 4, String(v), "sv-ts", "end");
    if(v) E("line", {x1:x0, y1:y, x2:x0 + W, y2:y, stroke:"var(--rule)"}, ch);
  });
  T(ch, x0 + W / 2, y0 + 38, "放上的砝碼（g）", "sv-ts");
  T(ch, x0, y0 - H - 12, "讀數（g）", "sv-ts", "start");
  var line = E("path", {d:"M" + x0 + "," + y0 + " L" + (x0 + W) + "," + (y0 - H), "class":"sv-accent-s"}, ch);
  var dots = wts.map(function(w){ return E("circle", {cx:x0 + w.g / 200 * W, cy:y0 - w.g / 200 * H, r:5.5, "class":"sv-accent"}, ch); });
  var zero = T(svg, 140, 140, "先歸零：送出 t", "sv-t");
  if(!tl){ wEls.forEach(function(g){ g.style.opacity = 1; }); val.textContent = "200.0 g"; return; }
  var o = {v:0};
  function show(){ val.textContent = o.v.toFixed(1) + " g"; }
  step("s1");
  tl.from(zero, {opacity:0, y:6, duration:0.3});
  tl.to(o, {v:0, duration:0.4, onUpdate:show});
  step("s2");
  var total = 0;
  wts.forEach(function(w, i){
    total = w.g;
    tl.set(wEls, {opacity:0});
    tl.fromTo(wEls[i], {opacity:0, y:-50}, {opacity:1, y:0, duration:0.45, ease:"bounce.out"});
    tl.to(o, {v:total, duration:0.5, ease:"power1.out", onUpdate:show}, "<0.2");
    tl.from(dots[i], {scale:0, transformOrigin:"50% 50%", duration:0.25}, ">-0.1");
    tl.to({}, {duration:0.35});
  });
  step("s3");
  tlDraw(tl, line, {duration:0.8});
};

/* ===== scene: push (thumbstick force control) ===== */
SC.push = function(svg, tl, step){
  var pad = G(svg);
  E("path", {d:"M60,250 h300 a20,20 0 0 1 20,20 v30 h-340 v-30 a20,20 0 0 1 20,-20z", "class":"sv-part"}, pad);
  T(pad, 210, 290, "遊戲手把（用治具固定）", "sv-ts");
  var stick = G(svg);
  E("circle", {cx:210, cy:250, r:16, "class":"sv-servo"}, stick);
  E("rect", {x:204, y:170, width:12, height:80, rx:4, "class":"sv-metal"}, stick);
  E("rect", {x:180, y:150, width:60, height:24, rx:10, "class":"sv-servo"}, stick);
  var probe = G(svg);
  E("rect", {x:300, y:154, width:150, height:14, rx:3, "class":"sv-metal"}, probe);
  E("rect", {x:440, y:132, width:60, height:58, rx:6, "class":"sv-part"}, probe);
  T(probe, 470, 208, "夾爪夾住治具", "sv-ts");
  E("circle", {cx:296, cy:161, r:9, "class":"sv-part"}, probe);
  T(probe, 370, 146, "荷重元", "sv-ts");
  var gauge = G(svg);
  var gx = 560, gy = 60, gh = 220;
  E("rect", {x:gx, y:gy, width:34, height:gh, rx:5, "class":"sv-box"}, gauge);
  var fill = E("rect", {x:gx + 3, y:gy + gh - 3, width:28, height:0, rx:3, "class":"sv-accent"}, gauge);
  function yOf(g){ return gy + gh - g / 320 * gh; }
  E("line", {x1:gx - 10, y1:yOf(50), x2:gx + 46, y2:yOf(50), stroke:"var(--mat)", "stroke-width":2.5}, gauge);
  T(gauge, gx - 14, yOf(50) + 4, "目標 50 g", "sv-ts", "end");
  E("line", {x1:gx - 10, y1:yOf(300), x2:gx + 46, y2:yOf(300), "class":"sv-red-s"}, gauge);
  T(gauge, gx - 14, yOf(300) + 4, "安全上限 300 g", "sv-ts", "end");
  var read = T(svg, gx + 17, gy + gh + 30, "0 g", "sv-tm");
  var stop = G(svg);
  E("rect", {x:250, y:40, width:200, height:44, rx:8, fill:"var(--mat)"}, stop);
  T(stop, 350, 68, "到達目標 → 停止", "sv-tw");
  stop.style.opacity = tl ? 0 : 1;
  var st = {px:90, f:0, tilt:0};
  function render(){
    probe.setAttribute("transform", "translate(" + st.px + ",0)");
    stick.setAttribute("transform", "rotate(" + (-st.tilt) + " 210 250)");
    var h = st.f / 320 * (gh - 6);
    fill.setAttribute("y", gy + gh - 3 - h); fill.setAttribute("height", Math.max(0, h));
    read.textContent = Math.round(st.f) + " g";
  }
  if(!tl){ st.px = 0; st.f = 50; st.tilt = 10; render(); return; }
  render();
  step("s1");
  tl.to(st, {px:20, duration:1.0, ease:"power1.inOut", onUpdate:render});
  step("s2");
  tl.to(st, {px:0, f:8, duration:0.5, ease:"none", onUpdate:render});
  tl.to(st, {px:-14, f:30, tilt:6, duration:0.8, ease:"none", onUpdate:render});
  tl.to(st, {px:-20, f:50, tilt:10, duration:0.8, ease:"power1.out", onUpdate:render});
  step("s3");
  tl.to(stop, {opacity:1, duration:0.3});
  tl.to(stop, {scale:1.05, transformOrigin:"50% 50%", yoyo:true, repeat:1, duration:0.2});
};
})();
