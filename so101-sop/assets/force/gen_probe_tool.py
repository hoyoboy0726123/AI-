#!/usr/bin/env python3
"""
gen_probe_tool.py - parametric SO-101 force-probe tool (TAL221 cantilever) -> binary STL.

Parts
  probe_block.stl : block that the SO-101 follower gripper clamps + "tongue" that holds the
                    FIXED end of the TAL221 (the end WITH the wires, M3 threaded holes)
                    + wire strain relief (weave pins + bridge channel).
  probe_tip.stl   : plate + rounded probe tip, bolted to the FREE end of the TAL221
                    (the end WITHOUT wires, M3 clearance holes) with 2x M3 screw + nut.

Same geometry and parameter names as probe_tool.scad. Measure your load cell with
calipers and edit the CELL_* values if they differ.

Requirements: python >= 3.10, numpy, trimesh, manifold3d
    pip install numpy trimesh manifold3d
Usage:
    python gen_probe_tool.py [--out DIR] [--clamp-w 24] [--preview]

Design frame (mm): x = gripper closing direction = load-cell sensing axis (screw axis),
y = across the finger width, z = along the fingers. Block grip zone z = 0..CLAMP_LEN,
fingertip side at z = 0; the load cell sticks out towards -z.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import trimesh
from manifold3d import Manifold

SEG = 64  # circle resolution


@dataclass
class P:
    # ---- TAL221 load cell (VERIFY WITH CALIPERS) ----
    cell_len: float = 47.0        # overall length (retailer + manufacturer listings)
    cell_w: float = 12.0          # width; the 2 holes of each end sit across this width
    cell_t: float = 6.0           # thickness = screw axis = sensing direction
    cell_head_len: float = 7.0    # solid end "head" carrying the holes (3rd-party CAD model value)
    hole_from_end: float = 3.5    # hole centre to bar end (3rd-party CAD model value)
    hole_pitch: float = 6.0       # hole centre-to-centre across width (checked on 3 mating parts)
    # ---- fasteners ----
    m3_clear_d: float = 3.4       # M3 clearance hole
    m3_head_d: float = 6.0        # pan/cap head diameter (for clearance checks only)
    # ---- clamp block (gripped by the SO-101 jaws on its +/-x faces) ----
    clamp_w: float = 24.0         # thickness between the jaws (x). SO-101 URDF: jaw faces ~parallel at 24-28 mm
    clamp_h: float = 16.0         # height across the finger width (y); SO-101 fingers are ~15-17 mm wide
    clamp_len: float = 32.0       # grip length along the fingers (z)
    edge_chamfer: float = 1.0     # chamfer on block's long edges
    tie_groove_z: float = 29.0    # zip-tie groove across the +/-y faces (strap block to BOTH fingers)
    tie_groove_w: float = 3.0
    tie_groove_d: float = 1.0
    # ---- tongue = pad for the fixed end of the cell ----
    tongue_t: float = 5.0         # pad thickness (x). With M3x10 screw -> 5 mm thread engagement
    cable_gap: float = 4.0        # free space between block front (z=0) and the bar's wire end
    pad_len: float = 6.0          # pad contact length on the head (MUST be <= cell_head_len)
    # ---- probe tip (on the free end) ----
    tip_plate_t: float = 3.5      # plate thickness (x); M3x12 + nut (3.5 + 6 + 2.4 = 11.9 mm)
    tip_pad_len: float = 6.0      # plate contact length on the free head (<= cell_head_len)
    tip_overhang: float = 7.0     # plate extends this far beyond the bar end; stem sits there
    stem_d: float = 6.0           # stem diameter at the plate
    tip_d: float = 4.0            # rounded tip diameter
    stem_len: float = 12.0        # stem length incl. rounded tip
    # ---- strain relief (on the +y face of the block) ----
    pin_d: float = 2.5
    pin_h: float = 3.0
    pin_dx: float = 2.0           # pins alternate x = -pin_dx / +pin_dx (wires weave between)
    bridge_gap_w: float = 6.0     # channel width under the bridge
    bridge_gap_h: float = 2.5     # channel height under the bridge
    bridge_len: float = 4.0       # bridge length along z


def box(x0, x1, y0, y1, z0, z1) -> Manifold:
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl_x(d, x0, x1, y, z, d2=None) -> Manifold:
    """Cylinder (or cone) along +x from x0 to x1 at (y, z)."""
    c = Manifold.cylinder(x1 - x0, d / 2, (d2 if d2 is not None else d) / 2, SEG)
    return c.rotate([0, 90, 0]).translate([x0, y, z])


def cyl_y(d, y0, y1, x, z) -> Manifold:
    c = Manifold.cylinder(y1 - y0, d / 2, d / 2, SEG)
    return c.rotate([-90, 0, 0]).translate([x, y0, z])


def cell_geometry(p: P):
    """Return useful coordinates of the mounted cell (bar centred on x = 0)."""
    x_neg = -p.cell_t / 2                     # bar -x face (sits on the tongue)
    x_pos = p.cell_t / 2                      # bar +x face (probe tip plate sits here)
    z_fixed_end = -p.cable_gap                # bar end with wires
    z_free_end = -p.cable_gap - p.cell_len    # bar end without wires
    z_fixed_holes = z_fixed_end - p.hole_from_end
    z_free_holes = z_free_end + p.hole_from_end
    return x_neg, x_pos, z_fixed_end, z_free_end, z_fixed_holes, z_free_holes


def make_block(p: P) -> Manifold:
    assert p.pad_len <= p.cell_head_len, "pad would touch the flexing part of the cell"
    x_neg, _, z_fixed_end, _, z_fixed_holes, _ = cell_geometry(p)
    hw, hh = p.clamp_w / 2, p.clamp_h / 2
    body = box(-hw, hw, -hh, hh, 0, p.clamp_len)
    # chamfer the 4 long edges (parallel to z) so the jaws seat cleanly
    c = p.edge_chamfer
    if c > 0:
        cutter = Manifold.cube([2 * c, 2 * c, p.clamp_len + 2], center=True).rotate([0, 0, 45])
        for sx in (-1, 1):
            for sy in (-1, 1):
                body -= cutter.translate([sx * hw, sy * hh, p.clamp_len / 2])
    # zip-tie groove across the +y and -y faces (tie goes around both fingers + block)
    if p.tie_groove_d > 0:
        for sy in (-1, 1):
            y0 = hh - p.tie_groove_d if sy > 0 else -hh - 1
            y1 = hh + 1 if sy > 0 else -hh + p.tie_groove_d
            body -= box(-hw - 1, hw + 1, y0, y1, p.tie_groove_z - p.tie_groove_w / 2, p.tie_groove_z + p.tie_groove_w / 2)
    # tongue: pad for the fixed end (contacts only the head, z_fixed_end .. z_fixed_end - pad_len)
    tongue = box(x_neg - p.tongue_t, x_neg, -hh, hh, z_fixed_end - p.pad_len, 0.5)
    part = body + tongue
    # M3 clearance holes through the tongue (screws go +x into the cell's threaded holes)
    for y in (-p.hole_pitch / 2, p.hole_pitch / 2):
        part -= cyl_x(p.m3_clear_d, x_neg - p.tongue_t - 1, x_neg + 1, y, z_fixed_holes)
    # strain relief on +y face: 3 weave pins + bridge channel
    top = hh
    for i, z in enumerate((5.0, 11.0, 17.0)):
        x = -p.pin_dx if i % 2 == 0 else p.pin_dx
        part += cyl_y(p.pin_d, top - 0.5, top + p.pin_h, x, z)
    zb0 = 22.0
    post_w = 2.5
    gx = p.bridge_gap_w / 2
    for sx in (-1, 1):
        x0, x1 = (gx, gx + post_w) if sx > 0 else (-gx - post_w, -gx)
        part += box(x0, x1, top - 0.5, top + p.bridge_gap_h, zb0, zb0 + p.bridge_len)
    part += box(-gx - post_w, gx + post_w, top + p.bridge_gap_h, top + p.bridge_gap_h + 1.6,
                zb0, zb0 + p.bridge_len)
    return part


def make_tip(p: P) -> Manifold:
    assert p.tip_pad_len <= p.cell_head_len, "tip plate would touch the flexing part of the cell"
    _, x_pos, _, z_free_end, _, z_free_holes = cell_geometry(p)
    hw = p.cell_w / 2
    x0, x1 = x_pos, x_pos + p.tip_plate_t
    z_lo, z_hi = z_free_end - p.tip_overhang, z_free_end + p.tip_pad_len
    plate = box(x0, x1, -hw, hw, z_lo, z_hi)
    z_stem = z_free_end - p.tip_overhang / 2
    # make sure the stem does not hit the screw heads
    assert (z_free_holes - p.m3_head_d / 2) - (z_stem + p.stem_d / 2) > 0.5, "stem hits screw heads"
    cone_len = p.stem_len - p.tip_d / 2
    stem = cyl_x(p.stem_d, x1 - 0.5, x1 + cone_len, 0, z_stem, d2=p.tip_d)
    ball = Manifold.sphere(p.tip_d / 2, SEG).translate([x1 + cone_len, 0, z_stem])
    part = plate + stem + ball
    for y in (-p.hole_pitch / 2, p.hole_pitch / 2):
        part -= cyl_x(p.m3_clear_d, x0 - 1, x1 + 1, y, z_free_holes)
    return part


def make_cell_dummy(p: P) -> Manifold:
    """Simple TAL221 envelope for the assembly preview only."""
    x_neg, x_pos, z_fixed_end, z_free_end, _, _ = cell_geometry(p)
    return box(x_neg, x_pos, -p.cell_w / 2, p.cell_w / 2, z_free_end, z_fixed_end)


def to_trimesh(m: Manifold) -> trimesh.Trimesh:
    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                           faces=np.asarray(mesh.tri_verts), process=True)


def for_printing(m: Manifold, which: str) -> Manifold:
    """Rotate so the flat print face is on the bed (z = 0)."""
    if which == "block":      # -y face down, strain-relief pins up
        m = m.rotate([90, 0, 0])
    elif which == "tip":      # plate face that touches the cell down, tip pointing up
        m = m.rotate([0, -90, 0])
    lo = np.array(m.bounding_box()[:3])
    return m.translate([-lo[0], -lo[1], -lo[2]])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--clamp-w", type=float, help="override clamp_w (mm)")
    ap.add_argument("--preview", action="store_true", help="also write probe_assembly_preview.stl")
    a = ap.parse_args()
    p = P()
    if a.clamp_w:
        p.clamp_w = a.clamp_w
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    parts = {"probe_block": for_printing(make_block(p), "block"),
             "probe_tip": for_printing(make_tip(p), "tip")}
    if a.preview:
        parts["probe_assembly_preview"] = make_block(p) + make_tip(p) + make_cell_dummy(p)
    for name, m in parts.items():
        tm = to_trimesh(m)
        path = out / f"{name}.stl"
        tm.export(path, file_type="stl")          # binary STL
        chk = trimesh.load(path)
        print(f"{name}.stl  watertight={chk.is_watertight}  volume={chk.volume:.1f} mm^3  "
              f"size={np.round(chk.extents, 2).tolist()} mm  triangles={len(chk.faces)}  "
              f"manifold_genus={m.genus()}")
    print("parameters:", asdict(p))


if __name__ == "__main__":
    main()
