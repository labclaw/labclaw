"""Tests for Gateway — covers gateway.py lines 110-111, 174, 177, 184-185,
207-208, 232-235, 256-259.
"""

from __future__ import annotations

import pytest

from labclaw.core.gateway import (
    ConnectionInfo,
    Gateway,
    GatewayMessage,
    RegistrationRequest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register(
    gateway: Gateway, client_id: str = "agent-01", client_type: str = "agent"
) -> ConnectionInfo:
    req = RegistrationRequest(client_id=client_id, client_type=client_type)
    return gateway.register_client(req)


def _message(source: str, target: str | None = None, message_type: str = "ping") -> GatewayMessage:
    return GatewayMessage(source=source, target=target, message_type=message_type)


# ---------------------------------------------------------------------------
# register_client / eviction of stale connection
# ---------------------------------------------------------------------------


class TestRegisterClient:
    def test_register_creates_connection(self) -> None:
        gw = Gateway()
        conn = _register(gw, "agent-01")
        assert conn.client_id == "agent-01"
        assert conn.client_type == "agent"
        assert conn.connection_id != ""

    def test_register_same_client_id_evicts_old_connection(self) -> None:
        """Lines 110-111: stale connection is evicted on re-register."""
        gw = Gateway()
        old_conn = _register(gw, "agent-01")
        new_conn = _register(gw, "agent-01")  # same client_id

        assert new_conn.connection_id != old_conn.connection_id
        assert old_conn.connection_id not in {c.connection_id for c in gw.get_connections()}
        assert new_conn.connection_id in {c.connection_id for c in gw.get_connections()}


# ---------------------------------------------------------------------------
# unregister_client
# ---------------------------------------------------------------------------


class TestUnregisterClient:
    def test_unregister_by_connection_id(self) -> None:
        gw = Gateway()
        conn = _register(gw, "agent-02")
        gw.unregister_client(conn.connection_id)
        assert gw.get_connections() == []

    def test_unregister_by_client_id(self) -> None:
        gw = Gateway()
        _register(gw, "agent-03")
        gw.unregister_client("agent-03")
        assert gw.get_connections() == []

    def test_unregister_unknown_raises(self) -> None:
        gw = Gateway()
        with pytest.raises(KeyError):
            gw.unregister_client("nonexistent")


# ---------------------------------------------------------------------------
# send — line 174 (no target), line 177 (target not connected)
# ---------------------------------------------------------------------------


class TestSend:
    def test_send_without_target_raises(self) -> None:
        """Line 174: message.target is None → ValueError."""
        gw = Gateway()
        _register(gw, "src")
        msg = _message(source="src", target=None)
        with pytest.raises(ValueError, match="without a target"):
            gw.send(msg)

    def test_send_to_disconnected_target_raises(self) -> None:
        """Line 177: target not in _client_id_to_connection_id → KeyError."""
        gw = Gateway()
        _register(gw, "src")
        msg = _message(source="src", target="ghost")
        with pytest.raises(KeyError, match="ghost"):
            gw.send(msg)

    def test_send_delivers_to_subscribed_handler(self) -> None:
        gw = Gateway()
        _register(gw, "src")
        _register(gw, "dst")

        received: list[GatewayMessage] = []
        gw.subscribe_client("dst", received.append)

        msg = _message(source="src", target="dst")
        gw.send(msg)
        assert len(received) == 1
        assert received[0].message_id == msg.message_id

    def test_send_handler_exception_does_not_propagate(self) -> None:
        """Lines 184-185: handler errors are caught and logged, not re-raised."""
        gw = Gateway()
        _register(gw, "src")
        _register(gw, "dst")

        def bad_handler(m: GatewayMessage) -> None:
            raise RuntimeError("boom")

        gw.subscribe_client("dst", bad_handler)
        msg = _message(source="src", target="dst")
        # Must not raise
        gw.send(msg)


# ---------------------------------------------------------------------------
# broadcast — lines 207-208
# ---------------------------------------------------------------------------


class TestBroadcast:
    def test_broadcast_delivers_to_all_subscribers(self) -> None:
        gw = Gateway()
        _register(gw, "a")
        _register(gw, "b")

        received_a: list[GatewayMessage] = []
        received_b: list[GatewayMessage] = []
        gw.subscribe_client("a", received_a.append)
        gw.subscribe_client("b", received_b.append)

        msg = _message(source="broadcaster")
        gw.broadcast(msg)

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_broadcast_handler_exception_does_not_propagate(self) -> None:
        """Lines 207-208: broadcast handler errors are caught, not re-raised."""
        gw = Gateway()
        _register(gw, "c")

        def bad_handler(m: GatewayMessage) -> None:
            raise RuntimeError("broadcast boom")

        gw.subscribe_client("c", bad_handler)
        msg = _message(source="src")
        # Must not raise
        gw.broadcast(msg)


# ---------------------------------------------------------------------------
# get_connections
# ---------------------------------------------------------------------------


class TestGetConnections:
    def test_get_connections_empty(self) -> None:
        gw = Gateway()
        assert gw.get_connections() == []

    def test_get_connections_returns_all(self) -> None:
        gw = Gateway()
        _register(gw, "x")
        _register(gw, "y")
        conns = gw.get_connections()
        client_ids = {c.client_id for c in conns}
        assert client_ids == {"x", "y"}


# ---------------------------------------------------------------------------
# get_connection — lines 232-235
# ---------------------------------------------------------------------------


class TestGetConnection:
    def test_get_connection_returns_correct_info(self) -> None:
        gw = Gateway()
        conn = _register(gw, "z")
        fetched = gw.get_connection(conn.connection_id)
        assert fetched.connection_id == conn.connection_id

    def test_get_connection_not_found_raises(self) -> None:
        """Lines 232-235: KeyError on unknown connection_id."""
        gw = Gateway()
        with pytest.raises(KeyError, match="not found"):
            gw.get_connection("no-such-id")


# ---------------------------------------------------------------------------
# _get_connection_or_by_client_id — lines 256-259
# ---------------------------------------------------------------------------


class TestGetConnectionOrByClientId:
    def test_lookup_by_connection_id(self) -> None:
        gw = Gateway()
        conn = _register(gw, "lookup-test")
        result = gw._get_connection_or_by_client_id(conn.connection_id)
        assert result.connection_id == conn.connection_id

    def test_lookup_by_client_id(self) -> None:
        """Lines 256-259: falls back to client_id lookup."""
        gw = Gateway()
        conn = _register(gw, "client-lookup")
        result = gw._get_connection_or_by_client_id("client-lookup")
        assert result.connection_id == conn.connection_id

    def test_lookup_unknown_raises(self) -> None:
        gw = Gateway()
        with pytest.raises(KeyError):
            gw._get_connection_or_by_client_id("totally-unknown")
