import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STATUS_COLORS: Record<string, string> = {
  Active: "bg-green-100 text-green-800",
  Inactive: "bg-gray-100 text-gray-800",
  New: "bg-blue-100 text-blue-800",
  Enriched: "bg-indigo-100 text-indigo-800",
  Matched: "bg-purple-100 text-purple-800",
  Contacted: "bg-yellow-100 text-yellow-800",
  Converted: "bg-green-100 text-green-800",
  Archived: "bg-gray-100 text-gray-800",
  "Request Intro": "bg-amber-100 text-amber-800",
  Intro: "bg-orange-100 text-orange-800",
  "In CRM": "bg-emerald-100 text-emerald-800",
  High: "bg-red-100 text-red-800",
  Medium: "bg-yellow-100 text-yellow-800",
  Low: "bg-green-100 text-green-800",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant="secondary" className={cn("font-normal", STATUS_COLORS[status])}>
      {status}
    </Badge>
  );
}
