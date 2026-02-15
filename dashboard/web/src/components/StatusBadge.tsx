interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

const statusStyles: Record<string, string> = {
  healthy: "bg-green-900 text-green-300 border-green-700",
  running: "bg-green-900 text-green-300 border-green-700",
  active: "bg-red-900 text-red-300 border-red-700",
  unhealthy: "bg-red-900 text-red-300 border-red-700",
  unreachable: "bg-red-900 text-red-300 border-red-700",
  degraded: "bg-yellow-900 text-yellow-300 border-yellow-700",
  executed: "bg-blue-900 text-blue-300 border-blue-700",
  detected: "bg-gray-700 text-gray-300 border-gray-600",
  failed: "bg-red-900 text-red-300 border-red-700",
};

export default function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const style = statusStyles[status.toLowerCase()] || "bg-gray-700 text-gray-300 border-gray-600";
  const sizeClass = size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-3 py-1";

  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${style} ${sizeClass}`}>
      {status}
    </span>
  );
}
