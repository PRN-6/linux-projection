# Sereen 📽️

Sereen is a professional-grade Linux application designed to discover and control Epson projectors over a network. It bridges the gap between proprietary Epson protocols and open-source Linux desktop environments.

[![Platform](https://img.shields.io/badge/platform-Linux-orange)](https://kernel.org)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Protocol](https://img.shields.io/badge/protocols-ESC\/VP_|_PJLink-green)](https://en.wikipedia.org/wiki/PJLink)

## ✨ Features

- **Automatic Discovery**: Fast, parallel TCP scanning and protocol identification.
- **Dual-Protocol Support**: 
  - **ESC/VP.net**: Support for Epson's proprietary control protocol.
  - **PJLink**: Support for the industry-standard projector control protocol.
- **Modern GUI**: A sleek GTK4/LibAdwaita interface for effortless control.
- **Remote Control**: Manage Power, Input Sources, and Volume from your desktop.
- **Screen Casting**: Integrated GStreamer/PipeWire pipeline for wireless desktop mirroring.

## 🚀 Getting Started

### Prerequisites (Linux)

To run the full GUI application, you will need the following system dependencies:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
                    gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
                    gstreamer1.0-plugins-bad
```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/sereen.git
   cd sereen
   ```

2. Install the Python package:
   ```bash
   pip install .
   ```

### Running the Application

**To launch the GUI:**
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python3 -m sereen
```

**To use the CLI (works on Windows/Linux):**
```bash
# Scan for projectors
python3 -m sereen.cli scan

# Turn on a projector
python3 -m sereen.cli power <IP_ADDRESS> on
```

## 🛠 Architecture

Sereen is built with a driver-based architecture to ensure maximum compatibility:
- **Discovery Layer**: Probes the network for open ports (4352, 3620, 3621).
- **Session Factory**: Automatically instantiates the correct protocol driver.
- **Protocol Layer**: Standardizes commands across different Epson model families.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to get started.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
