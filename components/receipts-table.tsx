"use client";

import { useEffect, useState } from "react";

export function ReceiptsTable() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/receipts");
        const json = await res.json();
        setData(json);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading receipts...</div>;
  }

  if (data.length === 0) {
    return (
      <div className="text-sm text-muted-foreground border rounded-lg p-6">
        No receipts found. Upload a file to get started.
      </div>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead className="border-b">
        <tr>
          <th className="text-left py-2">Date</th>
          <th className="text-left py-2">Vendor</th>
          <th className="text-left py-2">Amount</th>
          <th className="text-left py-2">Category</th>
          <th className="text-left py-2">Status</th>
        </tr>
      </thead>
      <tbody>
        {data.map((r) => (
          <tr key={r.id} className="border-b hover:bg-accent">
            <td className="py-2">{r.date || "-"}</td>
            <td className="py-2">{r.vendor || "Unknown"}</td>
            <td className="py-2">{r.amount ? `${r.amount} ${r.currency}` : "-"}</td>
            <td className="py-2">{r.category || "-"}</td>
            <td className="py-2">{r.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}