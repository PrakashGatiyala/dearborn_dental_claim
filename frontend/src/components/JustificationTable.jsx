import React from "react";

export default function JustificationTable({ dataSources }) {
  if (!dataSources || !dataSources.length) return null;

  // Flatten each data source row into individual field rows for the table
  const rows = [];
  dataSources.forEach(({ table, row }) => {
    Object.entries(row).forEach(([field, value]) => {
      if (value === null || value === undefined) return;
      rows.push({ table, field, value: String(value) });
    });
  });

  return (
    <div style={styles.wrapper}>
      <div style={styles.title}>Data Sources Used by Agent</div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>DB Table</th>
            <th style={styles.th}>Field</th>
            <th style={styles.th}>Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? "#0d1520" : "#0a1118" }}>
              <td style={{ ...styles.td, ...styles.tableCell }}>{row.table}</td>
              <td style={{ ...styles.td, ...styles.fieldCell }}>{row.field}</td>
              <td style={{ ...styles.td, color: "#e0e6f0" }}>{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const styles = {
  wrapper: { marginTop: "20px" },
  title: {
    fontSize: "12px",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.8px",
    color: "#667",
    marginBottom: "8px",
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: "12px" },
  th: {
    textAlign: "left",
    padding: "8px 12px",
    background: "#0a1118",
    color: "#667",
    fontWeight: 600,
    fontSize: "11px",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    borderBottom: "1px solid #1a2535",
  },
  td: { padding: "7px 12px", borderBottom: "1px solid #111a28", color: "#8899bb" },
  tableCell: { color: "#4a90d9", fontWeight: 600, whiteSpace: "nowrap" },
  fieldCell: { color: "#aab", fontStyle: "italic" },
};
