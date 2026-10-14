#!/usr/bin/env python3
"""
force_probe.py - PC side of the SO-101 force probe (TAL221 + HX711 + Arduino Nano).

The Nano (firmware so101_force.ino) streams lines at 115200 baud:
    F,<millis>,<grams>      force sample ("nan" until calibrated)
    OK,... / ERR,... / R,... replies to commands
    # ...                    info lines
Commands sent to the Nano: t (tare), c<grams> (calibrate), r (raw), a<n> (avg window).

Requirements: Python >= 3.10, pyserial  (pip install pyserial)
The "push" example additionally needs LeRobot installed and a calibrated SO-101 follower.

Examples
    python force_probe.py monitor --port /dev/ttyUSB0
    python force_probe.py tare    --port /dev/ttyUSB0
    python force_probe.py cal 100 --port /dev/ttyUSB0          # 100 g weight resting on the tip
    python force_probe.py raw     --port /dev/ttyUSB0
    python force_probe.py push --port /dev/ttyUSB0 --robot-port /dev/ttyACM0 \\
        --robot-id my_awesome_follower_arm --joint wrist_flex --direction 1 --target 50 --limit 300

Safety (push): stops at --target, backs off immediately at --limit, stops if the sensor goes
silent, reads a negative force, or the joint travelled --max-travel degrees. First Ctrl+C =
controlled stop and retreat to the start pose; second Ctrl+C = emergency: torque OFF (arm goes limp!).
"""
from __future__ import annotations

import argparse
import csv
import math
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover
    sys.exit("pyserial is missing:  pip install pyserial")

BAUD = 115200


@dataclass(frozen=True)
class Sample:
    seq: int          # running sample counter (PC side)
    t_host: float     # time.monotonic() when the line arrived
    millis: int       # Nano millis()
    grams: float      # nan if the Nano is not calibrated


class ForceProbe:
    """Reads the Nano CSV stream in a background thread."""

    def __init__(self, port: str, baud: int = BAUD, boot_timeout: float = 4.0, verbose: bool = False):
        # Opening the port resets a Nano (DTR). The firmware then prints a banner and auto-tares.
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.verbose = verbose
        self._latest: Sample | None = None
        self._seq = 0
        self._cv = threading.Condition()
        self._replies: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        if self.wait_new(-1, boot_timeout) is None:
            self.close()
            raise RuntimeError(f"No 'F,' data from {port} within {boot_timeout:.0f} s. "
                               "Wrong port? Firmware not uploaded? Baud must be 115200.")

    # ---------- reading ----------
    def _reader(self) -> None:
        while not self._stop.is_set():
            try:
                raw = self.ser.readline()
            except (serial.SerialException, OSError) as e:
                print(f"[force] serial error: {e}", file=sys.stderr)
                break
            if not raw:
                continue
            line = raw.decode("ascii", errors="replace").strip()
            if line.startswith("F,"):
                parts = line.split(",")
                if len(parts) != 3:
                    continue
                try:
                    millis, grams = int(parts[1]), float(parts[2])
                except ValueError:
                    continue  # partial line right after reset
                with self._cv:
                    self._seq += 1
                    self._latest = Sample(self._seq, time.monotonic(), millis, grams)
                    self._cv.notify_all()
            elif line.startswith(("OK,", "ERR,", "R,")):
                self._replies.put(line)
            elif line.startswith("#"):
                if self.verbose or "WARN" in line or "NOT CALIBRATED" in line:
                    print(f"[force] {line}")

    def latest(self) -> Sample | None:
        with self._cv:
            return self._latest

    def wait_new(self, after_seq: int, timeout: float) -> Sample | None:
        """Block until a sample with seq > after_seq arrives (or timeout)."""
        deadline = time.monotonic() + timeout
        with self._cv:
            while self._latest is None or self._latest.seq <= after_seq:
                left = deadline - time.monotonic()
                if left <= 0:
                    return None
                self._cv.wait(left)
            return self._latest

    # ---------- commands ----------
    def command(self, cmd: str, timeout: float = 6.0) -> str:
        while not self._replies.empty():
            self._replies.get_nowait()
        self.ser.write((cmd + "\n").encode("ascii"))
        self.ser.flush()
        try:
            reply = self._replies.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError(f"no reply to '{cmd}'") from None
        if reply.startswith("ERR"):
            raise RuntimeError(f"Nano replied {reply}")
        return reply

    def tare(self) -> str:
        return self.command("t")

    def calibrate(self, grams: float) -> str:
        return self.command(f"c{grams:g}")

    def raw(self) -> str:
        return self.command("r")

    def set_window(self, n: int) -> str:
        return self.command(f"a{int(n)}")

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        try:
            self.ser.close()
        except Exception:
            pass


