/**
 * Light palette: white surfaces with a green accent.
 *
 * Brand green (#008A4B) is the brand accent and is used for fills, borders,
 * buttons and the header rule. It is too light to read as text on white, so text
 * that should look green uses T.greenText, a deep green from the same hue.
 * Amber, azure and red are likewise darkened so they stay legible on white.
 *
 * The token names are unchanged from the dark theme, so every component picks
 * the new look up from here. Note T.white is the *primary text* token (it was
 * white on dark); it is now near-black.
 */
export const T = {
  // grounds
  bg:       "#EEF6F1",
  bgGrad:   "linear-gradient(180deg,#E3F1E9 0%,#F3F9F5 320px)",
  topbar:   "linear-gradient(90deg,#008A4B,#00743E)",
  panel:    "#FFFFFF",
  panelR:   "#EAF9F1",
  panelHd:  "#F3FAF6",
  border:   "#CFE5D8",

  // signal colours
  green:    "#008A4B",     // brand green — fills, borders, buttons
  green2:   "#00CC69",
  greenText:"#008A4B",     // same green, used for text
  greenBg:  "#E3F6EC",
  greenBd:  "#008A4B",
  azure:    "#0B7FC0",
  azureBg:  "#E7F4FC",
  amber:    "#B86A00",
  amberBg:  "#FFF4E0",
  purple:   "#8A3FD1",
  red:      "#C73E3E",

  // text
  white:    "#10231A",     // primary text
  mute:     "#3D5A4C",
  mute2:    "#4F6F5F",
  dark:     "#10231A",
};

/** Shared surface styles so panels stay consistent across pages. */
export const S = {
  card: {
    background: T.panel,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    overflow: "hidden",
    marginBottom: 18,
    boxShadow: "0 2px 10px rgba(0,90,50,.08)",
  },
  cardHead: {
    background: T.panelHd,
    padding: "11px 16px",
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: ".5px",
    color: T.greenText,
    borderBottom: `1px solid ${T.border}`,
    borderLeft: `5px solid ${T.green}`,
    fontSize: 12.5,
    textTransform: "uppercase",
  },
  cardBody: { padding: "14px 16px" },
  kvKey:   { color: T.mute2, fontSize: 12.5 },
  kvVal:   { color: T.white, fontWeight: 600, fontSize: 12.5 },
  think: {
    background: "#EEF7FD",
    borderLeft: `3px solid ${T.azure}`,
    padding: "9px 12px",
    borderRadius: "0 6px 6px 0",
    margin: "8px 0",
    lineHeight: 1.55,
    fontSize: 12,
    color: T.mute,
  },
  result: {
    background: T.greenBg,
    border: `1px solid ${T.greenBd}`,
    borderRadius: 7,
    padding: "9px 12px",
    marginTop: 8,
    fontSize: 12,
    color: T.mute,
  },
  resultLabel: {
    fontSize: 10,
    fontWeight: 700,
    color: T.greenText,
    letterSpacing: ".5px",
    marginBottom: 4,
  },
  flag: {
    background: T.amberBg,
    border: `1px solid ${T.amber}`,
    color: "#6B3F00",
    borderRadius: 7,
    padding: "10px 13px",
    fontSize: 12,
    marginTop: 10,
    lineHeight: 1.6,
  },
};

export const btn = {
  primary: {
    background: "linear-gradient(135deg,#00A15A,#007A42)", color: "#FFFFFF", fontWeight: 700, border: "none",
    padding: "11px 24px", borderRadius: 8, fontSize: 14, cursor: "pointer",
    boxShadow: "0 3px 10px rgba(0,138,75,.35)",
  },
  secondary: {
    background: "transparent", color: T.greenText, border: `1.5px solid ${T.green}`,
    padding: "11px 22px", borderRadius: 7, fontSize: 14, fontWeight: 700, cursor: "pointer",
  },
  hold: {
    background: "transparent", color: T.amber, border: `1.5px solid ${T.amber}`,
    padding: "11px 22px", borderRadius: 7, fontSize: 14, fontWeight: 700, cursor: "pointer",
  },
};

/** Status pill styling. */
export function pill(kind) {
  const map = {
    pend: { background: "#FFF1C9", color: "#7A5200" },
    ok:   { background: "#CFFBE3", color: "#05683A" },
    hold: { background: "#FFE2C2", color: "#8A4A00" },
    info: { background: T.azureBg, color: "#0A5E91" },
  };
  return {
    display: "inline-block", fontSize: 11, fontWeight: 700,
    padding: "4px 11px", borderRadius: 14,
    ...(map[kind] || map.pend),
  };
}

export function fmt$(n) {
  if (n === null || n === undefined || n === "") return "—";
  const v = Number(n);
  if (Number.isNaN(v)) return String(n);
  return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
