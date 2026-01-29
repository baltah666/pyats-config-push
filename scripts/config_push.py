#!/usr/bin/env python3
"""
===============================================================================
config_push.py
Version : v2.2.1
-------------------------------------------------------------------------------
PURPOSE:
- Push runtime IOS CLI configuration to Cisco devices using pyATS
- Support device listing for Jenkins parallel execution

IMPORTANT:
- This script MUST be executed using the Python interpreter
  inside the pyATS virtual environment.
  Example:
    pyats-venv/bin/python scripts/config_push.py

WHY:
- Jenkins does NOT persist 'source venv/bin/activate' across steps
===============================================================================
"""

import argparse
import sys
from pyats.topology import loader
from unicon.core.errors import ConnectionError

def list_devices(testbed_file):
    tb = loader.load(testbed_file)
    for dev in tb.devices:
        print(dev)

def push_config(testbed_file, devices, config, write_memory):
    tb = loader.load(testbed_file)

    for dev_name in devices:
        device = tb.devices[dev_name]
        try:
            print(f"Connecting to {dev_name}")
            device.connect(log_stdout=True)

            if config:
                print(f"Pushing config to {dev_name}")
                device.configure(config)

            if write_memory:
                device.execute("write memory")

            device.disconnect()
            print(f"{dev_name} → OK")

        except ConnectionError as e:
            print(f"{dev_name} → CONNECTION FAILED: {e}")
            sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", required=True)
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--devices")
    parser.add_argument("--config")
    parser.add_argument("--write-memory", action="store_true")

    args = parser.parse_args()

    if args.list_devices:
        list_devices(args.testbed)
        sys.exit(0)

    device_list = [d.strip() for d in args.devices.split(",")]
    push_config(
        args.testbed,
        device_list,
        args.config,
        args.write_memory
    )
