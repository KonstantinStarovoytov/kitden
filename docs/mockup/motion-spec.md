# Kitden motion spec (from the motion study mockup, 2026-10-24)

Calm values unless a "Rich:" line says otherwise. Times in ms. Curve names come from M0.

## M0 Tokens

**Easings**

| Name | Curve | Used for |
|---|---|---|
| CALM | cubic-bezier(.2,.8,.2,1) | default for every Web Animation in Calm |
| SPRING | linear(0, 0.0066, 0.0263 2.4%, 0.1061 5%, 0.2289 7.7%, 0.6235 15.9%, 0.7837 20.1%, 0.8986 24.5%, 0.9775 29.4%, 1.0122 33.2%, 1.031 37.5%, 1.0337 42.7%, 1.0242 49.5%, 1.0048 61.8%, 0.9989 75.4%, 1); fallback cubic-bezier(.3,1.25,.5,1). Peaks 3.4 % past the end | default in Rich; CSS press, switch knob, ports, badges, tick, chevron in both modes |
| OUT3 | 1 − (1 − t)³ | map blocks moving (Calm) |
| IN3 | t³ | map blocks leaving |
| SPRINGJS | 1 − e^(−6.2t) · cos(8t), forced to 1 at t = 1. Peaks 11.5 % past the end at t ≈ .31 | map blocks moving (Rich) |
| DRAW | cubic-bezier(.3,.7,.2,1) | icon stroke draw, Rich path overlay, Changes rail |
| DRAW-R | cubic-bezier(.3,.7,.1,1) | link draw-in (Rich) |
| RETRACT | cubic-bezier(.4,0,.2,1) | link undraw, Rich nav stretch, Rich sweep |
| BEAM | cubic-bezier(.45,0,.3,1) | Rich beam |
| SOFT | cubic-bezier(.2,.7,.2,1) | Rich title words, ripple |
| STRIKE | cubic-bezier(.6,0,.2,1) | Changes strike line |
| SPARK | cubic-bezier(.15,.7,.3,1) | Rich spark |
| REVEAL | cubic-bezier(.2,.7,.1,1) | Rich theme reveal |
| keywords | ease-in, ease-out, linear; plain `ease` for CSS transitions with no curve | exits, meters, loops |

Map block tweens run on one linear clock; each block gets its own eased progress k for x, y, scale and rotation. Opacity uses min(1, k), so it never overshoots. Stagger = extra delay per block in list order.

**Base durations**: element rise 260 · panel in 240 / out 180 · panel step 130 out + 220 in · tray bar in 220 · toast in 200 · dock out 160 · number roll 140 + 200 · pill glide 280 · nav marker 300 · map relayout 260 · block leaving 180 · link fade out 240 · dash blend 300 · link draw-in 260–280 · undraw 380 · shake 380 · spinner 800 per turn · Apply step 560 (meter 480) · toast life 9000. Web Animation default when none is given: 300.

**Slow factor**: every duration and delay is ms × slow. "Slow ×4" sets slow = 4; CSS transitions and loops use time × slow too. Toast life is 9000 × slow. Not scaled: the 240 ms link hover grace.

**Reduced motion** (prefers-reduced-motion: reduce): every scaled time becomes 0. No Web Animations, tweens jump to the end, waits are 0, number rolls and count-ups show the final value, all CSS transitions and loops are off, Rich can't be turned on, theme switch is instant. Still running: toast life (9 s) and the 240 ms hover grace.

**Colour tokens** (dark / light): accent #F09A7C / #A44226 · select fill #382A27 / #F6E8E2 · ok #47C27A / #1C8A4C · warn #EAC27C / #97590A · faint #6B7381 / #80868F · wire #59616F / #C3C8D0 · preview fill = accent at ~6 % · preview line = accent at 50 %.

**Lamp language** (6 px dot; tools use the same dot as "mark"):
- grey (faint) = off · green (ok) = on, works · amber (warn) = needs you (sign-in, not tested).
- transparent with a 1.5 px dashed accent ring = in preview.
- transparent with a 1.5 px solid grey ring = works outside the gateway.
- Colour change: background-color 400 ease. A lamp that flips "pops" (scale 2.2 or 2.4 → 1, see M3).

**Block looks**: normal = panel fill, 1 px line border · selected = select fill + accent border · open server/plugin = accent border · preview = preview fill, 1 px dashed preview-line border, accent meta text · leaving (removal in preview) = opacity .45 + dashed border · lifted / drop target: M5.

**Link looks**: base wire 1.2 px · on a lit path accent 1.7 px · selected path overlay accent 2.1 px drawn on top · preview accent dashes 4/4 at .65 · leaving muted dashes 4/4 at .4 · bypass (outside the gateway) faint dots 1.5/4 at .8 · bypass preview accent dashes 4/4 at .65 · hover / picked accent 2.4 px at 1 (bypass: amber). CSS: stroke 220, stroke-width 220, stroke-opacity 300, ease.

**Dimming**: map focus → blocks off the path filter opacity(.4) saturate(.6), links off the path stroke-opacity .16, both 300 ease. Find → see M6.

**CSS transitions** (both modes)

