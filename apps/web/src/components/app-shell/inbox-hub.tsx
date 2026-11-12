"use client"

import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PipelineBoard } from "./pipeline-board"
import { LeadOperationsWorkspace } from "./lead-operations-workspace"
import type { PipelineEntry } from "@/lib/api/pipeline"

/** Contacts (list + editable panel) and the daily outreach queue, over one shared CRM state. */
export function InboxHub({ entries: initialEntries, prospectError, initialView, initialContactId }: { entries: PipelineEntry[]; prospectError: string; initialView: string; initialContactId: string }) {
  const [entries, setEntries] = useState(initialEntries)
  const [view, setView] = useState(initialView === "conversations" || initialView === "queue" ? "queue" : "contacts")
  const [focusId, setFocusId] = useState(() => initialEntries.find((entry) => entry.id === initialContactId || entry.consumer.id === initialContactId)?.id ?? "")

  if (prospectError) return <p role="alert" className="rounded-lg border border-destructive/30 p-4 text-sm text-destructive">{prospectError}</p>

  return <Tabs value={view} onValueChange={setView} className="gap-4">
    <TabsList aria-label="Visualização dos contatos" className="w-fit">
      <TabsTrigger value="contacts" className="px-4">Contatos</TabsTrigger>
      <TabsTrigger value="queue" className="px-4">Fila do dia</TabsTrigger>
    </TabsList>
    {/* Inactive tabs unmount, so the board picks up focusId each time it is shown. */}
    <TabsContent value="contacts"><PipelineBoard entries={entries} onEntriesChange={setEntries} initialSelectedId={focusId} /></TabsContent>
    <TabsContent value="queue"><LeadOperationsWorkspace entries={entries} onOpen={(id) => { setFocusId(id); setView("contacts") }} /></TabsContent>
  </Tabs>
}
