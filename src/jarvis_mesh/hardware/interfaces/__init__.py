"""Hardware interface adapters.

Each adapter bridges a specific protocol to the unified device API:
  - file: watchdog-based monitoring of output folders
  - serial: pyserial/pyfirmata for Arduino, LED controllers, etc.
  - network: REST/gRPC/vendor SDK for networked instruments
  - daq: NI DAQmx / LabJack for analog/digital I/O
  - bridge: ZMQ/socket for software like Bonsai, PsychoPy, DeepLabCut-live
"""