# ======================= LeRobot SO-101 example =======================
def import_so101():
    """LeRobot >= 0.4: lerobot.robots.so_follower ; LeRobot 0.3.x: lerobot.robots.so101_follower."""
    try:
        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    except ImportError:
        try:
            from lerobot.robots.so101_follower import SO101Follower, SO101FollowerConfig
        except ImportError:
            sys.exit("LeRobot is not installed in this Python environment (activate the lerobot env).")
    return SO101Follower, SO101FollowerConfig


class StopFlag:
    """1st Ctrl+C -> graceful stop; 2nd Ctrl+C -> KeyboardInterrupt (emergency)."""

    def __init__(self) -> None:
        self.event = threading.Event()
        self._old = signal.signal(signal.SIGINT, self._handler)

    def _handler(self, signum, frame) -> None:
        if self.event.is_set():
            raise KeyboardInterrupt
        print("\n[Ctrl+C] stopping -> retreat to start pose. Press Ctrl+C again for EMERGENCY torque off.")
        self.event.set()

    def restore(self) -> None:
        signal.signal(signal.SIGINT, self._old)


def move_joint_to(robot, goal: dict, key: str, target: float, step: float, period: float) -> None:
    """Ramp one joint to `target` in increments of `step` degrees."""
    while abs(goal[key] - target) > 1e-6:
        delta = target - goal[key]
        goal[key] += max(-step, min(step, delta))
        robot.send_action(dict(goal))
        time.sleep(period)


