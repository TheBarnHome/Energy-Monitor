# Energy Monitor

Custom Home Assistant integration for forecasting home battery state of charge
until the next solar takeover window and recommending when to run flexible loads.

This first version is recommendation-only. It does not directly control EV
chargers, spa heating, or appliances.

## Features

- Battery SoC forecast at 30 minute resolution.
- `forecast` time-series attribute suitable for ApexCharts-style dashboards.
- Baseload profile learned from historical home consumption.
- Optional grid export support. If export is unavailable or disabled, surplus
  solar that cannot be stored is treated as clipped.
- Configurable flexible loads via integration options.
- Recommendation calendar for viable load windows.
- `energy_monitor.recalculate` service to force a refresh.

## Home Assistant entities

- `sensor.energy_monitor_battery_forecast`
- `sensor.energy_monitor_min_soc_before_solar`
- `sensor.energy_monitor_solar_takeover_time`
- `sensor.energy_monitor_recommendation_summary`
- `calendar.energy_monitor_recommendations`

The battery forecast sensor exposes:

```json
{
  "forecast": [
    {
      "datetime": "2026-05-28T22:30:00+02:00",
      "soc_percent": 62.1,
      "battery_energy_kwh": 6.21,
      "solar_forecast_kwh": 0.0,
      "baseload_kwh": 0.24
    }
  ],
  "actual_entity": "sensor.battery_soc",
  "generated_at": "2026-05-28T22:29:10+02:00",
  "resolution_minutes": 30,
  "horizon_end": "2026-05-29T18:00:00+02:00"
}
```

## Solar forecast input

The configured solar forecast entity should expose a list attribute named one of
`forecast`, `forecasts`, or `data`. Each item should include a datetime-like key
(`datetime`, `start`, or `period_start`) and an energy-like value
(`energy_kwh`, `solar_forecast_kwh`, `pv_estimate`, `estimate`, or `value`).

## Flexible loads

Loads are configured from the integration options as JSON:

```json
[
  {
    "id": "ev",
    "name": "EV",
    "priority": 1,
    "duration_minutes": 180,
    "energy_kwh": 7.2,
    "earliest_start": "22:00",
    "latest_end": "08:00"
  },
  {
    "id": "spa",
    "name": "Spa",
    "priority": 2,
    "duration_minutes": 90,
    "power_kw": 2.0
  }
]
```

For EVs, calculate `energy_kwh` from the car battery capacity and the difference
between current SoC and target SoC. A future version can read those entities
directly.

## Development

Run the pure Python forecast tests:

```bash
python3 -m unittest
```
