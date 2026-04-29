import os
import shutil

import homeassistant.core as ha
from homeassistant.setup import async_setup_component

BLUEPRINT_SRC = os.path.join(
    os.path.dirname(__file__), "..", "blueprints", "automation", "fenster_heizung.yaml"
)


async def setup_automation(hass, climate_target, window_sensors):
    """Copy blueprint into HA config, register mock climate services, return call list."""
    blueprints_dir = hass.config.path("blueprints/automation")
    os.makedirs(blueprints_dir, exist_ok=True)
    shutil.copy(BLUEPRINT_SRC, os.path.join(blueprints_dir, "fenster_heizung.yaml"))

    service_calls = []

    @ha.callback
    def capture_call(call):
        service_calls.append(call)

    hass.services.async_register("climate", "set_temperature", capture_call)
    hass.services.async_register("climate", "set_hvac_mode", capture_call)

    await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "fenster_heizung.yaml",
                    "input": {
                        "climate_target": climate_target,
                        "window_sensors": window_sensors,
                        "trigger_delay": 0,
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return service_calls


def assert_calls(captured, expected):
    """Compare captured service calls against expected list of dicts."""
    assert [
        {"domain": c.domain, "service": c.service, "data": dict(c.data)}
        for c in captured
    ] == expected


# ─────────────────────────── Window Open Scenarios ───────────────────────────


async def test_open_while_off(hass, enable_custom_integrations):
    """Window opens while heating is off: blueprint should do nothing."""
    hass.states.async_set("binary_sensor.window", "off")
    hass.states.async_set("climate.thermostat", "off")

    calls = await setup_automation(hass, "climate.thermostat", ["binary_sensor.window"])

    hass.states.async_set("binary_sensor.window", "on")
    await hass.async_block_till_done()

    assert_calls(calls, [])


async def test_open_while_auto_not_paused(hass, enable_custom_integrations):
    """Window opens while heating is auto and not yet paused: set to 6°C."""
    hass.states.async_set("binary_sensor.window", "off")
    hass.states.async_set("climate.thermostat", "auto", {"temperature": 20.0})

    calls = await setup_automation(hass, "climate.thermostat", ["binary_sensor.window"])

    hass.states.async_set("binary_sensor.window", "on")
    await hass.async_block_till_done()

    assert_calls(
        calls,
        [
            {
                "domain": "climate",
                "service": "set_temperature",
                "data": {
                    "entity_id": ["climate.thermostat"],
                    "temperature": 6.0,
                },
            }
        ],
    )


async def test_first_of_two_opens(hass, enable_custom_integrations):
    """First of two windows opens: set to 6°C."""
    hass.states.async_set("binary_sensor.window_a", "off")
    hass.states.async_set("binary_sensor.window_b", "off")
    hass.states.async_set("climate.thermostat", "auto", {"temperature": 20.0})

    calls = await setup_automation(
        hass, "climate.thermostat", ["binary_sensor.window_a", "binary_sensor.window_b"]
    )

    hass.states.async_set("binary_sensor.window_a", "on")
    await hass.async_block_till_done()

    assert_calls(
        calls,
        [
            {
                "domain": "climate",
                "service": "set_temperature",
                "data": {
                    "entity_id": ["climate.thermostat"],
                    "temperature": 6.0,
                },
            }
        ],
    )


async def test_second_of_two_opens_while_paused(hass, enable_custom_integrations):
    """Second window opens while already paused: do nothing."""
    hass.states.async_set("binary_sensor.window_a", "on")
    hass.states.async_set("binary_sensor.window_b", "off")
    hass.states.async_set("climate.thermostat", "auto", {"temperature": 6.0})

    calls = await setup_automation(
        hass, "climate.thermostat", ["binary_sensor.window_a", "binary_sensor.window_b"]
    )

    hass.states.async_set("binary_sensor.window_b", "on")
    await hass.async_block_till_done()

    assert_calls(calls, [])


# ─────────────────────────── Window Close Scenarios ───────────────────────────


async def test_close_last_window_while_paused(hass, enable_custom_integrations):
    """Last window closes while paused at 6°C: restore auto mode."""
    hass.states.async_set("binary_sensor.window", "on")
    hass.states.async_set("climate.thermostat", "auto", {"temperature": 6.0})

    calls = await setup_automation(hass, "climate.thermostat", ["binary_sensor.window"])

    hass.states.async_set("binary_sensor.window", "off")
    await hass.async_block_till_done()

    assert_calls(
        calls,
        [
            {
                "domain": "climate",
                "service": "set_hvac_mode",
                "data": {
                    "entity_id": ["climate.thermostat"],
                    "hvac_mode": "auto",
                },
            }
        ],
    )


async def test_close_last_window_while_off(hass, enable_custom_integrations):
    """Last window closes while heating is off: do nothing."""
    hass.states.async_set("binary_sensor.window", "on")
    hass.states.async_set("climate.thermostat", "off")

    calls = await setup_automation(hass, "climate.thermostat", ["binary_sensor.window"])

    hass.states.async_set("binary_sensor.window", "off")
    await hass.async_block_till_done()

    assert_calls(calls, [])


async def test_close_last_window_after_manual_override(
    hass, enable_custom_integrations
):
    """Last window closes after manual override (temp != 6°C): do nothing."""
    hass.states.async_set("binary_sensor.window", "on")
    hass.states.async_set("climate.thermostat", "auto", {"temperature": 20.0})

    calls = await setup_automation(hass, "climate.thermostat", ["binary_sensor.window"])

    hass.states.async_set("binary_sensor.window", "off")
    await hass.async_block_till_done()

    assert_calls(calls, [])


async def test_close_one_of_two_while_other_open(hass, enable_custom_integrations):
    """One of two windows closes, the other stays open: do nothing."""
    hass.states.async_set("binary_sensor.window_a", "on")
    hass.states.async_set("binary_sensor.window_b", "on")
    hass.states.async_set("climate.thermostat", "auto", {"temperature": 6.0})

    calls = await setup_automation(
        hass, "climate.thermostat", ["binary_sensor.window_a", "binary_sensor.window_b"]
    )

    hass.states.async_set("binary_sensor.window_a", "off")
    await hass.async_block_till_done()

    assert_calls(calls, [])


async def test_close_last_of_two_windows(hass, enable_custom_integrations):
    """Last of two windows closes while paused: restore auto mode."""
    hass.states.async_set("binary_sensor.window_a", "off")
    hass.states.async_set("binary_sensor.window_b", "on")
    hass.states.async_set("climate.thermostat", "auto", {"temperature": 6.0})

    calls = await setup_automation(
        hass, "climate.thermostat", ["binary_sensor.window_a", "binary_sensor.window_b"]
    )

    hass.states.async_set("binary_sensor.window_b", "off")
    await hass.async_block_till_done()

    assert_calls(
        calls,
        [
            {
                "domain": "climate",
                "service": "set_hvac_mode",
                "data": {
                    "entity_id": ["climate.thermostat"],
                    "hvac_mode": "auto",
                },
            }
        ],
    )
