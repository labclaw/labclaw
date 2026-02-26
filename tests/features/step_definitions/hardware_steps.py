"""BDD step definitions for Layer 1 — Hardware.

Covers: device_registry.feature, hardware_safety.feature,
hardware_manager.feature, hardware_interfaces.feature,
hardware_drivers.feature.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus
from labclaw.hardware.interfaces.daq import DAQDriver
from labclaw.hardware.interfaces.driver import DeviceDriver
from labclaw.hardware.interfaces.file_based import FileBasedDriver
from labclaw.hardware.interfaces.network_api import NetworkAPIDriver
from labclaw.hardware.interfaces.serial import SerialDriver
from labclaw.hardware.interfaces.software_bridge import SoftwareBridgeDriver
from labclaw.hardware.manager import HardwareManager
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.safety import HardwareSafetyChecker
from labclaw.hardware.schemas import (
    DeviceCapabilities,
    DeviceRecord,
    HardwareCommand,
    SafetyCheckResult,
)
from tests.features.conftest import EventCapture

# ---------------------------------------------------------------------------
# Core fixtures / Given steps — Registry & Safety
# ---------------------------------------------------------------------------


@given("the device registry is initialized", target_fixture="device_registry")
def device_registry_initialized(event_capture: EventCapture) -> DeviceRegistry:
    """Provide a fresh DeviceRegistry and wire event capture."""
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return DeviceRegistry()


@given("the safety checker is initialized", target_fixture="safety_checker")
def safety_checker_initialized(device_registry: DeviceRegistry) -> HardwareSafetyChecker:
    return HardwareSafetyChecker(device_registry)


@given("the hardware manager is initialized", target_fixture="hardware_manager")
def hardware_manager_initialized(
    device_registry: DeviceRegistry,
    safety_checker: HardwareSafetyChecker,
) -> HardwareManager:
    return HardwareManager(device_registry, safety_checker)


# ---------------------------------------------------------------------------
# Device ID mapping — maps human-readable names to UUIDs
# ---------------------------------------------------------------------------


@pytest.fixture()
def device_ids() -> dict[str, str]:
    """Map of human-friendly device names to their actual device_id UUIDs."""
    return {}


# ---------------------------------------------------------------------------
# Given steps — device pre-registration
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


@given(
    parsers.parse('device "{name}" is registered with status "{status}" and capabilities "{caps}"'),
    target_fixture="_device_registered_caps",
)
def device_is_registered_with_caps(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
    status: str,
    caps: str,
) -> DeviceRecord:
    """Register a device with can_control capabilities."""
    cap_list = [c.strip() for c in caps.split(",")]
    record = DeviceRecord(
        name=name,
        device_type="generic",
        status=DeviceStatus(status),
        capabilities=DeviceCapabilities(can_control=cap_list),
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


_REGISTER_WITH_CAPS_STEP = (
    'I register a device "{name}" of type "{device_type}"'
    ' with status "{status}" and capabilities "{caps}"'
)


@when(
    parsers.parse(_REGISTER_WITH_CAPS_STEP),
    target_fixture="registered_device",
)
def register_device_with_caps(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
    device_type: str,
    status: str,
    caps: str,
) -> DeviceRecord:
    cap_list = [c.strip() for c in caps.split(",")]
    record = DeviceRecord(
        name=name,
        device_type=device_type,
        status=DeviceStatus(status),
        capabilities=DeviceCapabilities(can_control=cap_list),
    )
    result = device_registry.register(record)
    device_ids[name] = result.device_id
    return result


_REGISTER_SECOND_STEP = (
    'I register a second device "{name}" of type "{device_type}" with status "{status}"'
)


@when(
    parsers.parse(_REGISTER_SECOND_STEP),
    target_fixture="second_registered_device",
)
def register_second_device(
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
    device_ids[f"{name}__second"] = result.device_id
    return result


@when(
    parsers.parse('I re-register device "{name}" with the same ID'),
    target_fixture="reregister_error",
)
def reregister_device_same_id(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
) -> Exception | None:
    existing_id = device_ids[name]
    record = DeviceRecord(
        device_id=existing_id,
        name=name,
        device_type="generic",
        status=DeviceStatus.ONLINE,
    )
    try:
        device_registry.register(record)
        return None
    except ValueError as exc:
        return exc


@when(parsers.parse('I update device "{name}" status to "{status}"'))
def update_device_status(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
    status: str,
) -> None:
    device_id = device_ids[name]
    device_registry.update_status(device_id, DeviceStatus(status))


@when(
    parsers.parse('I update status of nonexistent device "{name}" to "{status}"'),
    target_fixture="update_status_error",
)
def update_nonexistent_device_status(name: str, status: str) -> Exception | None:
    """Attempt to update status on a fresh registry — device will not exist."""
    fresh = DeviceRegistry()
    try:
        fresh.update_status(name, DeviceStatus(status))
        return None
    except KeyError as exc:
        return exc


@when(parsers.parse('I list devices with status "{status}"'), target_fixture="device_list")
def list_devices_with_status(
    device_registry: DeviceRegistry,
    status: str,
) -> list[DeviceRecord]:
    return device_registry.list_devices(DeviceStatus(status))


@when("I list all devices", target_fixture="device_list")
def list_all_devices(device_registry: DeviceRegistry) -> list[DeviceRecord]:
    return device_registry.list_devices()


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


@when(
    parsers.parse('I unregister nonexistent device "{name}"'),
    target_fixture="unregister_error",
)
def unregister_nonexistent_device(name: str) -> Exception | None:
    fresh = DeviceRegistry()
    try:
        fresh.unregister(name)
        return None
    except KeyError as exc:
        return exc


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
    device_id = device_ids.get(name, name)
    command = HardwareCommand(device_id=device_id, action=action)
    return safety_checker.check(command)


# ---------------------------------------------------------------------------
# When steps — Manager
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I execute command "{action}" on device "{name}" via manager'),
    target_fixture="exec_result",
)
def execute_command_via_manager(
    hardware_manager: HardwareManager,
    device_ids: dict[str, str],
    action: str,
    name: str,
) -> SafetyCheckResult:
    device_id = device_ids.get(name, name)
    command = HardwareCommand(device_id=device_id, action=action)
    return hardware_manager.execute_command(command)


@when(
    parsers.parse('I execute command "{action}" with parameters on device "{name}" via manager'),
    target_fixture="exec_result",
)
def execute_command_with_params_via_manager(
    hardware_manager: HardwareManager,
    device_ids: dict[str, str],
    action: str,
    name: str,
) -> SafetyCheckResult:
    device_id = device_ids.get(name, name)
    command = HardwareCommand(device_id=device_id, action=action, parameters={"fps": 30})
    return hardware_manager.execute_command(command)


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


@then(parsers.parse('device "{name}" has capability "{cap}"'))
def device_has_capability(
    device_registry: DeviceRegistry,
    device_ids: dict[str, str],
    name: str,
    cap: str,
) -> None:
    device_id = device_ids[name]
    device = device_registry.get(device_id)
    assert device.capabilities is not None
    assert cap in device.capabilities.can_control, (
        f"Expected {cap!r} in capabilities {device.capabilities.can_control}"
    )


@then(parsers.parse("I get {count:d} devices"))
def got_n_devices(device_list: list[DeviceRecord], count: int) -> None:
    assert len(device_list) == count, f"Expected {count}, got {len(device_list)}"


@then("a KeyError is raised")
def key_error_raised(get_device_error: object) -> None:
    """For 'When I get device' scenarios."""
    assert isinstance(get_device_error, KeyError), (
        f"Expected KeyError, got {type(get_device_error).__name__}: {get_device_error}"
    )


@then("an update status KeyError is raised")
def update_status_key_error_raised(update_status_error: object) -> None:
    assert isinstance(update_status_error, KeyError), (
        f"Expected KeyError, got {type(update_status_error).__name__}: {update_status_error}"
    )


@then("an unregister KeyError is raised")
def unregister_key_error_raised(unregister_error: object) -> None:
    assert isinstance(unregister_error, KeyError), (
        f"Expected KeyError, got {type(unregister_error).__name__}: {unregister_error}"
    )


@then("a ValueError is raised")
def value_error_raised(reregister_error: object) -> None:
    assert isinstance(reregister_error, ValueError), (
        f"Expected ValueError, got {type(reregister_error).__name__}"
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


@then("both devices are in the registry with different IDs")
def both_devices_different_ids(
    registered_device: DeviceRecord,
    second_registered_device: DeviceRecord,
) -> None:
    assert registered_device.device_id != second_registered_device.device_id
    assert registered_device.name == second_registered_device.name


@then(parsers.parse('the registered device has field "{field}"'))
def registered_device_has_field(registered_device: DeviceRecord, field: str) -> None:
    assert hasattr(registered_device, field), f"DeviceRecord missing field {field!r}"
    value = getattr(registered_device, field)
    assert value is not None or field in {"watch_path"}, (
        f"Field {field!r} is None on registered device"
    )


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


@then(parsers.parse('the safety history for device "{name}" has {count:d} entries'))
def safety_history_count(
    safety_checker: HardwareSafetyChecker,
    device_ids: dict[str, str],
    name: str,
    count: int,
) -> None:
    device_id = device_ids[name]
    history = safety_checker.get_safety_history(device_id)
    assert len(history) == count, f"Expected {count} history entries, got {len(history)}"


# ---------------------------------------------------------------------------
# Then steps — Manager
# ---------------------------------------------------------------------------


@then("the command execution result passes")
def exec_result_passes(exec_result: SafetyCheckResult) -> None:
    assert exec_result.passed is True, f"Expected pass, got fail: {exec_result.details}"


@then("the command execution result fails")
def exec_result_fails(exec_result: SafetyCheckResult) -> None:
    assert exec_result.passed is False, f"Expected fail, got pass: {exec_result.details}"


@then(parsers.parse('the command execution level is "{level}"'))
def exec_result_level(exec_result: SafetyCheckResult, level: str) -> None:
    assert exec_result.level.value == level, (
        f"Expected level {level!r}, got {exec_result.level.value!r}"
    )


@then("the manager registry is the same registry")
def manager_registry_same(
    hardware_manager: HardwareManager,
    device_registry: DeviceRegistry,
) -> None:
    assert hardware_manager.registry is device_registry


@then("the manager safety checker is the same checker")
def manager_safety_same(
    hardware_manager: HardwareManager,
    safety_checker: HardwareSafetyChecker,
) -> None:
    assert hardware_manager.safety is safety_checker


# ---------------------------------------------------------------------------
# Fixtures for interface / driver tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def watch_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for file-based drivers."""
    d = tmp_path / "watch"
    d.mkdir()
    return d