def push(args) -> int:
    if args.limit > args.capacity:
        sys.exit(f"--limit {args.limit} g is above the load-cell capacity {args.capacity} g. "
                 "For a 100 g TAL221 use e.g. --capacity 100 --limit 100 --target 50.")
    if not 0 < args.target < args.limit:
        sys.exit("need 0 < --target < --limit")
    SO101Follower, SO101FollowerConfig = import_so101()

    probe = stop = robot = None
    goal: dict | None = None
    start: dict = {}
    key = ""
    log_f = open(args.log, "w", newline="") if args.log else None
    log = csv.writer(log_f) if log_f else None
    if log:
        log.writerow(["t_s", "nano_ms", "force_g", "goal_deg", "phase"])
    exit_code = 1
    try:
        probe = ForceProbe(args.port, verbose=args.verbose)
        s = probe.latest()
        if s is None or math.isnan(s.grams):
            raise RuntimeError("Force sensor NOT calibrated. Run:  tare, then  cal <grams>  first.")
        probe.set_window(args.avg)
        input("Make sure NOTHING touches the probe tip, then press ENTER to tare... ")
        print("[force]", probe.tare())
        stop = StopFlag()   # from here on: 1st Ctrl+C = graceful stop, 2nd = emergency torque off

        cfg = SO101FollowerConfig(
            port=args.robot_port,
            id=args.robot_id,
            use_degrees=True,                                # joint values in degrees (all LeRobot versions)
            max_relative_target=float(args.max_rel),         # must be float (LeRobot raises TypeError on int)
            disable_torque_on_disconnect=args.release_torque,
        )
        robot = SO101Follower(cfg)
        robot.connect(calibrate=False)                       # never start the interactive calibration here
        if not robot.is_calibrated:
            raise RuntimeError("SO-101 is not calibrated for id "
                               f"'{args.robot_id}'. Run lerobot-calibrate --robot.type=so101_follower "
                               f"--robot.port={args.robot_port} --robot.id={args.robot_id}")
        obs = robot.get_observation()
        start = {k: float(v) for k, v in obs.items() if k.endswith(".pos")}
        key = f"{args.joint}.pos"
        if key not in start:
            raise RuntimeError(f"unknown joint '{args.joint}'. Valid: {[k[:-4] for k in start]}")
        goal = dict(start)
        if args.gripper_goal is not None and "gripper.pos" in goal:
            goal["gripper.pos"] = float(args.gripper_goal)   # squeeze the block (0..100 scale)
        robot.send_action(dict(goal))    # hold the current pose (connect() does not set goals)
        print(f"start {key} = {start[key]:.2f} deg, gripper.pos = {start.get('gripper.pos', float('nan')):.1f} "
              f"(goal {goal.get('gripper.pos', float('nan')):.1f}); target {args.target} g, hard limit {args.limit} g")

        t0 = time.monotonic()
        reason, reached, emergency = "stopped by user", False, False
        while not stop.event.is_set():
            t_loop = time.monotonic()
            s = probe.latest()
            if s is None or t_loop - s.t_host > args.stale:
                reason = "force sensor silent (cable? Nano reset?)"
                break
            f = s.grams
            if log:
                log.writerow([f"{t_loop - t0:.3f}", s.millis, f"{f:.2f}", f"{goal[key]:.3f}", "push"])
            if math.isnan(f):
                reason = "force is nan (calibration lost?)"
                break
            if f >= args.limit:
                reason, emergency = f"HARD LIMIT: {f:.1f} g >= {args.limit} g", True
                break
            if f <= -args.neg_limit:
                reason = (f"negative force {f:.1f} g: wrong --direction, probe pushed from the wrong side, "
                          "or calibrate again with the weight pressing the tip the pushing way")
                break
            if f >= args.target:
                reason, reached = f"target reached: {f:.1f} g", True
                break
            # big steps in free air, smaller steps once in contact (proportional to remaining force)
            step = args.step if f < args.contact else max(args.min_step, args.step * (args.target - f) / args.target)
            new = goal[key] + args.direction * step
            if abs(new - start[key]) > args.max_travel:
                reason = f"moved {args.max_travel} deg without reaching the target (no contact?)"
                break
            goal[key] = new
            sent = robot.send_action(dict(goal))   # may be clipped by max_relative_target
            goal[key] = float(sent.get(key, new))
            print(f"\r{key}={goal[key]:8.2f} deg  force={f:7.2f} g ", end="", flush=True)
            time.sleep(max(0.0, args.period - (time.monotonic() - t_loop)))
        print(f"\n-> {reason}")

        if emergency:
            goal[key] -= args.direction * args.backoff     # immediate back-off
            robot.send_action(dict(goal))
        elif reached and args.hold > 0:
            t_end = time.monotonic() + args.hold
            while time.monotonic() < t_end and not stop.event.is_set():
                s = probe.latest()
                if s is None or time.monotonic() - s.t_host > args.stale or s.grams >= args.limit:
                    print("hold aborted (limit or sensor silent)")
                    break
                if log:
                    log.writerow([f"{time.monotonic() - t0:.3f}", s.millis, f"{s.grams:.2f}", f"{goal[key]:.3f}", "hold"])
                print(f"\rholding: force={s.grams:7.2f} g ", end="", flush=True)
                time.sleep(args.period)
            print()
        exit_code = 0 if reached else 2
    except KeyboardInterrupt:
        print("\nEMERGENCY: disabling torque (arm will go limp)")
        if robot is not None:
            robot.config.disable_torque_on_disconnect = True
            try:
                robot.disconnect()
            except Exception as e:
                print("disconnect failed:", e)
            robot = None
        exit_code = 3
    except (RuntimeError, serial.SerialException) as e:
        print("ERROR:", e)
    finally:
        if robot is not None and robot.is_connected:
            if goal is not None:
                try:
                    print("retreating to start pose ...")
                    move_joint_to(robot, goal, key, start[key], step=1.0, period=0.05)
                except BaseException as e:  # bus error or 2nd Ctrl+C -> stop pushing at any cost
                    print("retreat failed/aborted:", repr(e), "-> torque OFF (arm goes limp)")
                    robot.config.disable_torque_on_disconnect = True
            try:
                robot.disconnect()
            except Exception as e:
                print("disconnect failed:", e)
        if stop is not None:
            stop.restore()
        if probe is not None:
            probe.close()
        if log_f:
            log_f.close()
    return exit_code


