"""Build the step-by-step assembly data from the official SO-101 URDF.

usage: python3 src/tools/gen_assembly.py <SO-ARM100>/Simulation/SO101

Reads so101_new_calib.urdf (follower) and so101_leader_new_calib.urdf (leader),
places every visual mesh at the zero pose (middle of each joint range),
decimates the meshes and writes:
  assets/asm/asm_<mesh>.stl   decimated meshes in millimetres, mesh-local coordinates
  assets/asm/assembly.json    part poses and the assembly order used by the page
Needs numpy and fast_simplification.
"""
import json, pathlib, struct, sys
import xml.etree.ElementTree as ET
import numpy as np
import fast_simplification

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/asm"
MAX_TRIS = 4500
STL_DT = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])

# (link, mesh stem, occurrence in that link) -> part id
PART_IDS = {
    ("base_link", "base_so101_v2", 0): "base",
    ("base_link", "sts3215_03a_v1", 0): "motor1",
    ("base_link", "base_motor_holder_so101_v1", 0): "holder1",
    ("base_link", "waveshare_mounting_plate_so101_v2", 0): "plate",
    ("shoulder_link", "rotation_pitch_so101_v1", 0): "shoulder",
    ("shoulder_link", "motor_holder_so101_base_v1", 0): "holder2",
    ("shoulder_link", "sts3215_03a_v1", 0): "motor2",
    ("upper_arm_link", "upper_arm_so101_v1", 0): "upper_arm",
    ("upper_arm_link", "sts3215_03a_v1", 0): "motor3",
    ("lower_arm_link", "under_arm_so101_v1", 0): "forearm",
    ("lower_arm_link", "motor_holder_so101_wrist_v1", 0): "holder4",
    ("lower_arm_link", "sts3215_03a_v1", 0): "motor4",
    ("wrist_link", "wrist_roll_pitch_so101_v2", 0): "wrist",
    ("wrist_link", "sts3215_03a_no_horn_v1", 0): "motor5",
    ("gripper_link", "sts3215_03a_v1", 0): "motor6",
    ("gripper_link", "wrist_roll_follower_so101_v1", 0): "gripper_body",
    ("moving_jaw_so101_v1_link", "moving_jaw_so101_v1", 0): "jaw",
    ("gripper_link", "Wrist_Roll_SO101", 0): "leader_holder",
    ("gripper_link", "Handle_SO101", 0): "handle",
    ("trigger_link", "Trigger_SO101", 0): "trigger",
}

LABELS = {
    "base": "底座", "motor1": "馬達 1", "holder1": "第一個馬達座", "plate": "驅動板固定板",
    "shoulder": "肩部零件", "holder2": "肩部馬達座", "motor2": "馬達 2", "upper_arm": "上臂",
    "motor3": "馬達 3", "forearm": "前臂", "holder4": "馬達座 4", "motor4": "馬達 4",
    "wrist": "手腕座", "motor5": "馬達 5", "motor6": "馬達 6", "gripper_body": "夾爪本體",
    "jaw": "活動爪", "leader_holder": "主控臂手腕座", "handle": "握把", "trigger": "扳機",
}

# Assembly order follows the official LeRobot so101.mdx text, sub-step by sub-step.
JOINTS = [
    {"id": "j1", "title": "關節 1", "subs": [
        (["base", "motor1"], "馬達 1 放進底座，上下各 2 顆 M2×6 固定"),
        (["holder1"], "套上第一個馬達座，左右各 1 顆 M2×6"),
        (["shoulder"], "裝上肩部零件，上下各 4 顆 M3×6"),
        (["holder2"], "裝上肩部馬達座"),
    ]},
    {"id": "j2", "title": "關節 2", "subs": [
        (["motor2"], "馬達 2 從上方滑入，4 顆 M2×6 固定"),
        (["upper_arm"], "裝上上臂，每側 4 顆 M3×6"),
    ]},
    {"id": "j3", "title": "關節 3", "subs": [
        (["motor3"], "馬達 3 裝進上臂，4 顆 M2×6 固定"),
        (["forearm"], "前臂接到馬達 3，每側 4 顆 M3×6"),
    ]},
    {"id": "j4", "title": "關節 4", "subs": [
        (["holder4"], "套上馬達座 4"),
        (["motor4"], "馬達 4 滑入，4 顆 M2×6 固定"),
    ]},
    {"id": "j5", "title": "關節 5", "subs": [
        (["wrist", "motor5"], "馬達 5 裝進手腕座，前面 2 顆 M2×6；只裝 1 個舵盤"),
        ([], "整個手腕用 M3×6 鎖到馬達 4 上"),
    ]},
]
FOLLOWER_TAIL = [
    {"id": "grip", "title": "夾爪", "subs": [
        (["gripper_body"], "夾爪本體鎖到馬達 5 的舵盤，4 顆 M3×6"),
        (["motor6"], "裝入夾爪馬達，每側 2 顆 M2×6"),
        (["jaw"], "裝上活動爪，用 M3×6 固定"),
    ]},
    {"id": "board", "title": "驅動板", "subs": [
        (["plate"], "驅動板固定板裝在底座後方"),
    ]},
]
LEADER_TAIL = [
    {"id": "handle", "title": "握把與扳機", "subs": [
        (["leader_holder"], "主控臂手腕座鎖到手腕，4 顆 M3×6"),
        (["handle"], "握把用 1 顆 M2×6 鎖上"),
        (["motor6"], "裝入夾爪馬達，每側 2 顆 M2×6，裝上舵盤"),
        (["trigger"], "扳機用 4 顆 M3×6 鎖上"),
    ]},
    {"id": "board", "title": "驅動板", "subs": [
        (["plate"], "驅動板固定板裝在底座後方"),
    ]},
]


