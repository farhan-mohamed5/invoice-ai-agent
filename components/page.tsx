export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Dashboard Overview</h2>

      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border p-4">Total Receipts</div>
        <div className="rounded-lg border p-4">Monthly Spend</div>
        <div className="rounded-lg border p-4">Average Amount</div>
      </div>

      <div className="rounded-lg border p-6 mt-4">
        <p className="text-sm text-muted-foreground">
          Activity feed and analytics will appear here.
        </p>
      </div>
    </div>
  );
}