"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { leads as api } from "@/lib/api";
import type { Lead } from "@/types";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

const STATUS_OPTIONS = ["All", "New", "Enriched", "Matched", "Contacted", "Converted", "Archived"];
const PRIORITY_OPTIONS = ["High", "Medium", "Low"];

export default function LeadsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("All");
  const [addOpen, setAddOpen] = useState(false);
  const [editedRows, setEditedRows] = useState<Record<string, Partial<Lead>>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: leadsList = [], isLoading } = useQuery({
    queryKey: ["leads", statusFilter],
    queryFn: () => api.list({ status: statusFilter !== "All" ? statusFilter : undefined }),
  });

  const createMutation = useMutation({
    mutationFn: api.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Lead created");
    },
  });

  const importCsvMutation = useMutation({
    mutationFn: ({ file, batch, priority }: { file: File; batch: string; priority: string }) =>
      api.importCsv(file, batch, priority),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Imported ${data.created} leads, ${data.skipped} skipped`);
      setAddOpen(false);
    },
  });

  const importPasteMutation = useMutation({
    mutationFn: ({ lines, batch, priority }: { lines: string[]; batch: string; priority: string }) =>
      api.importPaste(lines, batch, priority),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Imported ${data.created} leads, ${data.skipped} skipped`);
      setAddOpen(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ pageId, data }: { pageId: string; data: Record<string, unknown> }) =>
      api.update(pageId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Saved");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ pageId, name }: { pageId: string; name: string }) =>
      api.delete(pageId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success("Lead deleted");
    },
  });

  const archiveMutation = useMutation({
    mutationFn: api.archiveBatch,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Archived ${data.archived} leads`);
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

  function handleCsvUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    importCsvMutation.mutate({
      file,
      batch: form.get("batch") as string,
      priority: form.get("priority") as string || "Medium",
    });
  }

  function handlePasteImport(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const text = form.get("paste_text") as string;
    const lines = text.split("\n").filter((l) => l.trim());
    if (lines.length === 0) return;
    importPasteMutation.mutate({
      lines,
      batch: form.get("batch") as string,
      priority: form.get("priority") as string || "Medium",
    });
  }

  function handleAddSingle(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    createMutation.mutate({
      name: form.get("name") as string,
      linkedin_url: form.get("linkedin_url") as string,
      company_current: form.get("company_current") as string,
      title_current: form.get("title_current") as string,
      batch: form.get("batch") as string,
      priority: (form.get("priority") as string || "Medium") as Lead["priority"],
    });
    setAddOpen(false);
  }

  // Unique batches for archive
  const batches = [...new Set(leadsList.map((l) => l.batch).filter(Boolean))];

  if (isLoading) return <p className="text-muted-foreground">Loading leads...</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Leads</h1>
        <div className="flex gap-1 flex-wrap">
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

      {/* Status metrics */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        {["New", "Enriched", "Matched", "Contacted"].map((s) => (
          <span key={s}>{s}: {leadsList.filter((l) => l.status === s).length}</span>
        ))}
        <span>Total: {leadsList.length}</span>
      </div>

      <div className="flex gap-2">
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogTrigger render={<Button size="sm" />}>Import / Add</DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Import Leads</DialogTitle>
            </DialogHeader>
            <Tabs defaultValue="csv">
              <TabsList>
                <TabsTrigger value="csv">CSV Upload</TabsTrigger>
                <TabsTrigger value="paste">Paste List</TabsTrigger>
                <TabsTrigger value="single">Add Single</TabsTrigger>
              </TabsList>
              <TabsContent value="csv">
                <form onSubmit={handleCsvUpload} className="space-y-3">
                  <div>
                    <Label>CSV File</Label>
                    <Input type="file" accept=".csv" ref={fileInputRef} required />
                  </div>
                  <Input name="batch" placeholder="Batch label (e.g. 2026-03)" />
                  <Select name="priority" defaultValue="Medium">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PRIORITY_OPTIONS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Button type="submit" disabled={importCsvMutation.isPending}>
                    {importCsvMutation.isPending ? "Importing..." : "Import CSV"}
                  </Button>
                </form>
              </TabsContent>
              <TabsContent value="paste">
                <form onSubmit={handlePasteImport} className="space-y-3">
                  <Textarea name="paste_text" placeholder="One name per line..." rows={6} />
                  <Input name="batch" placeholder="Batch label" />
                  <Select name="priority" defaultValue="Medium">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PRIORITY_OPTIONS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Button type="submit" disabled={importPasteMutation.isPending}>
                    {importPasteMutation.isPending ? "Importing..." : "Import"}
                  </Button>
                </form>
              </TabsContent>
              <TabsContent value="single">
                <form onSubmit={handleAddSingle} className="space-y-3">
                  <Input name="name" placeholder="Full name" required />
                  <Input name="linkedin_url" placeholder="LinkedIn URL" />
                  <Input name="company_current" placeholder="Company" />
                  <Input name="title_current" placeholder="Title" />
                  <Input name="batch" placeholder="Batch label" />
                  <Select name="priority" defaultValue="Medium">
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PRIORITY_OPTIONS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Button type="submit" disabled={createMutation.isPending}>Add Lead</Button>
                </form>
              </TabsContent>
            </Tabs>
          </DialogContent>
        </Dialog>

        {batches.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}>Archive Batch</DropdownMenuTrigger>
            <DropdownMenuContent>
              {batches.map((b) => (
                <DropdownMenuItem key={b} onClick={() => {
                  if (confirm(`Archive all leads in batch "${b}"?`)) archiveMutation.mutate(b);
                }}>
                  {b}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

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
            <TableHead>Priority</TableHead>
            <TableHead>Batch</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Notes</TableHead>
            <TableHead className="w-10"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leadsList.map((l) => (
            <TableRow key={l.notion_page_id}>
              <TableCell className="font-medium">{l.name}</TableCell>
              <TableCell>
                <Input
                  defaultValue={l.company_current}
                  className="h-8 text-sm"
                  onBlur={(e) => {
                    if (e.target.value !== l.company_current)
                      handleCellEdit(l.notion_page_id, "company_current", e.target.value);
                  }}
                />
              </TableCell>
              <TableCell>
                <Input
                  defaultValue={l.title_current}
                  className="h-8 text-sm"
                  onBlur={(e) => {
                    if (e.target.value !== l.title_current)
                      handleCellEdit(l.notion_page_id, "title_current", e.target.value);
                  }}
                />
              </TableCell>
              <TableCell>
                <Select
                  defaultValue={l.priority}
                  onValueChange={(v) => v && handleCellEdit(l.notion_page_id, "priority", v)}
                >
                  <SelectTrigger className="h-8 text-sm w-20">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PRIORITY_OPTIONS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell className="text-sm">{l.batch || "-"}</TableCell>
              <TableCell><StatusBadge status={l.status} /></TableCell>
              <TableCell>
                <Input
                  defaultValue={l.notes}
                  className="h-8 text-sm"
                  placeholder="Notes..."
                  onBlur={(e) => {
                    if (e.target.value !== l.notes)
                      handleCellEdit(l.notion_page_id, "notes", e.target.value);
                  }}
                />
              </TableCell>
              <TableCell>
                <DropdownMenu>
                  <DropdownMenuTrigger render={<Button variant="ghost" size="sm" />}>...</DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem
                      className="text-destructive"
                      onClick={() => {
                        if (confirm(`Delete ${l.name}?`))
                          deleteMutation.mutate({ pageId: l.notion_page_id, name: l.name });
                      }}
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {leadsList.length === 0 && (
        <p className="text-center text-muted-foreground py-8">No leads found. Import a batch to get started.</p>
      )}
    </div>
  );
}
