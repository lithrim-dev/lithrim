/* brand.jsx — the real Lithrim logo, recreated from the marketing site.
   The mark is the two-vertical-bars glyph used in lithrim.com's nav + OG image
   (#1A2845 bars; the second shorter and offset down). Recreated as inline SVG so
   it is crisp at any size and theme-able (light/dark + the coral avatar) via `color`.
   Raster fallbacks (public/lithrim-logo.png, public/icon.svg) ship for the favicon/app-icon. */

export function Brand({ size = 22, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-label="Lithrim">
      <rect x="6.2" y="2.5" width="4.1" height="19" rx="1.4" fill={color} />
      <rect x="12.7" y="4.9" width="4.1" height="14.5" rx="1.4" fill={color} />
    </svg>
  );
}

/* The conversation's AI-assistant avatar = the Lithrim mark on a themed square
   (the `icon_dark_bg.png` look): a dark navy square + light bars on the light
   theme, inverted to a light square + dark bars on dark. `.msg .av.ai` paints the
   square with `--ink`; the bars take `var(--bg)` — so the avatar flips with the
   theme automatically (no per-theme asset). */
export function Mark({ size = 22 }) {
  return <Brand size={size} color="var(--bg)" />;
}

/* Full horizontal lockup (mark + wordmark) for the rail / chrome. */
export function Wordmark({ markSize = 18 }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth: 0 }}>
      <Brand size={markSize} color="var(--ink)" />
      <span style={{ fontWeight: 700, letterSpacing: "0.07em", fontSize: 13, color: "var(--ink)" }}>
        LITHRIM
      </span>
    </span>
  );
}
