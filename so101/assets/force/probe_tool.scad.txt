// probe_tool.scad - SO-101 force-probe tool for a TAL221 mini load cell (100 g / 500 g)
// Same design and parameter names as gen_probe_tool.py (which writes probe_block.stl / probe_tip.stl).
//
// HOW TO USE
//   1. Measure YOUR load cell with calipers and edit the "TAL221" section below
//      (most important: hole_pitch, hole_from_end, cell_head_len, cell_t).
//   2. Choose `part` below: "block", "tip", "assembly" (preview only) or "both" (print layout).
//   3. F6 (Render) -> File > Export > STL.
//
// Design frame (mm): x = gripper closing direction = load-cell sensing axis (= screw axis),
// y = across the finger width, z = along the fingers. Grip zone of the block: z = 0..clamp_len
// (fingertip side at z = 0). The load cell sticks out towards -z.
//
// Assembly
//   * FIXED end of the TAL221 = the end WITH the 4 wires (M3 threaded holes): screw it to the
//     tongue of the block with 2x M3x10 from the tongue side (do NOT use longer screws).
//   * FREE end (no wires, M3 clearance holes): probe tip plate on the other face,
//     2x M3x12 (or x14) through plate + cell, M3 nuts on the far side.
//   * Only the two end "heads" of the cell may touch printed parts. The middle (white potting /
//     strain gauges) must be free in air.

part = "assembly";   // "block" | "tip" | "assembly" | "both"

/* [TAL221 load cell - VERIFY WITH CALIPERS] */
cell_len      = 47.0;  // overall length (retailer + manufacturer listings: 47 x 12 x 6 mm)
cell_w        = 12.0;  // width; each end has 2 holes side by side across this width
cell_t        = 6.0;   // thickness = screw axis = sensing direction
cell_head_len = 7.0;   // length of the solid end "head" that carries the holes (3rd-party CAD model value)
hole_from_end = 3.5;   // hole centre to bar end (3rd-party CAD model value) -> pairs are 40 mm apart
hole_pitch    = 6.0;   // hole centre-to-centre across the width (checked on 3 independent mating parts)

/* [Fasteners] */
m3_clear_d = 3.4;      // M3 clearance hole (print test: M3 screw must slide through)
m3_head_d  = 6.0;      // screw head diameter (clearance check only)

/* [Clamp block gripped by the SO-101 jaws] */
clamp_w      = 24.0;   // thickness between the jaws. SO-101 URDF model: finger faces ~parallel at 24-28 mm
clamp_h      = 16.0;   // height across the finger width (fingers are ~15-17 mm wide)
clamp_len    = 32.0;   // grip length along the fingers
edge_chamfer = 1.0;
tie_groove_z = 29.0;   // zip-tie groove across the +/-y faces: strap the block to BOTH fingers
tie_groove_w = 3.0;
tie_groove_d = 1.0;

/* [Tongue = pad for the fixed end] */
tongue_t  = 5.0;       // pad thickness; M3x10 gives 5 mm thread engagement in the 6 mm cell
cable_gap = 4.0;       // space between block front and the wire end of the cell
pad_len   = 6.0;       // pad contact length on the head, MUST be <= cell_head_len

/* [Probe tip on the free end] */
tip_plate_t  = 3.5;    // with M3x12: 3.5 + 6 + 2.4 (nut) = 11.9 mm
tip_pad_len  = 6.0;    // <= cell_head_len
tip_overhang = 7.0;    // plate extends beyond the bar end; the stem sits there
stem_d       = 6.0;
tip_d        = 4.0;    // rounded tip diameter
stem_len     = 12.0;   // stem length including the rounded tip

/* [Wire strain relief on the +y face] */
pin_d        = 2.5;
pin_h        = 3.0;
pin_dx       = 2.0;    // pins alternate left/right, weave the wires between them
bridge_gap_w = 6.0;
bridge_gap_h = 2.5;
bridge_len   = 4.0;

$fn = 64;

// ---------- derived ----------
hw = clamp_w / 2;
hh = clamp_h / 2;
x_neg = -cell_t / 2;                 // cell face on the tongue
x_pos =  cell_t / 2;                 // cell face carrying the tip plate
z_fixed_end   = -cable_gap;
z_free_end    = -cable_gap - cell_len;
z_fixed_holes = z_fixed_end - hole_from_end;
z_free_holes  = z_free_end + hole_from_end;
z_stem        = z_free_end - tip_overhang / 2;

