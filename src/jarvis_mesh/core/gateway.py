"""WebSocket gateway — single control plane for devices, agents, and clients.

Inspired by OpenClaw's Gateway pattern:
  - Devices connect and self-register capabilities
  - Handles routing, session management, heartbeat
  - Single entry point for all real-time communication
"""
