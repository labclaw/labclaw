"""Hardware interface adapters.

Each adapter bridges a specific protocol to the unified device API:
  - file: watchdog-based monitoring of output folders
  - serial: pyserial/pyfirmata for Arduino, LED controllers, etc.
  - network: REST/gRPC/vendor SDK for networked instruments
  - daq: NI DAQmx / LabJack for analog/digital I/O
  - bridge: ZMQ/socket for software like Bonsai, PsychoPy, DeepLabCut-live
"""

from labclaw.hardware.interfaces.daq import DAQDriver
from labclaw.hardware.interfaces.driver import DeviceDriver
from labclaw.hardware.interfaces.file_based import FileBasedDriver
from labclaw.hardware.interfaces.network_api import NetworkAPIDriver
from labclaw.hardware.interfaces.serial import SerialDriver
from labclaw.hardware.interfaces.software_bridge import SoftwareBridgeDriver

__all__ = [
    "DAQDriver",
    "DeviceDriver",
    "FileBasedDriver",
    "NetworkAPIDriver",
    "SerialDriver",
    "SoftwareBridgeDriver",
]
