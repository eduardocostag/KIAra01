"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart3, CalendarDays, Copy, Download, ExternalLink, ImagePlus, Loader2, RefreshCw, Send, Trash2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type ObjectValue = Record<string, unknown>;
type Integration = { id: string; name: string; provider: string; picture: string };
type Post = { id: string; content: string; date: string; state: string; provider: string; channel: string; releaseUrl: string; version: number; media: Media[] };
type Media = { id: string; name: string; downloadUrl?: string };
type PublicationPackage = { id: string; content: string; version: number; targets: Array<{ provider?: string; name?: string }>; media: Media[] };

function object(value: unknown): ObjectValue { return value && typeof value === "object" && !Array.isArray(value) ? value as ObjectValue : {}; }
function string(value: unknown, fallback = "") { return typeof value === "string" ? value : fallback; }
function items(value: unknown, keys: string[]): unknown[] {
  if (Array.isArray(value)) return value;
  const record = object(value);
  for (const key of keys) if (Array.isArray(record[key])) return record[key] as unknown[];
  for (const key of ["data", "result"]) { const nested = items(record[key], keys); if (nested.length) return nested; }
  return [];
}
function errorMessage(body: unknown, fallback: string) { const value = object(body); const error = object(value.error); return string(error.message) || string(value.message) || string(value.msg) || fallback; }
async function responseBody(response: Response) { const body: unknown = await response.json().catch(() => ({})); if (!response.ok) throw new Error(errorMessage(body, "Não foi possível concluir a operação.")); return body; }
function parseIntegrations(value: unknown): Integration[] {
  return items(value, ["channels", "integrations", "items"]).map((entry) => { const item = object(entry); return { id: string(item.id), name: string(item.name, string(item.profile, "Canal")), provider: string(item.providerIdentifier, string(item.provider, "social")), picture: string(item.picture) }; }).filter((item) => item.id);
}
function parsePosts(value: unknown): Post[] {
  return items(value, ["posts", "items"]).map((entry) => { const item = object(entry); const targets = items(item.targets, ["items"]); const firstTarget = object(targets[0]); const integration = object(item.integration); const media = items(item.media, ["items"]).map((entry) => { const value = object(entry); return { id: string(value.id), name: string(value.name, "Mídia"), downloadUrl: string(value.download_url) }; }); return { id: string(item.id), content: string(item.content, string(item.message)), date: string(item.scheduled_at, string(item.published_at, string(item.created_at, string(item.publishDate, string(item.date))))), state: string(item.status, string(item.state, "UNKNOWN")), provider: string(firstTarget.provider, string(integration.providerIdentifier)), channel: string(firstTarget.channel_name, string(integration.name, "Canal")), releaseUrl: string(firstTarget.release_url, string(item.releaseURL)), version: typeof item.version === "number" ? item.version : 1, media }; }).filter((item) => item.id);
}
function localDateTime() { const date = new Date(Date.now() + 60 * 60 * 1000); date.setMinutes(date.getMinutes() - date.getTimezoneOffset()); return date.toISOString().slice(0, 16); }