@pytest.fixture()
def file_based_driver_holder() -> dict[str, Any]:
    """Mutable holder so multiple steps can share the driver instance."""
    return {}


@pytest.fixture()
def driver_error_holder() -> dict[str, Any]:
    """Mutable holder for caught errors."""
    return {}


# ---------------------------------------------------------------------------
# Given steps — filesystem setup for interfaces/drivers
# ---------------------------------------------------------------------------


@given("a temporary watch directory exists", target_fixture="watch_dir")
def given_watch_dir(tmp_path: Path) -> Path:
    d = tmp_path / "watch"
    d.mkdir()
    return d


@given("a temporary file exists at watch path", target_fixture="watch_dir")
def given_watch_file(tmp_path: Path) -> Path:
    f = tmp_path / "not_a_dir.csv"
    f.write_text("dummy")
    return f


_CSV_IN_DIR_STEP = (
    'a CSV file "{filename}" exists in that directory with header "{header}" and row "{row}"'
)


@given(parsers.parse(_CSV_IN_DIR_STEP))
def given_csv_file_in_dir(watch_dir: Path, filename: str, header: str, row: str) -> None:
    (watch_dir / filename).write_text(f"{header}\n{row}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Given / When steps — FileBasedDriver lifecycle
# ---------------------------------------------------------------------------


@when("I create a FileBasedDriver for that directory", target_fixture="file_driver")
def create_file_based_driver_dir(watch_dir: Path) -> FileBasedDriver:
    return FileBasedDriver(device_id="fb-001", device_type="generic", watch_path=watch_dir)


@when("I create a FileBasedDriver for a nonexistent directory", target_fixture="file_driver")
def create_file_based_driver_nodir(tmp_path: Path) -> FileBasedDriver:
    return FileBasedDriver(
        device_id="fb-002",
        device_type="generic",
        watch_path=tmp_path / "does_not_exist",
    )


@when("I create a FileBasedDriver for that file path", target_fixture="file_driver")
def create_file_based_driver_file(watch_dir: Path) -> FileBasedDriver:
    # watch_dir fixture was replaced by the given_watch_file fixture (returns a Path to a file)
    return FileBasedDriver(device_id="fb-003", device_type="generic", watch_path=watch_dir)


@when("I connect the FileBasedDriver", target_fixture="fb_connect_result")
def connect_file_based_driver(file_driver: FileBasedDriver, event_capture: EventCapture) -> bool:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return asyncio.run(file_driver.connect())


@when("I disconnect the FileBasedDriver")
def disconnect_file_based_driver(file_driver: FileBasedDriver) -> None:
    asyncio.run(file_driver.disconnect())


@when("I check FileBasedDriver status", target_fixture="fb_status")
def check_file_based_driver_status(file_driver: FileBasedDriver) -> DeviceStatus:
    return asyncio.run(file_driver.status())


@when(
    parsers.parse(
        'a CSV file "{filename}" is created in the watch directory with content "{content}"'
    )
)
def create_csv_in_watch_dir(watch_dir: Path, filename: str, content: str) -> None:
    (watch_dir / filename).write_text(content.replace("\\n", "\n"), encoding="utf-8")


@when("I read from the FileBasedDriver", target_fixture="fb_read_result")
def read_file_based_driver(file_driver: FileBasedDriver) -> dict[str, Any]:
    return asyncio.run(file_driver.read())


@when(
    parsers.parse('I write command "{action}" to the FileBasedDriver'),
    target_fixture="fb_write_result",
)
def write_file_based_driver(file_driver: FileBasedDriver, action: str) -> bool:
    cmd = HardwareCommand(device_id=file_driver.device_id, action=action)
    return asyncio.run(file_driver.write(cmd))


@when(
    parsers.parse('I parse "{filename}" with the FileBasedDriver'),
    target_fixture="parsed_file_data",
)
def parse_file_with_file_based_driver(
    watch_dir: Path, file_driver: FileBasedDriver, filename: str
) -> dict[str, Any]:
    return file_driver.parse_file(watch_dir / filename)


# ---------------------------------------------------------------------------
# Then steps — FileBasedDriver
# ---------------------------------------------------------------------------


@then("the FileBasedDriver is connected")
def fb_driver_is_connected(fb_connect_result: bool) -> None:
    assert fb_connect_result is True, "Expected FileBasedDriver to connect successfully"


@then("the FileBasedDriver connection fails")
def fb_driver_connection_fails(fb_connect_result: bool) -> None:
    assert fb_connect_result is False, "Expected FileBasedDriver connection to fail"


@then(parsers.parse('the FileBasedDriver status is "{status}"'))
def fb_driver_status_is(fb_status: DeviceStatus, status: str) -> None:
    assert fb_status.value == status, f"Expected status {status!r}, got {fb_status.value!r}"


@then(parsers.parse("the read result contains {count:d} new file"))
@then(parsers.parse("the read result contains {count:d} new files"))
def fb_read_new_file_count(fb_read_result: dict[str, Any], count: int) -> None:
    assert len(fb_read_result["new_files"]) == count, (
        f"Expected {count} new files, got {fb_read_result['new_files']}"
    )


@then("the FileBasedDriver write returns False")
def fb_write_returns_false(fb_write_result: bool) -> None:
    assert fb_write_result is False, "Expected FileBasedDriver write to return False"


@then("the DAQDriver write returns False")
def daq_write_returns_false(daq_write_result: bool) -> None:
    assert daq_write_result is False, "Expected DAQDriver write to return False"


@then("the SoftwareBridgeDriver write returns False")
def sw_write_returns_false(sw_write_result: bool) -> None:
    assert sw_write_result is False, "Expected SoftwareBridgeDriver write to return False"


@then(parsers.parse('the parsed data contains key "{key}"'))
def parsed_data_has_key(parsed_file_data: dict[str, Any], key: str) -> None:
    assert key in parsed_file_data, f"Expected key {key!r} in {list(parsed_file_data.keys())}"


@then(parsers.parse("the parsed data has row count {count:d}"))
def parsed_data_row_count(parsed_file_data: dict[str, Any], count: int) -> None:
    rows = parsed_file_data.get("rows", [])
    assert len(rows) == count, f"Expected {count} rows, got {len(rows)}"


# ---------------------------------------------------------------------------
# Given step — additional CSV fixture for FileBasedDriver
# ---------------------------------------------------------------------------


@given(
    parsers.parse('a plate reader CSV file "{filename}" with row "{row_letter}" values "{values}"')
)
def given_plate_csv(watch_dir: Path, filename: str, row_letter: str, values: str) -> None:
    content = f"{row_letter},{values}\n"
    (watch_dir / filename).write_text(content, encoding="utf-8")


@given(parsers.parse('a plate reader CSV file "{filename}" with metadata "{meta}"'))
def given_plate_csv_meta(watch_dir: Path, filename: str, meta: str) -> None:
    (watch_dir / filename).write_text(f"{meta}\n", encoding="utf-8")


@given(
    parsers.parse('a plate reader CSV file "{filename}" with row "{row_letter}" having 14 values')
)
def given_plate_csv_extra_cols(watch_dir: Path, filename: str, row_letter: str) -> None:
    values = ",".join(str(i * 0.1) for i in range(1, 15))
    content = f"{row_letter},{values}\n"
    (watch_dir / filename).write_text(content, encoding="utf-8")


@given(
    parsers.parse('a plate reader CSV file "{filename}" with row "{row_letter}" values "{values}"')
)
def given_plate_csv_str_vals(watch_dir: Path, filename: str, row_letter: str, values: str) -> None:
    # Alias — same as given_plate_csv; pytest-bdd deduplicates by step text
    (watch_dir / filename).write_text(f"{row_letter},{values}\n", encoding="utf-8")


@given(parsers.parse('an empty plate reader CSV file "{filename}"'))
def given_empty_plate_csv(watch_dir: Path, filename: str) -> None:
    (watch_dir / filename).write_text("", encoding="utf-8")


@given(parsers.parse('an empty qPCR export file "{filename}"'))
def given_empty_qpcr(watch_dir: Path, filename: str) -> None:
    (watch_dir / filename).write_text("", encoding="utf-8")


@given(parsers.parse('a qPCR export file "{filename}" with results header and one sample row'))
def given_qpcr_one_sample(watch_dir: Path, filename: str) -> None:
    content = "Well\tSample Name\tDetector Name\tCt\nA1\tSample1\tGAPDH\t22.45\n"
    (watch_dir / filename).write_text(content, encoding="utf-8")


@given(parsers.parse('a qPCR export file "{filename}" with a sample having ct value "{ct}"'))
def given_qpcr_sample_ct(watch_dir: Path, filename: str, ct: str) -> None:
    content = f"Well\tSample Name\tDetector Name\tCt\nA1\tSample1\tGAPDH\t{ct}\n"
    (watch_dir / filename).write_text(content, encoding="utf-8")


@given(
    parsers.parse('a qPCR export file "{filename}" with metadata "{meta_line}" and a sample row')
)
def given_qpcr_meta_and_sample(watch_dir: Path, filename: str, meta_line: str) -> None:
    # Interpret \t escape sequences so feature file can use literal \t
    decoded_meta = meta_line.replace("\\t", "\t")
    content = f"{decoded_meta}\nWell\tSample Name\tDetector Name\tCt\nA1\tSample1\tGAPDH\t22.0\n"
    (watch_dir / filename).write_text(content, encoding="utf-8")


@given(
    parsers.parse(
        'a qPCR export file "{filename}" with two sample rows then a blank line and trailing data'
    )
)
def given_qpcr_two_samples_then_blank(watch_dir: Path, filename: str) -> None:
    content = (
        "Well\tSample Name\tDetector Name\tCt\n"
        "A1\tSample1\tGAPDH\t22.0\n"
        "A2\tSample2\tGAPDH\t23.0\n"
        "\n"
        "This line should be ignored\n"
    )
    (watch_dir / filename).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# When / Then steps — PlateReaderCSVDriver
# ---------------------------------------------------------------------------


@when("I parse that plate CSV file with PlateReaderCSVDriver", target_fixture="parsed_plate_data")
def parse_plate_csv(watch_dir: Path) -> dict[str, Any]:
    from labclaw.hardware.drivers.plate_reader_csv import PlateReaderCSVDriver

    driver = PlateReaderCSVDriver(
        device_id="plate-001",
        device_type="plate_reader",
        watch_path=watch_dir,
    )
    # Find the first CSV file in watch_dir
    csv_files = list(watch_dir.glob("*.csv"))
    assert csv_files, f"No CSV files found in {watch_dir}"
    return driver.parse_file(csv_files[0])


@when("I create a PlateReaderCSVDriver for that directory", target_fixture="plate_driver")
def create_plate_driver(watch_dir: Path) -> Any:
    from labclaw.hardware.drivers.plate_reader_csv import PlateReaderCSVDriver

    return PlateReaderCSVDriver(
        device_id="plate-002",
        device_type="plate_reader",
        watch_path=watch_dir,
    )


@then(parsers.parse('the parsed plate data contains wells "{from_well}" through "{to_well}"'))
def plate_has_wells_range(parsed_plate_data: dict[str, Any], from_well: str, to_well: str) -> None:
    wells = parsed_plate_data["wells"]
    assert from_well in wells, f"Well {from_well!r} not found: {list(wells.keys())}"
    assert to_well in wells, f"Well {to_well!r} not found: {list(wells.keys())}"


@then(parsers.parse('well "{well}" has value {value:f}'))
def well_has_value(parsed_plate_data: dict[str, Any], well: str, value: float) -> None:
    wells = parsed_plate_data["wells"]
    assert well in wells, f"Well {well!r} not in {list(wells.keys())}"
    assert abs(float(wells[well]) - value) < 1e-6, f"Expected {well}={value}, got {wells[well]}"


@then(parsers.parse('the parsed plate metadata contains key "{key}" with value "{value}"'))
def plate_metadata_has(parsed_plate_data: dict[str, Any], key: str, value: str) -> None:
    meta = parsed_plate_data["metadata"]
    assert key in meta, f"Key {key!r} not in metadata: {list(meta.keys())}"
    assert meta[key] == value, f"Expected metadata[{key!r}]={value!r}, got {meta[key]!r}"


@then(parsers.parse('the parsed plate data has at most 12 wells for row "{row_letter}"'))
def plate_at_most_12_wells(parsed_plate_data: dict[str, Any], row_letter: str) -> None:
    wells = parsed_plate_data["wells"]
    row_wells = [k for k in wells if k.startswith(row_letter)]
    n = len(row_wells)
    assert n <= 12, f"Expected at most 12 wells for row {row_letter}, got {n}"


@then(parsers.parse('well "{well}" is stored as a string'))
def well_is_string(parsed_plate_data: dict[str, Any], well: str) -> None:
    wells = parsed_plate_data["wells"]
    assert well in wells, f"Well {well!r} not found"
    assert isinstance(wells[well], str), (
        f"Expected string for {well}, got {type(wells[well]).__name__}"
    )


@then(parsers.parse("the parsed plate data has {count:d} wells"))
def plate_has_n_wells(parsed_plate_data: dict[str, Any], count: int) -> None:
    wells = parsed_plate_data["wells"]
    assert len(wells) == count, f"Expected {count} wells, got {len(wells)}"


@then(parsers.parse('the PlateReaderCSVDriver file patterns include "{pattern}"'))
def plate_driver_has_pattern(plate_driver: Any, pattern: str) -> None:
    assert pattern in plate_driver._file_patterns, (
        f"Pattern {pattern!r} not in {plate_driver._file_patterns}"
    )


@then(parsers.parse('the parsed plate result includes key "{key}"'))
def plate_result_has_key(parsed_plate_data: dict[str, Any], key: str) -> None:
    assert key in parsed_plate_data, (
        f"Expected key {key!r} in parsed plate result: {list(parsed_plate_data.keys())}"
    )


# ---------------------------------------------------------------------------
# When / Then steps — QPCRExportDriver
# ---------------------------------------------------------------------------


@when("I parse that qPCR file with QPCRExportDriver", target_fixture="parsed_qpcr_data")
def parse_qpcr_file(watch_dir: Path) -> dict[str, Any]:
    from labclaw.hardware.drivers.qpcr_export import QPCRExportDriver

    driver = QPCRExportDriver(
        device_id="qpcr-001",
        device_type="qpcr",
        watch_path=watch_dir,
    )
    files = (
        list(watch_dir.glob("*.txt"))
        + list(watch_dir.glob("*.tsv"))
        + list(watch_dir.glob("*.csv"))
    )
    assert files, f"No qPCR files found in {watch_dir}"
    return driver.parse_file(files[0])


@when("I create a QPCRExportDriver for that directory", target_fixture="qpcr_driver")
def create_qpcr_driver(watch_dir: Path) -> Any:
    from labclaw.hardware.drivers.qpcr_export import QPCRExportDriver

    return QPCRExportDriver(
        device_id="qpcr-002",
        device_type="qpcr",
        watch_path=watch_dir,
    )


@then(parsers.parse("the parsed qPCR data contains {count:d} sample"))
@then(parsers.parse("the parsed qPCR data contains {count:d} samples"))
def qpcr_has_n_samples(parsed_qpcr_data: dict[str, Any], count: int) -> None:
    samples = parsed_qpcr_data["samples"]
    assert len(samples) == count, f"Expected {count} samples, got {len(samples)}"


@then(parsers.parse("the parsed sample has ct value {value:f}"))
def qpcr_ct_is_float(parsed_qpcr_data: dict[str, Any], value: float) -> None:
    assert parsed_qpcr_data["samples"], "No samples parsed"
    ct = parsed_qpcr_data["samples"][0]["ct"]
    assert isinstance(ct, float), f"Expected float ct, got {type(ct).__name__}"
    assert abs(ct - value) < 1e-6, f"Expected ct={value}, got {ct}"


@then(parsers.parse('the parsed sample has ct value "{value}"'))
def qpcr_ct_is_string(parsed_qpcr_data: dict[str, Any], value: str) -> None:
    assert parsed_qpcr_data["samples"], "No samples parsed"
    ct = parsed_qpcr_data["samples"][0]["ct"]
    assert ct == value, f"Expected ct={value!r}, got {ct!r}"


@then(parsers.parse('the parsed qPCR metadata contains key "{key}" with value "{value}"'))
def qpcr_metadata_has(parsed_qpcr_data: dict[str, Any], key: str, value: str) -> None:
    meta = parsed_qpcr_data["metadata"]
    assert key in meta, f"Key {key!r} not in metadata: {list(meta.keys())}"
    assert meta[key] == value, f"Expected metadata[{key!r}]={value!r}, got {meta[key]!r}"


@then(parsers.parse('the QPCRExportDriver file patterns include "{pattern}"'))
def qpcr_driver_has_pattern(qpcr_driver: Any, pattern: str) -> None:
    assert pattern in qpcr_driver._file_patterns, (
        f"Pattern {pattern!r} not in {qpcr_driver._file_patterns}"
    )


@then(parsers.parse('the parsed qPCR result includes key "{key}"'))
def qpcr_result_has_key(parsed_qpcr_data: dict[str, Any], key: str) -> None:
    assert key in parsed_qpcr_data, (
        f"Expected key {key!r} in qPCR result: {list(parsed_qpcr_data.keys())}"
    )


# ---------------------------------------------------------------------------
# NetworkAPIDriver steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create a NetworkAPIDriver with id "{dev_id}" and url "{url}"'),
    target_fixture="net_driver",
)
def create_network_driver(dev_id: str, url: str, event_capture: EventCapture) -> NetworkAPIDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return NetworkAPIDriver(device_id=dev_id, device_type="generic", base_url=url)


