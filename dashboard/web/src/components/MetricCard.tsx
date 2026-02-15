interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: "green" | "red" | "blue" | "yellow" | "gray";
}

const colorMap = {
  green: "text-green-400",
  red: "text-red-400",
  blue: "text-blue-400",
  yellow: "text-yellow-400",
  gray: "text-gray-400",
};

export default function MetricCard({ label, value, subtitle, color = "blue" }: MetricCardProps) {
  return (
    <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
      <p className="text-gray-400 text-sm mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colorMap[color]}`}>{value}</p>
      {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
    </div>
  );
}
