"use client";

import { useQuery } from "@tanstack/react-query";
import { contacts as contactsApi, leads as leadsApi, matches as matchesApi } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function DashboardPage() {
  const { data: contactsList = [] } = useQuery({
    queryKey: ["contacts", "Active"],
    queryFn: () => contactsApi.list("Active"),
  });

  const { data: leadsList = [] } = useQuery({
    queryKey: ["leads"],
    queryFn: () => leadsApi.list(),
  });

  const { data: matchesList = [] } = useQuery({
    queryKey: ["matches"],
    queryFn: () => matchesApi.list(),
  });

  const unenrichedContacts = contactsList.filter((c) => !c.last_enriched);
  const unenrichedLeads = leadsList.filter((l) => !l.last_enriched);
  const recentMatches = matchesList.slice(0, 20);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard title="Active Contacts" value={contactsList.length} />
        <MetricCard title="Active Leads" value={leadsList.length} />
        <MetricCard title="Total Matches" value={matchesList.length} />
        <MetricCard
          title="Unenriched"
          value={unenrichedContacts.length + unenrichedLeads.length}
          description={`${unenrichedContacts.length} contacts, ${unenrichedLeads.length} leads`}
        />
      </div>

      {/* Pipeline */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Match Pipeline</h2>
        <div className="grid grid-cols-4 gap-4">
          {["New", "Request Intro", "Intro", "In CRM"].map((status) => (
            <MetricCard
              key={status}
              title={status}
              value={matchesList.filter((m) => m.status === status).length}
            />
          ))}
        </div>
      </div>

      {/* Recent Matches */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Recent Matches</h2>
        {recentMatches.length === 0 ? (
          <p className="text-muted-foreground">No matches yet. Enrich contacts and leads to discover connections.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Contact</TableHead>
                <TableHead>Lead</TableHead>
                <TableHead>Shared Company</TableHead>
                <TableHead>Overlap</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentMatches.map((m) => (
                <TableRow key={m.notion_page_id}>
                  <TableCell className="font-medium">{m.contact_name}</TableCell>
                  <TableCell>{m.lead_name}</TableCell>
                  <TableCell>{m.shared_company}</TableCell>
                  <TableCell>{m.overlap_months}mo</TableCell>
                  <TableCell><StatusBadge status={m.confidence} /></TableCell>
                  <TableCell><StatusBadge status={m.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
