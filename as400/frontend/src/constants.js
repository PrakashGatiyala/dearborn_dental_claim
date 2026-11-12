export const API = (import.meta.env.VITE_API_URL || "") + "/as400";

export const SYSTEM  = "HCSCDEN01";
export const LIBRARY = "CLAIMLIB";

/** 5250 colour attribute per claim status. */
export const STATUS_META = {
  RCVD: { text: "RECEIVED",   cls: "a-dim",   rev: null },
  ADJU: { text: "ADJUDICATE", cls: "a-green", rev: null },
  PAID: { text: "ADJUDICATED", cls: "a-turq",  rev: null },
  SUSP: { text: "SUSPENDED",  cls: "a-red",   rev: "rev-red" },
  RFRD: { text: "REFERRED",   cls: "a-amber", rev: null },
  RVWD: { text: "RELEASED",   cls: "a-turq",  rev: null },
  RJCT: { text: "REJECTED",   cls: "a-red",   rev: "rev-red" },
};

export const SUSPEND_TEXT = {
  "COB-01": "PRIMARY PAYER EOB NOT ON FILE",
  "COB-02": "PRIMARY PAID EXCEEDS BILLED - OVERPAYMENT RISK",
  "COB-03": "PRIMARY/SECONDARY SETTLEMENT RULES INCOMPATIBLE",
  "COB-04": "SECONDARY COINSURANCE NOT ON FILE",
  "COB-05": "COB LIABILITY - OUR PLAN IS PRIMARY, REPROCESS",
  "COB-06": "COB LIABILITY CANNOT BE DETERMINED - RULE REVIEW",
  "EDI-01": "REQUIRED CLAIM DATA MISSING",
};

/** Right-align a number into a fixed-width money column, AS/400 style. */
export function amt(n, width = 12) {
  if (n === null || n === undefined) return ".".repeat(0).padStart(width, " ");
  return Number(n)
    .toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .padStart(width, " ");
}

export function pad(s, width) {
  const v = (s ?? "").toString().toUpperCase();
  return v.length > width ? v.slice(0, width) : v.padEnd(width, " ");
}

/** MM/DD/YY HH:MM:SS as the status line shows it. */
export function sysClock(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return (
    `${p(d.getMonth() + 1)}/${p(d.getDate())}/${String(d.getFullYear()).slice(2)}` +
    `  ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  );
}

export function julianBatch(d = new Date()) {
  const start = new Date(d.getFullYear(), 0, 0);
  const day = Math.floor((d - start) / 86400000);
  return `B${String(d.getFullYear()).slice(2)}${String(day).padStart(3, "0")}`;
}

export async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = (body.detail || detail).toString().toUpperCase();
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}
