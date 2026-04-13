# Spatial World Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a server-side 3D spatial simulation engine where vibs physically exist, move between locations, and discover each other through proximity (like Bluetooth).

**Architecture:** A `world/spatial/` subpackage layered beneath existing `world/`. Locations get real coordinates in a ~600x500m town. Vibs have physical bodies that move tick-by-tick. Encounters trigger when two vibs come within configurable "Bluetooth range". Feeds into existing pre-screening → vib conversation → match reporting pipeline.

**Tech Stack:** Python 3, dataclasses, existing world/vib/interviewer packages, pytest

---

## File Structure

**Create:**
- `world/spatial/__init__.py` — package exports
- `world/spatial/types.py` — Vec3, SpatialConfig
- `world/spatial/town.py` — TownLayout with location coordinates and spatial queries
- `world/spatial/movement.py` — VibBody position/movement state
- `world/spatial/proximity.py` — Bluetooth-range proximity detection
- `world/spatial/simulation.py` — SpatialSimulation tick loop
- `tests/test_spatial_types.py`
- `tests/test_spatial_town.py`
- `tests/test_spatial_movement.py`
- `tests/test_spatial_proximity.py`
- `tests/test_spatial_simulation.py`
- `tests/test_spatial_integration.py`

**Modify:**
- `world/locations.py` — add coordinates to all 20 locations
- `world/models.py` — add optional spatial fields to Location
- `world/orchestrator.py` — add `run_day_spatial()` method

---

### Task 1: Spatial Primitives (Vec3, SpatialConfig)

**Files:**
- Create: `world/spatial/__init__.py`
- Create: `world/spatial/types.py`
- Create: `tests/test_spatial_types.py`

- [ ] **Step 1: Write failing tests for Vec3**

```python
# tests/test_spatial_types.py
from world.spatial.types import Vec3, SpatialConfig

class TestVec3:
    def test_creation_defaults(self):
        v = Vec3()
        assert v.x == 0.0 and v.y == 0.0 and v.z == 0.0

    def test_addition(self):
        a = Vec3(1, 2, 3)
        b = Vec3(4, 5, 6)
        assert a + b == Vec3(5, 7, 9)

    def test_subtraction(self):
        assert Vec3(5, 7, 9) - Vec3(4, 5, 6) == Vec3(1, 2, 3)

    def test_scalar_multiply(self):
        assert Vec3(1, 2, 3) * 2 == Vec3(2, 4, 6)

    def test_length(self):
        assert Vec3(3, 4, 0).length() == 5.0

    def test_distance_to(self):
        a = Vec3(0, 0, 0)
        b = Vec3(3, 4, 0)
        assert a.distance_to(b) == 5.0

    def test_normalized(self):
        n = Vec3(0, 5, 0).normalized()
        assert abs(n.y - 1.0) < 1e-9
        assert abs(n.length() - 1.0) < 1e-9

    def test_normalized_zero_vector(self):
        assert Vec3(0, 0, 0).normalized() == Vec3(0, 0, 0)

    def test_lerp(self):
        a = Vec3(0, 0, 0)
        b = Vec3(10, 10, 0)
        mid = a.lerp(b, 0.5)
        assert mid == Vec3(5, 5, 0)

    def test_immutable(self):
        v = Vec3(1, 2, 3)
        try:
            v.x = 5
            assert False, "Should be frozen"
        except AttributeError:
            pass

class TestSpatialConfig:
    def test_defaults(self):
        c = SpatialConfig()
        assert c.bluetooth_range == 20.0
        assert c.walking_speed == 1.4
        assert c.tick_duration == 60.0
        assert c.path_factor == 1.3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_types.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement Vec3 and SpatialConfig**

```python
# world/spatial/__init__.py
from world.spatial.types import Vec3, SpatialConfig

# world/spatial/types.py
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def length(self):
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def distance_to(self, other):
        return (self - other).length()

    def normalized(self):
        l = self.length()
        if l == 0:
            return Vec3()
        return Vec3(self.x / l, self.y / l, self.z / l)

    def lerp(self, other, t):
        return self + (other - self) * t

