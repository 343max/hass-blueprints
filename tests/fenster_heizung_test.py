import os
import shutil

import homeassistant.core as ha
from homeassistant.setup import async_setup_component


async def test_fenster_heizung_automation(hass, enable_custom_integrations):
    # Set up blueprints directory in the HA config
    blueprints_dir = hass.config.path("../blueprints/automation")

    # Set up mock entities
    hass.states.async_set("binary_sensor.window_bedroom", "off")
    hass.states.async_set("climate.thermostat_bedroom", "auto", {"temperature": 21.0})

    # Capture service calls
    service_calls = []

    @ha.callback
    def capture_call(call):
        service_calls.append(call)

    hass.services.async_register("climate", "set_temperature", capture_call)
    hass.services.async_register("climate", "set_hvac_mode", capture_call)

    # Load the blueprint-based automation
    await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "fenster_heizung.yaml",
                    "input": {
                        "climate_target": "climate.thermostat_bedroom",
                        "window_sensors": ["binary_sensor.window_bedroom"],
                        "trigger_delay": 0,
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()

    # Fire a state change: window opens
    hass.states.async_set("binary_sensor.window_bedroom", "on")
    await hass.async_block_till_done()

    # The automation should call climate.set_temperature with 6.0
    assert len(service_calls) == 1
    assert [
        {"domain": c.domain, "service": c.service, "data": dict(c.data)}
        for c in service_calls
    ] == [
        {
            "domain": "climate",
            "service": "set_temperature",
            "data": {
                "entity_id": ["climate.thermostat_bedroom"],
                "temperature": 6.0,
            },
        }
    ]
