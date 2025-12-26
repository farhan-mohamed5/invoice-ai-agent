"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { name: "Dashboard", href: "/dashboard" },
  { name: "Receipts", href: "/receipts" },
  { name: "Upload", href: "/upload" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-full w-56 border-r bg-background p-4">
      <h1 className="text-xl font-bold mb-6">Receipt Agent</h1>

      <nav className="flex flex-col gap-2">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "rounded-md px-3 py-2 text-sm hover:bg-accent",
              pathname.startsWith(link.href) && "bg-accent font-medium"
            )}
          >
            {link.name}
          </Link>
        ))}
      </nav>
    </aside>
  );
}