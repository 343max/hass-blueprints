async def test_fenster_heizung_automation(hass, enable_custom_integrations):
    # Set up mock entities
    hass.states.async_set("binary_sensor.motion", "on")
    hass.states.async_set("light.kitchen", "off")

    # Load your blueprint-based automation
    await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "my_blueprint.yaml",
                    "input": {
                        "motion_sensor": "binary_sensor.motion",
                        "target_light": "light.kitchen",
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()

    # Fire a state change to trigger the automation
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()

    assert hass.states.get("light.kitchen").state == "off"
