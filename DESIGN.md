# MiroFish Design Tokens

Extracted from `PredictionView.vue`. All new views and components must follow these tokens.

---

## Typography

| Role        | Family                                            | Variable   |
|-------------|---------------------------------------------------|------------|
| Monospace   | `'JetBrains Mono', 'SF Mono', monospace`          | `--mono`   |
| Sans-serif  | `'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif` | `--sans` |

### Sizes & Weights

| Element           | Size    | Weight | Letter-spacing |
|-------------------|---------|--------|----------------|
| Page title        | 28px    | 700    | -0.02em        |
| Section heading   | 16px    | 600    | -0.01em        |
| Body text         | 14px    | 400    | normal         |
| Small / caption   | 12px    | 500    | 0.02em         |
| Badge label       | 11px    | 600    | 0.05em         |
| Mono data         | 13-14px | 500    | normal         |

---

## Colors

| Token              | Hex       | Usage                          |
|--------------------|-----------|--------------------------------|
| `--text-primary`   | `#000`    | Nav, headings, primary text    |
| `--orange`         | `#FF4500` | Accent, links, active states   |
| `--green`          | `#10B981` | Success, BUY signal, positive  |
| `--red`            | `#dc2626` | Error, SELL signal, negative   |
| `--amber`          | `#F59E0B` | Warning, MEDIUM tier           |
| `--amber-bg`       | `#FFFBEB` | Amber background fill          |
| `--border`         | `#EAEAEA` | Panel borders, dividers        |
| `--bg-subtle`      | `#FAFAFA` | Subtle background fills        |
| `--text-secondary` | `#666`    | Secondary labels               |
| `--text-muted`     | `#999`    | Muted / tertiary text          |

---

## Spacing

| Token       | Value   | Usage                      |
|-------------|---------|----------------------------|
| Max-width   | 1400px  | Page container             |
| Padding     | 40px    | Container horizontal pad   |
| Grid gap    | 30px    | Between panel columns      |

---

## Components

### Panels
- Border: `1px solid var(--border)`
- Border-radius: **0** (no rounded corners)
- Background: `#fff`
- No box-shadow

### Badges
- Uppercase text, `11px` font, `600` weight, `0.05em` letter-spacing
- Padding: `4px 10px`
- Border: `1px solid` (color matches text)
- No border-radius

### Skeleton Loaders
- Background: `var(--bg-subtle)`
- Shimmer animation (left-to-right sweep)
- Match the dimensions of the content they replace

### Empty States
- Centered text, muted color (`var(--text-muted)`)
- Optional icon above text

### Progress Bars
- Track: `var(--bg-subtle)`
- Fill: `var(--orange)` or signal color
- Height: 4-6px
- No border-radius

---

## Anti-patterns

Do **not** use:
- Rounded corners (`border-radius`)
- Box shadows (`box-shadow`)
- Gradient fills (`linear-gradient`, `radial-gradient`)

---

## CSS Variables Reference

```css
:root {
  --mono: 'JetBrains Mono', 'SF Mono', monospace;
  --sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --orange: #FF4500;
  --green: #10B981;
  --red: #dc2626;
  --border: #EAEAEA;
  --bg-subtle: #FAFAFA;
  --text-primary: #000;
  --text-secondary: #666;
  --text-muted: #999;
}
```

---

## Responsive Breakpoints

| Breakpoint | Target  | Notes                             |
|------------|---------|-----------------------------------|
| 1024px     | Tablet  | Stack grid to single column       |
| 768px      | Mobile  | Reduce padding, smaller type      |
