#!/usr/bin/env python3
"""
File: scripts/config_push.py
Project: pyats-config-push
Version: 2.1.0
Date: 2026-01-29

Purpose
-------
Push runtime CLI config to Cisco IOS devices using pyATS/Unicon.

Why this exists
---------------
We want Jenkins to show a visual "parallel graph" per device.
So Jenkins will:
  1) call --list-devices to discover devices from the testbed
  2) run one parallel branch per device, calling this script with --devices <name>

Usage examples
--------------
List devices:
  python3 scripts/config_push.py --testbed testbeds/testbed_access_2960.yaml --list-devices

Push config to ALL devices:
  python3 scripts/config_push.py --testbed testbeds/testbed_access_2960.yaml --config "ip http server"

Push config to ONE device:
  python3 scripts/config_push.py --testbed testbeds/testbed_access_2960.yaml --devices home-lab-access-sw01 --config "ip http server"
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

from pyats.topology import loader


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_logs_dir() -> Path:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="pyATS/Unicon Config Push (v2.1.0)")

    p.add_argument(
        "--testbed",
        required=True,
        help="Path to pyATS testbed YAML (e.g., testbeds/testbed_access_2960.yaml)",
    )

    p.add_argument(
        "--list-devices",
        action="store_true",
        help="Print device names (one per line) and exit (used by Jenkins).",
    )

    p.add_argument(
        "--devices",
        default="ALL",
        help="Comma-separated device names to run on, or ALL (default).",
    )

    p.add_argument(
        "--config",
        default="",
        help="Multiline CLI config to push. If empty, uses env CONFIG_COMMANDS.",
    )

    p.add_argument(
        "--write-memory",
        action="store_true",
        help="If set, runs 'write memory' after configuration.",
    )

    p.add_argument(
        "--connect-timeout",
        type=int,
        default=30,
        help="Connection timeout in seconds (best-effort).",
    )

    return p.parse_args()


def load_testbed(testbed_path: str):
    tb = loader.load(testbed_path)
    return tb


def get_device_names(tb) -> List[str]:
    return sorted(list(tb.devices.keys()))


def select_devices(all_devices: List[str], devices_arg: str) -> List[str]:
    if not devices_arg or devices_arg.strip().upper() == "ALL":
        return all_devices

    requested = [d.strip() for d in devices_arg.split(",") if d.strip()]
    missing = [d for d in requested if d not in all_devices]
    if missing:
        raise ValueError(f"Unknown device(s) requested: {missing}. Available: {all_devices}")
    return requested


def normalize_config(config_text: str) -> str:
    # Keep it exactly as provided, but trim leading/trailing whitespace.
    return config_text.strip("\n").strip()


def push_config_to_device(device, config_text: str, write_memory: bool, logs_dir: Path) -> Tuple[bool, str]:
    """
    Returns: (ok, message)
    Writes a per-device log file under logs/.
    """
    dev_name = device.name
    log_file = logs_dir / f"{dev_name}.log"

    start = time.time()
    try:
        # Make unicon create a logfile as well (in addition to our own file)
        # If device has its own logfile configured, Unicon will still log there too.
        device.logfile = str(log_file)

        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"\n[{now_ts()}] ===== START {dev_name} =====\n")
            f.write(f"[{now_ts()}] Connecting...\n")

        device.connect(
            learn_hostname=True,
            log_stdout=False,
            init_exec_commands=[],
            init_config_commands=[],
        )

        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{now_ts()}] Connected.\n")
            f.write(f"[{now_ts()}] Pushing configuration...\n")
            f.write("----- CONFIG BEGIN -----\n")
            f.write(config_text + "\n")
            f.write("----- CONFIG END -----\n")

        # Unicon configure() accepts:
        # - string: multiline config
        # - list of commands
        device.configure(config_text)

        if write_memory:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"[{now_ts()}] Running: write memory\n")
            device.execute("write memory")

        elapsed = time.time() - start
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{now_ts()}] DONE OK in {elapsed:.2f}s\n")
            f.write(f"[{now_ts()}] ===== END {dev_name} =====\n")

        try:
            device.disconnect()
        except Exception:
            pass

        return True, f"{dev_name}: OK ({elapsed:.2f}s)"

    except Exception as e:
        elapsed = time.time() - start
        try:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"[{now_ts()}] ERROR after {elapsed:.2f}s: {repr(e)}\n")
                f.write(f"[{now_ts()}] ===== END {dev_name} =====\n")
        except Exception:
            pass

        try:
            device.disconnect()
        except Exception:
            pass

        return False, f"{dev_name}: NOT OK ({elapsed:.2f}s) - {e}"


def main() -> int:
    args = parse_args()

    tb = load_testbed(args.testbed)
    all_devices = get_device_names(tb)

    # Jenkins discovery mode
    if args.list_devices:
        for d in all_devices:
            print(d)
        return 0

    config_text = args.config if args.config.strip() else os.getenv("CONFIG_COMMANDS", "")
    config_text = normalize_config(config_text)

    if not config_text:
        print("[ERROR] No configuration provided. Use --config or set env CONFIG_COMMANDS.", file=sys.stderr)
        return 2

    try:
        targets = select_devices(all_devices, args.devices)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    logs_dir = ensure_logs_dir()

    print("\n🔧 Configuration to be pushed:")
    print("--------------------------------------------------")
    print(config_text)
    print("--------------------------------------------------\n")
    print(f"🚀 Running on testbed: {args.testbed}")
    print(f"🎯 Target devices: {', '.join(targets)}\n")

    results: Dict[str, bool] = {}

    # NOTE:
    # Jenkins v2.1.0 will run one device per parallel branch,
    # so here we run sequentially for simplicity and clean logs.
    # If you want local parallel later, we can add ThreadPoolExecutor.
    for dev_name in targets:
        device = tb.devices[dev_name]
        ok, msg = push_config_to_device(device, config_text, args.write_memory, logs_dir)
        results[dev_name] = ok
        print(("[OK] " if ok else "[ERROR] ") + msg)

    success = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    print("\n================ Execution Report ================")
    print(f"Success: {success}")
    print(f"Failed : {failed}")
    print("==================================================\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
