# Spatial World Engine — Design Spec

## Vision

The vibs need an actual place to live. Not a label that says "coffee shop" — a physical space with coordinates where they walk, linger, and bump into each other through proximity. Like Bluetooth: broadcast presence, discover nearby, connect when in range.

The user never sees this world. Their vib relays experiences back through conversation. The world is the ground truth engine — it generates genuine spatial encounters that produce richer stories than random matching ever could.

This is barebones scaffolding for something much bigger. The architecture matters more than the polish.

## Architecture

**Server-side 3D spatial simulation in Python.** No renderer. The world is mathematically real but never drawn.

- `world/spatial/` subpackage layered beneath the existing `world/` system
- Locations get real coordinates in a ~600m x 500m walkable neighborhood
- Vibs have physical bodies (`VibBody`) with position, velocity, destination
- Tick-based simulation: 1-minute ticks, 1080 ticks per simulated day (6am-midnight)
- Encounters trigger when two vibs come within "Bluetooth range" (~20m)
- Feeds encounters into the existing pipeline: pre-screening → vib conversation → match reporting

## The Town

A single walkable neighborhood (~600m x 500m) with 6 districts:

```
         North (y+)
    ┌──────────┬───────────┐
    │ Downtown │ Arts Qtr  │
    │  (NW)    │   (NE)    │
    ├──────────┼───────────┤
    │  Green Belt (center) │
    │                      │
    ├──────────┼───────────┤
    │ Active   │ Community │
    │  (SW)    │  Hub (SE) │
    └──────────┴───────────┘
         South (y-)

    Quiet Corner (E edge)
```

All 20 existing locations placed with real (x, y, z) coordinates. Z = 0 (ground level) for v1.

## Core Components

### Vec3
Immutable 3D vector with distance, direction, interpolation. Foundation for all spatial math.

### TownLayout
Registry of location coordinates. Spatial queries: nearest location, locations within radius, distance between locations.

### VibBody
Physical presence of a vib: position, destination, speed, state (idle/walking/at_location). Tick method advances position toward destination.

### Proximity Detection
"Bluetooth range" — configurable radius (~20m). When two vibs overlap, encounter opportunity detected. Each pair detected only once per day.

### SpatialSimulation
Main tick loop. Manages all VibBodies. Each tick: move vibs → check arrivals → detect proximity → emit encounters. Driven by routines (personality → daily schedule → destinations).

### SpatialConfig
Tuning knobs: bluetooth_range, walking_speed, tick_duration, linger_time.

## Integration

The spatial simulation produces `Encounter` objects that feed directly into the existing pipeline:

```
Routines (existing) → destinations per time block
    ↓
SpatialSimulation (new) → tick movement, detect proximity
    ↓
Encounter objects (existing model) → pre-screening → vib conversation → match report
```

Backward compatible: existing `run_day()` still works. New `run_day_spatial()` uses the spatial engine.

## What This Is NOT (Yet)

- No renderer / no visuals
- No street graph / pathfinding (straight-line paths with distance factor)
- No weather, no NPCs, no events
- No elevation (z=0 everywhere)
- No persistence of positions (ephemeral per simulation run)

These are all future layers on top of a solid spatial foundation.
