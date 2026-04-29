# Plan: Home Assistant Blueprint – Fenster-Heizung (Window-Heating) Automation

## Goal
Create a Home Assistant Blueprint that pauses room heating when any window opens and resumes the schedule once all windows close. **Zero helpers, zero snapshots, zero state storage** — the thermostat itself is the memory.

## Design Philosophy: The Thermostat is the State Machine

| Thermostat State | Meaning | Blueprint Behaviour |
|-----------------|---------|-------------------|
| `auto` | Following heating schedule. May be paused by blueprint. | Window open → set temp to 6 °C. Window close + still 6 °C → restore `auto`. |
| `off` | Heating is off (summer or user choice). | **Never touch.** |
| Any mode with `temperature == 6 °C` | **Paused by blueprint** (marker temperature). | Window close + still 6 °C → restore `auto`. |
| Any mode with `temperature != 6 °C` | User is controlling manually. | **Never touch.** |

This design is:
- **Restart-safe**: Home Assistant reboots don't lose any state.
- **Override-safe**: If the user changes the temperature while a window is open, the blueprint sees "not 6 °C anymore" and stays hands-off.
- **Summer-safe**: If the thermostat is `off`, the blueprint does nothing.

## Inputs

| Input | Type | Selector | Default | Purpose |
|-------|------|----------|---------|---------|
| `climate_target` | `entity` | `domain: climate`, `multiple: false` | — | Thermostat to control |
| `window_sensors` | `list` | `domain: binary_sensor`, `device_class: [window, door, opening]`, `multiple: true` | — | All door/window sensors in the room |
| `trigger_delay` | `number` | `min: 0`, `max: 600`, `unit_of_measurement: seconds`, `mode: slider`, `step: 1` | `0` | How long the sensors must stay in the new state before the automation reacts (applies to both opening and closing) |

**Hardcoded constants**

| Constant | Value | Rationale |
|----------|-------|-----------|
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

> **Note**: `mode: restart` automatically aborts a pending close sequence if another window opens while heating is resuming. When the *last* window closes, a new run starts fresh.

## Edge-Case Matrix

| Scenario | Window Opens Action | Window Closes Action |
|----------|--------------------|---------------------|
| Thermostat in `auto` | → temp 6 °C | → `auto` if still 6 °C |
| Thermostat in `off` | → no action | → no action |
| User changes temp from 6 °C → 20 °C while window open | — | → no action (was overridden) |
| HA restarts while window open | 6 °C still set | → `auto` if still 6 °C |
| Second window opens while first already open | → already paused, no action | → waits for *last* window |
| Window briefly open/closed (< `trigger_delay`) | → no action | → no action |

## File Structure
```
fenster-heizung/
├── blueprints/automation/fenster_heizung.yaml
├── README.md
└── PLAN.md
```

## Next Steps
- [ ] Approve the plan
- [ ] Draft YAML blueprint
- [ ] Write README with Home Assistant blueprint import instructions