| Element | Trigger | Property, from → to | ms | Curve |
|---|---|---|---|---|
| Button | hover | border → 40 % accent mix; primary: fill → darker action colour | 180 | ease |
| Button | press | scale 1 → .97 | 260 | SPRING |
| Map block | hover | border → 38 % accent mix | 180 | ease |
| Map block | press | scale 1 → .98 | 260 | SPRING |
| Map block | look change | fill, border 180; shadow 300; filter 300 | — | ease |
| Port (9 px ring) | block selected or on the lit path | border → accent | 200 | ease |
| Server/plugin right port | open | opacity 0 → 1, scale .4 → 1 | 200 / 300 | ease / SPRING |
| Count badge (20 px) | open | opacity 1 → 0, scale 1 → .3 | 200 / 300 | ease / SPRING |
| Preview block | hover or focus | border → full accent; × badge (18 px, corner −8/−8) opacity 0 → 1, scale .5 → 1 | 180 / 320 | ease / SPRING |
| Nav item, segment label | hover, current | colour | 180 | ease |
| Top bar toggles | on | fill → select, text and border → accent | 180 | ease |
| List row, project button | hover | fill → dim | 180 | ease |
| Result row, pick row, Changes row | hover | border → 38–40 % accent mix | 180 | ease |
| Radio (14 px) | picked | fill + border → accent, 3 px inner ring | 200 | ease |
| Checkbox (16 px) | ticked | fill, border 200; tick opacity 0 → 1 160, scale .5 → 1 320 | — | ease / SPRING |
| Switch (34×20) | on / pending | track colour 250; knob 14 px moves 0 → 14 px (pending: 7 px, accent knob, dashed track) 340 | — | ease / SPRING |
| Link × | hover | fill → accent, icon → panel colour | 120 | ease |
| Notes chevron | open | rotate 0 → 90° | 280 | SPRING |
| Lamp, mark | state | background-color | 400 | ease |
| Panel ×, menu item | hover | fill → dim | 0 | — |
| Focus | keyboard focus | 2 px solid accent outline, 2 px offset | 0 | — |

**Shared one-shots** (both modes)
- Shake (refused or failed): translateX 0 → −7 → 6 → −3 → 0 px, 380 ease-out.
- Number roll: old value moves 70 % of its height and fades, 140 ease-in; new value comes in from the other side, 200 CALM (Rich 440 SPRING). Goes up when the new number is bigger, down otherwise (text always goes down).
- Count-up: text 0 → value, OUT3.
- Spinner: rotate 360° per 800, linear, loops.
- Check draw: stroke-dashoffset length → 0, 300 DRAW, 120 between paths.

**Motion controls** (top bar): Motion Calm/Rich (pill glide, then the page replays) · Slow ×4 · Fail next Apply · Replay (page rebuilt with its entrance, no fade-out).

**Rich-only effects** (none of these run in Calm)
- Ripple: ring box-shadow 0 → 16 px, glow alpha a → 0, 720 SOFT; a = .3 to .7 per use.
- Spark on success: 12 lines (12×2 px) fly out from the centre (from .55 × radius to radius + 26 px, scaleX 1 → .15, fade), 560 SPARK.
- Beam: a 2.6 px glowing segment, length min(48, .45 × link length), runs along links one group after another; time max(260, 1.5 × link length in px), BEAM; amber on bypass links.
- Spotlight on blocks and cards: border glow (130 px circle) and fill glow (200 px) follow the pointer; fade in 250 on hover.
- Dot grid around the pointer (22 px grid, 130 px radius, dots pushed out up to 5 px); fades 16 % per frame.
- Primary button sheen on hover: band translateX −130 % → 130 %, 750 ease.
- Preview blocks: a light runs round the border, 2400 linear loop. Preview links: dashes march (offset 0 → −16), 1100 linear loop.
- Skeleton shimmer 1100 ease-in-out loop; blur on entrances (4–10 px); drag tilt; project sweep; theme circle reveal; Map↔List morph; toast morph.

## M1 Page and map entrance

**Page switch** (click in the left rail)

| Step | Element | From → to | ms | Delay | Easing |
|---|---|---|---|---|---|
| 1 | Nav label | colour → accent, weight 600 (weight at once) | 180 | 0 | ease |
| 1 | Nav marker (38 px pill) | top: old item → new item | 300 | 0 | CALM |
| 2 | Old page | opacity 1 → 0, translateY 0 → −6 px | 120 | 0 | ease-in |
| 3 | Old panel, tray or toast, search text, scroll | removed / reset at once | 0 | after 2 | — |
| 4 | Title, as one piece | opacity 0 → 1, translateY 6 → 0 | 260 | 0 | CALM |
| 4 | Lede, then scope line | same rise | 260 | 120, 180 | CALM |
| 4 | Page entrance (below) and hint line text (swaps at once) | | | 0 | |

Rich: the marker stretches; at 45 % it spans both items, then shrinks to the new one, 520 RETRACT. Old page also blurs 0 → 6 px, 170. Title splits into words: each blur 10 → 0, opacity 0 → 1, translateY 8 → 0, 640 SOFT, 55 apart. Lede and scope 560 SPRING with blur 6 → 0.
First load and Replay: no fade-out; the marker and every pill are placed without motion.

**Map entrance** (Gateway and Library)
- Every block and caption: from its final x, y + 6 px, opacity 0 → final y, opacity 1; 260 OUT3; 22 apart in layout order.
- A link's opacity is the lower of its two blocks' opacities, so each link fades in with its later block.
- Gateway order (15): captions Clients, Gateway, Servers → Claude Code, Codex, Cursor → gateway → Remote, GitHub, Linear → Local, Filesystem → Outside caption, Browser, Dropbox (→ Tools caption and tools if a server is open). Ends at 568.
- Library order (17): Clients caption, 3 clients, Plugins caption, Community, Developer kit, Docs writer, Team, Design tools, Your skills, Release notes, Inside caption, 4 inside items. Ends at 612.

