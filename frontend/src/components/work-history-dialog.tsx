"use client";

import { useQuery } from "@tanstack/react-query";
import { workHistory as whApi } from "@/lib/api";
import type { WorkHistoryEntry } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

interface WorkHistoryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  personName: string;
}

function formatDate(d: string | null): string {
  if (!d) return "Present";
  return d.slice(0, 7); // YYYY-MM
}

export function WorkHistoryDialog({ open, onOpenChange, personName }: WorkHistoryDialogProps) {
  const { data: entries = [], isLoading } = useQuery({
    queryKey: ["work-history", personName],
    queryFn: () => whApi.forPerson(personName),
    enabled: open && !!personName,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{personName} — Work History</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <p className="text-muted-foreground text-sm">Loading...</p>
        ) : entries.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No work history found. Use Enrich to add work history for this person.
          </p>
        ) : (
          <ol className="space-y-3">
            {entries.map((e: WorkHistoryEntry, i: number) => (
              <li key={e.notion_page_id || i} className="flex gap-3">
                <div className="w-1 rounded-full bg-border flex-shrink-0 mt-1" />
                <div className="space-y-0.5 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-sm truncate">{e.employer_name}</span>
                    {e.is_advisory && (
                      <Badge variant="outline" className="text-xs">Advisory</Badge>
                    )}
                    <Badge variant="secondary" className="text-xs">{e.seniority}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{e.role_title}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(e.start_date)} – {formatDate(e.end_date)}
                    {e.tenure_years > 0 && ` · ${e.tenure_years.toFixed(1)}y`}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}
