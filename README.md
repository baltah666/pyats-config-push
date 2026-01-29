# pyats-config-push

Jenkins-driven pyATS configuration push system.

## Purpose
This project allows network engineers to push **runtime CLI configuration**
to Cisco devices using **pyATS**, controlled fully from **Jenkins Build Parameters**.

## Key Features
- Jenkins "Build with Parameters"
- User-provided configuration (no config files)
- Testbed selection from Jenkins
- Parallel execution using pyATS
- Clear per-device execution results

## Repository Status
- Version: 2.0.0
- This repository replaces legacy pyATS config push implementations.
- Old repositories are frozen and kept for reference only.

## Structure
- `scripts/`   → Python automation scripts
- `testbeds/`  → pyATS testbed YAML files
- `jenkins/`   → Jenkins pipelines
- `docs/`      → Design and usage documentation