@dataclass
class SpatialConfig:
    bluetooth_range: float = 20.0    # meters — encounter detection radius
    walking_speed: float = 1.4       # m/s (~5 km/h)
    tick_duration: float = 60.0      # seconds per simulation tick
    path_factor: float = 1.3         # straight-line distance multiplier
    linger_min: float = 1800.0       # 30 min minimum at a location
    linger_max: float = 5400.0       # 90 min maximum at a location
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_types.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add world/spatial/__init__.py world/spatial/types.py tests/test_spatial_types.py
git commit -m "feat(spatial): add Vec3 vector math and SpatialConfig"
```

---

### Task 2: Town Layout with Location Coordinates

**Files:**
- Create: `world/spatial/town.py`
- Create: `tests/test_spatial_town.py`
- Modify: `world/locations.py` — add LOCATION_COORDINATES dict

- [ ] **Step 1: Write failing tests for TownLayout**

```python
# tests/test_spatial_town.py
from world.spatial.town import TownLayout
from world.spatial.types import Vec3

class TestTownLayout:
    def test_all_20_locations_have_coordinates(self):
        town = TownLayout()
        assert len(town.locations) >= 20

    def test_get_position(self):
        town = TownLayout()
        pos = town.get_position("coffee_shop")
        assert isinstance(pos, Vec3)

    def test_unknown_location_raises(self):
        town = TownLayout()
        try:
            town.get_position("nonexistent")
            assert False
        except KeyError:
            pass

    def test_distance_between(self):
        town = TownLayout()
        d = town.distance_between("coffee_shop", "corner_bar")
        assert d > 0

    def test_nearest_location(self):
        town = TownLayout()
        pos = town.get_position("coffee_shop")
        nearest = town.nearest_location(pos, exclude={"coffee_shop"})
        assert nearest != "coffee_shop"
        assert isinstance(nearest, str)

    def test_locations_within_radius(self):
        town = TownLayout()
        pos = town.get_position("corner_bar")
        nearby = town.locations_within_radius(pos, 100.0)
        assert "corner_bar" in nearby

    def test_districts_are_spatially_coherent(self):
        """Locations in same district should be closer than cross-district."""
        town = TownLayout()
        # Downtown locations should be near each other
        d_internal = town.distance_between("corner_bar", "comedy_club")
        # Cross-district should be farther
        d_cross = town.distance_between("corner_bar", "yoga_studio")
        assert d_internal < d_cross

    def test_town_bounds(self):
        """Town should fit in ~800x600m."""
        town = TownLayout()
        for loc_id, pos in town.locations.items():
            assert -400 <= pos.x <= 400, f"{loc_id} x out of bounds"
            assert -350 <= pos.y <= 350, f"{loc_id} y out of bounds"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_town.py -v`

- [ ] **Step 3: Add coordinates to locations.py and implement TownLayout**

Add to `world/locations.py`:
```python
from world.spatial.types import Vec3

LOCATION_COORDINATES = {
    # Downtown (NW)
    "corner_bar": Vec3(-250, 220, 0),
    "coffee_shop": Vec3(-180, 250, 0),
    "late_night_diner": Vec3(-220, 180, 0),
    "comedy_club": Vec3(-270, 190, 0),
    # Arts Quarter (NE)
    "art_gallery": Vec3(180, 250, 0),
    "pottery_class": Vec3(230, 210, 0),
    "makerspace": Vec3(250, 240, 0),
    "live_music": Vec3(170, 190, 0),
    # Green Belt (center)
    "city_park": Vec3(-50, 30, 0),
    "botanical_garden": Vec3(60, 50, 0),
    "hiking_trail": Vec3(20, -30, 0),
    # Active Zone (SW)
    "morning_gym": Vec3(-230, -180, 0),
    "running_club": Vec3(-180, -220, 0),
    "yoga_studio": Vec3(-210, -240, 0),
    # Community Hub (SE)
    "dog_park": Vec3(180, -180, 0),
    "farmers_market": Vec3(220, -210, 0),
    "volunteer_day": Vec3(250, -190, 0),
    "cooking_class": Vec3(190, -240, 0),
    # Quiet Corner (E)
    "indie_bookstore": Vec3(280, 80, 0),
    "lecture_hall": Vec3(260, 40, 0),
    "meditation_group": Vec3(300, 60, 0),
    "rooftop_lounge": Vec3(270, 20, 0),
}
```

Create `world/spatial/town.py`:
```python
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, List
from world.spatial.types import Vec3
from world.locations import LOCATION_COORDINATES

