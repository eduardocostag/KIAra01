"use client";

import { AdminOnly } from "@/components/app-shell/admin-access"

import { useCallback, useEffect, useState } from "react";
import { BarChart3, Loader2, RefreshCw, Send, Trash2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type Channel = { id: string; name: string; identifier: string; disabled?: boolean };
type Post = { id: string; content: string; publishDate: string; state: string; releaseURL?: string; integration?: { name?: string } };
type Media = { id: string; path: string; name: string };
type Metric = { label: string; data: Array<{ total: number | string; date: string }> };
const supported = new Set(["tiktok", "instagram", "instagram-standalone", "facebook", "threads", "linkedin", "linkedin-page", "youtube", "bluesky", "mastodon", "telegram", "nostr", "vk"]);
const selectClass = "h-10 w-full rounded-md border bg-background px-3 text-sm";
function localTime() { const d = new Date(Date.now() + 3600000); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); }
async function request(path: string, init?: RequestInit) {
  const response = await fetch(`/api/content/postiz/${path}`, { cache: "no-store", ...init });
  if (response.status === 204) return {};
  const body = await response.json().catch(() => null);
  if (!response.ok || body === null) throw new Error(body?.error?.message || `Não foi possível acessar o Postiz (HTTP ${response.status}).`);
  return body;
}
function safeUrl(value?: string) { try { return value && new URL(value).protocol === "https:" ? value : undefined; } catch { return undefined; } }

