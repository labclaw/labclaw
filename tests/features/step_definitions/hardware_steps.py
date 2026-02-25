"""BDD step definitions for Layer 1 — Hardware (registry + safety).

Provides Given/When/Then steps for device_registry.feature and
hardware_safety.feature.
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.safety import HardwareSafetyChecker
from labclaw.hardware.schemas import DeviceRecord, HardwareCommand, SafetyCheckResult
from tests.features.conftest import EventCapture

# ---------------------------------------------------------------------------
# Fixtures exposed as step targets
# ---------------------------------------------------------------------------


@given("the device registry is initialized", target_fixture="device_registry")
def device_registry_initialized(event_capture: EventCapture) -> DeviceRegistry:
    """Provide a fresh DeviceRegistry and wire event capture."""
    # Subscribe capture to all hardware events
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return DeviceRegistry()


@given("the safety checker is initialized", target_fixture="safety_checker")
def safety_checker_initialized(device_registry: DeviceRegistry) -> HardwareSafetyChecker:
    return HardwareSafetyChecker(device_registry)


# ---------------------------------------------------------------------------
# Device ID mapping — maps human-readable names to UUIDs
# ---------------------------------------------------------------------------


@pytest.fixture()
def device_ids() -> dict[str, str]:
    """Map of human-friendly device names to their actual device_id UUIDs."""
    return {}


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse('device "{name}" is registered with status "{status}"'),
    target_fixture="_device_registered",
)
def device_is_registered(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    event_capture: EventCapture,
    name: str,
    status: str,
) -> DeviceRecord:
    """Register a device with a given name and status."""
    record = DeviceRecord(
        name=name,
        device_type="generic",
        status=DeviceStatus(status),
    )
    result = device_registry.register(record)
    device_ids[name] = result.device_id
    return result


# ---------------------------------------------------------------------------
# When steps — Registry
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I register a device "{name}" of type "{device_type}" with status "{status}"'),
    target_fixture="registered_device",
)
def register_device(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
    device_type: str,
    status: str,
) -> DeviceRecord:
    record = DeviceRecord(
        name=name,
        device_type=device_type,
        status=DeviceStatus(status),
    )
    result = device_registry.register(record)
    device_ids[name] = result.device_id
    return result


@when(parsers.parse('I update device "{name}" status to "{status}"'))
def update_device_status(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
    status: str,
) -> None:
    device_id = device_ids[name]
    device_registry.update_status(device_id, DeviceStatus(status))


@when(parsers.parse('I list devices with status "{status}"'), target_fixture="device_list")
def list_devices_with_status(
    device_registry: DeviceRegistry,
    status: str,
) -> list[DeviceRecord]:
    return device_registry.list_devices(DeviceStatus(status))


@when(parsers.parse('I get device "{name}"'), target_fixture="get_device_error")
def get_device(device_registry: DeviceRegistry, name: str) -> Exception | DeviceRecord:
    try:
        return device_registry.get(name)
    except KeyError as exc:
        return exc


@when(parsers.parse('I unregister device "{name}"'))
def unregister_device(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
) -> None:
    device_id = device_ids[name]
    device_registry.unregister(device_id)


# ---------------------------------------------------------------------------
# When steps — Safety
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I check safety for command "{action}" on device "{name}"'),
    target_fixture="safety_result",
)
def check_safety(
    safety_checker: HardwareSafetyChecker,
    device_ids: dict[str, str],
    action: str,
    name: str,
) -> SafetyCheckResult:
    device_id = device_ids.get(name, name)  # Fall through to raw name if not mapped
    command = HardwareCommand(device_id=device_id, action=action)
    return safety_checker.check(command)


# ---------------------------------------------------------------------------
# Then steps — Registry
# ---------------------------------------------------------------------------


@then(parsers.parse('the registry contains device "{name}"'))
def registry_contains(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
) -> None:
    device_id = device_ids[name]
    device = device_registry.get(device_id)
    assert device.name == name


@then(parsers.parse('device "{name}" has status "{status}"'))
def device_has_status(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
    status: str,
) -> None:
    device_id = device_ids[name]
    device = device_registry.get(device_id)
    assert device.status == DeviceStatus(status), f"Expected {status}, got {device.status.value}"


@then(parsers.parse("I get {count:d} devices"))
def got_n_devices(device_list: list[DeviceRecord], count: int) -> None:
    assert len(device_list) == count, f"Expected {count}, got {len(device_list)}"


@then("a KeyError is raised")
def key_error_raised(get_device_error: object) -> None:
    assert isinstance(get_device_error, KeyError), (
        f"Expected KeyError, got {type(get_device_error).__name__}"
    )


@then(parsers.parse('the registry does not contain device "{name}"'))
def registry_does_not_contain(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
) -> None:
    device_id = device_ids[name]
    with pytest.raises(KeyError):
        device_registry.get(device_id)


# ---------------------------------------------------------------------------
# Then steps — Safety
# ---------------------------------------------------------------------------


@then("the safety check passes")
def safety_passes(safety_result: SafetyCheckResult) -> None:
    assert safety_result.passed is True, f"Expected pass, got fail: {safety_result.details}"


@then("the safety check fails")
def safety_fails(safety_result: SafetyCheckResult) -> None:
    assert safety_result.passed is False, f"Expected fail, got pass: {safety_result.details}"


@then(parsers.parse('the safety level is "{level}"'))
def safety_level_is(safety_result: SafetyCheckResult, level: str) -> None:
    assert safety_result.level.value == level, (
        f"Expected level {level!r}, got {safety_result.level.value!r}"
    )
