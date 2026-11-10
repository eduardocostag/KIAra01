"use client";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ContentConsole } from "./content-console";
import { PostizConsole } from "./postiz-console";
export function ContentWorkspace() {
  return <Tabs defaultValue="automatic" className="min-w-0 space-y-4"><TabsList className="max-w-full"><TabsTrigger value="automatic">Publicar e agendar</TabsTrigger><TabsTrigger value="assisted">Preparar conteúdo</TabsTrigger></TabsList><TabsContent value="automatic"><PostizConsole /></TabsContent><TabsContent value="assisted"><ContentConsole /></TabsContent></Tabs>;
}