@when(
    parsers.parse(
        'I create a NetworkAPIDriver with id "{dev_id}" type "{dev_type}" and url "{url}"'
    ),
    target_fixture="net_driver",
)
def create_network_driver_typed(
    dev_id: str, dev_type: str, url: str, event_capture: EventCapture
) -> NetworkAPIDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return NetworkAPIDriver(device_id=dev_id, device_type=dev_type, base_url=url)


@when("I check NetworkAPIDriver status", target_fixture="net_status")
def check_net_driver_status(net_driver: NetworkAPIDriver) -> DeviceStatus:
    return asyncio.run(net_driver.status())


@when("I disconnect the NetworkAPIDriver")
def disconnect_net_driver(net_driver: NetworkAPIDriver) -> None:
    asyncio.run(net_driver.disconnect())


@then(parsers.parse('the NetworkAPIDriver device_id is "{dev_id}"'))
def net_driver_device_id(net_driver: NetworkAPIDriver, dev_id: str) -> None:
    assert net_driver.device_id == dev_id


@then(parsers.parse('the NetworkAPIDriver device_type is "{dev_type}"'))
def net_driver_device_type(net_driver: NetworkAPIDriver, dev_type: str) -> None:
    assert net_driver.device_type == dev_type


@then(parsers.parse('the NetworkAPIDriver status is "{status}"'))
def net_driver_status_is(net_status: DeviceStatus, status: str) -> None:
    assert net_status.value == status, f"Expected {status!r}, got {net_status.value!r}"


