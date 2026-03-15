"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { enrichment as enrichApi, settings as settingsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";

interface EnrichDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  personName: string;
  personType: "Contact" | "Lead";
  notionPageId: string;
}

export function EnrichDialog({
  open,
  onOpenChange,
  personName,
  personType,
  notionPageId,
}: EnrichDialogProps) {
  const queryClient = useQueryClient();
  const [rawText, setRawText] = useState("");
  const [batchSize, setBatchSize] = useState<number>(5);

  const { data: enrichmentConfig } = useQuery({
    queryKey: ["settings", "enrichment"],
    queryFn: settingsApi.enrichment,
  });

  useEffect(() => {
    if (enrichmentConfig) setBatchSize(enrichmentConfig.batch_size);
  }, [enrichmentConfig]);

  const enrichMutation = useMutation({
    mutationFn: () =>
      enrichApi.enrich({
        person_name: personName,
        person_type: personType,
        raw_text: rawText,
        notion_page_id: notionPageId,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["contacts"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["matches"] });
      queryClient.invalidateQueries({ queryKey: ["work-history"] });
      toast.success(
        `Enriched ${personName}: ${data.positions_stored} positions, ${data.new_matches} new matches`
      );
      setRawText("");
      onOpenChange(false);
    },
    onError: (err) => toast.error(`Enrichment failed: ${err.message}`),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Enrich: {personName}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>LinkedIn Experience Text</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Copy the experience section from their LinkedIn profile and paste below.
            </p>
            <Textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste LinkedIn experience text here..."
              rows={12}
            />
          </div>
          <div className="flex justify-between items-end">
            <div className="space-y-1">
              <Label htmlFor="enrich-batch-size" className="text-xs">Batch size</Label>
              <div className="flex items-center gap-1.5">
                <Input
                  id="enrich-batch-size"
                  type="number"
                  min={1}
                  max={50}
                  value={batchSize}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (!isNaN(v) && v >= 1) setBatchSize(v);
                  }}
                  className="h-7 w-16 text-sm"
                />
                <span className="text-xs text-muted-foreground">per session</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {rawText.length > 0 ? `${rawText.split("\n").filter(Boolean).length} lines` : ""}
              </span>
              <Button
                onClick={() => enrichMutation.mutate()}
                disabled={!rawText.trim() || enrichMutation.isPending}
              >
                {enrichMutation.isPending ? "Enriching..." : "Enrich"}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
