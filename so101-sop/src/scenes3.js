(function(){
"use strict";
var X = window.__SO101; if(!X) return;
var E = X.E, T = X.T, G = X.G, tlDraw = X.tlDraw, SC = X.SCENES;

/* ---- facts used by the scenes (kept in one place) ---- */
var MOTOR_ORDER = [
  ["gripper", "夾爪", 6], ["wrist_roll", "手腕旋轉", 5], ["wrist_flex", "手腕俯仰", 4],
  ["elbow_flex", "手肘", 3], ["shoulder_lift", "肩部抬升", 2], ["shoulder_pan", "肩部旋轉", 1]
];
var CELL_WIRES = [ // [load-cell wire colour class, colour name, HX711 terminal]
  ["w-red", "紅", "E+"], ["w-black", "黑", "E-"], ["w-white", "白", "A-"], ["w-green", "綠", "A+"]
];
var HX_OUT = [ // [HX711 pin, Nano pin, wire class]; VDD exists only on the SparkFun board
  ["VCC", "5V", "w-red"], ["VDD", "5V", "w-red"], ["GND", "GND", "w-black"], ["DT", "D2", "w-yellow"], ["SCK", "D3", "w-blue"]
];
var NANO_PINS = ["5V", "GND", "D2", "D3"];

/* ===== scene: motor ID setup ===== */
SC.motorid = function(svg, tl, step){
  var pc = G(svg);
  E("rect", {x:30, y:24, width:170, height:96, rx:6, "class":"sv-box"}, pc);
  E("rect", {x:18, y:120, width:194, height:8, rx:3, "class":"sv-box"}, pc);
  T(pc, 115, 56, "電腦", "sv-t");
  T(pc, 115, 82, "lerobot-setup-motors", "sv-tm");
  var prompt = T(pc, 115, 106, "", "sv-ts");
  var board = G(svg);
  E("rect", {x:50, y:206, width:130, height:70, rx:6, "class":"sv-pcb"}, board);
  T(board, 115, 236, "驅動板", "sv-tw"); T(board, 115, 256, "電源 + USB-C", "sv-tw");
  var usb = E("path", {d:"M115,206 C115,170 115,150 115,128", "class":"w w-blue"}, svg);
  var motor = G(svg);
  E("rect", {x:300, y:196, width:76, height:54, rx:6, "class":"sv-servo"}, motor);
  T(motor, 338, 228, "STS3215", "sv-tw");
  var badge = G(svg);
  E("rect", {x:304, y:150, width:68, height:30, rx:15, "class":"sv-accent"}, badge);
  var badgeT = T(badge, 338, 170, "ID ?", "sv-tw");
  var cable = E("path", {d:"M180,236 C230,236 250,224 300,224", "class":"w w-black"}, svg);
  T(svg, 338, 290, "一次只接一顆馬達", "sv-ts");
  var list = G(svg);
  var rows = MOTOR_ORDER.map(function(m, i){
    var g = G(list); var y = 44 + i * 44;
    E("rect", {x:440, y:y - 22, width:220, height:36, rx:6, "class":"sv-box"}, g);
    T(g, 456, y + 1, m[1], "sv-t", "start");
    T(g, 456, y + 14 - 2, "", "sv-ts", "start");
    T(g, 600, y + 1, "ID " + m[2], "sv-tm", "end");
    var ck = G(g);
    E("circle", {cx:640, cy:y - 4, r:11, "class":"sv-accent"}, ck);
    E("path", {d:"M634," + (y - 4) + " l4,5 l8,-9", stroke:"#fff", "stroke-width":2.6, fill:"none", "stroke-linecap":"round"}, ck);
    return {g:g, ck:ck};
  });
  if(!tl){ badgeT.textContent = "ID 1"; return; }
  step("s1");
  tl.from([pc, board], {opacity:0, y:10, duration:0.4, stagger:0.15});
  tlDraw(tl, usb, {duration:0.4});
  tl.set(rows.map(function(r){ return r.ck; }), {opacity:0});
  step("s2");
  MOTOR_ORDER.forEach(function(m, i){
    tl.call(function(){ prompt.textContent = "請只接上「" + m[1] + "」馬達，按 Enter"; badgeT.textContent = "ID ?"; });
    tl.fromTo(motor, {x:60, opacity:0}, {x:0, opacity:1, duration:0.35});
    tlDraw(tl, cable, {duration:0.35});
    tl.fromTo(badge, {scale:0, transformOrigin:"50% 50%"}, {scale:1, duration:0.3, ease:"back.out(2)"});
    tl.call(function(){ badgeT.textContent = "ID " + m[2]; });
    tl.to(rows[i].ck, {opacity:1, duration:0.2});
    tl.to(rows[i].g, {x:-4, duration:0.12, yoyo:true, repeat:1});
    if(i < MOTOR_ORDER.length - 1){
      tl.to(cable, {opacity:0, duration:0.15});
      tl.to([motor, badge], {x:-40, opacity:0, duration:0.3});
      tl.set([motor, badge, cable], {x:0, opacity:1});
    }
  });
  step("s3");
  tl.call(function(){ prompt.textContent = "6 顆都設定完成"; });
  tl.from(list, {scale:1.02, transformOrigin:"50% 50%", duration:0.3});
};

/* ===== scene: probe jig assembly (side view, matches probe_tool design) ===== */
SC.jig = function(svg, tl, step){
  var X0 = 300, k = 3;
  function px(x){ return X0 + x * k; }
  function pz(z){ return 40 + (32 - z) * k; }
  T(svg, 20, 26, "側視圖，單位依實際尺寸等比例", "sv-ts", "start");
  var jawL = G(svg), jawR = G(svg);
  E("path", {d:"M" + px(-26) + "," + pz(40) + " H" + px(-12) + " V" + pz(-2) + " L" + px(-16) + "," + pz(-6) + " H" + px(-26) + "z", "class":"sv-part"}, jawL);
  T(jawL, px(-19), pz(42), "固定爪", "sv-ts");
  E("path", {d:"M" + px(12) + "," + pz(40) + " H" + px(26) + " V" + pz(-6) + " H" + px(16) + " L" + px(12) + "," + pz(-2) + "z", "class":"sv-part"}, jawR);
  T(jawR, px(19), pz(42), "活動爪", "sv-ts");
  var block = G(svg);
  E("rect", {x:px(-12), y:pz(32), width:24 * k, height:32 * k, rx:3, fill:"var(--w-blue)", opacity:0.85, stroke:"var(--ink)", "stroke-width":1.4}, block);
  T(block, px(0), pz(16), "治具座", "sv-tw");
  E("rect", {x:px(-8), y:pz(0), width:5 * k, height:10 * k, fill:"var(--w-blue)", opacity:0.85, stroke:"var(--ink)", "stroke-width":1.4}, block);
  var bar = G(svg);
  E("rect", {x:px(-3), y:pz(-4), width:6 * k, height:47 * k, rx:2, "class":"sv-metal"}, bar);
  T(bar, px(-30), pz(-28), "TAL221：中間要懸空", "sv-ts", "end");
  E("path", {d:"M" + px(-29) + "," + pz(-27) + " H" + px(-4), "class":"sv-thin"}, bar);
  var s1 = G(svg);
  E("rect", {x:px(-14), y:pz(-7.5) - 3, width:15 * k, height:6, rx:1, "class":"sv-servo"}, s1);
  E("rect", {x:px(-16), y:pz(-7.5) - 6, width:2 * k, height:12, rx:1, "class":"sv-servo"}, s1);
  T(s1, px(-30), pz(-7.5) + 4, "固定端：2 × M3×10", "sv-ts", "end");
  var tip = G(svg);
  E("rect", {x:px(3), y:pz(-45), width:3.5 * k, height:13 * k, fill:"var(--red)", opacity:0.85, stroke:"var(--ink)", "stroke-width":1.2}, tip);
  E("path", {d:"M" + px(6.5) + "," + (pz(-54) - 9) + " L" + px(16) + "," + (pz(-54) - 6) + " A6,6 0 0 1 " + px(16) + "," + (pz(-54) + 6) + " L" + px(6.5) + "," + (pz(-54) + 9) + "z", fill:"var(--red)", opacity:0.85, stroke:"var(--ink)", "stroke-width":1.2}, tip);
  var s2 = G(svg);
  E("rect", {x:px(-6), y:pz(-47.5) - 3, width:14 * k, height:6, rx:1, "class":"sv-servo"}, s2);
  E("rect", {x:px(-9), y:pz(-47.5) - 6, width:3 * k, height:12, rx:1, "class":"sv-servo"}, s2);
  T(s2, px(24), pz(-44), "自由端：推頭 + 2 × M3×12 + 螺帽", "sv-ts", "start");
  var wires = G(svg);
  var wd = "M" + px(-1) + "," + pz(-4) + " C" + px(-1) + "," + pz(2) + " " + px(-10) + "," + pz(4) + " " + px(-10) + "," + pz(12);
  E("path", {d:wd, "class":"w w-red"}, wires);
  E("path", {d:wd, "class":"w w-green", transform:"translate(4,0)"}, wires);
  T(wires, px(-30), pz(12), "細線穿過治具座側面的固定柱", "sv-ts", "end");
  var tie = G(svg);
  E("rect", {x:px(-28), y:pz(29) - 4, width:56 * k, height:8, rx:3, fill:"var(--amber)", stroke:"var(--ink)", "stroke-width":1}, tie);
  T(tie, px(30), pz(29) + 4, "束帶綁住兩根爪", "sv-ts", "start");
  var arrow = G(svg);
  E("path", {d:"M" + px(22) + "," + pz(-54) + " H" + px(44) + " M" + px(38) + "," + (pz(-54) - 6) + " L" + px(44) + "," + pz(-54) + " L" + px(38) + "," + (pz(-54) + 6), "class":"sv-accent-s"}, arrow);
  T(arrow, px(46), pz(-54) + 5, "推的方向", "sv-ts", "start");
  if(!tl) return;
  step("s1");
  tl.from(block, {opacity:0, duration:0.4});
  tl.from(bar, {y:60, opacity:0, duration:0.6});
  tl.from(s1, {x:-60, opacity:0, duration:0.5});
  step("s2");
  tl.from(tip, {x:50, opacity:0, duration:0.5});
  tl.from(s2, {x:-40, opacity:0, duration:0.4});
  step("s3");
  tl.from(wires, {opacity:0, duration:0.5});
  step("s4");
  tl.from(jawL, {x:-40, opacity:0, duration:0.5});
  tl.from(jawR, {x:40, opacity:0, duration:0.5}, "<");
  tl.from(tie, {scaleX:0, transformOrigin:"50% 50%", duration:0.5});
  tl.from(arrow, {opacity:0, x:-10, duration:0.4});
};

/* ===== scene: force sensor wiring ===== */
SC.forcewire = function(svg, tl, step){
  var cell = G(svg);
  E("rect", {x:24, y:150, width:170, height:26, rx:3, "class":"sv-metal"}, cell);
  T(cell, 109, 202, "TAL221 荷重元", "sv-t");
  E("path", {d:"M150,120 v22 M144,134 l6,8 l6,-8", "class":"sv-ink"}, cell);
  T(cell, 150, 112, "受力方向", "sv-ts");
  var hx = G(svg);
  E("rect", {x:280, y:90, width:140, height:170, rx:6, "class":"sv-pcb"}, hx);
  T(hx, 350, 82, "HX711 放大板", "sv-t");
  var hxL = {}, hxR = {};
  CELL_WIRES.forEach(function(w, i){ var y = 120 + i * 30; E("circle", {cx:290, cy:y, r:5, fill:"var(--w-yellow)", stroke:"var(--ink)"}, hx); T(hx, 302, y + 4, w[2], "sv-tw", "start"); hxL[w[2]] = [290, y]; });
  HX_OUT.forEach(function(p, i){ var y = 112 + i * 30; E("circle", {cx:410, cy:y, r:5, fill:"var(--w-yellow)", stroke:"var(--ink)"}, hx); T(hx, 398, y + 4, p[0], "sv-tw", "end"); hxR[p[0]] = [410, y]; });
  var nano = G(svg);
  E("rect", {x:510, y:70, width:120, height:210, rx:6, fill:"var(--w-blue)", stroke:"var(--ink)", "stroke-width":1.4}, nano);
  T(nano, 570, 62, "Arduino Nano", "sv-t");
  var nanoP = {};
  NANO_PINS.forEach(function(n, i){ var y = 120 + i * 36; E("circle", {cx:520, cy:y, r:5, fill:"var(--w-yellow)", stroke:"var(--ink)"}, nano); T(nano, 532, y + 4, n, "sv-tw", "start"); nanoP[n] = [520, y]; });
  E("rect", {x:552, y:270, width:36, height:22, rx:3, "class":"sv-metal"}, nano);
  var usb = E("path", {d:"M570,292 C570,310 600,316 640,316", "class":"w w-blue"}, svg);
  T(svg, 650, 312, "接電腦", "sv-ts", "start");
  var cw = CELL_WIRES.map(function(w, i){
    var a = [194, 156 + i * 4], b = hxL[w[2]];
    E("path", {d:X.curve(a, b, 30), "class":"w-under"}, svg);
    var p = E("path", {d:X.curve(a, b, 30), "class":"w " + w[0]}, svg);
    return p;
  });
  var hw = HX_OUT.map(function(p){
    var a = hxR[p[0]], b = nanoP[p[1]];
    E("path", {d:X.curve(a, b, 20), "class":"w-under"}, svg);
    return E("path", {d:X.curve(a, b, 20), "class":"w " + p[2]}, svg);
  });
  var legend = G(svg);
  CELL_WIRES.forEach(function(w, i){ T(legend, 24 + i * 62, 248, w[1] + "→" + w[2], "sv-ts", "start"); });
  T(legend, 24, 274, "VDD 只有 SparkFun 板才有，也接 5V", "sv-ts", "start");
  var pulse = E("circle", {r:5, fill:"var(--amber)", opacity:0}, svg);
  var serial = G(svg);
  E("rect", {x:24, y:26, width:220, height:40, rx:5, fill:"var(--code)", stroke:"var(--rule)"}, serial);
  T(serial, 36, 51, "F,10342,50.12", "sv-tm", "start");
  if(!tl) return;
  step("s1");
  tl.from([cell, hx, nano], {opacity:0, y:8, duration:0.35, stagger:0.12});
  step("s2");
  cw.forEach(function(p){ tlDraw(tl, p, {duration:0.45}); });
  step("s3");
  hw.forEach(function(p){ tlDraw(tl, p, {duration:0.45}); });
  tlDraw(tl, usb, {duration:0.4});
  step("s4");
  tl.set(pulse, {opacity:1});
  var dt = hw[3], L = dt.getTotalLength(), o = {t:0};
  tl.to(o, {t:1, duration:0.6, ease:"none", repeat:2, onUpdate:function(){ var pt = dt.getPointAtLength(o.t * L); pulse.setAttribute("cx", pt.x); pulse.setAttribute("cy", pt.y); }});
  tl.to(pulse, {opacity:0, duration:0.2});
  tl.from(serial, {opacity:0, y:-8, duration:0.35});
};
})();
