# Full lighting replacement: census and plan (2026-11-05)

User request: replace all of the game's light sources with new dynamic lighting and shadows (full
replacement, chosen over upgrading the existing shadows or adding screen-space light). Everything
opt-in; the original lighting stays the default.

## Census (VERIFIED from the race's shaders)

Sources:
- the 133 fragment and 82 vertex programs of a race, decompiled HLSL taken from the SPIR-V cache
  (`census/`, private);
- `tools/census.py`;
- Kk60's draw log of the main scene pass (`passes/draws.txt`, private).

**Fragment programs:**
- 81 are sun-lit and shadowed: `dot(N, +-fp_constants[k])` plus `_rsx_shadow13`;
- 2 more are shadowed without the dot;
- 13 are lit without a shadow;
- 37 are unlit (sky, particles, UI, post effects).

**The sun's shadow map:** unit 13 in every program. It is one 1024x2048 D24 target (0x0B030000)
sampled with a depth compare, 4-tap PCF.

**The sun direction:** a fragment constant. The game's shader compiler places it in a different slot in
nearly every program (40 different slots), so it has to be found at runtime by its value: the same
unit vector in every lit program.

**Material units (the main scene pass, every draw):**

| Unit | Contents |
|---|---|
| t0 | albedo (512x512 DXT, read through sRGB decode) |
| t1-t3 | 1024x1024 maps (normal, detail, specular; per program) |
| t4 | 1x1 default |
| t10 | 4x1 lookup |
| t11 | 256x1 lookup (sky/ambient ramp: read with a height-like coordinate) |
| t12 | 32x512 lookup |
| t13 | shadow map |

**Typical program** (`e39db44ac569d19f`):
- colour = albedo x vertex colour x (ambient(t11) + sun_colour(c10, c11) x shadow x N.L(c9));
- normal map in tangent space with the frame in tc2/tc3;
- fog towards c12 by tc7.y; glow target = colour x c13.

**Render targets:** the scene pass writes 4 colour targets (cmask 01010101; 54 programs write 4).
Their contents are not identified yet: Kk60's pass capture tripped the game's flip watchdog
(`GcKernel::Present() Timeout`) on the first synchronous pass readback.

## Plan

**Milestone 1 (first visible result): a new dynamic sun with new shadows, through the game's own shading.**
1. **Sun direction by value:** in the engine, find the sun-direction constant of each lit program by
   its value (the vector shared by all lit programs in a frame), and replace it with the new sun
   (time of day, or set).
2. **Shadows:** the game renders its shadow map with a light view-projection in the shadow pass's
   vertex constants, and the scene's vertex programs carry the same matrix (biased) to make the shadow
   coordinates (tc6). Find both by value and replace them with matrices for the new sun.
   - The game's own shadow pass then renders the new shadow map;
   - its resolution can rise as well (4096x8192 under a scale).
3. **Ambient:** replace the t11/t12 lookup textures (sky/ambient ramps) with ones made for the new sun.

**Milestone 2: replace the shading itself.**
- Rewrite the 81 sun-lit programs' light term with our own lighting function (PBR: albedo, normal,
  roughness from the texture-pack maps).
- Add extra dynamic lights (point and spot) with screen-space or shadow-map shadows.

**Milestone 3:** tune, test across tracks, weather and times of day, and measure the cost.

**Risks:**
- value matching can pick a wrong constant (guard: only exact matches across many programs);
- shader slots differ per program;
- the 4 MRT outputs (glow, motion and others) must stay consistent;
- a pass capture needs an asynchronous path that does not stall frames.
