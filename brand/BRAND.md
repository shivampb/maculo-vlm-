# Maculo brand kit

**Maculo** comes from *macule*, the dermatology term for a flat spot on the skin.
The product outlines a spot in a photo and compares it with conditions the user
chooses. The brand is bold and fresh on the outside, calm and honest on the inside.

- Visual board: open [`index.html`](index.html), or see [`maculo-brand-board.png`](maculo-brand-board.png).
- Tokens: [`tokens.json`](tokens.json) and [`tokens.css`](tokens.css).

---

## 1. Positioning

| | |
|---|---|
| **Tagline** | A closer look at skin spots. |
| **One-liner** | Outline a spot, then compare it with the conditions you choose. |
| **Secondary line** | Outline. Compare. Ask better questions. |
| **Audience** | Researchers, students and clinicians exploring skin image models. |
| **Status line** | Research preview · Not a diagnosis |

Maculo is not a medical device. Brand copy never implies that it diagnoses,
detects or rules out any condition.

## 2. Logo

The mark is a focus frame (four soft corners) around an organic outline with a
single point inside: you point at a spot and Maculo draws its outline.

| File | Use |
|---|---|
| `logo/maculo-mark.svg` | Primary mark: Deep Forest tile, lime outline, sky point. App icon, favicon, avatar. |
| `logo/maculo-mark-lime.svg` | Lime tile. Use on Deep Forest or black backgrounds. |
| `logo/maculo-logo.svg` | Horizontal lockup on white. |
| `logo/maculo-logo-reversed.svg` | Lockup on Deep Forest or black (lime tile, white wordmark). |
| `logo/maculo-logo-on-lime.svg` | Lockup on lime backgrounds. |
| `logo/maculo-mark-mono.svg` | One-color mark for print, stamps, embossing. |
| `logo/maculo-mark-white.svg` | Tile-less mark for photos and dark backgrounds. |
| `png/` | Raster exports, 16 to 1024 px. |
| `social/og-image.png` | 1200×630 link preview. |

**Wordmark.** Always lowercase `maculo`, Outfit SemiBold (600), letter-spacing
−0.03em. On dark backgrounds the last two letters may be set in lime
(`macu`**`lo`**) for hero moments only. In running text write **Maculo**.

The lockup SVGs set the wordmark as live text. Convert it to outlines in a design
tool before sending files to print or to anyone who doesn't have Outfit.

**Clear space:** half the mark's width on every side. **Minimum size:** mark 16 px /
6 mm; lockup 96 px / 25 mm wide.

**Don't:** recolor the tile outside the palette, put the lime tile on lime or the
Forest tile on Forest, stretch or rotate the mark, add shadows, or add crosshairs,
magnifying glasses or medical crosses.

## 3. Color

| # | Name | Hex | Role |
|---|---|---|---|
| 01 | Black | `#000000` | Photography backgrounds, high-contrast print |
| 02 | **Maculo Lime** | `#91F188` | Hero accent: highlights, posters, selected states, the outline on photos |
| 03 | **Deep Forest** | `#0C1F19` | Primary dark: text, buttons, dark surfaces |
| 04 | Sky | `#99DBF5` | Secondary accent: the point in the mark, info, charts |
| 05 | White | `#FFFFFF` | Backgrounds. Interfaces stay mostly white |

Derived colors for interfaces only: Lime tint `#EAFBE7`, Sky tint `#E8F6FD`,
Green `#1E7A3C` (links and green text on white), Grey `#5C6B66` (secondary
text), border `#DFE5E2`, caution `#FFF4D9` / `#6B4A0E`, error `#C0392B`.

**Contrast rules (WCAG):**

| Pair | Ratio | OK for |
|---|---|---|
| White on Deep Forest | 17.1:1 | Everything |
| Lime on Deep Forest | 12.4:1 | Everything |
| Sky on Deep Forest | 11.3:1 | Everything |
| Deep Forest on Lime | 12.4:1 | Everything |
| Green `#1E7A3C` on white | 5.4:1 | Text and links |
| **Lime on white** | **1.4:1** | **Never for text, icons or focus rings** |

Proportions in the product: about 70% white, 20% Deep Forest, 10% lime and sky.
Marketing (posters, social, merch) can flip to lime or Forest backgrounds.

## 4. Typography

**Outfit** for everything: titles, body and the wordmark. Free under the SIL Open
Font License (Google Fonts).

| Use | Weight | Notes |
|---|---|---|
| Display and titles | SemiBold 600 | Tracking −0.03em, sentence case |
| Large intros | Light 300 | |
| Body and UI | Regular 400 / Medium 500 | 16 px body, line height 1.5 |
| Numbers | 500–600 | Tabular figures for scores |

Lufga (commercial) is a drop-in alternative if you license it.

## 5. Voice and tone

Calm, plain and honest. A careful researcher talking to a friend.

- **Say what the tool does, not what it means.** "Closest match on your list:
  eczema (62%)." Never "You have eczema."
- **Show uncertainty plainly.** "No condition on your list is a strong match."
- **Point to a person.** "A dermatologist should look at anything that changes,
  bleeds or worries you."

| Use | Avoid |
|---|---|
| compare, closest match, outline, score | diagnose, detect, screen, identify disease |
| research preview, educational | clinically proven, accurate, AI doctor |
| may, the model suggests | definitely, guaranteed, safe |

## 6. Imagery and applications

- Real, well-lit skin photos across many skin tones. Nothing shocking or sensational.
- On photos, draw the outline in lime with a thin Deep Forest edge so it reads on any skin.
- Posters and social: big lime or Forest fields, one short line in Outfit SemiBold,
  the lockup bottom-left, the status line in Sky.
- Merch and signage: lime field with the Forest mark, or Forest field with the lime tile.
- Get consent for every identifiable photo, and crop out faces unless they matter.

## 7. Interface patterns

- White page, white cards with a 1 px `#DFE5E2` border, 20 px radius, no heavy shadows.
- Primary button: Deep Forest fill, white text. Secondary: white with a border.
- Selected chips: lime fill, Forest text.
- Focus ring: 3 px Green `#1E7A3C`. Never remove it.
- Confidence: High = lime tint, Moderate = sky tint, Low = caution.
- Every screen with a result also shows the "Not a diagnosis" line.

## 8. Regenerating assets

Edit the SVGs in `logo/` (or the board in `index.html`), then run:

```bash
python brand/export.py
```

This re-renders `png/`, `social/og-image.png`, `maculo-brand-board.png` and the
web app's icons in `static/`. It needs Edge or Chrome installed.
