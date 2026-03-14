"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/contacts", label: "Contacts" },
  { href: "/leads", label: "Leads" },
  { href: "/matches", label: "Matches" },
  { href: "/enrich", label: "Enrich" },
  { href: "/research", label: "Research" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();

  if (pathname === "/login") return null;

  return (
    <aside className="w-56 border-r bg-muted/40 min-h-screen p-4 flex flex-col">
      <h1 className="text-lg font-semibold mb-6 px-2">VC Connections</h1>
      <nav className="flex flex-col gap-1 flex-1">
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
      </nav>
      {session?.user && (
        <div className="border-t pt-3 mt-3 px-2">
          <p className="text-xs text-muted-foreground truncate">{session.user.email}</p>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="text-xs text-muted-foreground hover:text-foreground mt-1"
          >
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