# ======================= CLI =======================
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_port(p):
        p.add_argument("--port", required=True, help="Nano serial port, e.g. /dev/ttyUSB0 or COM5")
        p.add_argument("--verbose", action="store_true", help="also print '#' info lines")

    p = sub.add_parser("monitor", help="print force values")
    add_port(p)
    p.add_argument("--seconds", type=float, default=0, help="stop after N s (0 = until Ctrl+C)")
    p.add_argument("--csv", help="also save samples to this CSV file")
    add_port(sub.add_parser("tare", help="zero the sensor (nothing on the tip)"))
    p = sub.add_parser("cal", help="calibrate: known weight resting on the tip")
    p.add_argument("grams", type=float)
    add_port(p)
    add_port(sub.add_parser("raw", help="print one raw HX711 reading"))

    p = sub.add_parser("push", help="SO-101 example: move one joint until force reaches target")
    add_port(p)
    p.add_argument("--robot-port", required=True, help="SO-101 follower bus port (lerobot-find-port)")
    p.add_argument("--robot-id", default="my_awesome_follower_arm", help="same id as used for lerobot-calibrate")
    p.add_argument("--joint", default="wrist_flex",
                   choices=["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll"])
    p.add_argument("--direction", type=int, choices=[-1, 1], default=1, help="+1 or -1: which way pushes")
    p.add_argument("--target", type=float, default=50.0, help="stop when force >= this (g)")
    p.add_argument("--limit", type=float, default=300.0, help="hard safety limit (g)")
    p.add_argument("--capacity", type=float, default=500.0, help="load-cell capacity (g): 500 or 100")
    p.add_argument("--contact", type=float, default=3.0, help="force (g) that counts as contact")
    p.add_argument("--neg-limit", type=float, default=20.0, help="stop if force <= -this (g)")
    p.add_argument("--step", type=float, default=0.2, help="step in free air (deg)")
    p.add_argument("--min-step", type=float, default=0.03, help="smallest step near target (deg)")
    p.add_argument("--period", type=float, default=0.1, help="control period (s)")
    p.add_argument("--max-travel", type=float, default=15.0, help="max joint travel from start (deg)")
    p.add_argument("--max-rel", type=float, default=5.0, help="LeRobot max_relative_target (deg)")
    p.add_argument("--backoff", type=float, default=3.0, help="immediate back-off at hard limit (deg)")
    p.add_argument("--stale", type=float, default=0.6, help="max age of a force sample (s)")
    p.add_argument("--avg", type=int, default=2, help="firmware moving-average window during push")
    p.add_argument("--hold", type=float, default=2.0, help="hold at target for N s before retreat")
    p.add_argument("--gripper-goal", type=float, default=None,
                   help="gripper goal (0..100) to keep squeezing the probe block; default: hold present value. "
                        "Strap the block to the fingers with a zip tie anyway.")
    p.add_argument("--release-torque", action="store_true",
                   help="disable torque at the end (arm goes limp!) - default keeps holding the start pose")
    p.add_argument("--log", default="push_log.csv", help="CSV log file ('' to disable)")

    args = ap.parse_args(argv)
    if args.cmd == "push":
        return push(args)

    try:
        probe = ForceProbe(args.port, verbose=args.verbose)
    except (RuntimeError, serial.SerialException) as e:
        print("ERROR:", e)
        return 1
    try:
        if args.cmd == "tare":
            print(probe.tare())
        elif args.cmd == "cal":
            print(probe.calibrate(args.grams))
        elif args.cmd == "raw":
            print(probe.raw())
        elif args.cmd == "monitor":
            writer, fh = None, None
            if args.csv:
                fh = open(args.csv, "w", newline="")
                writer = csv.writer(fh)
                writer.writerow(["nano_ms", "force_g"])
            t_end = time.monotonic() + args.seconds if args.seconds > 0 else math.inf
            seq = -1
            try:
                while time.monotonic() < t_end:
                    s = probe.wait_new(seq, 1.0)
                    if s is None:
                        print("no data ...")
                        continue
                    seq = s.seq
                    print(f"{s.millis:>10d} ms  {s.grams:9.2f} g")
                    if writer:
                        writer.writerow([s.millis, s.grams])
            except KeyboardInterrupt:
                pass
            finally:
                if fh:
                    fh.close()
    except RuntimeError as e:
        print("ERROR:", e)
        return 1
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
