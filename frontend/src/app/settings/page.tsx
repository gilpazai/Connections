"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settings as settingsApi, matches as matchesApi, leads as leadsApi } from "@/lib/api";
import type { LLMConfig, EnrichmentConfig } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useState, useEffect } from "react";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [confirmDeleteLeads, setConfirmDeleteLeads] = useState(false);
  const [confirmDeleteMatches, setConfirmDeleteMatches] = useState(false);

  const { data: connectivity } = useQuery({
    queryKey: ["settings", "connectivity"],
    queryFn: settingsApi.connectivity,
  });

  const { data: llmConfig } = useQuery({
    queryKey: ["settings", "llm"],
    queryFn: settingsApi.llm,
  });

  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");

  useEffect(() => {
    if (llmConfig && !provider) {
      setProvider(llmConfig.provider);
      setModel(llmConfig.model);
    }
  }, [llmConfig, provider]);

  const { data: enrichmentConfig } = useQuery({
    queryKey: ["settings", "enrichment"],
    queryFn: settingsApi.enrichment,
  });

  const [batchSize, setBatchSize] = useState<number | "">(5);

  useEffect(() => {
    if (enrichmentConfig && batchSize === 5) {
      setBatchSize(enrichmentConfig.batch_size);
    }
  }, [enrichmentConfig, batchSize]);

  const saveEnrichmentMutation = useMutation({
    mutationFn: () => settingsApi.updateEnrichment(batchSize as number),
    onSuccess: (data: EnrichmentConfig) => {
      queryClient.setQueryData(["settings", "enrichment"], data);
      toast.success(`Enrichment batch size set to ${data.batch_size}`);
    },
    onError: (err) => toast.error(`Save failed: ${err.message}`),
  });

  const isEnrichmentDirty = enrichmentConfig && batchSize !== enrichmentConfig.batch_size;

  const saveLlmMutation = useMutation({
    mutationFn: () => settingsApi.updateLlm(provider, model),
    onSuccess: (data: LLMConfig) => {
      queryClient.setQueryData(["settings", "llm"], data);
      toast.success(`LLM updated to ${data.provider} / ${data.model}`);
    },
    onError: (err) => toast.error(`Save failed: ${err.message}`),
  });

  const deleteLeadsMutation = useMutation({
    mutationFn: leadsApi.deleteAll,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Archived ${data.deleted} leads`);
      setConfirmDeleteLeads(false);
    },
  });

  const deleteMatchesMutation = useMutation({
    mutationFn: matchesApi.deleteAll,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["matches"] });
      toast.success(`Archived ${data.deleted} matches`);
      setConfirmDeleteMatches(false);
    },
  });

  const isDirty = llmConfig && (provider !== llmConfig.provider || model !== llmConfig.model);

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Tabs defaultValue="llm">
        <TabsList>
          <TabsTrigger value="llm">LLM</TabsTrigger>
          <TabsTrigger value="enrichment">Enrichment</TabsTrigger>
          <TabsTrigger value="connectivity">Connectivity</TabsTrigger>
          <TabsTrigger value="data">Data Management</TabsTrigger>
        </TabsList>

        <TabsContent value="llm" className="space-y-4">
          <h2 className="text-lg font-semibold">LLM Configuration</h2>
          {llmConfig ? (
            <Card>
              <CardContent className="pt-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <Label>Provider</Label>
                    <Select
                      value={provider}
                      onValueChange={(v) => {
                        if (!v) return;
                        setProvider(v);
                        const first = llmConfig.available_models[v]?.[0] ?? "";
                        setModel(first);
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(llmConfig.available_providers ?? []).map((p) => (
                          <SelectItem key={p} value={p}>
                            {p.charAt(0).toUpperCase() + p.slice(1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label>Model</Label>
                    <Select
                      value={model}
                      onValueChange={(v) => v && setModel(v)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(llmConfig.available_models[provider] ?? (model ? [model] : [])).map((m) => (
                          <SelectItem key={m} value={m}>{m}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    onClick={() => saveLlmMutation.mutate()}
                    disabled={!isDirty || saveLlmMutation.isPending}
                  >
                    {saveLlmMutation.isPending ? "Saving..." : "Save"}
                  </Button>
                  {isDirty && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setProvider(llmConfig.provider);
                        setModel(llmConfig.model);
                      }}
                    >
                      Reset
                    </Button>
                  )}
                  {!isDirty && (
                    <p className="text-xs text-muted-foreground">
                      Changes take effect immediately and persist to .env
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          ) : (
            <p className="text-muted-foreground">Loading...</p>
          )}
        </TabsContent>

        <TabsContent value="enrichment" className="space-y-4">
          <h2 className="text-lg font-semibold">Enrichment Settings</h2>
          <Card>
            <CardContent className="pt-6 space-y-4">
              <div className="space-y-1 max-w-xs">
                <Label htmlFor="batch-size">LinkedIn Batch Size</Label>
                <p className="text-xs text-muted-foreground">
                  How many profiles to enrich per LinkedIn session. Shown as the default in the enrich dialog and overridable per session.
                </p>
                <Input
                  id="batch-size"
                  type="number"
                  min={1}
                  max={50}
                  value={batchSize}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    setBatchSize(isNaN(v) ? "" : v);
                  }}
                  className="w-24"
                />
              </div>
              <div className="flex items-center gap-3">
                <Button
                  onClick={() => saveEnrichmentMutation.mutate()}
                  disabled={!isEnrichmentDirty || !batchSize || saveEnrichmentMutation.isPending}
                >
                  {saveEnrichmentMutation.isPending ? "Saving..." : "Save"}
                </Button>
                {isEnrichmentDirty && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setBatchSize(enrichmentConfig!.batch_size)}
                  >
                    Reset
                  </Button>
                )}
                {!isEnrichmentDirty && enrichmentConfig && (
                  <p className="text-xs text-muted-foreground">
                    Default batch size: {enrichmentConfig.batch_size}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="connectivity" className="space-y-4">
          <h2 className="text-lg font-semibold">API Connectivity</h2>
          {connectivity ? (
            <div className="grid grid-cols-5 gap-4">
              <MetricCard title="Notion" value={connectivity.notion ? "Connected" : "Not configured"} />
              <MetricCard title="Anthropic" value={connectivity.anthropic ? "Connected" : "Not configured"} />
              <MetricCard title="Gemini" value={connectivity.gemini ? "Connected" : "Not configured"} />
              <MetricCard title="OpenAI" value={connectivity.openai ? "Connected" : "Not configured"} />
              <MetricCard title="Ollama" value={connectivity.ollama ? "Running" : "Not running"} />
            </div>
          ) : (
            <p className="text-muted-foreground">Loading...</p>
          )}
        </TabsContent>

        <TabsContent value="data" className="space-y-4">
          <h2 className="text-lg font-semibold">Data Management</h2>
          <p className="text-sm text-muted-foreground">
            These operations affect all data in Notion. Pages are archived (recoverable from Notion trash).
          </p>
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Delete All Leads</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={confirmDeleteLeads}
                    onChange={(e) => setConfirmDeleteLeads(e.target.checked)}
                  />
                  I understand this archives all leads
                </label>
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={!confirmDeleteLeads || deleteLeadsMutation.isPending}
                  onClick={() => deleteLeadsMutation.mutate()}
                >
                  {deleteLeadsMutation.isPending ? "Deleting..." : "Delete All Leads"}
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Reset Matches</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={confirmDeleteMatches}
                    onChange={(e) => setConfirmDeleteMatches(e.target.checked)}
                  />
                  I understand this archives all matches
                </label>
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={!confirmDeleteMatches || deleteMatchesMutation.isPending}
                  onClick={() => deleteMatchesMutation.mutate()}
                >
                  {deleteMatchesMutation.isPending ? "Deleting..." : "Reset All Matches"}
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
