"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { research as researchApi, enrichment as enrichApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function ResearchPage() {
  const [personName, setPersonName] = useState("");
  const [company, setCompany] = useState("");
  const [report, setReport] = useState("");

  const researchMutation = useMutation({
    mutationFn: () => researchApi.run(personName, company),
    onSuccess: (data) => {
      setReport(data.report);
      if (data.cached) toast.info("Loaded cached report");
      else toast.success("Research complete");
    },
    onError: (err) => toast.error(`Research failed: ${err.message}`),
  });

  const extractMutation = useMutation({
    mutationFn: () =>
      enrichApi.enrich({
        person_name: personName,
        person_type: "Lead",
        raw_text: report,
      }),
    onSuccess: (data) => {
      toast.success(`Extracted ${data.positions_stored} positions, ${data.new_matches} new matches`);
    },
    onError: (err) => toast.error(`Extraction failed: ${err.message}`),
  });

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-2xl font-bold">Research</h1>
      <p className="text-muted-foreground">
        Run AI-powered web research to discover background information about a person.
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Research a Person</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label>Person Name</Label>
            <Input
              value={personName}
              onChange={(e) => setPersonName(e.target.value)}
              placeholder="e.g. John Smith"
            />
          </div>
          <div>
            <Label>Company (optional)</Label>
            <Input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="e.g. Acme Ventures"
            />
          </div>
          <Button
            onClick={() => researchMutation.mutate()}
            disabled={!personName.trim() || researchMutation.isPending}
          >
            {researchMutation.isPending ? "Researching..." : "Run Research"}
          </Button>
        </CardContent>
      </Card>

      {report && (
        <>
          <Separator />
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Report: {personName}</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() => extractMutation.mutate()}
              disabled={extractMutation.isPending}
            >
              {extractMutation.isPending ? "Extracting..." : "Extract Work History"}
            </Button>
          </div>
          <Card>
            <CardContent className="prose prose-sm max-w-none pt-6">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