@dataclass
class TownLayout:
    locations: Dict[str, Vec3] = field(default_factory=lambda: dict(LOCATION_COORDINATES))

    def get_position(self, location_id: str) -> Vec3:
        if location_id not in self.locations:
            raise KeyError(f"Unknown location: {location_id}")
        return self.locations[location_id]

    def distance_between(self, loc_a: str, loc_b: str) -> float:
        return self.get_position(loc_a).distance_to(self.get_position(loc_b))

    def nearest_location(self, position: Vec3, exclude: Optional[Set[str]] = None) -> str:
        exclude = exclude or set()
        best_id, best_dist = None, float("inf")
        for loc_id, loc_pos in self.locations.items():
            if loc_id in exclude:
                continue
            d = position.distance_to(loc_pos)
            if d < best_dist:
                best_id, best_dist = loc_id, d
        return best_id

    def locations_within_radius(self, position: Vec3, radius: float) -> List[str]:
        return [
            loc_id for loc_id, loc_pos in self.locations.items()
            if position.distance_to(loc_pos) <= radius
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_town.py -v`

- [ ] **Step 5: Verify existing world tests still pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_world.py -v`

- [ ] **Step 6: Commit**

```bash
git add world/locations.py world/spatial/town.py tests/test_spatial_town.py
git commit -m "feat(spatial): add town layout with coordinates for all 20 locations"
```

---

### Task 3: VibBody Movement System

**Files:**
- Create: `world/spatial/movement.py`
- Create: `tests/test_spatial_movement.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_spatial_movement.py
from world.spatial.movement import VibBody, MovementState
from world.spatial.types import Vec3

class TestVibBody:
    def test_creation(self):
        body = VibBody(soul_id=1, position=Vec3(0, 0, 0))
        assert body.state == MovementState.IDLE
        assert body.position == Vec3(0, 0, 0)

    def test_send_to_starts_walking(self):
        body = VibBody(soul_id=1, position=Vec3(0, 0, 0))
        body.send_to(Vec3(100, 0, 0), "coffee_shop")
        assert body.state == MovementState.WALKING
        assert body.destination == Vec3(100, 0, 0)

    def test_tick_moves_toward_destination(self):
        body = VibBody(soul_id=1, position=Vec3(0, 0, 0), speed=10.0)
        body.send_to(Vec3(100, 0, 0), "coffee_shop")
        body.tick(1.0)  # 1 second at 10 m/s = 10m
        assert body.position.x > 0
        assert body.state == MovementState.WALKING

    def test_tick_arrives_at_destination(self):
        body = VibBody(soul_id=1, position=Vec3(0, 0, 0), speed=10.0)
        body.send_to(Vec3(5, 0, 0), "coffee_shop")
        body.tick(1.0)  # 10m step but only 5m away
        assert body.position == Vec3(5, 0, 0)
        assert body.state == MovementState.AT_LOCATION
        assert body.current_location_id == "coffee_shop"

    def test_tick_idle_does_nothing(self):
        body = VibBody(soul_id=1, position=Vec3(10, 20, 0))
        body.tick(1.0)
        assert body.position == Vec3(10, 20, 0)

    def test_arrive_clears_destination(self):
        body = VibBody(soul_id=1, position=Vec3(0, 0, 0), speed=100.0)
        body.send_to(Vec3(5, 0, 0), "park")
        body.tick(1.0)
        assert body.destination is None
        assert body.destination_location_id is None

    def test_linger_countdown(self):
        body = VibBody(soul_id=1, position=Vec3(0, 0, 0))
        body.state = MovementState.AT_LOCATION
        body.linger_remaining = 120.0  # 2 minutes
        body.tick(60.0)
        assert body.linger_remaining == 60.0
        body.tick(60.0)
        assert body.linger_remaining == 0.0
        assert body.state == MovementState.IDLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_movement.py -v`

- [ ] **Step 3: Implement VibBody**

```python
# world/spatial/movement.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from world.spatial.types import Vec3

class MovementState(Enum):
    IDLE = "idle"
    WALKING = "walking"
    AT_LOCATION = "at_location"

@dataclass
class VibBody:
    soul_id: int
    position: Vec3
    speed: float = 1.4
    state: MovementState = MovementState.IDLE
    destination: Optional[Vec3] = None
    destination_location_id: Optional[str] = None
    current_location_id: Optional[str] = None
    linger_remaining: float = 0.0

    def send_to(self, position: Vec3, location_id: str):
        self.destination = position
        self.destination_location_id = location_id
        self.current_location_id = None
        self.state = MovementState.WALKING

    def tick(self, dt: float):
        if self.state == MovementState.WALKING and self.destination is not None:
            direction = self.destination - self.position
            distance = direction.length()
            step = self.speed * dt

            if step >= distance:
                self.position = self.destination
                self.current_location_id = self.destination_location_id
                self.destination = None
                self.destination_location_id = None
                self.state = MovementState.AT_LOCATION
            else:
                self.position = self.position + direction.normalized() * step

        elif self.state == MovementState.AT_LOCATION and self.linger_remaining > 0:
            self.linger_remaining = max(0.0, self.linger_remaining - dt)
            if self.linger_remaining == 0.0:
                self.state = MovementState.IDLE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_movement.py -v`

- [ ] **Step 5: Commit**

```bash
git add world/spatial/movement.py tests/test_spatial_movement.py
git commit -m "feat(spatial): add VibBody movement with tick-based position updates"
```

---

### Task 4: Proximity Detection

**Files:**
- Create: `world/spatial/proximity.py`
- Create: `tests/test_spatial_proximity.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_spatial_proximity.py
from world.spatial.proximity import find_nearby, detect_encounters
from world.spatial.movement import VibBody, MovementState
from world.spatial.types import Vec3

class TestFindNearby:
    def test_finds_vib_within_range(self):
        bodies = {
            1: VibBody(1, Vec3(0, 0, 0)),
            2: VibBody(2, Vec3(10, 0, 0)),
        }
        assert 2 in find_nearby(bodies, 1, radius=20.0)

    def test_ignores_vib_outside_range(self):
        bodies = {
            1: VibBody(1, Vec3(0, 0, 0)),
            2: VibBody(2, Vec3(100, 0, 0)),
        }
        assert 2 not in find_nearby(bodies, 1, radius=20.0)

    def test_excludes_self(self):
        bodies = {1: VibBody(1, Vec3(0, 0, 0))}
        assert 1 not in find_nearby(bodies, 1, radius=20.0)

    def test_multiple_nearby(self):
        bodies = {
            1: VibBody(1, Vec3(0, 0, 0)),
            2: VibBody(2, Vec3(5, 0, 0)),
            3: VibBody(3, Vec3(10, 0, 0)),
            4: VibBody(4, Vec3(500, 0, 0)),
        }
        nearby = find_nearby(bodies, 1, radius=20.0)
        assert 2 in nearby and 3 in nearby and 4 not in nearby

class TestDetectEncounters:
    def test_detects_new_encounter(self):
        bodies = {
            1: VibBody(1, Vec3(0, 0, 0)),
            2: VibBody(2, Vec3(10, 0, 0)),
        }
        encounters = detect_encounters(bodies, radius=20.0, already_detected=set())
        assert len(encounters) == 1
        assert encounters[0] == (1, 2)

    def test_skips_already_detected(self):
        bodies = {
            1: VibBody(1, Vec3(0, 0, 0)),
            2: VibBody(2, Vec3(10, 0, 0)),
        }
        encounters = detect_encounters(bodies, radius=20.0, already_detected={(1, 2)})
        assert len(encounters) == 0

    def test_pair_is_ordered(self):
        bodies = {
            5: VibBody(5, Vec3(0, 0, 0)),
            2: VibBody(2, Vec3(10, 0, 0)),
        }
        encounters = detect_encounters(bodies, radius=20.0, already_detected=set())
        assert encounters[0] == (2, 5)  # lower ID first

    def test_no_encounters_when_far_apart(self):
        bodies = {
            1: VibBody(1, Vec3(0, 0, 0)),
            2: VibBody(2, Vec3(500, 0, 0)),
        }
        encounters = detect_encounters(bodies, radius=20.0, already_detected=set())
        assert len(encounters) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_proximity.py -v`

- [ ] **Step 3: Implement proximity detection**

```python
# world/spatial/proximity.py
from typing import Dict, List, Set, Tuple
from world.spatial.movement import VibBody

def find_nearby(bodies: Dict[int, VibBody], soul_id: int, radius: float) -> List[int]:
    origin = bodies[soul_id].position
    return [
        other_id for other_id, body in bodies.items()
        if other_id != soul_id and origin.distance_to(body.position) <= radius
    ]

def detect_encounters(
    bodies: Dict[int, VibBody],
    radius: float,
    already_detected: Set[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    encounters = []
    soul_ids = list(bodies.keys())
    for i, a_id in enumerate(soul_ids):
        for b_id in soul_ids[i + 1:]:
            pair = (min(a_id, b_id), max(a_id, b_id))
            if pair in already_detected:
                continue
            if bodies[a_id].position.distance_to(bodies[b_id].position) <= radius:
                encounters.append(pair)
    return encounters
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_proximity.py -v`

- [ ] **Step 5: Commit**

```bash
git add world/spatial/proximity.py tests/test_spatial_proximity.py
git commit -m "feat(spatial): add Bluetooth-range proximity detection"
```

---

### Task 5: Spatial Simulation Engine

**Files:**
- Create: `world/spatial/simulation.py`
- Create: `tests/test_spatial_simulation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_spatial_simulation.py
import random
from world.spatial.simulation import SpatialSimulation, TimeMapper
from world.spatial.town import TownLayout
from world.spatial.types import Vec3, SpatialConfig
from world.spatial.movement import MovementState
from world.models import TimeOfDay

class TestTimeMapper:
    def test_early_morning_start(self):
        assert TimeMapper.time_block_start(TimeOfDay.EARLY_MORNING) == 0.0

    def test_morning_start(self):
        assert TimeMapper.time_block_start(TimeOfDay.MORNING) == 7200.0

    def test_time_block_at_seconds(self):
        assert TimeMapper.time_block_at(0) == TimeOfDay.EARLY_MORNING
        assert TimeMapper.time_block_at(7200) == TimeOfDay.MORNING
        assert TimeMapper.time_block_at(50400) == TimeOfDay.NIGHT

class TestSpatialSimulation:
    def _make_sim(self):
        config = SpatialConfig(bluetooth_range=20.0, tick_duration=60.0)
        return SpatialSimulation(TownLayout(), config, seed=42)

    def test_add_vib(self):
        sim = self._make_sim()
        sim.add_vib(1, "coffee_shop")
        assert 1 in sim.bodies
        assert sim.bodies[1].current_location_id == "coffee_shop"

    def test_send_vib_to_location(self):
        sim = self._make_sim()
        sim.add_vib(1, "coffee_shop")
        sim.send_vib_to(1, "corner_bar")
        assert sim.bodies[1].state == MovementState.WALKING

    def test_tick_advances_time(self):
        sim = self._make_sim()
        sim.tick()
        assert sim.time_elapsed == 60.0

    def test_vib_arrives_after_enough_ticks(self):
        config = SpatialConfig(walking_speed=1000.0, tick_duration=60.0)
        sim = SpatialSimulation(TownLayout(), config, seed=42)
        sim.add_vib(1, "coffee_shop")
        sim.send_vib_to(1, "corner_bar")
        for _ in range(100):
            sim.tick()
        assert sim.bodies[1].state == MovementState.AT_LOCATION

    def test_proximity_encounter_detected(self):
        config = SpatialConfig(bluetooth_range=500.0, tick_duration=60.0)
        sim = SpatialSimulation(TownLayout(), config, seed=42)
        # Place two vibs at same location
        sim.add_vib(1, "coffee_shop")
        sim.add_vib(2, "coffee_shop")
        sim.tick()
        assert len(sim.encounters) == 1

    def test_encounter_detected_only_once(self):
        config = SpatialConfig(bluetooth_range=500.0, tick_duration=60.0)
        sim = SpatialSimulation(TownLayout(), config, seed=42)
        sim.add_vib(1, "coffee_shop")
        sim.add_vib(2, "coffee_shop")
        sim.tick()
        sim.tick()
        sim.tick()
        assert len(sim.encounters) == 1

    def test_no_encounter_when_far(self):
        config = SpatialConfig(bluetooth_range=20.0, tick_duration=60.0)
        sim = SpatialSimulation(TownLayout(), config, seed=42)
        sim.add_vib(1, "coffee_shop")  # NW
        sim.add_vib(2, "yoga_studio")  # SW
        sim.tick()
        assert len(sim.encounters) == 0

    def test_run_time_block(self):
        """Run a full time block and verify vibs moved."""
        sim = self._make_sim()
        sim.add_vib(1, "coffee_shop")
        routines = {1: [("corner_bar", TimeOfDay.MORNING)]}
        sim.run_time_block(TimeOfDay.MORNING, routines)
        # After running a full time block, vib should have moved
        assert sim.time_elapsed > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_simulation.py -v`

- [ ] **Step 3: Implement SpatialSimulation**

```python
# world/spatial/simulation.py
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Callable
from world.spatial.types import Vec3, SpatialConfig
from world.spatial.town import TownLayout
from world.spatial.movement import VibBody, MovementState
from world.spatial.proximity import detect_encounters
from world.models import TimeOfDay

class TimeMapper:
    """Maps TimeOfDay blocks to continuous seconds (6am = 0)."""

    BLOCK_STARTS = {
        TimeOfDay.EARLY_MORNING: 0.0,       # 6:00
        TimeOfDay.MORNING: 7200.0,           # 8:00
        TimeOfDay.MIDDAY: 18000.0,           # 11:00
        TimeOfDay.AFTERNOON: 28800.0,        # 14:00
        TimeOfDay.EVENING: 39600.0,          # 17:00
        TimeOfDay.NIGHT: 50400.0,            # 20:00
    }

    BLOCK_ORDER = [
        TimeOfDay.EARLY_MORNING,
        TimeOfDay.MORNING,
        TimeOfDay.MIDDAY,
        TimeOfDay.AFTERNOON,
        TimeOfDay.EVENING,
        TimeOfDay.NIGHT,
    ]

    DAY_END = 64800.0  # midnight (18h from 6am)

    @classmethod
    def time_block_start(cls, block: TimeOfDay) -> float:
        return cls.BLOCK_STARTS[block]

    @classmethod
    def time_block_end(cls, block: TimeOfDay) -> float:
        idx = cls.BLOCK_ORDER.index(block)
        if idx + 1 < len(cls.BLOCK_ORDER):
            return cls.BLOCK_STARTS[cls.BLOCK_ORDER[idx + 1]]
        return cls.DAY_END

    @classmethod
    def time_block_at(cls, seconds: float) -> TimeOfDay:
        for block in reversed(cls.BLOCK_ORDER):
            if seconds >= cls.BLOCK_STARTS[block]:
                return block
        return TimeOfDay.EARLY_MORNING


class SpatialSimulation:
    def __init__(self, town: TownLayout, config: Optional[SpatialConfig] = None, seed: Optional[int] = None):
        self.town = town
        self.config = config or SpatialConfig()
        self.rng = random.Random(seed)
        self.bodies: Dict[int, VibBody] = {}
        self.time_elapsed: float = 0.0
        self.encounters: List[Tuple[int, int]] = []
        self.detected_pairs: Set[Tuple[int, int]] = set()

    def add_vib(self, soul_id: int, location_id: str):
        pos = self.town.get_position(location_id)
        self.bodies[soul_id] = VibBody(
            soul_id=soul_id,
            position=pos,
            speed=self.config.walking_speed,
            state=MovementState.AT_LOCATION,
            current_location_id=location_id,
        )

    def send_vib_to(self, soul_id: int, location_id: str):
        dest = self.town.get_position(location_id)
        body = self.bodies[soul_id]
        # Apply path factor (streets aren't straight lines)
        effective_distance = body.position.distance_to(dest) * self.config.path_factor
        effective_speed = body.speed if effective_distance == 0 else (
            body.speed * (body.position.distance_to(dest) / effective_distance)
            if effective_distance > 0 else body.speed
        )
        body.speed = effective_speed
        body.send_to(dest, location_id)

    def tick(self):
        dt = self.config.tick_duration
        self.time_elapsed += dt

        # Move all vibs
        for body in self.bodies.values():
            body.tick(dt)

        # Detect proximity encounters
        new_encounters = detect_encounters(
            self.bodies, self.config.bluetooth_range, self.detected_pairs
        )
        for pair in new_encounters:
            self.detected_pairs.add(pair)
            self.encounters.append(pair)

    def run_time_block(
        self,
        block: TimeOfDay,
        routines: Dict[int, List[Tuple[str, TimeOfDay]]],
        on_encounter: Optional[Callable] = None,
    ):
        """Run simulation for one time block. routines: {soul_id: [(location_id, time_block), ...]}"""
        block_end = TimeMapper.time_block_end(block)

        # Send vibs to their destinations for this block
        for soul_id, stops in routines.items():
            if soul_id not in self.bodies:
                continue
            for loc_id, stop_time in stops:
                if stop_time == block:
                    self.send_vib_to(soul_id, loc_id)
                    linger = self.rng.uniform(self.config.linger_min, self.config.linger_max)
                    self.bodies[soul_id].linger_remaining = linger
                    break

        # Tick until end of block
        while self.time_elapsed < block_end:
            prev_count = len(self.encounters)
            self.tick()
            if on_encounter and len(self.encounters) > prev_count:
                for enc in self.encounters[prev_count:]:
                    on_encounter(enc)

    def run_full_day(
        self,
        routines: Dict[int, List[Tuple[str, TimeOfDay]]],
        on_encounter: Optional[Callable] = None,
    ):
        """Run simulation for an entire day (all time blocks)."""
        for block in TimeMapper.BLOCK_ORDER:
            self.run_time_block(block, routines, on_encounter)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_simulation.py -v`

- [ ] **Step 5: Commit**

```bash
git add world/spatial/simulation.py tests/test_spatial_simulation.py
git commit -m "feat(spatial): add spatial simulation engine with tick loop and time system"
```

---

### Task 6: Update __init__.py Exports

**Files:**
- Modify: `world/spatial/__init__.py`

- [ ] **Step 1: Update exports**

```python
# world/spatial/__init__.py
from world.spatial.types import Vec3, SpatialConfig
from world.spatial.town import TownLayout
from world.spatial.movement import VibBody, MovementState
from world.spatial.proximity import find_nearby, detect_encounters
from world.spatial.simulation import SpatialSimulation, TimeMapper
```

- [ ] **Step 2: Run all spatial tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_types.py tests/test_spatial_town.py tests/test_spatial_movement.py tests/test_spatial_proximity.py tests/test_spatial_simulation.py -v`

- [ ] **Step 3: Commit**

```bash
git add world/spatial/__init__.py
git commit -m "feat(spatial): export all spatial types from package"
```

---

### Task 7: Integrate with WorldOrchestrator

**Files:**
- Modify: `world/orchestrator.py` — add `run_day_spatial()` method

- [ ] **Step 1: Write failing test**

Add to `tests/test_world.py` (or new file `tests/test_spatial_integration.py`):

```python
# tests/test_spatial_integration.py
import pytest
from world.orchestrator import WorldOrchestrator
from world.spatial.types import SpatialConfig
from tests.test_world import _make_storage_with_souls, _make_mock_llm

class TestSpatialOrchestrator:
    @pytest.mark.asyncio
    async def test_run_day_spatial_completes(self):
        storage = _make_storage_with_souls()
        llm = _make_mock_llm()
        orch = WorldOrchestrator(storage, llm, seed=42)
        activities = []
        matches = []
        reports = await orch.run_day_spatial(
            on_activity=lambda a: activities.append(a),
            on_encounter=lambda e: None,
            on_match=lambda m: matches.append(m),
            spatial_config=SpatialConfig(bluetooth_range=50.0),
        )
        assert isinstance(reports, list)
        assert len(activities) > 0

    @pytest.mark.asyncio
    async def test_run_day_spatial_detects_encounters(self):
        storage = _make_storage_with_souls()
        llm = _make_mock_llm()
        orch = WorldOrchestrator(storage, llm, seed=42)
        encounters = []
        await orch.run_day_spatial(
            on_activity=lambda a: None,
            on_encounter=lambda e: encounters.append(e),
            on_match=lambda m: None,
            spatial_config=SpatialConfig(bluetooth_range=500.0),
        )
        # With large bluetooth range, the two souls should encounter each other
        assert len(encounters) > 0

    @pytest.mark.asyncio
    async def test_original_run_day_still_works(self):
        """Backward compatibility: existing run_day unaffected."""
        storage = _make_storage_with_souls()
        llm = _make_mock_llm()
        orch = WorldOrchestrator(storage, llm, seed=42)
        reports = await orch.run_day(
            on_activity=lambda a: None,
            on_encounter=lambda e: None,
            on_match=lambda m: None,
        )
        assert isinstance(reports, list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_spatial_integration.py -v`

- [ ] **Step 3: Add run_day_spatial() to WorldOrchestrator**

Add to `world/orchestrator.py`:

```python
from world.spatial.simulation import SpatialSimulation, TimeMapper
from world.spatial.town import TownLayout
from world.spatial.types import SpatialConfig

# In WorldOrchestrator class:

async def run_day_spatial(
    self,
    soul_ids=None,
    on_activity=None,
    on_encounter=None,
    on_match=None,
    spatial_config=None,
):
    """Run a full day simulation using spatial proximity detection."""
    spatial_config = spatial_config or SpatialConfig()
    souls = self._gather_souls(soul_ids)
    if len(souls) < 2:
        return []

    self.state.cycle = WorldCycle.GENERATING_ROUTINES
    self.state.active_soul_ids = set(souls.keys())

    # Generate routines for all souls
    for soul_id, data in souls.items():
        r = generate_routine(soul_id, data["name"], data["cartographer"], self._rng.randint(0, 999999))
        self.state.routines[soul_id] = r

    # Build spatial simulation
    town = TownLayout()
    sim = SpatialSimulation(town, spatial_config, seed=self._rng.randint(0, 999999))

    # Convert routines to spatial format: {soul_id: [(location_id, time_block), ...]}
    spatial_routines = {}
    for soul_id, routine in self.state.routines.items():
        first_stop = routine.stops[0] if routine.stops else None
        start_loc = first_stop.location_id if first_stop else "coffee_shop"
        sim.add_vib(soul_id, start_loc)
        spatial_routines[soul_id] = [
            (stop.location_id, stop.time_of_day) for stop in routine.stops
        ]

    self.state.cycle = WorldCycle.SIMULATING
    reports = []

    # Emit initial activities
    for soul_id, routine in self.state.routines.items():
        if on_activity and routine.stops:
            stop = routine.stops[0]
            on_activity({
                "soul_id": soul_id,
                "soul_name": souls[soul_id]["name"],
                "location": stop.location_id,
                "activity": stop.activity,
                "time": stop.time_of_day.value,
            })

    # Run spatial simulation for full day
    def handle_spatial_encounter(pair):
        a_id, b_id = pair
        if a_id not in souls or b_id not in souls:
            return

        # Determine location context
        body_a = sim.bodies[a_id]
        body_b = sim.bodies[b_id]
        location_id = body_a.current_location_id or body_b.current_location_id or "city_park"

        if on_encounter:
            on_encounter({
                "soul_a": souls[a_id]["name"],
                "soul_b": souls[b_id]["name"],
                "location": location_id,
            })

        self.state.encounters_today.append((a_id, b_id, location_id))

    sim.run_full_day(spatial_routines, on_encounter=handle_spatial_encounter)

    # Process encounters through existing pipeline
    self.state.cycle = WorldCycle.EVALUATING
    for a_id, b_id, location_id in self.state.encounters_today:
        if a_id not in souls or b_id not in souls:
            continue

        cart_a = souls[a_id]["cartographer"]
        cart_b = souls[b_id]["cartographer"]
        score, should_proceed = prescreen_compatibility(cart_a, cart_b)

        if not should_proceed:
            self._mark_evaluated(a_id, b_id)
            continue

        # Build encounter for existing pipeline
        from world.models import Encounter, EncounterOutcome
        enc = Encounter(
            soul_a_id=a_id,
            soul_b_id=b_id,
            location_id=location_id,
            time_of_day=TimeMapper.time_block_at(sim.time_elapsed),
            outcome=EncounterOutcome.IN_PROGRESS,
        )

        result = await self._run_vib_conversation(souls[a_id], souls[b_id], enc)
        self.state.total_encounters += 1

        if result and result.compatibility_score >= MATCH_REPORT_THRESHOLD:
            enc.outcome = EncounterOutcome.MATCH_FOUND
            enc.compatibility_score = result.compatibility_score
            report = build_match_report(
                a_id, souls[a_id]["name"], souls[b_id]["name"],
                cart_b, result, enc,
            )
            reports.append(report)
            self.state.total_matches += 1
            if on_match:
                on_match(report)
        else:
            enc.outcome = EncounterOutcome.NO_SPARK

        self._mark_evaluated(a_id, b_id)

    self.state.cycle = WorldCycle.IDLE
    self.state.current_day += 1
    return reports
```

- [ ] **Step 4: Run all tests**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add world/orchestrator.py tests/test_spatial_integration.py
git commit -m "feat(spatial): integrate spatial simulation with WorldOrchestrator"
```

---

### Task 8: Verify Everything Works End-to-End

- [ ] **Step 1: Run full test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/ -v`

- [ ] **Step 2: Verify no regressions in existing tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_world.py tests/test_orchestrator.py tests/test_storage.py -v`

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "feat(spatial): complete spatial world engine — vibs move and discover through proximity"
```