Rich Gateway (times from start; block moves use SPRINGJS):
- 0: gateway scale .84 → 1, opacity 0 → 1, 680 SPRINGJS; ripple .6 at 220.
- 120: clients and the Clients/Gateway captions fly from the gateway centre (scale .42, opacity 0) to place, 640, 60 apart.
- 210: servers, tools and their captions, same flight, 660, 40 apart.
- 510: outside blocks and their caption rise 28 px, 600, 80 apart.
- Then bypass links draw 520 DRAW-R; 220 later: beam client links, then server links.

Rich Library: clients and caption from x − 30, scale .9, 560, 60 apart; then the rest from x 150 (own y), scale .4, 640, 36 apart; then beam client → item links, then Developer kit's inside links.

**Pill (segmented control)**: Map/List, Library tabs, Add panel filter, Motion. The raised pill moves left and width from the old segment to the new, 280 CALM (Rich 420 SPRING); labels recolour 180.

**Map / List switch** (Gateway)
- Selection let go (panel out 180); dock cleared if the tray is empty.
- Old view: opacity 1 → 0, translateY 0 → −4 px, 120 ease-in. New view: opacity 0 → 1, translateY 6 → 0, 260 CALM.
- Rich (container transform): each block that has a list row becomes a box that moves and resizes to that row (left, top, width, height; radius 8 → 0, fill panel → clear, border line → clear; reverse on the way back), 560 SPRING, 20 apart. Inside the box the old content is gone by 32 % and the new content fades in from 42 %. The rest of the old view fades 200 ease-in. Unpaired items fade in 280, 22 apart (to list) or 14 apart (to map). Back on the map every link redraws 460 DRAW-R.
- Library's List button: the pill shakes and a toast says the List view is on Gateway.

**Theme switch** (Appearance): Calm instant. Rich: the new theme is revealed by a circle from the button centre, radius 0 → farthest window corner, 700 REVEAL.

## M2 Select and Details

**One active element**: at most one selected thing per page. A click on a block or a link makes it active and lets go of the last one. Clicking the active one again, clicking empty map, or the panel × lets go. Hover previews run only while nothing is selected or dragged.

**Select**

| Element | From → to | ms | Easing |
|---|---|---|---|
| Selected block | fill → select, border → accent | 180 | ease |
| Blocks on the path | ports → accent | 200 | ease |
| Blocks off the path | filter → opacity(.4) saturate(.6) | 300 | ease |
| Links off the path | stroke-opacity → .16 | 300 | ease |
| Links on the path | stroke → accent, width 1.2 → 1.7 | 220 | ease |
| Path overlay (new 2.1 px accent line on each path link) | opacity 0 → 1, all at once | 180 | CALM |

Rich: overlays draw along the link instead (dashoffset length → 0), 280 DRAW, group g starts at g × 120; then a beam group by group; ripple on the selected block (.35 to .55).

Path groups, in order: client = its gateway link · gateway → server links · open server's tool links (its bypass links turn on too, no overlay). Gateway = client links · server links. Server = client links · its gateway link · its tool links. Tool = client links · its server link · its own link if on. Outside server = focus on it, its client and its bypass link only (Rich amber beam). Library: M7.

**Let go**: looks go back by CSS (180 / 300); overlays fade 1 → 0, 160 ease-in, then removed; panel closes.

**Hover preview** (nothing selected): pointer on a client or an outside server → same focus without overlays (Rich: beam; amber along the bypass links of a client that is not on the gateway). Pointer on another kind of block or off the map → unfocus.

**Side panel** (right 22, top 190, bottom 46, 320 px wide)

| Trigger | Element | From → to | ms | Delay / stagger | Easing |
|---|---|---|---|---|---|
| First open | panel | opacity 0 → 1, translateX 28 px scale .98 → none | 240 | 0 | CALM |
| Load | skeleton bars | shown at once | 0 | | |
| Load | real content | replaces the skeleton | 0 | after 160 | |
| Load | each child | opacity 0 → 1, translateY 6 → 0 | 260 | 20 apart | CALM |
| Close | panel | opacity 1 → 0, translateX 0 → 22 px | 180 | 0 | ease-in |
| Step forward / back | old children, together | opacity 1 → 0, translateX 0 → −18 px (back: +18) | 130 | 0 | ease-in |
| Step forward / back | new children, together | opacity 0 → 1, translateX +22 → 0 (back: −22) | 220 | 0 | CALM |

Rich: open 580 SPRING with blur 8 → 0; skeleton lasts 380 and shimmers; children 560 SPRING, 45 apart, blur 6 → 0; step-in 460 SPRING, blur 4 → 0, 32 apart.
- Swap: choosing another client, server, tool or the gateway on Gateway, or another row on Changes, keeps the panel: content goes back to the skeleton at once, then loads. An outside server, a link, the Add panel, or anything in Library first closes the old panel and opens a new one (out 180 and in 240 run together).
- Page switch removes the panel with no motion.

