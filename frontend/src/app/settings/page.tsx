"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settings as settingsApi, matches as matchesApi, leads as leadsApi } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { useState } from "react";

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

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Tabs defaultValue="connectivity">
        <TabsList>
          <TabsTrigger value="connectivity">Connectivity</TabsTrigger>
          <TabsTrigger value="llm">LLM</TabsTrigger>
          <TabsTrigger value="data">Data Management</TabsTrigger>
        </TabsList>

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

        <TabsContent value="llm" className="space-y-4">
          <h2 className="text-lg font-semibold">LLM Configuration</h2>
          {llmConfig ? (
            <Card>
              <CardContent className="pt-6">
                <div className="flex gap-8">
                  <div>
                    <span className="text-sm text-muted-foreground">Provider</span>
                    <p className="font-medium">{llmConfig.provider}</p>
                  </div>
                  <div>
                    <span className="text-sm text-muted-foreground">Model</span>
                    <p className="font-medium">{llmConfig.model}</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-4">
                  LLM settings are configured via environment variables on the backend.
                </p>
              </CardContent>
            </Card>
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
