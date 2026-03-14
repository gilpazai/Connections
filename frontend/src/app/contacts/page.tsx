"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { contacts as api, workHistory as whApi } from "@/lib/api";
import type { Contact } from "@/types";
import { StatusBadge } from "@/components/status-badge";
import { EnrichDialog } from "@/components/enrich-dialog";
import { WorkHistoryDialog } from "@/components/work-history-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

const STATUS_OPTIONS = ["Active", "Inactive"];
const STRENGTH_OPTIONS = ["Close", "Medium", "Loose"];

export default function ContactsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("Active");
  const [addOpen, setAddOpen] = useState(false);
  const [editedRows, setEditedRows] = useState<Record<string, Partial<Contact>>>({});
  const [enrichTarget, setEnrichTarget] = useState<{ name: string; pageId: string } | null>(null);
  const [historyTarget, setHistoryTarget] = useState<string | null>(null);

  const { data: contactsList = [], isLoading } = useQuery({
    queryKey: ["contacts", statusFilter],
    queryFn: () => api.list(statusFilter),
  });

  // Fetch grouped work history for all contacts in one call
  const { data: groupedWH = {} } = useQuery({
    queryKey: ["work-history", "Contact"],
    queryFn: () => whApi.grouped("Contact"),
  });

  const createMutation = useMutation({
    mutationFn: api.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      setAddOpen(false);
      toast.success("Contact created");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ pageId, data }: { pageId: string; data: Record<string, unknown> }) =>
      api.update(pageId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      toast.success("Saved");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ pageId, name }: { pageId: string; name: string }) =>
      api.delete(pageId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      toast.success("Contact deleted");
    },
  });

  function handleCellEdit(pageId: string, field: string, value: string) {
    setEditedRows((prev) => ({
      ...prev,
      [pageId]: { ...prev[pageId], [field]: value },
    }));
  }

  function handleSave() {
    const entries = Object.entries(editedRows);
    if (entries.length === 0) return;
    entries.forEach(([pageId, changes]) => {
      updateMutation.mutate({ pageId, data: changes });
    });
    setEditedRows({});
  }

  function handleSubmitAdd(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createMutation.mutate({
      name: form.get("name") as string,
      linkedin_url: form.get("linkedin_url") as string,
      company_current: form.get("company_current") as string,
      title_current: form.get("title_current") as string,
    });
  }

  if (isLoading) return <p className="text-muted-foreground">Loading contacts...</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Contacts</h1>
        <div className="flex gap-2">
          {STATUS_OPTIONS.map((s) => (
            <Button
              key={s}
              variant={statusFilter === s ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter(s)}
            >
              {s}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogTrigger render={<Button size="sm" />}>Add Contact</DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Contact</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmitAdd} className="space-y-3">
              <Input name="name" placeholder="Full name" required />
              <Input name="linkedin_url" placeholder="LinkedIn URL" />
              <Input name="company_current" placeholder="Company" />
              <Input name="title_current" placeholder="Title" />
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>

        {Object.keys(editedRows).length > 0 && (
          <Button size="sm" onClick={handleSave} disabled={updateMutation.isPending}>
            Save {Object.keys(editedRows).length} change(s)
          </Button>
        )}
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Title</TableHead>
            <TableHead>Strength</TableHead>
            <TableHead>Employment</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Notes</TableHead>
            <TableHead className="w-10"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {contactsList.map((c) => {
            const positions = groupedWH[c.name] ?? [];
            return (
              <TableRow key={c.notion_page_id}>
                <TableCell className="font-medium">
                  <div className="flex flex-col gap-0.5">
                    <span>{c.name}</span>
                    {c.linkedin_url && (
                      <a
                        href={c.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline"
                      >
                        LinkedIn
                      </a>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Input
                    defaultValue={c.company_current}
                    className="h-8 text-sm"
                    onBlur={(e) => {
                      if (e.target.value !== c.company_current)
                        handleCellEdit(c.notion_page_id, "company_current", e.target.value);
                    }}
                  />
                </TableCell>
                <TableCell>
                  <Input
                    defaultValue={c.title_current}
                    className="h-8 text-sm"
                    onBlur={(e) => {
                      if (e.target.value !== c.title_current)
                        handleCellEdit(c.notion_page_id, "title_current", e.target.value);
                    }}
                  />
                </TableCell>
                <TableCell>
                  <Select
                    defaultValue={c.relationship_strength}
                    onValueChange={(v) => v && handleCellEdit(c.notion_page_id, "relationship_strength", v)}
                  >
                    <SelectTrigger className="h-8 text-sm w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STRENGTH_OPTIONS.map((s) => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  {positions.length > 0 ? (
                    <button
                      onClick={() => setHistoryTarget(c.name)}
                      className="text-left"
                    >
                      <Badge variant="secondary" className="cursor-pointer hover:bg-secondary/80">
                        {positions.length} position{positions.length !== 1 ? "s" : ""}
                      </Badge>
                      <p className="text-xs text-muted-foreground mt-0.5 max-w-[140px] truncate">
                        {positions[0]?.employer_name}
                      </p>
                    </button>
                  ) : (
                    <span className="text-xs text-muted-foreground">Not enriched</span>
                  )}
                </TableCell>
                <TableCell>
                  <StatusBadge status={c.status} />
                </TableCell>
                <TableCell>
                  <Input
                    defaultValue={c.notes}
                    className="h-8 text-sm"
                    placeholder="Notes..."
                    onBlur={(e) => {
                      if (e.target.value !== c.notes)
                        handleCellEdit(c.notion_page_id, "notes", e.target.value);
                    }}
                  />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger render={<Button variant="ghost" size="sm" />}>...</DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem onClick={() => setHistoryTarget(c.name)}>
                        View History
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setEnrichTarget({ name: c.name, pageId: c.notion_page_id })}
                      >
                        Enrich
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => {
                          if (confirm(`Delete ${c.name}?`))
                            deleteMutation.mutate({ pageId: c.notion_page_id, name: c.name });
                        }}
                      >
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      {contactsList.length === 0 && (
        <p className="text-center text-muted-foreground py-8">No contacts found. Add one to get started.</p>
      )}

      {historyTarget && (
        <WorkHistoryDialog
          open={!!historyTarget}
          onOpenChange={(open) => { if (!open) setHistoryTarget(null); }}
          personName={historyTarget}
        />
      )}

      {enrichTarget && (
        <EnrichDialog
          open={!!enrichTarget}
          onOpenChange={(open) => { if (!open) setEnrichTarget(null); }}
          personName={enrichTarget.name}
          personType="Contact"
          notionPageId={enrichTarget.pageId}
        />
      )}
    </div>
  );
}
