# Plan: Home Assistant Blueprint – Fenster-Heizung (Window-Heating) Automation

## Goal

Create a Home Assistant Blueprint that pauses room heating when any window opens and resumes the schedule once all windows close. **Zero helpers, zero snapshots, zero state storage** — the thermostat itself is the memory.

## Design Philosophy: The Thermostat is the State Machine

| Thermostat State                    | Meaning                                                 | Blueprint Behaviour                                                         |
| ----------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------------- |
| `auto`                              | Following heating schedule. May be paused by blueprint. | Window open → set temp to 6 °C. Window close + still 6 °C → restore `auto`. |
| `off`                               | Heating is off (summer or user choice).                 | **Never touch.**                                                            |
| Any mode with `temperature == 6 °C` | **Paused by blueprint** (marker temperature).           | Window close + still 6 °C → restore `auto`.                                 |
| Any mode with `temperature != 6 °C` | User is controlling manually.                           | **Never touch.**                                                            |

This design is:

- **Restart-safe**: Home Assistant reboots don't lose any state.
- **Override-safe**: If the user changes the temperature while a window is open, the blueprint sees "not 6 °C anymore" and stays hands-off.
- **Summer-safe**: If the thermostat is `off`, the blueprint does nothing.

## Inputs

| Input            | Type     | Selector                                                                           | Default | Purpose                                                                                                            |
| ---------------- | -------- | ---------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------ |
| `climate_target` | `entity` | `domain: climate`, `multiple: false`                                               | —       | Thermostat to control                                                                                              |
| `window_sensors` | `list`   | `domain: binary_sensor`, `device_class: [window, door, opening]`, `multiple: true` | —       | All door/window sensors in the room                                                                                |
| `trigger_delay`  | `number` | `min: 0`, `max: 600`, `unit_of_measurement: seconds`, `mode: slider`, `step: 1`    | `0`     | How long the sensors must stay in the new state before the automation reacts (applies to both opening and closing) |

**Hardcoded constants**

| Constant            | Value | Rationale                                                                           |
| ------------------- | ----- | ----------------------------------------------------------------------------------- |
| `PAUSE_TEMPERATURE` | `6.0` | Marker temperature while paused. Must be a value the user would never manually set. |

## Core Logic

`mode: restart`

### Trigger

- Any `window_sensors` state → `on` (with `for: !input trigger_delay`)
- Any `window_sensors` state → `off` (with `for: !input trigger_delay`)

### Variables

```yaml
variables:
  climate: !input climate_target
  windows: !input window_sensors
  any_open: "{{ windows | select('is_state', 'on') | list | count > 0 }}"
  is_paused: "{{ state_attr(climate, 'temperature') | float(0) == 6.0 }}"
  mode: "{{ states(climate) }}"
```

### Action: Any Window Opens (`any_open == true`)

1. If `mode == 'off'` → **stop** (summer / user off). ✅
2. If `mode == 'auto'` and `not is_paused`:
   - `climate.set_temperature` → `6.0`
3. If already `is_paused` → do nothing (already paused).

### Action: All Windows Closed (`any_open == false`)

1. If `is_paused` is **true** (temperature still == `6.0`):
   - `climate.set_hvac_mode` → `auto`
2. If `is_paused` is **false** → **stop** (user overrode while window was open, or thermostat was off). ✅

> **Note**: `mode: restart` automatically aborts a pending close sequence if another window opens while heating is resuming. When the _last_ window closes, a new run starts fresh.

## Edge-Case Matrix

| Scenario                                              | Window Opens Action         | Window Closes Action         |
| ----------------------------------------------------- | --------------------------- | ---------------------------- |
| Thermostat in `auto`                                  | → temp 6 °C                 | → `auto` if still 6 °C       |
| Thermostat in `off`                                   | → no action                 | → no action                  |
| User changes temp from 6 °C → 20 °C while window open | —                           | → no action (was overridden) |
| HA restarts while window open                         | 6 °C still set              | → `auto` if still 6 °C       |
| Second window opens while first already open          | → already paused, no action | → waits for _last_ window    |
| Window briefly open/closed (< `trigger_delay`)        | → no action                 | → no action                  |

## File Structure

```
fenster-heizung/
├── blueprints/automation/fenster_heizung.yaml
├── README.md
└── PLAN.md
```

## Definition of Done

The implementation is complete when **all** of the following are true:

### Deliverables

1. `blueprints/automation/fenster_heizung.yaml` exists and is valid YAML.
2. `README.md` exists with installation instructions and an "Open in Home Assistant" import badge.
3. No other files were created or modified unnecessarily.

### Blueprint Acceptance Criteria (checklist to verify against this plan)

- [ ] `blueprint:` section has `name`, `description`, `domain: automation`, and `source_url`.
- [ ] Input `climate_target` uses `entity` selector with `domain: climate` and `multiple: false`.
- [ ] Input `window_sensors` uses `entity` selector with `domain: binary_sensor`, `device_class: [window, door, opening]`, and `multiple: true`.
- [ ] Input `trigger_delay` uses `number` selector with `min: 0`, `max: 600`, `unit_of_measurement: seconds`, default `0`.
- [ ] The automation runs in `mode: restart`.
- [ ] Triggers fire on `state` change of any `window_sensors` to `on` **and** to `off`, each with `for: !input trigger_delay`.
- [ ] A `variables` block defines `any_open` checking if any sensor is `on`.
- [ ] A `variables` block defines `is_paused` comparing `state_attr(climate_target, 'temperature')` to **exactly `6.0`** (hardcoded, not an input).
- [ ] When a window opens and `states(climate_target) == 'off'` → **the blueprint does nothing**.
- [ ] When a window opens, thermostat is `auto`, and `not is_paused` → the blueprint calls `climate.set_temperature` to **exactly `6.0`** (no hvac_mode change).
- [ ] When the last window closes and `is_paused` is **true** → the blueprint calls `climate.set_hvac_mode` with value `auto`.
- [ ] When the last window closes and `is_paused` is **false** → **the blueprint does nothing**.
- [ ] There are **no notification actions**, no `scene.create`, no helpers, no `input_text`/`input_number` references.
- [ ] The README explains how to import the blueprint via URL and how to create an automation from it.

## Verification Questions (ask me after implementation)

1. _"Show me the exact YAML for the blueprint file."_ — I should produce the full `fenster_heizung.yaml`.
2. _"Walk me through the open-window logic line-by-line."_ — I should explain the trigger, variables, and action branches exactly as specified above.
3. _"What happens in summer when the thermostat is off?"_ — I should explain that the `off` state is an early exit with no service calls.
4. _"What happens if I manually change the temperature from 6 °C to 22 °C while the window is still open?"_ — I should explain that `is_paused` becomes false, so closing the window does **not** flip back to `auto`.
5. _"What happens if Home Assistant restarts while a window is open?"_ — I should explain that the thermostat still shows 6 °C, so the close logic still works because the state is stored in the thermostat itself.
6. _"Show me the README and the blueprint import badge."_ — I should produce the full `README.md` with a working `source_url` and my.home-assistant.io badge.
7. _"Is `6.0` hardcoded or configurable?"_ — The answer must be "hardcoded."
8. _"Are there separate delays for open and close?"_ — The answer must be "no, there is a single `trigger_delay`."

## Next Steps

- [ ] Approve the plan
- [ ] Draft YAML blueprint
- [ ] Write README with Home Assistant blueprint import instructions
