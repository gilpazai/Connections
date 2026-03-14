"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { contacts as contactsApi, leads as leadsApi, enrichment as enrichApi } from "@/lib/api";
import type { Contact, Lead } from "@/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

export default function EnrichPage() {
  const queryClient = useQueryClient();
  const [selectedPerson, setSelectedPerson] = useState("");
  const [rawText, setRawText] = useState("");

  const { data: contactsList = [] } = useQuery({
    queryKey: ["contacts", "Active"],
    queryFn: () => contactsApi.list("Active"),
  });

  const { data: leadsList = [] } = useQuery({
    queryKey: ["leads", "enrichable"],
    queryFn: () => leadsApi.list(),
  });

  // Build a unified person list for the selector
  const people = [
    ...contactsList.map((c: Contact) => ({
      key: `Contact:${c.notion_page_id}`,
      label: `${c.name} (Contact)`,
      name: c.name,
      type: "Contact" as const,
      pageId: c.notion_page_id,
      enriched: !!c.last_enriched,
    })),
    ...leadsList.map((l: Lead) => ({
      key: `Lead:${l.notion_page_id}`,
      label: `${l.name} (Lead)`,
      name: l.name,
      type: "Lead" as const,
      pageId: l.notion_page_id,
      enriched: !!l.last_enriched,
    })),
  ];

  const selected = people.find((p) => p.key === selectedPerson);

  const enrichMutation = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("No person selected");
      return enrichApi.enrich({
        person_name: selected.name,
        person_type: selected.type,
        raw_text: rawText,
        notion_page_id: selected.pageId,
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["matches"] });
      queryClient.invalidateQueries({ queryKey: ["work-history"] });
      toast.success(
        `Enriched ${selected?.name}: ${data.positions_stored} positions, ${data.new_matches} new matches`
      );
      setRawText("");
    },
    onError: (err) => toast.error(`Enrichment failed: ${err.message}`),
  });

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-2xl font-bold">Enrich</h1>
      <p className="text-muted-foreground">
        Paste LinkedIn experience text to extract work history and auto-discover matches.
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Manual Enrichment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Select Person</Label>
            <Select value={selectedPerson} onValueChange={(v) => v && setSelectedPerson(v)}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a contact or lead..." />
              </SelectTrigger>
              <SelectContent>
                {people.length === 0 && (
                  <SelectItem value="_none" disabled>No contacts or leads</SelectItem>
                )}
                {people.map((p) => (
                  <SelectItem key={p.key} value={p.key}>
                    {p.label}{p.enriched ? " [enriched]" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>LinkedIn Experience Text</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Go to their LinkedIn profile, select all text in the Experience section, copy, and paste below.
            </p>
            <Textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste LinkedIn experience text here..."
              rows={14}
            />
            {rawText.length > 0 && (
              <p className="text-xs text-muted-foreground mt-1">
                {rawText.split("\n").filter(Boolean).length} lines pasted
              </p>
            )}
          </div>

          <Button
            onClick={() => enrichMutation.mutate()}
            disabled={!selected || !rawText.trim() || enrichMutation.isPending}
          >
            {enrichMutation.isPending ? "Enriching..." : "Enrich"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
