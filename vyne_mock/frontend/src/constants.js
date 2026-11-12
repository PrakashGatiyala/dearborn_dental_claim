export const API = (import.meta.env.VITE_API_URL || "") + "/v1";

export const V = {
  teal:      "#006D63",
  tealDark:  "#004D45",
  tealLight: "#E0F2F0",
  tealBright:"#00BFA5",
  navy:      "#1B3A4B",
  bg:        "#F4F7F9",
  white:     "#FFFFFF",
  black:     "#1A1A1A",
  grey:      "#6B7A8D",
  midGrey:   "#C8D0DA",
  lightGrey: "#EDF1F5",
  border:    "#DDE4EC",
  green:     "#1B7A3E",
  greenBg:   "#E8F5EE",
  red:       "#B91C1C",
  redBg:     "#FEE2E2",
  amber:     "#B45309",
  amberBg:   "#FEF3C7",
  blue:      "#1D4ED8",
  blueBg:    "#DBEAFE",
  purple:    "#6D28D9",
  purpleBg:  "#EDE9FE",
};

/**
 * Vyne is a clearinghouse. Its only outcomes are "envelope accepted and sent
 * to the payer" or "envelope rejected". Adjudication status lives on the
 * payer's AS/400, not here.
 */
export const STATUS_META = {
  RECEIVED:     { label: "Received",     color: V.grey, bg: V.lightGrey, dot: "#6B7A8D" },
  ACKNOWLEDGED: { label: "Acknowledged", color: V.blue, bg: V.blueBg,    dot: "#1D4ED8" },
  FORWARDED:    { label: "Sent to Payer", color: V.green, bg: V.greenBg, dot: "#1B7A3E" },
  REJECTED:     { label: "EDI Rejected", color: V.red,  bg: V.redBg,     dot: "#B91C1C" },
};

export const STATUS_ORDER = ["RECEIVED", "ACKNOWLEDGED", "FORWARDED", "REJECTED"];

/** Where a forwarded claim goes next. */
export const AS400_PORTAL = import.meta.env.VITE_AS400_PORTAL_URL || "http://localhost:5175";

export function fmt$(n) {
  if (n == null) return "—";
  return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
