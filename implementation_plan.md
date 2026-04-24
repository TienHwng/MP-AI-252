# Digital Twin House Simulation — HERA Dashboard

## Goal

Build an interactive **Digital Twin** visualization of the house inside the HERA dashboard's "House Simulation" tab (replacing the current placeholder `Devices` page). The twin will:

- Reflect **real-time device states** from the hardware board (3 LEDs, 1 mini fan, 1 relay)
- Allow **interactive control** — click a device on the floor plan to toggle it via the existing REST API
- Display **live sensor readings** (temperature, humidity, light, air quality, gas) overlaid on the floor plan
- Support **zoom, pan, and click** interactions
- Run smoothly on **low-bandwidth** connections (no heavy 3D libraries, no large assets)

---

## Architecture Decision: SVG + CSS (No 3D Library)

> [!IMPORTANT]
> Instead of Three.js or WebGL, the simulation uses **pure SVG rendered through React** with CSS animations. This keeps the bundle tiny (~0 KB extra dependencies), works offline after first load, and renders crisply at any zoom level.

| Approach | Bundle Size | GPU Required | Low Wi-Fi | Zoom Quality |
|----------|-------------|-------------|-----------|--------------|
| Three.js 3D | ~600 KB | Yes | ❌ Poor | Good |
| Canvas 2D | ~0 KB | No | ✅ Great | ⚠️ Pixelated |
| **SVG + CSS** | **~0 KB** | **No** | **✅ Great** | **✅ Crisp** |

---

## Proposed Changes

### Navigation & Routing

#### [MODIFY] [Sidebar.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/components/layout/Sidebar.jsx)
- Replace `devices` menu item with `simulation` (label: "House Simulation")
- Use a `House` icon from lucide-react instead of `Lightbulb`

#### [MODIFY] [App.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/App.jsx)
- Add `'simulation'` to `VALID_PAGES`
- Import and render `HouseSimulation` page for the `simulation` case
- Remove the placeholder `Devices` component

---

### Digital Twin Page

#### [NEW] [HouseSimulation.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/pages/HouseSimulation.jsx)
The main page component that:
- Polls sensor data every 5 seconds (reuses `fetchLatestSensorData`)
- Manages device toggle handlers (reuses `toggleLedLight`, `toggleNeoLight`, adds new API calls for fan/relay/ws2812)
- Passes state down to child components
- Layout: Full-width floor plan viewer on the left (~70%), device control panel on the right (~30%)

---

### Floor Plan SVG Components

#### [NEW] [FloorPlanViewer.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/components/simulation/FloorPlanViewer.jsx)
The interactive wrapper providing:
- **Zoom**: Mouse wheel / pinch to zoom (0.5x → 3x range)
- **Pan**: Click-and-drag to move around the floor plan
- **Minimap**: Small overview in the bottom-right showing viewport position
- **Zoom controls**: +/- buttons and zoom percentage indicator
- Uses CSS `transform: scale() translate()` for smooth zooming

#### [NEW] [FloorPlanSVG.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/components/simulation/FloorPlanSVG.jsx)
The actual SVG house layout inspired by the provided floor plan images:

**Rooms** (matching the reference images):
| Room | Color | Dimensions (SVG units) |
|------|-------|----------------------|
| Garage | `#d4b8e8` (purple tint) | 180 × 228 |
| Living Room | `#f5e6c8` (warm beige) | 250 × 228 |
| Kitchen | `#f5e6c8` (warm beige) | 160 × 120 |
| Bedroom | `#f0c4c4` (soft pink) | 160 × 120 |
| Bathroom | `#c4ddf0` (soft blue) | 80 × 120 |
| Front Porch | `#c4e8d0` (soft green) | 94 × 68 |

**Device placements** on the floor plan:
| Device | Room | Visual Effect When ON |
|--------|------|----------------------|
| LED Light (`led_state`) | Living Room ceiling | Yellow radial glow + pulsing animation |
| Neo LED (`neo_led_state`) | Bedroom ceiling | RGB rainbow gradient glow |
| WS2812 LED Strip (`ws2812_status`) | Kitchen under-cabinet | Colored light strip glow |
| Mini Fan (`mini_fan_status`) | Living Room | Spinning fan blade animation |
| Relay (`relay_status`) | Garage | Power indicator + connected device highlight |