def rpy_matrix(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return rz @ ry @ rx


def origin_tf(el):
    t = np.eye(4)
    if el is None:
        return t
    xyz = [float(v) for v in el.get("xyz", "0 0 0").split()]
    rpy = [float(v) for v in el.get("rpy", "0 0 0").split()]
    t[:3, :3] = rpy_matrix(*rpy)
    t[:3, 3] = xyz
    return t


def link_poses(root):
    """World pose of every link with all joints at 0."""
    joints = {j.find("child").get("link"): j for j in root.findall("joint")}
    poses = {}

    def pose(link):
        if link in poses:
            return poses[link]
        j = joints.get(link)
        poses[link] = np.eye(4) if j is None else pose(j.find("parent").get("link")) @ origin_tf(j.find("origin"))
        return poses[link]

    for l in root.findall("link"):
        pose(l.get("name"))
    return poses


def read_stl(path):
    data = path.read_bytes()
    n = struct.unpack("<I", data[80:84])[0]
    return np.frombuffer(data, dtype=STL_DT, count=n, offset=84)["v"].astype(np.float64)


def weld(tris, tol=1e-3):
    pts = tris.reshape(-1, 3)
    uniq, first, inv = np.unique(np.round(pts / tol).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    faces = inv.reshape(-1, 3)
    ok = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    return pts[first], faces[ok]


def write_stl(path, points, faces, header):
    tris = points[faces].astype(np.float32)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]).astype(np.float64)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    rec = np.zeros(len(faces), dtype=STL_DT)
    rec["n"] = (n / ln).astype(np.float32)
    rec["v"] = tris
    path.write_bytes(header.encode("ascii")[:80].ljust(80, b" ") + struct.pack("<I", len(faces)) + rec.tobytes())


def arm(urdf, tail, meshes_used):
    root = ET.parse(urdf).getroot()
    poses = link_poses(root)
    parts = {}
    for link in root.findall("link"):
        seen = {}
        for vis in link.findall("visual"):
            stem = pathlib.Path(vis.find("geometry/mesh").get("filename")).stem
            k = seen.get(stem, 0)
            seen[stem] = k + 1
            pid = PART_IDS.get((link.get("name"), stem, k))
            if pid is None:
                continue
            m = poses[link.get("name")] @ origin_tf(vis.find("origin"))
            m[:3, 3] *= 1000.0  # metres -> millimetres; meshes are scaled the same way
            parts[pid] = {"mesh": "asm_" + stem, "m": [round(float(v), 6) for v in m.T.reshape(-1)],
                          "motor": stem.startswith("sts3215"), "label": LABELS[pid]}
            meshes_used.add(stem)
    steps = []
    for st in JOINTS + tail:
        subs = [{"parts": p, "text": t} for p, t in st["subs"]]
        for s in subs:
            for p in s["parts"]:
                assert p in parts, (urdf.name, p)
        steps.append({"id": st["id"], "title": st["title"], "subs": subs})
    listed = {p for s in steps for sub in s["subs"] for p in sub["parts"]}
    assert listed == set(parts), (urdf.name, set(parts) ^ listed)
    return {"parts": parts, "steps": steps}


def main(sim):
    sim = pathlib.Path(sim)
    OUT.mkdir(parents=True, exist_ok=True)
    used = set()
    data = {"source": "TheRobotStudio/SO-ARM100 Simulation/SO101 (URDF, zero pose)",
            "arms": {"follower": arm(sim / "so101_new_calib.urdf", FOLLOWER_TAIL, used),
                     "leader": arm(sim / "so101_leader_new_calib.urdf", LEADER_TAIL, used)},
            "labels": LABELS}
    for stem in sorted(used):
        tris = read_stl(sim / "assets" / (stem + ".stl")) * 1000.0
        pts, faces = weld(tris)
        if len(faces) > MAX_TRIS:
            pts, faces = fast_simplification.simplify(pts.astype(np.float32), faces.astype(np.int32),
                                                      target_reduction=1 - MAX_TRIS / len(faces))
            pts = pts.astype(np.float64)
        write_stl(OUT / f"asm_{stem}.stl", pts, faces, f"SO-ARM100 {stem} decimated, mm")
        print(f"{stem}: {len(tris)} -> {len(faces)} triangles")
    (OUT / "assembly.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT / "assembly.json")


if __name__ == "__main__":
    main(sys.argv[1])