**Server unfold** (Gateway, click a closed server)
1. It becomes active and open: border → accent, badge out, right port in (CSS, M0). Its panel loads.
2. Tools appear: Tools caption and one 200×34 block per tool, x 636, tops 42 apart, the column centred on the server's middle (top at least 24).
   - Blocks placed on their final spot, invisible.
   - Tool links draw from the server's right port, 170 CALM.
   - Blocks fade in 0 → 1, 120 OUT3, 15 apart.
3. Then the path lights (table above).
- Rich: tools grow out of the server (from x = server right − 100, y = server middle − 17, scale .3, opacity 0) to place, 580 SPRINGJS, 34 apart; links follow their opacity.

**Server fold** (click the open server while it is the active one, or open another): tools go back to that start point, scale .3, opacity 0, 180 IN3 (Rich 300), then removed; links fade with them. Border, badge and port go back by CSS.
- Click an open server while one of its tools is active: the server becomes active, no fold. A tool of a closed server opens that server first.
- Any block that changes place in a relayout: 260 OUT3 (Rich 540 SPRINGJS).

**Panel content changes**
- A tool change lands while its Tool panel is open: content re-renders; facts, text and actions rise again, 260, translateY 6 → 0, 40 apart.
- Server panel switches: a click sets the switch to pending at once; when it lands the knob goes to on or off (M0); "n of m on" rolls.
- Client and Gateway panels re-render with no motion when a change enters or leaves the preview ("in preview" text, button disabled).
- Project change with a Tool or Server panel open: the panel steps forward. A change landing while a picker step is open: the panel steps back.

## M3 Links

**Pointing**
- Each removable link has an invisible 14 px-wide stroke on top that takes the pointer; it is off while the link is below .5 opacity. Removable: client → gateway, gateway → server, server → tool, bypass, leaving, moving-in and preview links; in Library client → plugin/skill, plugin → inside item, previews. Instruction file links are not.
- Hover: the link takes the hover look by CSS (accent, bypass amber; 2.4 px; opacity 1, also inside a dimmed map); stroke and width 220, opacity 300, ease.
- The ×: 16 px circle, panel fill, 1 px accent border, 10 px accent ×. Its centre sits on the point at half the path's length. Pointer area 28 px. Appears opacity 0 → 1, 120 CALM (Rich 180). Jumps with no motion to another link; follows the link while blocks move. Tooltip names the action ("Remove GitHub from the gateway", "Turn off Push files", "Disconnect Codex", "Take it out of the preview").
- Leave the link or the ×: 240 grace, then the hover look goes (CSS) and the × hides at once; if a link is picked, the × jumps back to it. Moving onto the × cancels the grace.

**Click → Connection Details**: the last selection lets go; the link is picked (keeps the hover look and the ×); only its two blocks and the link stay bright (focus, 300). Rich: beam along it (amber for bypass). A new Connection panel opens. Click again → let go.