assert(pad_len <= cell_head_len, "pad_len would touch the flexing part of the cell");
assert(tip_pad_len <= cell_head_len, "tip_pad_len would touch the flexing part of the cell");
assert((z_free_holes - m3_head_d / 2) - (z_stem + stem_d / 2) > 0.5, "stem hits screw heads");

module box(x0, x1, y0, y1, z0, z1) { translate([x0, y0, z0]) cube([x1 - x0, y1 - y0, z1 - z0]); }
module cyl_x(d, x0, x1, y, z, d2 = undef) {
    translate([x0, y, z]) rotate([0, 90, 0]) cylinder(h = x1 - x0, d1 = d, d2 = (d2 == undef ? d : d2));
}
module cyl_y(d, y0, y1, x, z) { translate([x, y0, z]) rotate([-90, 0, 0]) cylinder(h = y1 - y0, d = d); }

module clamp_block() {
    difference() {
        union() {
            difference() {
                box(-hw, hw, -hh, hh, 0, clamp_len);
                if (edge_chamfer > 0)
                    for (sx = [-1, 1], sy = [-1, 1])
                        translate([sx * hw, sy * hh, clamp_len / 2]) rotate([0, 0, 45])
                            cube([2 * edge_chamfer, 2 * edge_chamfer, clamp_len + 2], center = true);
                if (tie_groove_d > 0) {
                    box(-hw - 1, hw + 1, hh - tie_groove_d, hh + 1, tie_groove_z - tie_groove_w / 2, tie_groove_z + tie_groove_w / 2);
                    box(-hw - 1, hw + 1, -hh - 1, -hh + tie_groove_d, tie_groove_z - tie_groove_w / 2, tie_groove_z + tie_groove_w / 2);
                }
            }
            // tongue (pad for the fixed end)
            box(x_neg - tongue_t, x_neg, -hh, hh, z_fixed_end - pad_len, 0.5);
            // strain relief: weave pins
            for (i = [0 : 2])
                cyl_y(pin_d, hh - 0.5, hh + pin_h, (i % 2 == 0 ? -pin_dx : pin_dx), 5 + 6 * i);
            // strain relief: bridge channel
            zb0 = 22;
            post_w = 2.5;
            gx = bridge_gap_w / 2;
            box(gx, gx + post_w, hh - 0.5, hh + bridge_gap_h, zb0, zb0 + bridge_len);
            box(-gx - post_w, -gx, hh - 0.5, hh + bridge_gap_h, zb0, zb0 + bridge_len);
            box(-gx - post_w, gx + post_w, hh + bridge_gap_h, hh + bridge_gap_h + 1.6, zb0, zb0 + bridge_len);
        }
        // M3 clearance holes through the tongue
        for (y = [-hole_pitch / 2, hole_pitch / 2])
            cyl_x(m3_clear_d, x_neg - tongue_t - 1, x_neg + 1, y, z_fixed_holes);
    }
}

module probe_tip() {
    x0 = x_pos;
    x1 = x_pos + tip_plate_t;
    cone_len = stem_len - tip_d / 2;
    difference() {
        union() {
            box(x0, x1, -cell_w / 2, cell_w / 2, z_free_end - tip_overhang, z_free_end + tip_pad_len);
            cyl_x(stem_d, x1 - 0.5, x1 + cone_len, 0, z_stem, tip_d);
            translate([x1 + cone_len, 0, z_stem]) sphere(d = tip_d);
        }
        for (y = [-hole_pitch / 2, hole_pitch / 2])
            cyl_x(m3_clear_d, x0 - 1, x1 + 1, y, z_free_holes);
    }
}

module cell_dummy() {   // TAL221 envelope, preview only
    color("silver") box(x_neg, x_pos, -cell_w / 2, cell_w / 2, z_free_end, z_fixed_end);
}

// print orientation: flat face on the bed (z = 0)
module block_for_print() {
    translate([hw, clamp_len, hh]) rotate([90, 0, 0]) clamp_block();
}
module tip_for_print() {
    translate([z_free_end + tip_pad_len, cell_w / 2, -x_pos]) rotate([0, -90, 0]) probe_tip();
}

if (part == "block") block_for_print();
else if (part == "tip") tip_for_print();
else if (part == "both") { block_for_print(); translate([clamp_w + 8, 0, 0]) tip_for_print(); }
else { color("steelblue") clamp_block(); color("tomato") probe_tip(); cell_dummy(); }
