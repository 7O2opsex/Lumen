# Lumen interface design

## Direction

Lumen is a private desktop analysis instrument. Its interface borrows the
theme-tinted light and reflections of 702oxygen while expressing them through
an optical workspace: permanent task navigation, layered work surfaces, and
crisp local-analysis controls.

## Color and surfaces

The default Violet theme pairs a deep blue-charcoal background with lavender
bubbles and a cool mint accent. Clair rouge et blanc uses a crisp, cool-white
surface with red controls and rose reflections. Marron uses dark graphite-brown
surfaces and copper highlights. Obsidienne dorée reserves restrained gold light
for its cosmetic Premium theme.

Panels use quiet borders, softly rounded corners, and a fine illuminated top
edge. Inputs and results remain opaque, high-contrast work surfaces. Primary
buttons use the current theme's accent and a responsive hover light.

## Motion and interaction

Qt paints the ambient optical glow, illuminated surfaces, and Premium reveal
with antialiased vectors at the active display's native scale. Hover light uses
short, interruptible property animations. Background motion stays restrained
and does not delay local analysis actions. Premium's secret cosmetic unlock adds
a centered, borderless 620 × 420 gold reveal for three seconds; Escape can
dismiss it. In the Premium theme, primary task buttons receive a restrained,
animated gold reflection that pauses while their page is hidden.

The first screen keeps Lumen's wordmark, local/private status, four persistent
analysis destinations, and current activity visible. The four destinations are
independent tools, not a numbered sequence. Existing analysis flows, local
data handling, and theme preferences remain intact.