**Removal** (× or the panel's remove button): the link first goes into preview.

| Link | Blends to | Far block |
|---|---|---|
| client → gateway | leaving (muted dashes, .4) | — |
| gateway → server | leaving | server: leaving look (opacity .45, dashed border, 300) |
| server → tool | preview (accent dashes, .65) | tool mark: dashed ring |
| bypass | bypass preview (accent dashes, .65) | outside block: leaving look |
| Library client → plugin | leaving | — |
| Library plugin → skill | leaving | skill: leaving look and dashed mark |

- Blend: from the old dash and opacity to the new, 300 CALM (Rich 420). A solid line counts as dash "8 0", so gaps open out of the line. Taking it out of the preview blends back and restores the block.
- × on a link that is a preview only takes it out of the preview (M4).

**On Apply** (the change lands)
1. The link keeps its dashes (no blend back while Apply writes) and fades opacity → 0, 240 ease-out (Rich 320), then is removed.
2. Far block:
   - Server removed: shrinks into the gateway (to gateway right − 85, middle − 30, scale .4, opacity 0), 180 IN3 (Rich 360); servers below move up 260 OUT3; "n servers" rolls.
   - Outside server removed: moves 24 px left, scale .85, opacity 0, 180 IN3 (Rich 320); the list closes up 260.
   - Tool off: mark pops scale 1.9 → 1, 200 CALM (Rich 520 SPRING) and turns grey (400); "n of m on" rolls; the server lamp pops 2.2 → 1, 200 (Rich 520) if the server turns all off or back on.
   - Client disconnected: lamp pops 2.4 → 1, 200 (Rich 560) and turns grey; "n clients" rolls; Rich ripple .5.

**Undraw** (a solid link removed with no preview step: Undo of an add, a project change): the stroke shrinks back to its start (dashoffset 0 → length), 380 RETRACT, then the line is removed.

**Draw in** (a link lands or comes back): the stroke grows from its start port to its end port, CALM (Rich DRAW-R, then a beam). While it draws it is solid; dots or dashes come back when it ends.
- Tool on 260 (Rich 520) · client connected 260 (Rich 560) · server added or moved in 280 (Rich 560) · moved-out bypass 280 (Rich 600) · Library add 260 (Rich 520) · project change 240 (Rich 520) · Undo restores 480 (Library skill 420).
- New preview link: opacity 0 → 1, 300 CALM (tool preview 240, moved-out pair 320).

**Quiet bypass links** (servers set up in one client, outside the gateway)
- Shape: right angles. From the client's right port go right by the channel (Browser 16 px, Dropbox 24 px, a moved-out server = largest + 8), turn with 8 px round corners, go down, turn, go right into the block's left port. Other links are curves with horizontal handles of max(18, half the x distance).
- Look: grey dots 1.5/4 at .8; the block's port stays grey; its lamp is a grey ring. No motion of their own.
- Hover the link: amber, 2.4 px. Hover the outside block: focus on it, its client and the link (Rich amber beam). Lit by a client selection: muted colour at full opacity.

## M4 Preview tray and Apply

The dock sits bottom left of the page (left 22, bottom 46), 380 px wide. Every change waits there until Apply.

**Tray bar**

| Trigger | Element | From → to | ms | Delay | Easing |
|---|---|---|---|---|---|
| First change | bar | opacity 0 → 1, translateY 18 px scale .97 → none | 220 | 0 | CALM |
| Count changes | bar | height and width old → new | 200 | 0 | CALM |
| Change added (2+) | new list row | opacity 0 → 1, translateY 10 px scale .98 → none | 200 | 80 | CALM |
| Count changes while ≥ 2 | "N changes" number | roll | 140 + 200 | | |
| One taken out | its row | opacity 1 → 0, translateX 0 → 18 px | 180 | 0 | ease-in |
| Last one out, Cancel all | bar | opacity 1 → 0, translateY 0 → 10 px | 160 | 0 | ease-in |

Rich: bar in 540 SPRING with blur 6 → 0; resize 480 SPRING; new row 480 with blur 4 → 0; ripple .3 on the bar for each later add.
- One change: title, detail, Cancel, Apply. Two or more: "N changes in preview", a list (rows have the dashed preview border and fill, scroll above 212 px), Cancel all, Apply all. Going from 1 to 2 rebuilds the bar; both rows play the row entrance.
- A new change while a toast shows replaces the toast at once.
- Take one out: the row ×, a click on its preview block or preview link, or unticking it in a picker. The row slides out first, then the map part reverts (blend back, fade, or the block goes home in 180–260), then the bar resizes.
- Cancel all: every change reverts at once (reverse order, no stagger); the bar leaves.

**Apply all** (N steps = changes + 1; the last step is the check)
1. Cancel and every row × are disabled at once (opacity .5 / .35); Apply stops taking clicks.
2. Arrow icon → spinner; label → "Applying 1 of N".
3. Every 560 one step: the step number rolls (from step 2); the meter (2 px white line at 75 %, button bottom, grows from the left) scaleX i/N → (i+1)/N, 480 ease-out; that change's row status shows a spinner at the start of its step and a check when done.
4. Success: button fill → green (180 ease), label "All applied" ("Applied" for one); the spinner becomes a check that draws in 300 DRAW; row checks turn green at once. Rich: spark.
5. Wait 200 (Rich 480).
6. Changes land in tray order, change i at i × 60 (Rich 170). Each landing is in M3, M5, M7.
7. At count × 60 (Rich 170) the toast replaces the bar.

**Toast**
- In: opacity 0 → 1, translateY 14 px → 0, 200 CALM.
- Rich: the toast grows out of the bar (width, height and bottom edge from the bar's to its own), 520 SPRING; its parts fade up 6 px, 260, delay 180 + 50 per part; the green tick draws 420, delay 200. With no bar before: plain 480.
- Content: green tick, text ("Applied 3 changes" or the change's own sentence), "Undo all" or "Undo", sometimes one more button ("Show website").
- Life bar: 2 px green line at .7 along the bottom, scaleX 1 → 0 toward the left, linear, 9000 × slow. Pointer on the toast pauses it; leaving resumes it. At the end the toast leaves (160, down 10 px, ease-in).
- Undo all: the toast leaves; changes undo in reverse order, 120 apart, each playing its way back.

**Failure** ("Fail next Apply" on)
- Stops after step N − 1 (the last change; with one change, step 1). That row's status shows an accent ×.
- Bar border → accent at once; the bar shakes (380). Header → "Nothing was changed" and who changed the file. Buttons → Cancel (all) and Try again (keyboard focus, ring). The meter is gone; row × work again; the map stays in preview.
- Try again: the bar is rebuilt in place (no entrance) and Apply runs again.

## M5 Drag and drop

**Common**
- A drag starts after the pointer moves 5 px (pointer captured); less is a click. A finished drag swallows its click. While dragging, hover previews are off and any selection lets go.
- The dragged block follows the pointer 1:1, no easing; its links redraw on every move.
- Lift look: shadow (300), accent border, above other blocks, grabbing cursor. Rich: scale 1.05 and tilt = clamp(1.2 × v, −8°, 8°), v = .75 × v + .25 × x movement per pointer move.
- Drop target look: accent border, select fill, scale 1 → 1.05 (260 SPRING). Rich: ripple .45.
- Drag tip: small pill at the dragged block's top-left + (6, −28) px; for the wire drag at the pointer + (12, −30) px. Plain (muted) normally; accent fill, border and text when a drop would work. Text switches at once.

**Outside server into the gateway** (Browser, Dropbox)
- Start: focus on the block, the gateway and its bypass link.
- Zone: block centre x 330–700 and centre y above the Outside caption (−4 px).
- Enter the zone: the gateway takes the drop target look. A slot opens at the end of the block's group: a dashed preview box 170×60 with a dashed preview link from the gateway. It grows from the gateway's right side (scale .4, opacity 0) to its place while blocks below move down 70 px; 220 OUT3 (Rich 420 SPRINGJS).
- Leave the zone: the slot shrinks back into the gateway, 180 IN3 (Rich 300); blocks move back up 220; the gateway goes back.
- Drop in the zone: slot removed; the block moves onto the slot spot, scale 1, rotation 0, 200 OUT3 (Rich 420 SPRINGJS). It becomes a server block in preview ("Moves in · 3 tools") on the same spot; its gateway link fades in 300 CALM; the bypass link stays, now ending at the new block; Rich ripple .5. The outside list closes up (260).
- Same result from the panel's "Move into the gateway…": the slot opens (260), then the block moves (200).
- Lands on Apply: preview look goes (180), × badge removed, meta becomes lamp + "n of m on"; the bypass link fades (240); the gateway link turns solid and draws 280 (Rich 560 + beam); "n servers" rolls. Rich: ripple .7 and scale 1.06 → 1, 520.
- Taken out: it turns back into the outside block on the spot, its new links fade (240), and a relayout carries it home (260).

**Gateway server onto a client**
- Start: focus on the block, all clients and its gateway link; tip "Drop on a client".
- Target: the pointer inside a client box widened 24 px left, 40 px right, 16 px up and down.
- Over a client: the client takes the drop target look; a temporary wire (accent dashes 4/4, 1.7 px, .65) appears at once from the client's right port to the block's left port and follows; tip "Move into Claude Code".
- Off the client: the client goes back; the wire fades 240 ease-out.
- Drop on a client: the block becomes an outside block in preview ("Moves to Codex") where it was dropped. Two links fade in 320 CALM: a bypass preview link from the client (accent dashes, right angles) and a leaving link from the gateway. A relayout moves it into the Outside list (260); then Rich ripple .5.
- Same from the panel: "Move out of the gateway…" steps forward to a client list; pick one (radio fills, 200).
- Lands on Apply: the leaving link fades (240); the bypass link turns to plain dots and draws 280 (Rich 600 + amber beam); preview look goes; Rich ripple .6; "n servers" rolls; its Server panel closes.

**Free client wire to the gateway** (a client not on the gateway and not in preview: Cursor)
- Start: focus on the client and the gateway. A wire (accent dashes 4/4, .65) runs from the client's right port to the pointer, curve as in M3; tip "Drop on the gateway".
- Over the gateway (box widened 24 px sideways, 16 px up and down): the gateway takes the drop target look; the wire end snaps to its left port; tip "Connect Cursor".
- Drop on the gateway: the wire is removed; a preview link client → gateway fades in 300 CALM; Rich ripple .45 on the client.
- Miss: the wire fades 1 → 0, 180 CALM, then is removed.
- Lands on Apply: state text "Connected"; lamp pops 2.4 → 1 (200, Rich 560) and turns green (400); the preview link fades while the solid link draws 260 (Rich 560 + beam on to the servers); "n clients" rolls; the client can't be dragged any more.

**Marketplace row from the Add panel onto the map**
- Start (row not in the gateway and not in preview): the row drops to .4 opacity at once; a copy of the row with a shadow (ghost) sits on it and follows the pointer.
- Zone: pointer x 180–760 and y −20 px down to the Outside caption (map space), not over the panel. Enter: ghost border → accent, fill → select (180); the slot opens in the server's group and the gateway lights, as above. Leave: both undone.
- Drop in the zone: the ghost flies onto the slot and resizes to 170×60, 200 CALM (Rich 380 SPRING), then is removed; the row comes back to full; the slot goes; the server appears in preview on that spot, its link fades in 300, Rich ripple .5; the row shows "In preview" (select fill, accent border).
- Click a row instead: the server block grows from the gateway's right side (scale .4, opacity 0) to its place, 260 OUT3, while blocks below make room. Rich: a copy of the row flies from the panel to the map spot and resizes, 620 SPRING; then the block shows there, ripple .5, link fades in 300.
- Lands on Apply: as moving in; the row's text becomes green "Added", sliding in from 6 px right, 280 CALM; the row turns off (opacity .55).
- Taken out (click the block, its ×, or the row): link fades (240); the block shrinks back into the gateway 180 IN3 (Rich 380); blocks below move up 260.

**Drop misses**

| Drag | What goes back | ms | Easing |
|---|---|---|---|
| Outside server, gateway server | block to its start spot, scale 1, rotation 0 | 220 (Rich 560) | OUT3 (Rich SPRINGJS) |
| Library plugin (always, hit or miss) | block to its place | 220 (Rich 560) | OUT3 (Rich SPRINGJS) |
| Free client wire | wire fades out | 180 | CALM |
| Marketplace ghost | ghost back onto its row, then removed | 180 (Rich 320) | CALM |

On every drop the lift look, tip, temporary wire, target look and map focus go (CSS times; the tip at once).

## M6 Add panel, project picker, find in map, list view

**Add panel** ("+ Add" in the Servers caption, or "Add a server…" in Gateway Details)
- The selection lets go; the panel opens fresh and loads (M2); "+ Add" turns primary (180) and back on close.
- Filter pill All / Community / Team glides (M1); it does not filter in the mockup.
- Search: rows that stop matching hide at once; rows that match again come back opacity 0 → 1, translateY −4 px → 0, 240 CALM.
- Rows: hover border 40 % accent (180); "In preview" = select fill + accent border; "In the gateway" / "Added" = opacity .55, no hover. Click and drag: M5.

**Project picker** (top bar)

| Trigger | Element | From → to | ms | Stagger | Easing |
|---|---|---|---|---|---|
| Click the button | menu (6 px under it, grows from its top-left) | opacity 0 → 1, translateY −8 px scale .96 → none | 180 | | CALM |
| Click the button | menu items | opacity 0 → 1, translateY 6 → 0 | 260 | 0, all at once | CALM |
| Pick, click outside, click the button, page switch | menu | opacity 1 → 0, translateY 0 → −4 px scale .98 | 140 | | ease-in |

Rich: menu 440 SPRING with blur 6 → 0; items 560 SPRING, 35 apart, 4 px.
- The search field takes focus; typing hides items at once. The current item has select fill and an accent check.
- After a pick the name in the button rolls (text: old goes down, new comes from above) and turns accent at once.
- Gateway reacts:
  - Scope line: opacity 0 → 1, translateY 4 px → 0, 320 CALM.
  - Each server: "n of m on" rolls; its lamp pops 2.2 → 1 (200) if it flips.
  - Each tool block re-renders; project tags pop opacity 0 scale .7 → 1, 200 CALM (Rich 420, delay 260).
  - Tools whose state flips: mark pops 1.9 → 1, 200 CALM (Rich 520 SPRING, delay 260); link draws in 240 (Rich 520) or undraws (380 RETRACT); Rich ripple .5 at 260.
  - An open Tool or Server panel steps forward; the list view re-renders at once.
  - Rich: a soft glow band (30 % wide) sweeps across the map: translateX −40 % → 240 %, opacity 0 → 1 at 25 % → 0, 1000 RETRACT.
- Other pages: the scope line's text and colour change at once.

**Find in map** (top bar search; Gateway and Library only)
- Each keystroke: blocks whose name does not contain the text → filter opacity(.3) saturate(.5) blur(1.2px); every link → stroke-opacity .2; 300 ease. Captions stay. Empty text → back. A page switch clears the field.
- Rich: a block that becomes a match ripples once (.5).

**List view** (Gateway)
- Rows 40 px; tool rows 34 px, indented 44 px; GitHub is shown open.
- Hover: dim fill, 180. Click a tool row: that row → select fill (180; the last one goes back) and the Tool panel loads (M2). Other rows don't respond.
- Rich: the switch itself morphs (M1).

## M7 Library

Map: clients (150×54) on the left; "Plugins and skills" at x 250, grouped by source (Community, Team, Your skills); the open plugin's Inside column at x 500 (200×34, tops 42 apart, centred on the plugin). Plugin block 180×60: icon, name, lamp + "n of m on", count badge, ports. Standalone skill 180×34 with a green mark and "Skill". A plugin that is not added (Design tools): grey lamp "Not added", a small + button, inside links in muted dashes.

**Plugins and skills**
- Click a plugin: the last selection lets go (panel out 180); the plugin takes the selected look (Rich ripple .4). If it was not open, the open plugin's inside items go back into it (to plugin right − 100, middle − 17, scale .3, opacity 0), 160 IN3 (Rich 300); this plugin's items grow out from the same kind of spot, 220 OUT3, 15 apart (Rich 600 SPRINGJS, 34 apart); other blocks move 260 OUT3 (Rich 540). Then the path lights: client → plugin links, then plugin → inside links (overlay 180; Rich draw + beam). A new panel opens.
- Click the active plugin again: let go and fold (inside items go back, 160 IN3).
- Inside item: path = client → plugin, then plugin → item; panel "Skill" or "Command". Standalone skill: path = client → skill.
- Client: hover → focus on it and its items, links on (Rich beam). Click → path = its links, Rich ripple .45, panel "Client".
- Tabs "Plugins and skills" / "Instructions": pill glide; selection lets go; leaving blocks go to x 150 at their own y, scale .4, opacity 0, 160 IN3 (Rich 300); new blocks grow from x 150, y 200, scale .4, 220 OUT3, 15 apart (Rich 600, 34 apart). Rich then beams file links, then import links. Files and imports select like plugins; their links can't be removed.

**Skill off in a plugin** (× on a plugin → skill link)
- Preview: the link blends to leaving (300 CALM); the skill block takes the leaving look (opacity .45, dashed border, 300); its mark gets the dashed ring.
- Lands: the link fades (240); the skill block goes back to full; its mark turns grey (400); the plugin re-renders "3 of 4 on" (no roll). Rich: the plugin ripples .7 and pops scale 1.05 → 1, 520.
- Undo: the link draws back, 420 CALM.
- Removing a plugin from a client (× on client → plugin) works the same way. If no client keeps it, it turns "Not added" with the + button and its inside links switch at once to muted dashes (colour 220, opacity 300).

**Plugin drag onto a client**
- Start: lift look (M5); focus on the plugin and all clients (no links on); tip "Drop on a client". Target test as in M5.
- Allowed client: drop target look, temporary dashed wire, tip "Add to Codex" in accent.
- Blocked client: no target look, no wire; the tip shows the reason in the plain style: "Cursor gets plugins through Claude Code", "Already in Claude Code", "Already in preview".
- Release: the plugin always flies back to its place, rotation 0, 220 OUT3 (Rich 560 SPRINGJS). Blocked → that client shakes (380). Allowed → a preview link client → plugin (accent dashes) fades in 300 CALM; Rich ripple .5; tray item. A plugin that was not added takes the preview look ("Preview · Codex", × badge on hover).
- "+" on a plugin that is not added, or "Add for all projects…": two preview links fade in 300, the second 90 later; the block says "Preview · for all projects". Nothing left to add → the plugin shakes.

**Add to one client** (plugin Details → "Add to Codex…" or "Add to one client…")
- The panel steps forward to a checklist of clients. Cursor and clients that already have it are disabled (opacity .45) with the reason as the note.
- Tick: the add goes into the tray (preview link fades in 300); the row takes select fill and accent border (180); the box fills (200), the tick fades in (160) and scales .5 → 1 (320 SPRING); the box pops scale .6 → 1, 160 CALM (Rich 420 SPRING); the note → "In preview".
- Untick: the change leaves the tray (M4); row and box go back by CSS.
- Done or Back: the panel steps back.
- Lands on Apply: the preview link fades (240); the solid link draws 260 (Rich 520, beam 420 later); the plugin re-renders as on (Rich ripple .7 and pop 1.05 → 1); an open checklist steps back to the plugin.
- Undo: the new links undraw (380 RETRACT).

## M8 Overview and Changes

**Overview entrance**

| Element | From → to | ms | Delay / stagger | Easing |
|---|---|---|---|---|
| Title, as one piece | opacity 0 → 1, translateY 6 → 0 | 260 | 0 | CALM |
| Lede, scope line | same | 260 | 120, 180 | CALM |
| Lede numbers 2, 3, 4 | count up from 0 | 700 | 200, 260, 320 | OUT3 |
| Mini-map numbers 4 servers, 11 tools · 3 plugins, 6 skills | count up from 0 | 900 | 500 · 560 | OUT3 |
| Captions, cards, "Show 3 notes" (8 items, page order) | opacity 0 → 1, translateY 6 → 0 | 260 | 160, then 40 apart | CALM |
| Mini-map, as one piece | opacity 0 → 1, translateY 6 → 0 | 260 | 200 | CALM |

Rich: cards rise 14 px with blur, 70 apart, 560 SPRING; the first two card icons ripple .6 at 700 and 820; mini-map blocks start 16 px outward (clients to the left, the other two to the right), scale .8, opacity 0, and at 260 move in, 620 SPRINGJS, 70 apart; then every link draws 520 DRAW-R; 380 later one beam over all links.

**Overview interactions**
- Card hover: the mini-map focuses the card's clients and links (300); Rich beam and spotlight. Pointer onto anything that is not a card → unfocus.
- Mini-map: click the gateway or Library → page switch (M1); click a client → focus its links (Rich beam).
- Fix… / Sign in… / Connect…:
  1. The button keeps its width; its content becomes a spinner; 700.
  2. Button → green (180); a check draws 300 DRAW (Rich spark). Wait 150 (Rich 420).
  3. The card leaves: opacity 1 → 0, translateX 0 → 28 px, 180 ease-in (Rich 320 with blur 6).
  4. The card collapses: height → 0, padding and border → 0, bottom margin 0 → −8 px (closes the gap), 160 CALM (Rich 260); then hidden.
  5. Cards below slide from their old top: translateY(old − new) → 0, 220 CALM (Rich 520 SPRING).
  6. The "Needs attention" number rolls down (2 → 1); the words change at once.
  7. Toast with Undo. Undo: the card comes back, opacity 0 → 1, translateY −8 px scale .98 → none, 220 CALM (Rich 520); the number rolls up.
- Move in… (Dropbox): page switch to Gateway; after the entrance Dropbox gets the lit look for 1600 (Rich ripple .7).
- Show 3 notes: chevron turns 90° (280 SPRING); the label swaps at once; the notes open height 0 → full and opacity 0 → 1, 280 CALM (Rich 460 SPRING); then each note rises 260, 40 apart. Hide: height → 0 and fade, 220 ease-in.

**Changes entrance**
- Day labels and rows in page order (Today, 3 rows, Yesterday, 2 rows): opacity 0 → 1, translateY 6 → 0, 260 CALM, 40 apart. The first row is selected at once and its panel opens (M2).
- Rich: each day's vertical line grows scaleY 0 → 1 from the top, 700 DRAW, delay 120 + 260 × day; rows slide in from −14 px with blur 5, 560 SPRING, delay 180 + 80 × row; row dots scale 0 → 1, 520, delay 260 + 80 × row; day labels rise 260 apart.

**Changes interactions**
- Click a row: it takes the selected look (select fill, accent border, 180; its dot fills accent at once; the old row goes back). The panel goes back to the skeleton and loads (M2). Rich: the dot ripples .7; history steps fade .2 → 1, 300, from 420, 220 apart.
- Undo (row button or panel):
  1. The button becomes a spinner; 600.
  2. A strike line crosses the title, scaleX 0 → 1 from the left, 200 STRIKE (Rich 420); the title turns muted at once.
  3. The lamp turns grey (400); the state word rolls "Applied" → "Undone" (down).
  4. The Undo button: opacity 1 → 0, scale 1 → .8, 180 CALM, then removed.
  5. If the row is selected, its panel reloads.
  6. Toast "Undid “…”. The backup is back in place." with Redo.
- Redo: strike and muted title go at once; the lamp turns green (400); the word rolls back; the Undo button returns, opacity 0 → 1, scale .8 → 1, 300 CALM.
- "See it on the map": page switch to Gateway with GitHub open (tools enter with the map); after the entrance the tool Push files is selected (M2).
