# Lumen interface design

## Direction

Lumen is a private desktop analysis instrument. Its interface borrows the slow,
floating oxygen bubbles and theme-tinted highlights of 702oxygen, while its own
optical wordmark and focused analysis workspace keep the product distinct.

## Color and surfaces

The default Violet theme pairs a deep blue-charcoal background with lavender
bubbles and a cool mint accent. Clair rouge et blanc uses a crisp, cool-white
surface with red controls and rose reflections. Marron uses dark graphite-brown
surfaces and copper highlights. Obsidienne dorée reserves restrained gold light
for its cosmetic Premium theme.

Panels use quiet, thin borders and softly rounded corners. Inputs and results
remain opaque, high-contrast work surfaces. Primary buttons use the current
theme's accent and a slightly darker hover state.

## Motion and interaction

Ambient bubbles rise slowly behind the workspace and carry a small curved
reflection. Their positions are interpolated against elapsed time and scaled
with the active monitor; the Windows process enables per-monitor DPI awareness
before the Tk window is created. Motion stays decorative and does not delay
analysis actions.
Premium's secret cosmetic unlock adds a single, full-screen, three-second gold
reveal with a smoother vector sweep; Escape can dismiss the sequence. Text keeps
the system font's native high-DPI rendering instead of being enlarged from a
low-resolution bitmap.

The first screen keeps the Lumen wordmark, the local/private status, the four
analysis task tabs, and the current local status visible. Existing analysis
flows, local data handling, and theme preferences remain unchanged.