**Furniture silhouettes** (simple SVG shapes):
- Garage: Car silhouette (rect + rounded front)
- Living Room: Sofa (rect), coffee table (rect), TV (line)
- Kitchen: Counter (rect), stove (rect with circles)
- Bedroom: Bed (rect with headboard), nightstand
- Bathroom: Bathtub (rounded rect), toilet (small shape)

#### [NEW] [DeviceMarker.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/components/simulation/DeviceMarker.jsx)
Individual interactive device markers placed on the floor plan:
- Clickable — triggers API toggle
- Shows tooltip on hover with device name + state
- Animated glow/pulse when device is ON
- Dimmed/grey when OFF
- Ripple effect on click

#### [NEW] [SensorOverlay.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/components/simulation/SensorOverlay.jsx)
Floating badges showing live sensor data on the floor plan:
- Temperature badge (with thermometer icon)
- Humidity badge (with droplet icon)
- Light level badge (with sun icon)
- Gas detection warning badge (only visible when gas detected)
- Positioned near relevant rooms

---

### Device Control Side Panel

#### [NEW] [SimulationPanel.jsx](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/components/simulation/SimulationPanel.jsx)
Right-side panel showing:
- **Connection status** — WiFi / MQTT indicators with signal strength
- **Device cards** — Each device with toggle switch, status, and last-updated timestamp
- **Sensor readings** — Compact display of all sensor values
- **Legend** — Color coding explanation for the floor plan

---

### API Extensions

#### [MODIFY] [api.js](file:///d:/HCMUT/252/thesis/MP-AI-252/FE/hera-dashboard/src/services/api.js)
Add new control functions:
- `toggleFan(enabled)` → `POST /api/control/fan`
- `toggleRelay(enabled)` → `POST /api/control/relay`  
- `toggleWS2812(enabled)` → `POST /api/control/ws2812`

> [!NOTE]
> If the backend doesn't support these endpoints yet, the UI will still show the device states from the polling data. The toggle buttons will show a "not available" toast until the backend is ready.

---

## Visual Design

### Floor Plan Style
- **Walls**: 4px dark grey (`#333`) strokes with subtle shadow
- **Doors**: Arc-shaped door swing indicators (like architectural drawings)
- **Room fills**: Soft pastel colors with subtle texture pattern
- **Device markers**: Circular icons with glow effects
- **When device ON**: Radial gradient "light pool" emanating from the device location
- **Overall**: Clean, modern architectural style matching the reference images

### Animations (CSS-only, GPU-accelerated)
- `@keyframes pulse-glow` — Soft breathing glow for active lights
- `@keyframes spin-fan` — Rotation for fan blades
- `@keyframes ripple` — Click feedback on device markers
- `@keyframes rainbow` — RGB shift for Neo LED
- All use `transform` and `opacity` only (no layout thrashing)

### Color Palette (aligned with existing Tailwind config)
- Primary actions: `#8B9A84` (existing primary green)
- Active device: `#D6AFA6` (existing cardDark pink)
- Background: `#F7F5F0` (existing background)
- Danger/Gas: `#E85D5D`
- Device ON glow: `#FFD93D` (warm yellow)

---

## File Structure

```
src/
├── pages/
│   └── HouseSimulation.jsx          ← Main page
├── components/
│   └── simulation/
│       ├── FloorPlanViewer.jsx       ← Zoom/pan wrapper
│       ├── FloorPlanSVG.jsx          ← SVG house layout
│       ├── DeviceMarker.jsx          ← Interactive device icons
│       ├── SensorOverlay.jsx         ← Floating sensor badges
│       └── SimulationPanel.jsx       ← Side control panel
```

---

## Verification Plan

### Automated
- Run `npm run build` to ensure no compilation errors
- Run `npm run dev` and use browser tool to visually verify: 
  - Floor plan renders correctly
  - Zoom/pan interactions work
  - Device markers are clickable
  - Animations play smoothly

### Manual (User)
- Connect to real hardware board to verify device state synchronization
- Test on low-bandwidth connection to verify lightweight performance
- Verify the simulation tab appears correctly in the sidebar navigation
