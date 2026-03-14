"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { matches as api } from "@/lib/api";
import type { Match } from "@/types";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";

const STATUS_OPTIONS = ["All", "New", "Request Intro", "Intro", "In CRM"];
const CONFIDENCE_OPTIONS = ["All", "High", "Medium", "Low"];
const MATCH_STATUS_VALUES = ["New", "Request Intro", "Intro", "In CRM"];

export default function MatchesPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("All");
  const [confidenceFilter, setConfidenceFilter] = useState("All");
  const [editedRows, setEditedRows] = useState<Record<string, Partial<Match>>>({});

  const { data: matchesList = [], isLoading } = useQuery({
    queryKey: ["matches", statusFilter, confidenceFilter],
    queryFn: () =>
      api.list({
        status: statusFilter !== "All" ? statusFilter : undefined,
        confidence: confidenceFilter !== "All" ? confidenceFilter : undefined,
      }),
  });

  // All matches for pipeline metrics
  const { data: allMatches = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: () => api.list(),
  });

  const recheckMutation = useMutation({
    mutationFn: api.recheck,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["matches"] });
      toast.success(`Recheck done: ${data.created} new, ${data.skipped} skipped`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ pageId, data }: { pageId: string; data: Record<string, unknown> }) =>
      api.update(pageId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["matches"] });
      toast.success("Saved");
    },
  });

  function handleCellEdit(pageId: string, field: string, value: string) {
    setEditedRows((prev) => ({
      ...prev,
      [pageId]: { ...prev[pageId], [field]: value },
    }));
  }

  function handleSave() {
    Object.entries(editedRows).forEach(([pageId, changes]) => {
      updateMutation.mutate({ pageId, data: changes });
    });
    setEditedRows({});
  }

  if (isLoading) return <p className="text-muted-foreground">Loading matches...</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Matches</h1>
        <Button
          variant="outline"
          size="sm"
          onClick={() => recheckMutation.mutate()}
          disabled={recheckMutation.isPending}
        >
          {recheckMutation.isPending ? "Checking..." : "Recheck All"}
        </Button>
      </div>

      {/* Pipeline metrics */}
      <div className="grid grid-cols-4 gap-4">
        {MATCH_STATUS_VALUES.map((s) => (
          <MetricCard key={s} title={s} value={allMatches.filter((m) => m.status === s).length} />
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-2 items-center">
        <span className="text-sm text-muted-foreground">Status:</span>
        {STATUS_OPTIONS.map((s) => (
          <Button key={s} variant={statusFilter === s ? "default" : "outline"} size="sm" onClick={() => setStatusFilter(s)}>
            {s}
          </Button>
        ))}
        <span className="text-sm text-muted-foreground ml-4">Confidence:</span>
        {CONFIDENCE_OPTIONS.map((c) => (
          <Button key={c} variant={confidenceFilter === c ? "default" : "outline"} size="sm" onClick={() => setConfidenceFilter(c)}>
            {c}
          </Button>
        ))}
      </div>

      {Object.keys(editedRows).length > 0 && (
        <Button size="sm" onClick={handleSave} disabled={updateMutation.isPending}>
          Save {Object.keys(editedRows).length} change(s)
        </Button>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Contact</TableHead>
            <TableHead>Lead</TableHead>
            <TableHead>Shared Company</TableHead>
            <TableHead>Overlap</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Notes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {matchesList.map((m) => (
            <TableRow key={m.notion_page_id}>
              <TableCell>
                <div className="font-medium">{m.contact_name}</div>
                {m.contact_role && <div className="text-xs text-muted-foreground">{m.contact_role}</div>}
              </TableCell>
              <TableCell>
                <div className="font-medium">{m.lead_name}</div>
                {m.lead_role && <div className="text-xs text-muted-foreground">{m.lead_role}</div>}
              </TableCell>
              <TableCell>{m.shared_company}</TableCell>
              <TableCell>{m.overlap_months}mo</TableCell>
              <TableCell><StatusBadge status={m.confidence} /></TableCell>
              <TableCell>
                <Select
                  defaultValue={m.status}
                  onValueChange={(v) => v && handleCellEdit(m.notion_page_id, "status", v)}
                >
                  <SelectTrigger className="h-8 text-sm w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MATCH_STATUS_VALUES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <Input
                  defaultValue={m.notes}
                  className="h-8 text-sm"
                  placeholder="Notes..."
                  onBlur={(e) => {
                    if (e.target.value !== m.notes) handleCellEdit(m.notion_page_id, "notes", e.target.value);
                  }}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {matchesList.length === 0 && (
        <p className="text-center text-muted-foreground py-8">No matches found. Enrich contacts and leads to discover connections.</p>
      )}
    </div>
  );
}