# ---------------------------------------------------------------------------
# SerialDriver steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create a SerialDriver with id "{dev_id}" and port "{port}"'),
    target_fixture="serial_driver",
)
def create_serial_driver(dev_id: str, port: str, event_capture: EventCapture) -> SerialDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return SerialDriver(device_id=dev_id, device_type="generic", port=port)


@when(
    parsers.parse('I create a SerialDriver with id "{dev_id}" type "{dev_type}" and port "{port}"'),
    target_fixture="serial_driver",
)
def create_serial_driver_typed(
    dev_id: str, dev_type: str, port: str, event_capture: EventCapture
) -> SerialDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return SerialDriver(device_id=dev_id, device_type=dev_type, port=port)


@when("I check SerialDriver status", target_fixture="serial_status")
def check_serial_status(serial_driver: SerialDriver) -> DeviceStatus:
    return asyncio.run(serial_driver.status())


@when(
    "I attempt to read from SerialDriver without connecting",
    target_fixture="serial_read_error",
)
def serial_read_without_connect(serial_driver: SerialDriver) -> Exception | None:
    try:
        asyncio.run(serial_driver.read())
        return None
    except RuntimeError as exc:
        return exc


@when(
    parsers.parse('I parse serial response "{raw}"'),
    target_fixture="parsed_serial_response",
)
def parse_serial_response(serial_driver: SerialDriver, raw: str) -> dict[str, Any]:
    return serial_driver.parse_response(raw)