export function ContentConsole() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [integrationId, setIntegrationId] = useState("");
  const [content, setContent] = useState("");
  const [publishType, setPublishType] = useState<"draft" | "schedule" | "now">("draft");
  const [date, setDate] = useState(localDateTime);
  const [media, setMedia] = useState<Media[]>([]);
  const [publicationPackage, setPublicationPackage] = useState<PublicationPackage | null>(null);
  const [busy, setBusy] = useState<"load" | "save" | "upload" | "delete" | "channel" | "package" | "confirm" | null>("load");
  const [notice, setNotice] = useState<{ title: string; text: string; error?: boolean } | null>(null);

  const selectedIntegration = useMemo(() => integrations.find((item) => item.id === integrationId), [integrationId, integrations]);
  const load = useCallback(async () => {
    setBusy("load"); setNotice(null);
    try {
      const dashboard = object(await responseBody(await fetch("/api/content/dashboard?limit=100", { cache: "no-store" })));
      const channels = parseIntegrations(dashboard.channels ?? dashboard.integrations);
      setIntegrations(channels); setIntegrationId((current) => channels.some((item) => item.id === current) ? current : channels[0]?.id ?? ""); setPosts(parsePosts(dashboard.posts));
    } catch (error) { setNotice({ title: "Conteúdo indisponível", text: error instanceof Error ? error.message : "Verifique a API Kiara.", error: true }); }
    finally { setBusy(null); }
  }, []);
  useEffect(() => {
    const initialLoad = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [load]);

  async function upload(file?: File) {
    if (!file) return;
    setBusy("upload"); setNotice(null);
    try {
      const form = new FormData(); form.set("file", file);
      const body = object(await responseBody(await fetch("/api/content/upload", { method: "POST", body: form })));
      const uploaded = object(body.data && typeof body.data === "object" ? body.data : body);
      const id = string(uploaded.id);
      if (!id) throw new Error("A Kiara não registrou a mídia.");
      setMedia((current) => [...current, { id, name: file.name, downloadUrl: `/api/content/media/${id}` }]);
      setNotice({ title: "Mídia armazenada", text: `${file.name} foi validada e guardada no armazenamento privado da Kiara.` });
    } catch (error) { setNotice({ title: "Falha no upload", text: error instanceof Error ? error.message : "Tente novamente.", error: true }); }
    finally { setBusy(null); }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedIntegration) return;
    setBusy("save"); setNotice(null);
    try {
      await responseBody(await fetch("/api/content/posts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: publishType, date: new Date(date).toISOString(), integrationId: selectedIntegration.id, provider: selectedIntegration.provider, content, media, settings: { post_type: "post" } }) }));
      setContent(""); setMedia([]); setNotice({ title: publishType === "draft" ? "Rascunho salvo" : publishType === "now" ? "Pacote pronto" : "Publicação agendada", text: publishType === "now" ? "Baixe a mídia, copie a legenda e conclua a publicação no aplicativo da rede." : "O conteúdo foi salvo na Kiara Social API." });
      await load();
    } catch (error) { setNotice({ title: "Não foi possível salvar", text: error instanceof Error ? error.message : "Revise o conteúdo.", error: true }); setBusy(null); }
  }

  async function remove(postId: string) {
    if (!window.confirm("Excluir este conteúdo da Kiara?")) return;
    setBusy("delete"); setNotice(null);
    try { await responseBody(await fetch(`/api/content/posts/${encodeURIComponent(postId)}`, { method: "DELETE" })); setPosts((current) => current.filter((post) => post.id !== postId)); setNotice({ title: "Publicação excluída", text: "O item foi removido do calendário." }); }
    catch (error) { setNotice({ title: "Não foi possível excluir", text: error instanceof Error ? error.message : "Tente novamente.", error: true }); }
    finally { setBusy(null); }
  }

  async function createAssistedChannel() {
    const name = window.prompt("Nome do canal", "Instagram")?.trim();
    if (!name) return;
    const handle = window.prompt("Usuário ou identificação do canal", "@minhaconta")?.trim() || null;
    setBusy("channel"); setNotice(null);
    try {
      await responseBody(await fetch("/api/content/integrations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, handle, provider: "instagram" }) }));
      setNotice({ title: "Canal criado", text: "O canal assistido está pronto para organizar e preparar publicações gratuitamente." });
      await load();
    } catch (error) { setNotice({ title: "Não foi possível criar o canal", text: error instanceof Error ? error.message : "Tente novamente.", error: true }); setBusy(null); }
  }

  async function openPackage(post: Post) {
    setBusy("package"); setNotice(null);
    try {
      const body = object(await responseBody(await fetch(`/api/content/posts/${encodeURIComponent(post.id)}/package`, { cache: "no-store" })));
      const targets = items(body.targets, ["items"]).map((entry) => { const value = object(entry); return { provider: string(value.provider), name: string(value.name) }; });
      const packageMedia = items(body.media, ["items"]).map((entry) => { const value = object(entry); return { id: string(value.id), name: string(value.original_name, "Mídia"), downloadUrl: string(value.download_url) }; });
      setPublicationPackage({ id: string(body.id), content: string(body.content), version: typeof body.version === "number" ? body.version : post.version, targets, media: packageMedia });
    } catch (error) { setNotice({ title: "Pacote indisponível", text: error instanceof Error ? error.message : "Tente novamente.", error: true }); }
    finally { setBusy(null); }
  }

  async function copyCaption() {
    if (!publicationPackage) return;
    await navigator.clipboard.writeText(publicationPackage.content);
    setNotice({ title: "Legenda copiada", text: "Cole a legenda no aplicativo da rede social." });
  }

  async function confirmPublication() {
    if (!publicationPackage) return;
    const releaseUrl = window.prompt("Cole a URL pública da publicação concluída")?.trim();
    if (!releaseUrl) return;
    setBusy("confirm"); setNotice(null);
    try {
      await responseBody(await fetch(`/api/content/posts/${encodeURIComponent(publicationPackage.id)}/confirm`, { method: "POST", headers: { "Content-Type": "application/json", "If-Match": `\"${publicationPackage.version}\"` }, body: JSON.stringify({ release_url: releaseUrl }) }));
      setPublicationPackage(null); setNotice({ title: "Publicação confirmada", text: "A URL e a conclusão foram registradas na Kiara." }); await load();
    } catch (error) { setNotice({ title: "Não foi possível confirmar", text: error instanceof Error ? error.message : "Revise a URL.", error: true }); setBusy(null); }
  }

  return <div className="space-y-4">
    {notice && <Alert variant={notice.error ? "destructive" : "default"}><AlertTitle>{notice.title}</AlertTitle><AlertDescription>{notice.text}</AlertDescription></Alert>}
    {publicationPackage && <Card className="border-primary/25"><CardHeader><CardTitle>Pacote pronto para publicar</CardTitle><CardDescription>A etapa final permanece sob seu controle. A Kiara não usa cookies nem automação não oficial.</CardDescription></CardHeader><CardContent className="space-y-4"><div className="rounded-xl border bg-muted/20 p-4 text-sm whitespace-pre-wrap">{publicationPackage.content || "Sem legenda"}</div><div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => void copyCaption()}><Copy />Copiar legenda</Button>{publicationPackage.media.map((item) => <Button key={item.id} asChild variant="outline"><a href={item.downloadUrl || `/api/content/media/${item.id}`}><Download />{item.name}</a></Button>)}<Button asChild variant="outline"><a href="https://www.instagram.com/" target="_blank" rel="noopener noreferrer"><ExternalLink />Abrir Instagram</a></Button><Button onClick={() => void confirmPublication()} disabled={busy !== null}>{busy === "confirm" ? <Loader2 className="animate-spin" /> : <Send />}Confirmar publicação</Button></div></CardContent></Card>}
    <Tabs defaultValue="calendar" className="space-y-4">
      <TabsList><TabsTrigger value="calendar"><CalendarDays />Calendário</TabsTrigger><TabsTrigger value="compose"><Send />Criar conteúdo</TabsTrigger><TabsTrigger value="analytics"><BarChart3 />Analytics</TabsTrigger></TabsList>
      <TabsContent value="calendar">
        <Card><CardHeader className="flex-row items-center justify-between"><div><CardTitle>Publicações</CardTitle><CardDescription>Rascunhos, agenda e entrega assistida gratuita mantidos pela Kiara Social API.</CardDescription></div><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => void createAssistedChannel()} disabled={busy !== null}>{busy === "channel" ? <Loader2 className="animate-spin" /> : <Send />}Novo canal</Button><Button variant="outline" size="sm" onClick={() => void load()} disabled={busy !== null}>{busy === "load" ? <Loader2 className="animate-spin" /> : <RefreshCw />}Atualizar</Button></div></CardHeader><CardContent>
          {posts.length ? <div className="grid gap-2">{posts.map((post) => <article key={post.id} className="flex items-center gap-3 rounded-xl border p-3"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{post.state}</Badge><span className="text-xs text-muted-foreground">{post.channel}</span></div><p className="mt-2 line-clamp-2 text-sm">{post.content || "Publicação com mídia"}</p><time className="mt-1 block text-[11px] text-muted-foreground">{post.date ? new Date(post.date).toLocaleString("pt-BR") : "Sem data"}</time></div>{post.state !== "draft" && <Button variant="outline" size="sm" onClick={() => void openPackage(post)} disabled={busy !== null}>{busy === "package" ? <Loader2 className="animate-spin" /> : <Send />}Preparar</Button>}{post.releaseUrl && <Button asChild variant="outline" size="sm"><a href={post.releaseUrl} target="_blank" rel="noopener noreferrer">Abrir</a></Button>}<Button variant="ghost" size="icon" aria-label="Excluir publicação" onClick={() => void remove(post.id)} disabled={busy !== null}><Trash2 /></Button></article>)}</div> : <div className="grid min-h-40 place-items-center text-sm text-muted-foreground">{busy === "load" ? <Loader2 className="animate-spin" /> : "Nenhuma publicação encontrada."}</div>}
        </CardContent></Card>
      </TabsContent>
      <TabsContent value="compose">
        <Card><CardHeader><CardTitle>Novo conteúdo</CardTitle><CardDescription>Salve como rascunho, agende ou publique nos canais conectados.</CardDescription></CardHeader><CardContent><form className="grid gap-4" onSubmit={save}>
          <div className="grid gap-2"><Label htmlFor="content-channel">Canal</Label><Select value={integrationId} onValueChange={setIntegrationId}><SelectTrigger id="content-channel"><SelectValue placeholder="Selecione um canal" /></SelectTrigger><SelectContent>{integrations.map((item) => <SelectItem key={item.id} value={item.id}>{item.name} · {item.provider}</SelectItem>)}</SelectContent></Select></div>
          <div className="grid gap-2"><Label htmlFor="content-copy">Legenda</Label><Textarea id="content-copy" value={content} onChange={(event) => setContent(event.target.value)} maxLength={10000} className="min-h-36" placeholder="Escreva o conteúdo da publicação…" /><span className="text-right text-[11px] text-muted-foreground">{content.length}/10.000</span></div>
          <div className="grid gap-2"><Label htmlFor="content-file">Mídia</Label><Input id="content-file" type="file" accept="image/jpeg,image/png,image/webp,image/gif,video/mp4" onChange={(event) => { void upload(event.target.files?.[0]); event.currentTarget.value = ""; }} disabled={busy !== null} />{media.length > 0 && <div className="flex flex-wrap gap-2">{media.map((item) => <Badge key={item.id} variant="outline"><ImagePlus />{item.name}</Badge>)}</div>}</div>
          <div className="grid gap-4 sm:grid-cols-2"><div className="grid gap-2"><Label htmlFor="content-type">Ação</Label><Select value={publishType} onValueChange={(value) => setPublishType(value as typeof publishType)}><SelectTrigger id="content-type"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="draft">Salvar rascunho</SelectItem><SelectItem value="schedule">Agendar lembrete</SelectItem><SelectItem value="now">Preparar para publicar</SelectItem></SelectContent></Select></div><div className="grid gap-2"><Label htmlFor="content-date">Data e hora</Label><Input id="content-date" type="datetime-local" value={date} onChange={(event) => setDate(event.target.value)} disabled={publishType === "now"} /></div></div>
          <Button type="submit" disabled={busy !== null || !selectedIntegration || (!content.trim() && !media.length)}>{busy === "save" ? <Loader2 className="animate-spin" /> : <Send />}{publishType === "draft" ? "Salvar rascunho" : publishType === "schedule" ? "Agendar lembrete" : "Preparar pacote"}</Button>
        </form></CardContent></Card>
      </TabsContent>
      <TabsContent value="analytics">
        <Card><CardHeader><CardTitle>Analytics em construção</CardTitle><CardDescription>A API própria já preserva canais, conteúdo e tentativas. Métricas oficiais serão habilitadas com os providers OAuth.</CardDescription></CardHeader><CardContent><Button disabled><BarChart3 />Indisponível no modo simulado</Button></CardContent></Card>
      </TabsContent>
    </Tabs>
  </div>;
}