export function PostizConsole() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [channelId, setChannelId] = useState("");
  const [content, setContent] = useState("");
  const [media, setMedia] = useState<Media[]>([]);
  const [action, setAction] = useState("draft");
  const [date, setDate] = useState(localTime);
  const [month, setMonth] = useState(() => localTime().slice(0, 7));
  const [title, setTitle] = useState("");
  const [visibility, setVisibility] = useState("private");
  const [madeForKids, setMadeForKids] = useState("no");
  const [tiktokPrivacy, setTiktokPrivacy] = useState("SELF_ONLY");
  const [tiktokOptions, setTiktokOptions] = useState({ duet: false, stitch: false, comment: true, brand_content_toggle: false, brand_organic_toggle: false, video_made_with_ai: false });
  const [postType, setPostType] = useState("post");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [failed, setFailed] = useState(false);
  const [metrics, setMetrics] = useState<Metric[] | null>(null);
  const [showComposer, setShowComposer] = useState(false);
  const channel = channels.find((item) => item.id === channelId);
  const canCompose = !!channel && supported.has(channel.identifier) && !channel.disabled;
  const load = useCallback(async () => {
    if (!/^\d{4}-\d{2}$/.test(month)) return;
    const [year, number] = month.split("-").map(Number);
    const startDate = new Date(Date.UTC(year, number - 1, 1)).toISOString();
    const endDate = new Date(Date.UTC(year, number, 1) - 1).toISOString();
    const body = await request(`dashboard?${new URLSearchParams({ startDate, endDate })}`);
    if (!Array.isArray(body.integrations) || !Array.isArray(body.posts)) throw new Error("O Postiz retornou um calendário inválido.");
    setChannels(body.integrations); setPosts(body.posts);
    setChannelId((current) => body.integrations.some((item: Channel) => item.id === current) ? current : body.integrations.find((item: Channel) => !item.disabled)?.id || "");
  }, [month]);
  const run = useCallback(async (work: () => Promise<void>) => {
    setBusy(true); setNotice(""); setFailed(false);
    try { await work(); } catch (error) { setFailed(true); setNotice(error instanceof Error ? error.message : "A operação falhou."); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { const timer = window.setTimeout(() => void run(load), 0); return () => window.clearTimeout(timer); }, [load, run]);

  async function upload(file?: File) {
    if (!file) return;
    await run(async () => {
      if (file.size > 4 * 1024 * 1024) throw new Error("Use um arquivo de até 4 MB aqui. Para vídeos maiores, faça o envio pelo painel Postiz.");
      const form = new FormData(); form.set("file", file);
      const body = await request("upload", { method: "POST", body: form });
      if (!body.id || !safeUrl(body.path)) throw new Error("O Postiz não devolveu uma mídia válida.");
      setMedia((current) => [...current, { id: body.id, path: body.path, name: file.name }]);
    });
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!channel || !canCompose) return;
    await run(async () => {
      if (action !== "draft" && (channel.identifier.startsWith("instagram") || ["tiktok", "youtube"].includes(channel.identifier)) && !media.length) throw new Error("Adicione uma mídia para publicar nesta rede.");
      const settings: Record<string, unknown> = {};
      if (channel.identifier === "tiktok") Object.assign(settings, { ...tiktokOptions, title: title.slice(0, 90), privacy_level: tiktokPrivacy, autoAddMusic: "no", content_posting_method: "DIRECT_POST" });
      if (channel.identifier.startsWith("instagram")) { settings.post_type = postType; settings.collaborators = []; }
      if (channel.identifier.startsWith("linkedin")) settings.post_as_images_carousel = false;
      if (channel.identifier === "youtube") Object.assign(settings, { title, type: visibility, selfDeclaredMadeForKids: madeForKids, tags: [] });
      await request("posts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: action, date: action === "schedule" ? new Date(date).toISOString() : new Date().toISOString(), integrationId: channel.id, provider: channel.identifier, content, media, settings }) });
      setContent(""); setMedia([]);
      let refreshWarning = "";
      try { await load(); } catch { refreshWarning = " O envio foi aceito, mas a lista não atualizou. Use Atualizar antes de reenviar."; }
      setNotice((action === "draft" ? "Rascunho salvo no Postiz. Continue a edição pelo painel Postiz." : action === "schedule" ? "Agendamento enviado ao Postiz. Acompanhe o status no calendário." : "Publicação enviada ao Postiz. Acompanhe o status de entrega no calendário.") + refreshWarning);
    });
  }
  async function analytics() {
    if (!channel) return;
    setMetrics(null);
    await run(async () => {
      const body = await request(`analytics/channel/${encodeURIComponent(channel.id)}?date=30`);
      if (!Array.isArray(body)) throw new Error("As métricas ainda não estão disponíveis para este canal.");
      setMetrics(body);
    });
  }
  return <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{channels.length ? `${channels.length} ${channels.length === 1 ? "canal disponível" : "canais disponíveis"}` : "Conecte um canal para começar."} <AdminOnly><a className="ml-1 underline underline-offset-4" href="/app/integrations">Gerenciar canais</a></AdminOnly></p><Button type="button" aria-expanded={showComposer} aria-controls="postiz-composer" onClick={() => setShowComposer((current) => !current)}>{showComposer ? "Fechar editor" : "Criar publicação"}</Button></div>
    {notice && <Alert variant={failed ? "destructive" : "default"}><AlertTitle>{failed ? "Operação não concluída" : "Conteúdo atualizado"}</AlertTitle><AlertDescription>{notice}</AlertDescription></Alert>}
    <div className={`grid min-w-0 gap-4 ${showComposer ? "lg:grid-cols-2" : ""}`}>
      {showComposer && <Card id="postiz-composer" className="min-w-0"><CardHeader><CardTitle>Criar publicação</CardTitle></CardHeader><CardContent>
        <form onSubmit={save} className="grid gap-4"><fieldset disabled={busy} className="grid min-w-0 gap-4">
          <div className="grid gap-2"><Label htmlFor="postiz-channel">Canal conectado</Label><select id="postiz-channel" className={selectClass} value={channelId} onChange={(event) => { setChannelId(event.target.value); setMetrics(null); }}><option value="">Selecione um canal</option>{channels.map((item) => <option key={item.id} value={item.id} disabled={item.disabled}>{item.name} · {item.identifier}{item.disabled ? " (reconectar no Postiz)" : ""}</option>)}</select></div>
          {channel && !supported.has(channel.identifier) && <p className="text-sm text-muted-foreground">Este canal exige opções específicas. Crie a publicação no painel Postiz; ela aparecerá neste calendário.</p>}
          <div className="grid gap-2"><Label htmlFor="postiz-content">Legenda</Label><Textarea id="postiz-content" value={content} onChange={(event) => setContent(event.target.value)} maxLength={10000} className="min-h-32" /></div>
          {channel?.identifier.startsWith("instagram") && <div className="grid gap-2"><Label htmlFor="postiz-format">Formato</Label><select id="postiz-format" className={selectClass} value={postType} onChange={(event) => setPostType(event.target.value)}><option value="post">Publicação</option><option value="story">Story</option></select></div>}
          {channel?.identifier === "tiktok" && <>
            <div className="grid gap-2"><Label htmlFor="tiktok-title">Título TikTok</Label><Input id="tiktok-title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={90} /></div>
            <div className="grid gap-2"><Label htmlFor="tiktok-privacy">Quem pode assistir?</Label><select id="tiktok-privacy" className={selectClass} value={tiktokPrivacy} onChange={(event) => setTiktokPrivacy(event.target.value)}><option value="SELF_ONLY">Somente eu</option><option value="PUBLIC_TO_EVERYONE">Todos</option><option value="MUTUAL_FOLLOW_FRIENDS">Amigos mútuos</option><option value="FOLLOWER_OF_CREATOR">Seguidores</option></select></div>
            <details className="rounded-xl border"><summary className="cursor-pointer p-3 text-sm font-medium">Opções do TikTok</summary><div className="grid gap-2 border-t p-3 text-sm">{([
              ["duet", "Permitir duetos"], ["stitch", "Permitir costura"], ["comment", "Permitir comentários"],
              ["brand_content_toggle", "Parceria paga com outra marca"], ["brand_organic_toggle", "Promove minha própria marca"], ["video_made_with_ai", "Vídeo gerado com IA"],
            ] as const).map(([key, label]) => <label key={key} className="flex items-center gap-2"><input type="checkbox" checked={tiktokOptions[key]} onChange={(event) => setTiktokOptions((current) => ({ ...current, [key]: event.target.checked }))} />{label}</label>)}</div></details>
          </>}
          {channel?.identifier === "youtube" && <><div className="grid gap-2"><Label htmlFor="postiz-title">Título do vídeo</Label><Input id="postiz-title" value={title} onChange={(event) => setTitle(event.target.value)} minLength={2} maxLength={100} required /></div><div className="grid gap-2"><Label htmlFor="postiz-visibility">Visibilidade</Label><select id="postiz-visibility" className={selectClass} value={visibility} onChange={(event) => setVisibility(event.target.value)}><option value="private">Privado</option><option value="unlisted">Não listado</option><option value="public">Público</option></select></div><div className="grid gap-2"><Label htmlFor="postiz-kids">Conteúdo feito para crianças?</Label><select id="postiz-kids" className={selectClass} value={madeForKids} onChange={(event) => setMadeForKids(event.target.value)}><option value="no">Não</option><option value="yes">Sim</option></select></div></>}
          <div className="grid gap-2"><Label htmlFor="postiz-media">Mídia (até 4 MB por arquivo)</Label><Input id="postiz-media" type="file" accept="image/jpeg,image/png,image/webp,image/gif,video/mp4" disabled={media.length >= 20} onChange={(event) => { void upload(event.target.files?.[0]); event.currentTarget.value = ""; }} />{media.map((item) => <div key={item.id} className="flex items-center justify-between gap-2 text-sm"><span className="truncate">{item.name}</span><Button type="button" variant="ghost" size="icon" aria-label={`Remover ${item.name}`} onClick={() => setMedia((current) => current.filter((entry) => entry.id !== item.id))}><Trash2 /></Button></div>)}</div>
          <div className="grid gap-2"><Label htmlFor="postiz-action">Ação</Label><select id="postiz-action" className={selectClass} value={action} onChange={(event) => setAction(event.target.value)}><option value="draft">Salvar rascunho no Postiz</option><option value="schedule">Agendar publicação automática</option><option value="now">Publicar agora</option></select></div>
          {action === "schedule" && <div className="grid gap-2"><Label htmlFor="postiz-date">Data e hora local</Label><Input id="postiz-date" type="datetime-local" required value={date} onChange={(event) => setDate(event.target.value)} /></div>}
          <Button type="submit" disabled={!canCompose || (!content.trim() && !media.length)}>{busy ? <Loader2 className="animate-spin" /> : <Send />}{action === "draft" ? "Salvar rascunho" : action === "schedule" ? "Agendar publicação" : "Publicar agora"}</Button>
        </fieldset></form>
      </CardContent></Card>}
      <Card className="min-w-0"><CardHeader><CardTitle>Publicações</CardTitle></CardHeader><CardContent className="space-y-4"><div className="flex flex-wrap items-end gap-2"><div className="grid gap-2"><Label htmlFor="postiz-month">Mês</Label><Input id="postiz-month" type="month" value={month} disabled={busy} onChange={(event) => setMonth(event.target.value)} /></div><Button variant="outline" disabled={busy} onClick={() => void run(load)}><RefreshCw />Atualizar</Button></div>
        {!posts.length && <p className="py-8 text-center text-sm text-muted-foreground">{busy ? "Carregando…" : "Nenhuma publicação neste período."}</p>}
        {posts.map((post) => <article key={post.id} className="space-y-2 rounded-xl border p-3"><div className="flex justify-between gap-2 text-xs"><span>{post.integration?.name || "Canal"}</span><strong>{post.state}</strong></div><p className="line-clamp-3 whitespace-pre-wrap text-sm">{post.content || "Publicação com mídia"}</p><time className="text-xs text-muted-foreground">{new Date(post.publishDate).toLocaleString("pt-BR")}</time><div className="flex items-center gap-2">{safeUrl(post.releaseURL) && <a href={safeUrl(post.releaseURL)} target="_blank" rel="noopener noreferrer" className="text-sm underline">Ver publicação</a>}<Button variant="ghost" size="sm" disabled={busy} onClick={() => { if (window.confirm("Excluir esta publicação e os itens do mesmo grupo no Postiz? Isso não remove conteúdo já publicado na rede social.")) void run(async () => { await request(`posts/${encodeURIComponent(post.id)}`, { method: "DELETE" }); await load(); }); }}><Trash2 />Excluir do Postiz</Button></div></article>)}
      </CardContent></Card>
    </div>
    <details className="rounded-2xl border bg-card"><summary className="cursor-pointer p-5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">Métricas dos canais</summary><div className="space-y-4 border-t p-5"><div className="grid max-w-sm gap-2"><Label htmlFor="postiz-metrics-channel">Canal</Label><select id="postiz-metrics-channel" className={selectClass} value={channelId} onChange={(event) => { setChannelId(event.target.value); setMetrics(null); }}><option value="">Selecione um canal</option>{channels.map((item) => <option key={item.id} value={item.id} disabled={item.disabled}>{item.name}</option>)}</select></div><p className="text-xs text-muted-foreground">Últimos 30 dias, conforme os dados disponibilizados pela rede.</p><Button variant="outline" disabled={busy || !channel} onClick={() => void analytics()}><BarChart3 />Consultar métricas</Button>{metrics && (metrics.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{metrics.map((metric, index) => <div key={`${metric.label}-${index}`} className="min-w-0 rounded-xl border p-4"><h3 className="font-medium">{metric.label}</h3><div className="mt-2 max-h-48 overflow-auto">{Array.isArray(metric.data) && metric.data.map((point, index) => <div key={index} className="flex justify-between gap-4 text-sm"><span>{point.date}</span><span>{point.total}</span></div>)}</div></div>)}</div> : <p className="text-sm text-muted-foreground">A rede não retornou métricas para este período.</p>)}</div></details>
    <details className="rounded-2xl border bg-card"><summary className="cursor-pointer p-5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring">Ajuda com a publicação</summary><div className="space-y-2 border-t p-5 text-sm text-muted-foreground"><p>Para publicar automaticamente, conecte suas redes no Postiz e configure a conexão em <AdminOnly><a className="underline" href="/app/integrations">Integrações</a></AdminOnly>.</p><p>Use Preparar conteúdo para criar rascunhos e concluir a publicação manualmente na rede social.</p></div></details>
  </div>;
}