@then(parsers.parse('the SerialDriver device_id is "{dev_id}"'))
def serial_driver_id(serial_driver: SerialDriver, dev_id: str) -> None:
    assert serial_driver.device_id == dev_id


@then(parsers.parse('the SerialDriver device_type is "{dev_type}"'))
def serial_driver_type(serial_driver: SerialDriver, dev_type: str) -> None:
    assert serial_driver.device_type == dev_type


@then(parsers.parse('the SerialDriver status is "{status}"'))
def serial_status_is(serial_status: DeviceStatus, status: str) -> None:
    assert serial_status.value == status, f"Expected {status!r}, got {serial_status.value!r}"


@then("a RuntimeError is raised")
def runtime_error_raised(serial_read_error: object) -> None:
    assert isinstance(serial_read_error, RuntimeError), (
        f"Expected RuntimeError, got {type(serial_read_error).__name__}"
    )


@then(parsers.parse('the parsed serial response contains key "{key}" with value "{value}"'))
def serial_response_has_key_value(
    parsed_serial_response: dict[str, Any], key: str, value: str
) -> None:
    assert key in parsed_serial_response, f"Key {key!r} not found"
    assert parsed_serial_response[key] == value, (
        f"Expected {value!r}, got {parsed_serial_response[key]!r}"
    )


