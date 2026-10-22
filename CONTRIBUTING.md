# Contributing to Sereen 🤝

First off, thank you for considering contributing to Sereen! It's a community effort to bring native projector control to Linux.

## How to Contribute

### 1. Report Bugs
If you find a bug or a projector model that isn't working, please open an issue on GitHub. Include:
- Your projector model number (e.g., EB-X41).
- The protocol it uses (if known).
- A description of what happened vs. what was expected.

### 2. Adding New Protocol Support
If you have documentation for a newer Epson protocol or a different brand:
1. Create a new driver in `src/sereen/protocol/`.
2. Inherit from `src/sereen/control/base.Session`.
3. Register the protocol in `src/sereen/models.Protocol`.
4. Update `src/sereen/control/factory.py` to handle the new protocol.

### 3. Improving Casting
Screen casting is the most experimental part of the project. If you are a GStreamer expert, we need help with:
- Implementing low-latency H.264 streaming.
- Supporting different projector receiving ports.
- Improving the PipeWire source capture.

## Development Setup

1. Create a virtual environment: `python -m venv venv`
2. Activate it: `source venv/bin/activate`
3. Install in editable mode: `pip install -e .`
4. Run tests: `pytest`

## Code of Conduct
Please be respectful and helpful. This is an educational and utility-focused project.
