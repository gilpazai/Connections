"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/contacts", label: "Contacts" },
  { href: "/leads", label: "Leads" },
  { href: "/matches", label: "Matches" },
  { href: "/research", label: "Research" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 border-r bg-muted/40 min-h-screen p-4 flex flex-col gap-1">
      <h1 className="text-lg font-semibold mb-6 px-2">VC Connections</h1>
      {NAV_ITEMS.map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent",
            pathname.startsWith(href) ? "bg-accent text-accent-foreground" : "text-muted-foreground",
          )}
        >
          {label}
        </Link>
      ))}
    </aside>
  );
}