# ---------------------------------------------------------------------------
# DAQDriver concrete subclass for testing
# ---------------------------------------------------------------------------


class _SuccessDAQDriver(DAQDriver):
    """DAQDriver that opens/closes/reads/writes successfully."""

    def _open_device(self) -> None:
        pass  # No-op: always succeeds

    def _close_device(self) -> None:
        pass

    def _read_channels(self) -> dict[str, Any]:
        return {"ch0": 1.0, "ch1": 2.0}

    def _write_channels(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class _FailOpenDAQDriver(DAQDriver):
    """DAQDriver whose _open_device always raises."""

    def _open_device(self) -> None:
        raise OSError("DAQ hardware not found")

    def _close_device(self) -> None:
        pass

    def _read_channels(self) -> dict[str, Any]:
        return {}

    def _write_channels(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class _FailCloseDAQDriver(DAQDriver):
    """DAQDriver whose _close_device always raises (but connect succeeds)."""

    def _open_device(self) -> None:
        pass

    def _close_device(self) -> None:
        raise OSError("Cannot close DAQ device")

    def _read_channels(self) -> dict[str, Any]:
        return {}

    def _write_channels(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class _FailWriteDAQDriver(DAQDriver):
    """DAQDriver whose _write_channels always raises."""

    def _open_device(self) -> None:
        pass

    def _close_device(self) -> None:
        pass

    def _read_channels(self) -> dict[str, Any]:
        return {}

    def _write_channels(self, action: str, parameters: dict[str, Any]) -> None:
        raise RuntimeError("Write channel failed")


# ---------------------------------------------------------------------------
# DAQDriver steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create a DAQDriver with id "{dev_id}"'),
    target_fixture="daq_driver",
)
def create_daq_driver(dev_id: str, event_capture: EventCapture) -> DAQDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _SuccessDAQDriver(device_id=dev_id, device_type="gpio")


@when(
    parsers.parse('I create a DAQDriver with id "{dev_id}" type "{dev_type}"'),
    target_fixture="daq_driver",
)
def create_daq_driver_typed(dev_id: str, dev_type: str, event_capture: EventCapture) -> DAQDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _SuccessDAQDriver(device_id=dev_id, device_type=dev_type)


@when(
    parsers.parse('I create a DAQDriver with id "{dev_id}" that raises on open'),
    target_fixture="daq_driver",
)
def create_fail_open_daq_driver(dev_id: str, event_capture: EventCapture) -> DAQDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _FailOpenDAQDriver(device_id=dev_id, device_type="gpio")


@when(
    parsers.parse('I create a DAQDriver with id "{dev_id}" that raises on close'),
    target_fixture="daq_driver",
)
def create_fail_close_daq_driver(dev_id: str, event_capture: EventCapture) -> DAQDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _FailCloseDAQDriver(device_id=dev_id, device_type="gpio")


@when(
    parsers.parse('I create a DAQDriver with id "{dev_id}" that raises on write'),
    target_fixture="daq_driver",
)
def create_fail_write_daq_driver(dev_id: str, event_capture: EventCapture) -> DAQDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _FailWriteDAQDriver(device_id=dev_id, device_type="gpio")


@when("I check DAQDriver status", target_fixture="daq_status")
def check_daq_status(daq_driver: DAQDriver) -> DeviceStatus:
    return asyncio.run(daq_driver.status())


@when("I connect the DAQDriver", target_fixture="daq_connect_result")
def connect_daq_driver(daq_driver: DAQDriver) -> bool:
    return asyncio.run(daq_driver.connect())


@when("I connect the DAQDriver successfully")
def connect_daq_driver_ok(daq_driver: DAQDriver) -> None:
    result = asyncio.run(daq_driver.connect())
    assert result is True, "Expected DAQDriver connect to succeed"


@when("I disconnect the DAQDriver")
def disconnect_daq_driver(daq_driver: DAQDriver) -> None:
    asyncio.run(daq_driver.disconnect())


@when(
    parsers.parse('I write command "{action}" to the DAQDriver'),
    target_fixture="daq_write_result",
)
def write_daq_driver(daq_driver: DAQDriver, action: str) -> bool:
    cmd = HardwareCommand(device_id=daq_driver.device_id, action=action)
    return asyncio.run(daq_driver.write(cmd))


@then(parsers.parse('the DAQDriver device_id is "{dev_id}"'))
def daq_driver_id(daq_driver: DAQDriver, dev_id: str) -> None:
    assert daq_driver.device_id == dev_id


@then(parsers.parse('the DAQDriver device_type is "{dev_type}"'))
def daq_driver_type(daq_driver: DAQDriver, dev_type: str) -> None:
    assert daq_driver.device_type == dev_type


@then(parsers.parse('the DAQDriver status is "{status}"'))
def daq_status_is(daq_status: DeviceStatus, status: str) -> None:
    assert daq_status.value == status, f"Expected {status!r}, got {daq_status.value!r}"


@then("the DAQDriver connection fails")
def daq_connection_fails(daq_connect_result: bool) -> None:
    assert daq_connect_result is False, "Expected DAQDriver connection to fail"


# ---------------------------------------------------------------------------
# SoftwareBridgeDriver concrete subclasses for testing
# ---------------------------------------------------------------------------


class _SuccessSoftwareBridgeDriver(SoftwareBridgeDriver):
    """SoftwareBridgeDriver that always connects/disconnects/reads/writes ok."""

    def _open_connection(self) -> None:
        pass

    def _close_connection(self) -> None:
        pass

    def _recv(self) -> dict[str, Any]:
        return {"frame": 1}

    def _send(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class _FailOpenSoftwareBridgeDriver(SoftwareBridgeDriver):
    def _open_connection(self) -> None:
        raise ConnectionRefusedError("ZMQ endpoint not available")

    def _close_connection(self) -> None:
        pass

    def _recv(self) -> dict[str, Any]:
        return {}

    def _send(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class _FailCloseSoftwareBridgeDriver(SoftwareBridgeDriver):
    def _open_connection(self) -> None:
        pass

    def _close_connection(self) -> None:
        raise RuntimeError("Cannot close ZMQ socket")

    def _recv(self) -> dict[str, Any]:
        return {}

    def _send(self, action: str, parameters: dict[str, Any]) -> None:
        pass


class _FailSendSoftwareBridgeDriver(SoftwareBridgeDriver):
    def _open_connection(self) -> None:
        pass

    def _close_connection(self) -> None:
        pass

    def _recv(self) -> dict[str, Any]:
        return {}

    def _send(self, action: str, parameters: dict[str, Any]) -> None:
        raise RuntimeError("Send failed")


# ---------------------------------------------------------------------------
# SoftwareBridgeDriver steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I create a SoftwareBridgeDriver with id "{dev_id}"'),
    target_fixture="sw_driver",
)
def create_sw_driver(dev_id: str, event_capture: EventCapture) -> SoftwareBridgeDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _SuccessSoftwareBridgeDriver(device_id=dev_id, device_type="software_bridge")


@when(
    parsers.parse('I create a SoftwareBridgeDriver with id "{dev_id}" that raises on open'),
    target_fixture="sw_driver",
)
def create_fail_open_sw_driver(dev_id: str, event_capture: EventCapture) -> SoftwareBridgeDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _FailOpenSoftwareBridgeDriver(device_id=dev_id, device_type="software_bridge")


@when(
    parsers.parse('I create a SoftwareBridgeDriver with id "{dev_id}" that raises on close'),
    target_fixture="sw_driver",
)
def create_fail_close_sw_driver(dev_id: str, event_capture: EventCapture) -> SoftwareBridgeDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _FailCloseSoftwareBridgeDriver(device_id=dev_id, device_type="software_bridge")


@when(
    parsers.parse('I create a SoftwareBridgeDriver with id "{dev_id}" that raises on send'),
    target_fixture="sw_driver",
)
def create_fail_send_sw_driver(dev_id: str, event_capture: EventCapture) -> SoftwareBridgeDriver:
    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return _FailSendSoftwareBridgeDriver(device_id=dev_id, device_type="software_bridge")


@when("I check SoftwareBridgeDriver status", target_fixture="sw_status")
def check_sw_status(sw_driver: SoftwareBridgeDriver) -> DeviceStatus:
    return asyncio.run(sw_driver.status())


@when("I connect the SoftwareBridgeDriver", target_fixture="sw_connect_result")
def connect_sw_driver(sw_driver: SoftwareBridgeDriver) -> bool:
    return asyncio.run(sw_driver.connect())


@when("I connect the SoftwareBridgeDriver successfully")
def connect_sw_driver_ok(sw_driver: SoftwareBridgeDriver) -> None:
    result = asyncio.run(sw_driver.connect())
    assert result is True, "Expected SoftwareBridgeDriver connect to succeed"


@when("I disconnect the SoftwareBridgeDriver")
def disconnect_sw_driver(sw_driver: SoftwareBridgeDriver) -> None:
    asyncio.run(sw_driver.disconnect())


@when(
    parsers.parse('I write command "{action}" to the SoftwareBridgeDriver'),
    target_fixture="sw_write_result",
)
def write_sw_driver(sw_driver: SoftwareBridgeDriver, action: str) -> bool:
    cmd = HardwareCommand(device_id=sw_driver.device_id, action=action)
    return asyncio.run(sw_driver.write(cmd))


@then(parsers.parse('the SoftwareBridgeDriver device_id is "{dev_id}"'))
def sw_driver_id(sw_driver: SoftwareBridgeDriver, dev_id: str) -> None:
    assert sw_driver.device_id == dev_id


@then(parsers.parse('the SoftwareBridgeDriver status is "{status}"'))
def sw_driver_status_is(sw_status: DeviceStatus, status: str) -> None:
    assert sw_status.value == status, f"Expected {status!r}, got {sw_status.value!r}"


@then("the SoftwareBridgeDriver connection fails")
def sw_connection_fails(sw_connect_result: bool) -> None:
    assert sw_connect_result is False, "Expected SoftwareBridgeDriver connection to fail"


# ---------------------------------------------------------------------------
# DeviceDriver protocol compliance
# ---------------------------------------------------------------------------


@then("the FileBasedDriver satisfies the DeviceDriver protocol")
def fb_satisfies_driver_protocol(file_driver: FileBasedDriver) -> None:
    assert isinstance(file_driver, DeviceDriver), (
        f"{type(file_driver).__name__} does not satisfy DeviceDriver protocol"
    )


@then("the NetworkAPIDriver satisfies the DeviceDriver protocol")
def net_satisfies_driver_protocol(net_driver: NetworkAPIDriver) -> None:
    assert isinstance(net_driver, DeviceDriver), (
        f"{type(net_driver).__name__} does not satisfy DeviceDriver protocol"
    )


@then("the SerialDriver satisfies the DeviceDriver protocol")
def serial_satisfies_driver_protocol(serial_driver: SerialDriver) -> None:
    assert isinstance(serial_driver, DeviceDriver), (
        f"{type(serial_driver).__name__} does not satisfy DeviceDriver protocol"
    )


@then("the DAQDriver satisfies the DeviceDriver protocol")
def daq_satisfies_driver_protocol(daq_driver: DAQDriver) -> None:
    assert isinstance(daq_driver, DeviceDriver), (
        f"{type(daq_driver).__name__} does not satisfy DeviceDriver protocol"
    )


@then("the SoftwareBridgeDriver satisfies the DeviceDriver protocol")
def sw_satisfies_driver_protocol(sw_driver: SoftwareBridgeDriver) -> None:
    assert isinstance(sw_driver, DeviceDriver), (
        f"{type(sw_driver).__name__} does not satisfy DeviceDriver protocol"
    )


# ---------------------------------------------------------------------------
# FileWatcherDriver steps
# ---------------------------------------------------------------------------


@when("I create a FileWatcherDriver for that directory", target_fixture="watcher_driver")
def create_file_watcher_driver_dir(watch_dir: Path, event_capture: EventCapture) -> Any:
    from labclaw.hardware.drivers.file_watcher import FileWatcherDriver

    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return FileWatcherDriver(
        device_id="fw-001",
        device_type="watcher",
        watch_path=watch_dir,
    )


@when("I create a FileWatcherDriver for a nonexistent directory", target_fixture="watcher_driver")
def create_file_watcher_driver_nodir(tmp_path: Path, event_capture: EventCapture) -> Any:
    from labclaw.hardware.drivers.file_watcher import FileWatcherDriver

    for evt_name in event_registry.list_events():
        if evt_name.startswith("hardware."):
            event_registry.subscribe(evt_name, event_capture)
    return FileWatcherDriver(
        device_id="fw-002",
        device_type="watcher",
        watch_path=tmp_path / "does_not_exist",
    )


@when("I connect the FileWatcherDriver", target_fixture="fw_connect_result")
def connect_file_watcher_driver(watcher_driver: Any) -> bool:
    return asyncio.run(watcher_driver.connect())


@when("I disconnect the FileWatcherDriver to clean up")
@then("I disconnect the FileWatcherDriver to clean up")
def disconnect_file_watcher_cleanup(watcher_driver: Any) -> None:
    asyncio.run(watcher_driver.disconnect())


@when("I disconnect the FileWatcherDriver")
def disconnect_file_watcher_driver(watcher_driver: Any) -> None:
    asyncio.run(watcher_driver.disconnect())


@when("I check FileWatcherDriver status", target_fixture="fw_status")
def check_file_watcher_status(watcher_driver: Any) -> DeviceStatus:
    return asyncio.run(watcher_driver.status())


@when(
    "I read from the FileWatcherDriver without connecting",
    target_fixture="fw_read_result",
)
def read_file_watcher_no_connect(watcher_driver: Any) -> dict[str, Any]:
    return asyncio.run(watcher_driver.read())


@when(
    parsers.parse('I parse "{filename}" with the FileWatcherDriver'),
    target_fixture="parsed_file_data",
)
def parse_file_with_watcher_driver(
    watch_dir: Path, watcher_driver: Any, filename: str
) -> dict[str, Any]:
    return watcher_driver.parse_file(watch_dir / filename)


@then("the FileWatcherDriver is connected")
def fw_driver_is_connected(fw_connect_result: bool) -> None:
    assert fw_connect_result is True, "Expected FileWatcherDriver to connect"


@then("the FileWatcherDriver connection fails")
def fw_driver_connection_fails(fw_connect_result: bool) -> None:
    assert fw_connect_result is False, "Expected FileWatcherDriver connection to fail"


@then(parsers.parse('the FileWatcherDriver status is "{status}"'))
def fw_driver_status_is(fw_status: DeviceStatus, status: str) -> None:
    assert fw_status.value == status, f"Expected {status!r}, got {fw_status.value!r}"


@then(parsers.parse("the watcher read result has {count:d} new files"))
def fw_read_no_new_files(fw_read_result: dict[str, Any], count: int) -> None:
    assert len(fw_read_result["new_files"]) == count, (
        f"Expected {count} new files, got {fw_read_result['new_files']}"
    )
