"use client";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ContentConsole } from "./content-console";
import { PostizConsole } from "./postiz-console";
export function ContentWorkspace() {
  return <Tabs defaultValue="automatic" className="space-y-4"><TabsList><TabsTrigger value="automatic">Publicação automática</TabsTrigger><TabsTrigger value="assisted">Conteúdo assistido</TabsTrigger></TabsList><TabsContent value="automatic"><PostizConsole /></TabsContent><TabsContent value="assisted"><ContentConsole /></TabsContent></Tabs>;
}
