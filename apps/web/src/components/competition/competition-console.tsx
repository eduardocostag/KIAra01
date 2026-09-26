"use client";

/* eslint-disable @next/next/no-img-element */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AtSign,
  BadgeCheck,
  CheckCircle2,
  Database,
  Heart,
  ListChecks,
  Link2,
  Loader2,
  LogOut,
  MessageCircle,
  MessageCircleMore,
  Radar,
  RefreshCw,
  ScanSearch,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import styles from "@/app/(app)/app/concorrencia/competition.module.css";

type JsonObject = Record<string, unknown>;
type Mode = "commenters" | "likers" | "post_audience";
type Notice = { title: string; text: string };
type InstagramConnection = {
  state: "loading" | "connected" | "disconnected" | "connecting";
  username: string;
};

const modes: Record<Mode, { label: string; description: string }> = {
  post_audience: {
    label: "Curtidas e comentários",
    description: "Reúne todas as interações acessíveis da publicação",
  },
  commenters: {
    label: "Somente comentários",
    description: "Perfis que comentaram na publicação selecionada",
  },
  likers: {
    label: "Somente curtidas",
    description: "Perfis que curtiram a publicação selecionada",
  },
};

function asObject(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : {};
}
function firstString(value: JsonObject, keys: string[]) {
  for (const key of keys)
    if (typeof value[key] === "string") return value[key] as string;
  return "";
}
function firstNumber(value: JsonObject, keys: string[]) {
  for (const key of keys)
    if (typeof value[key] === "number") return value[key] as number;
  return undefined;
}
function findItems(value: unknown, keys: string[]): JsonObject[] {
  if (Array.isArray(value))
    return value.filter(
      (item) => item && typeof item === "object",
    ) as JsonObject[];
  const object = asObject(value);
  for (const key of keys)
    if (Array.isArray(object[key])) return findItems(object[key], keys);
  for (const key of ["data", "result"])
    if (object[key]) {
      const nested = findItems(object[key], keys);
      if (nested.length) return nested;
    }
  return [];
}
function findIdentifier(value: unknown): string {
  const object = asObject(value);
  const direct = firstString(object, ["id", "analysisId", "analysis_id"]);
  if (direct) return direct;
  for (const key of ["analysis", "data", "result"])
    if (object[key]) {
      const nested = findIdentifier(object[key]);
      if (nested) return nested;
    }
  return "";
}
function analysisRecord(value: unknown): JsonObject {
  const object = asObject(value);
  if (!Object.keys(object).length) return {};
  if (firstString(object, ["status", "state"]) || findIdentifier(object))
    return object;
  for (const key of ["analysis", "data", "result"]) {
    const nested = analysisRecord(object[key]);
    if (Object.keys(nested).length) return nested;
  }
  return object;
}
function analysisStatus(value: unknown) {
  return firstString(analysisRecord(value), ["status", "state"]).toUpperCase();
}
function isRunning(value: unknown) {
  return ["RUNNING", "STARTING", "QUEUED", "PROCESSING", "PENDING"].includes(
    analysisStatus(value),
  );
}
function isFinished(value: unknown) {
  return [
    "COMPLETED",
    "FINISHED",
    "DONE",
    "PAUSED",
    "FAILED",
    "CANCELLED",
  ].includes(analysisStatus(value));
}
function statusLabel(value: unknown) {
  const labels: Record<string, string> = {
    CANCELLED: "Cancelada",
    COMPLETED: "Concluída",
    DONE: "Concluída",
    FAILED: "Não concluída",
    FINISHED: "Concluída",
    PAUSED: "Concluída",
  };
  return isRunning(value)
    ? "Pesquisa em andamento"
    : (labels[analysisStatus(value)] ?? "Criada");
}
function instagramUrl(username: string) {
  const handle = username
    .trim()
    .replace(/^https?:\/\/(?:www\.)?instagram\.com\//i, "")
    .replace(/^@/, "")
    .split(/[/?#]/)[0];
  return handle
    ? `https://www.instagram.com/${encodeURIComponent(handle)}/`
    : "";
}
async function bodyOrError(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      body?.error?.message ?? "Não foi possível concluir a operação.",
    );
  return body;
}

export function CompetitionConsole() {
  const [mode, setMode] = useState<Mode>("post_audience");
  const [target, setTarget] = useState("");
  const [profilePreview, setProfilePreview] = useState<JsonObject>({});
  const [selectedPublication, setSelectedPublication] = useState("");
  const [overview, setOverview] = useState<JsonObject>({});
  const [prospects, setProspects] = useState<JsonObject[]>([]);
  const [selectedAnalysis, setSelectedAnalysis] = useState("");
  const [trackingId, setTrackingId] = useState("");
  const [liveAnalysis, setLiveAnalysis] = useState<JsonObject | null>(null);
  const [loading, setLoading] = useState<
    "overview" | "profile" | "create" | "start" | "prospects" | null
  >("overview");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [connection, setConnection] = useState<InstagramConnection>({
    state: "loading",
    username: "",
  });
  const [showConnection, setShowConnection] = useState(false);
  const [connectionBusy, setConnectionBusy] = useState(false);
  const [browserSession, setBrowserSession] = useState("");
  const [browserImage, setBrowserImage] = useState("");
  const [browserText, setBrowserText] = useState("");

  const loadOverview = useCallback(async () => {
    setLoading("overview");
    try {
      const response = await fetch("/api/competition/overview", {
        cache: "no-store",
      });
      setOverview(await bodyOrError(response));
    } catch (error) {
      setNotice({
        title: "Concorrência indisponível",
        text:
          error instanceof Error
            ? error.message
            : "Falha ao consultar a Kiara.",
      });
    } finally {
      setLoading(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function initialLoad() {
      try {
        const [response, connectionResponse] = await Promise.all([
          fetch("/api/competition/overview", { cache: "no-store" }),
          fetch("/api/competition/instagram/connection", {
            cache: "no-store",
          }),
        ]);
        const body = await bodyOrError(response);
        if (!cancelled) {
          setOverview(body);
          if (connectionResponse.ok) {
            const connectionBody = await connectionResponse.json();
            const connected = connectionBody.connected === true;
            setConnection({ state: connected ? "connected" : "disconnected", username: "" });
            setShowConnection(!connected);
          } else {
            setConnection({ state: "disconnected", username: "" });
            setShowConnection(true);
          }
        }
      } catch (error) {
        if (!cancelled)
          setNotice({
            title: "Concorrência indisponível",
            text:
              error instanceof Error
                ? error.message
                : "Falha ao consultar a Kiara.",
          });
      } finally {
        if (!cancelled) setLoading(null);
      }
    }
    void initialLoad();
    return () => {
      cancelled = true;
    };
  }, []);

  async function beginInstagramConnection() {
    setConnectionBusy(true);
    setNotice(null);
    try {
      const response = await fetch("/api/competition/instagram/connection", {
        method: "POST",
      });
      const body = await bodyOrError(response);
      const sessionId = typeof body.session_id === "string" ? body.session_id : "";
      if (!sessionId) throw new Error("O navegador não devolveu uma sessão válida.");
      setBrowserSession(sessionId);
      setConnection({ state: "connecting", username: "" });
      setShowConnection(true);
    } catch (error) {
      setConnection({ state: "disconnected", username: "" });
      setNotice({
        title: "Não foi possível abrir o Instagram",
        text:
          error instanceof Error
            ? error.message
            : "Verifique o navegador da Kiara e tente novamente.",
      });
    } finally {
      setConnectionBusy(false);
    }
  }

  const refreshBrowserImage = useCallback(async () => {
    if (!browserSession) return;
    const response = await fetch(
      `/api/competition/instagram/connection/${encodeURIComponent(browserSession)}/screenshot`,
      { cache: "no-store" },
    );
    const body = await bodyOrError(response);
    if (typeof body.image === "string") setBrowserImage(body.image);
  }, [browserSession]);

  useEffect(() => {
    if (!browserSession) return;
    const initial = window.setTimeout(() => void refreshBrowserImage(), 0);
    const timer = window.setInterval(() => void refreshBrowserImage(), 1800);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, [browserSession, refreshBrowserImage]);

  async function sendBrowserInput(command: JsonObject) {
    if (!browserSession) return;
    const response = await fetch(
      `/api/competition/instagram/connection/${encodeURIComponent(browserSession)}/input`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(command),
      },
    );
    await bodyOrError(response);
    window.setTimeout(() => void refreshBrowserImage(), 250);
  }

  async function completeInstagramConnection() {
    if (!browserSession) return;
    setConnectionBusy(true);
    try {
      const response = await fetch(
        `/api/competition/instagram/connection/${encodeURIComponent(browserSession)}/complete`,
        { method: "POST" },
      );
      await bodyOrError(response);
      setBrowserSession("");
      setBrowserImage("");
      setBrowserText("");
      setConnection({ state: "connected", username: "" });
      setShowConnection(false);
      setNotice({
        title: "Instagram conectado",
        text: "A Kiara preservou seu navegador. Agora informe o @ do concorrente.",
      });
    } catch (error) {
      setNotice({
        title: "O login ainda não terminou",
        text: error instanceof Error ? error.message : "Conclua o login na tela acima.",
      });
    } finally {
      setConnectionBusy(false);
    }
  }

  async function disconnectInstagram() {
    setConnectionBusy(true);
    setNotice(null);
    try {
      const response = await fetch("/api/competition/instagram/connection", {
        method: "DELETE",
      });
      if (!response.ok && response.status !== 204) await bodyOrError(response);
      setConnection({ state: "disconnected", username: "" });
      setShowConnection(true);
      setBrowserSession("");
      setBrowserImage("");
      setProfilePreview({});
      setSelectedPublication("");
      setNotice({
        title: "Instagram desconectado",
        text: "A credencial deste usuário foi removida.",
      });
    } catch (error) {
      setNotice({
        title: "Não foi possível desconectar",
        text: error instanceof Error ? error.message : "Tente novamente.",
      });
    } finally {
      setConnectionBusy(false);
    }
  }

  const analyses = useMemo(
    () => findItems(overview.analyses, ["analyses", "items"]),
    [overview],
  );
  const activeFromOverview = useMemo(
    () => analyses.find(isRunning) ?? null,
    [analyses],
  );
  const activeId = trackingId || findIdentifier(activeFromOverview);
  const liveRecord = analysisRecord(liveAnalysis ?? activeFromOverview);
  const liveName =
    firstString(liveRecord, ["name", "target", "username"]) ||
    "Audiência selecionada";
  const liveCount =
    firstNumber(liveRecord, [
      "prospectsCount",
      "prospectCount",
      "prospect_count",
      "totalProspects",
    ]) ?? 0;
  const liveProgress = firstNumber(liveRecord, [
    "progress",
    "progressPercent",
    "percentage",
  ]);
  const progressValue =
    typeof liveProgress === "number"
      ? Math.min(
          100,
          Math.max(0, liveProgress <= 1 ? liveProgress * 100 : liveProgress),
        )
      : null;
  const loadedProfile = asObject(profilePreview.profile);
  const publications = useMemo(
    () => findItems(profilePreview.publications, ["publications"]),
    [profilePreview],
  );

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const response = await fetch(
          `/api/competition/analyses/${encodeURIComponent(activeId)}`,
          { cache: "no-store" },
        );
        const body = await bodyOrError(response);
        if (cancelled) return;
        setLiveAnalysis(body);
        if (isFinished(body)) {
          const [overviewResponse, prospectsResponse] = await Promise.all([
            fetch("/api/competition/overview", { cache: "no-store" }),
            fetch(
              `/api/competition/prospects?${new URLSearchParams({ analysis_id: activeId, limit: "100" })}`,
              { cache: "no-store" },
            ),
          ]);
          const [overviewBody, prospectsBody] = await Promise.all([
            bodyOrError(overviewResponse),
            bodyOrError(prospectsResponse),
          ]);
          if (cancelled) return;
          setOverview(overviewBody);
          setProspects(findItems(prospectsBody, ["prospects", "items"]));
          setSelectedAnalysis(activeId);
          setTrackingId("");
          setLiveAnalysis(null);
          return;
        }
      } catch {
        // A falha transitória é tentada novamente sem interromper a experiência.
      }
      if (!cancelled) timer = setTimeout(() => void poll(), 4_000);
    }
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeId]);

  async function loadProfile() {
    setLoading("profile");
    setNotice(null);
    setSelectedPublication("");
    setProfilePreview({});
    try {
      const response = await fetch("/api/competition/kiara/profile-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: target }),
      });
      const body = await bodyOrError(response);
      setProfilePreview(asObject(body));
      if (!findItems(asObject(body).publications, ["publications"]).length) {
        setNotice({
          title: "Perfil carregado",
          text: "Nenhuma publicação acessível foi encontrada neste perfil.",
        });
      }
    } catch (error) {
      setNotice({
        title: "Não foi possível carregar o perfil",
        text:
          error instanceof Error
            ? error.message
            : "Revise o @ informado e a conexão do Instagram.",
      });
    } finally {
      setLoading(null);
    }
  }

  async function createAnalysis(event: React.FormEvent) {
    event.preventDefault();
    setLoading("create");
    setNotice(null);
    try {
      const publication = publications.find(
        (item) => firstString(item, ["id"]) === selectedPublication,
      );
      const publicationUrl = publication
        ? firstString(publication, ["url"])
        : "";
      if (!publicationUrl)
        throw new Error("Selecione uma publicação antes de iniciar a análise.");
      const response = await fetch("/api/competition/kiara/analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          target: publicationUrl,
          media_id: selectedPublication,
          name: `Kiara · ${modes[mode].label} · @${firstString(loadedProfile, ["username"])}`,
        }),
      });
      const body = await bodyOrError(response);
      const id = findIdentifier(asObject(body.analysis));
      if (!id)
        throw new Error(
          "A pesquisa terminou, mas não foi possível abrir o arquivo criado.",
        );
      await loadOverview();
      await loadProspects(id);
      if (typeof body.message === "string" && body.message)
        setNotice({ title: "Consulta concluída", text: body.message });
    } catch (error) {
      setNotice({
        title: "Não foi possível concluir",
        text:
          error instanceof Error
            ? error.message
            : "Revise o perfil ou publicação informada.",
      });
    } finally {
      setLoading(null);
    }
  }

  async function loadProspects(analysisId: string) {
    setSelectedAnalysis(analysisId);
    setLoading("prospects");
    setProspects([]);
    setNotice(null);
    try {
      const query = new URLSearchParams({
        analysis_id: analysisId,
        limit: "100",
      });
      const response = await fetch(`/api/competition/prospects?${query}`, {
        cache: "no-store",
      });
      const body = await bodyOrError(response);
      setProspects(findItems(body, ["prospects", "items"]));
    } catch (error) {
      setNotice({
        title: "Prospectos indisponíveis",
        text:
          error instanceof Error
            ? error.message
            : "A análise pode ainda estar processando.",
      });
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p>Prospecção por audiência</p>
          <h1>Inteligência de concorrência</h1>
          <span>
            Selecione uma publicação e encontre os perfis reais que interagiram
            com ela.
          </span>
        </div>
        <Badge
          variant="outline"
          className={
            connection.state === "connected"
              ? styles.connected
              : styles.connectionPending
          }
        >
          <i />{" "}
          {connection.state === "connected"
            ? `Instagram conectado${connection.username ? ` · @${connection.username}` : ""}`
            : "Conecte seu Instagram"}
        </Badge>
      </header>

      {notice && (
        <Alert variant="destructive">
          <ShieldCheck />
          <AlertTitle>{notice.title}</AlertTitle>
          <AlertDescription>{notice.text}</AlertDescription>
        </Alert>
      )}

      <Card className={styles.connectionCard}>
        <CardContent className={styles.connectionContent}>
          <div className={styles.connectionSummary}>
            <span
              className={
                connection.state === "connected"
                  ? styles.connectionIconReady
                  : styles.connectionIcon
              }
            >
              <AtSign />
            </span>
            <div>
              <strong>
                {connection.state === "connected"
                  ? "Seu Instagram está conectado"
                  : "Conecte seu Instagram para começar"}
              </strong>
              <p>
                {connection.state === "connected"
                  ? `Conexão individual e protegida${connection.username ? ` para @${connection.username}` : ""}.`
                  : "Cada usuário conecta a própria conta. Nenhuma conexão é compartilhada com o administrador ou outros usuários."}
              </p>
            </div>
          </div>
          <div className={styles.connectionActions}>
            {connection.state === "connected" && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => void disconnectInstagram()}
                disabled={connectionBusy}
              >
                <LogOut />
                Desconectar
              </Button>
            )}
            <Button
              type="button"
              variant={connection.state === "connected" ? "outline" : "default"}
              onClick={() => void beginInstagramConnection()}
              disabled={connectionBusy || connection.state === "loading"}
            >
              <Link2 />
              {connection.state === "connected"
                ? "Reconectar"
                : "Conectar meu Instagram"}
            </Button>
          </div>
        </CardContent>

        {showConnection && (
          <div className={styles.connectionGuide}>
            <div className={styles.guideHeader}>
              <div>
                <span>Navegador protegido da Kiara</span>
                <h2>Entre no Instagram nesta tela</h2>
              </div>
              {!browserSession && (
                <Button
                  type="button"
                  onClick={() => void beginInstagramConnection()}
                  disabled={connectionBusy}
                >
                  {connectionBusy ? <Loader2 className="animate-spin" /> : <Link2 />}
                  Abrir Instagram
                </Button>
              )}
            </div>
            {browserSession ? (
              <div className={styles.remoteBrowser}>
                <div className={styles.browserViewportHelp}>
                  <p>Clique no campo desejado da imagem e use o teclado protegido abaixo.</p>
                  <span>A Kiara preserva o navegador, mas não armazena sua senha.</span>
                </div>
                <button
                  type="button"
                  className={styles.browserViewport}
                  aria-label="Tela interativa do Instagram"
                  onClick={(event) => {
                    const bounds = event.currentTarget.getBoundingClientRect();
                    void sendBrowserInput({
                      action: "click",
                      x: ((event.clientX - bounds.left) / bounds.width) * 1280,
                      y: ((event.clientY - bounds.top) / bounds.height) * 800,
                    });
                  }}
                >
                  {browserImage ? (
                    <img src={browserImage} alt="Tela de login do Instagram" />
                  ) : (
                    <span><Loader2 className="animate-spin" /> Preparando navegador…</span>
                  )}
                </button>
                <form
                  className={styles.browserControls}
                  autoComplete="off"
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (!browserText) return;
                    void sendBrowserInput({ action: "type", text: browserText });
                    setBrowserText("");
                  }}
                >
                  <div>
                    <Label htmlFor="remote-browser-text">Digitar no campo selecionado</Label>
                    <Input
                      id="remote-browser-text"
                      type="password"
                      value={browserText}
                      onChange={(event) => setBrowserText(event.target.value)}
                      placeholder="Conteúdo protegido"
                      autoComplete="off"
                    />
                  </div>
                  <Button type="submit" variant="outline" disabled={!browserText}>Digitar</Button>
                  <Button type="button" variant="outline" onClick={() => void sendBrowserInput({ action: "key", key: "Tab" })}>Tab</Button>
                  <Button type="button" variant="outline" onClick={() => void sendBrowserInput({ action: "key", key: "Enter" })}>Enter</Button>
                </form>
                <div className={styles.browserFinish}>
                  <p>Depois que o Instagram abrir normalmente, confirme para salvar a conexão.</p>
                  <Button
                    type="button"
                    size="lg"
                    onClick={() => void completeInstagramConnection()}
                    disabled={connectionBusy}
                  >
                    {connectionBusy ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
                    Concluir conexão
                  </Button>
                </div>
              </div>
            ) : (
              <div className={styles.connectionEmpty}>
                <p>
                  A janela será criada exclusivamente para seu usuário. Quando o
                  login terminar, ela ficará salva para as próximas análises.
                </p>
              </div>
            )}
          </div>
        )}
      </Card>

      <div className={styles.workspace}>
        <Card className={styles.builder}>
          <CardHeader>
            <CardTitle>Nova análise</CardTitle>
            <CardDescription>
              Carregue o perfil, escolha a publicação e defina quais interações
              deseja extrair.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={createAnalysis} className={styles.form}>
              <div className={styles.profileSearch}>
                <div className={styles.field}>
                  <Label htmlFor="competition-target">
                    Perfil do concorrente
                  </Label>
                  <Input
                    id="competition-target"
                    value={target}
                    onChange={(event) => {
                      setTarget(event.target.value);
                      setProfilePreview({});
                      setSelectedPublication("");
                    }}
                    placeholder="@perfilconcorrente"
                    required
                    minLength={2}
                    autoComplete="off"
                  />
                  <p>
                    Informe o @ e carregue o perfil antes de escolher a
                    publicação.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void loadProfile()}
                  disabled={
                    loading !== null ||
                    !target.trim() ||
                    connection.state !== "connected"
                  }
                >
                  {loading === "profile" ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <Search />
                  )}
                  Carregar perfil
                </Button>
              </div>

              {Object.keys(loadedProfile).length > 0 && (
                <section
                  className={styles.profilePreview}
                  aria-label="Perfil carregado"
                >
                  <div className={styles.profileIdentity}>
                    {firstString(loadedProfile, ["profile_pic_url"]) ? (
                      <img
                        src={firstString(loadedProfile, ["profile_pic_url"])}
                        alt=""
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <span>
                        <AtSign />
                      </span>
                    )}
                    <div>
                      <strong>
                        @{firstString(loadedProfile, ["username"])}
                      </strong>
                      <p>{firstString(loadedProfile, ["full_name"])}</p>
                    </div>
                    {loadedProfile.is_verified === true && (
                      <BadgeCheck aria-label="Perfil verificado" />
                    )}
                  </div>
                  <div className={styles.profileStats}>
                    <span>
                      <b>
                        {firstNumber(loadedProfile, [
                          "follower_count",
                        ])?.toLocaleString("pt-BR") ?? "—"}
                      </b>{" "}
                      seguidores
                    </span>
                    <span>
                      <b>
                        {firstNumber(loadedProfile, [
                          "media_count",
                        ])?.toLocaleString("pt-BR") ?? publications.length}
                      </b>{" "}
                      publicações
                    </span>
                  </div>
                </section>
              )}

              {publications.length > 0 && (
                <div className={styles.publicationSection}>
                  <div>
                    <Label>Selecione uma publicação</Label>
                    <p>As métricas abaixo vieram do perfil carregado.</p>
                  </div>
                  <div className={styles.publicationGrid}>
                    {publications.map((publication) => {
                      const id = firstString(publication, ["id"]);
                      const selected = id === selectedPublication;
                      return (
                        <button
                          key={id}
                          type="button"
                          className={
                            selected ? styles.publicationSelected : undefined
                          }
                          onClick={() => setSelectedPublication(id)}
                          aria-pressed={selected}
                        >
                          {firstString(publication, ["thumbnail_url"]) ? (
                            <img
                              src={firstString(publication, ["thumbnail_url"])}
                              alt={
                                firstString(publication, ["caption"]) ||
                                "Publicação do Instagram"
                              }
                              loading="lazy"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <span className={styles.publicationFallback}>
                              <AtSign />
                            </span>
                          )}
                          <span className={styles.publicationMetrics}>
                            <small>
                              <Heart />
                              {firstNumber(publication, [
                                "like_count",
                              ])?.toLocaleString("pt-BR") ?? 0}
                            </small>
                            <small>
                              <MessageCircle />
                              {firstNumber(publication, [
                                "comment_count",
                              ])?.toLocaleString("pt-BR") ?? 0}
                            </small>
                          </span>
                          {selected && (
                            <i>
                              <CheckCircle2 />
                            </i>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {selectedPublication && (
                <div className={styles.field}>
                  <Label htmlFor="competition-mode">
                    O que deseja extrair?
                  </Label>
                  <Select
                    value={mode}
                    onValueChange={(value) => setMode(value as Mode)}
                  >
                    <SelectTrigger id="competition-mode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(modes).map(([value, item]) => (
                        <SelectItem key={value} value={value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p>{modes[mode].description}</p>
                </div>
              )}
              <Button
                type="submit"
                size="lg"
                disabled={loading !== null || !selectedPublication}
              >
                {loading === "create" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <ScanSearch />
                )}
                Extrair interações da publicação
              </Button>
            </form>
          </CardContent>
        </Card>

        <aside className={styles.summary}>
          <Card>
            <CardHeader>
              <CardDescription>Motor próprio da Kiara</CardDescription>
              <CardTitle>Coleta pública ativa</CardTitle>
            </CardHeader>
            <CardContent className={styles.accountStats}>
              <span>
                <b>{analyses.length}</b> pesquisas arquivadas
              </span>
              <span className={styles.serverlessStatus}>
                <i />
                Processamento ativo
              </span>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className={styles.listHeader}>
              <div>
                <CardTitle>Análises recentes</CardTitle>
                <CardDescription>
                  {analyses.length} registros encontrados
                </CardDescription>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => void loadOverview()}
                disabled={loading !== null}
                aria-label="Atualizar análises"
              >
                <RefreshCw
                  className={loading === "overview" ? "animate-spin" : ""}
                />
              </Button>
            </CardHeader>
            <CardContent className={styles.analysisList}>
              {analyses.length ? (
                analyses.map((analysis, index) => {
                  const id = firstString(analysis, [
                    "id",
                    "analysisId",
                    "analysis_id",
                  ]);
                  const name =
                    firstString(analysis, ["name", "target", "username"]) ||
                    `Análise ${index + 1}`;
                  const count = firstNumber(analysis, [
                    "prospectCount",
                    "prospectsCount",
                    "prospect_count",
                    "totalProspects",
                  ]);
                  const running = isRunning(analysis);
                  const source = firstString(analysis, ["provider"]);
                  return (
                    <button
                      type="button"
                      key={id || index}
                      onClick={() => {
                        if (!id) return;
                        if (running) {
                          setSelectedAnalysis(id);
                          setTrackingId(id);
                        } else void loadProspects(id);
                      }}
                      disabled={!id || loading !== null}
                    >
                      <span>
                        <strong>{name}</strong>
                        <small>
                          {source === "kiara_public" ? "Kiara" : "MailerFind"} ·{" "}
                          {statusLabel(analysis)}
                          {typeof count === "number" ? ` · ${count} leads` : ""}
                        </small>
                      </span>
                      <Badge variant="outline">
                        {running ? "Acompanhar" : "Ver leads"}
                      </Badge>
                    </button>
                  );
                })
              ) : (
                <div className={styles.empty}>
                  <Radar />
                  <p>Nenhuma análise encontrada.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>

      {(activeId || loading === "create") && (
        <section
          className={styles.livePanel}
          role="status"
          aria-live="polite"
          aria-label="Pesquisa de concorrência em andamento"
        >
          <div className={styles.liveVisual} aria-hidden="true">
            <span className={styles.liveOrbitOne} />
            <span className={styles.liveOrbitTwo} />
            <span className={styles.liveSweep} />
            <span className={styles.liveCore}>
              <ScanSearch />
            </span>
            <i className={styles.liveDotOne} />
            <i className={styles.liveDotTwo} />
            <i className={styles.liveDotThree} />
          </div>
          <div className={styles.liveContent}>
            <span className={styles.liveEyebrow}>
              <i /> Pesquisa em andamento
            </span>
            <h2>Analisando sinais públicos</h2>
            <p>{activeId ? liveName : target}</p>
            <div
              className={styles.liveProgress}
              aria-label={
                progressValue === null
                  ? "Progresso em processamento"
                  : `Progresso ${Math.round(progressValue)}%`
              }
            >
              <span
                style={
                  progressValue === null
                    ? undefined
                    : { width: `${progressValue}%` }
                }
                className={progressValue === null ? styles.indeterminate : ""}
              />
            </div>
            <div className={styles.liveStages}>
              <span className={styles.stageDone}>
                <Database />
                Consulta iniciada
              </span>
              <span className={styles.stageActive}>
                <ScanSearch />
                Coletando perfis
              </span>
              <span>
                <ListChecks />
                Salvando resultados
              </span>
            </div>
          </div>
          <div className={styles.liveMetric}>
            <Sparkles />
            <strong>{liveCount}</strong>
            <span>leads encontrados</span>
            <small>Atualização automática</small>
          </div>
        </section>
      )}

      {!activeId && (selectedAnalysis || prospects.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle>Prospectos da análise</CardTitle>
          </CardHeader>
          <CardContent>
            {loading === "prospects" ? (
              <div className={styles.loading}>
                <Loader2 className="animate-spin" /> Consultando prospectos…
              </div>
            ) : prospects.length ? (
              <div className={styles.prospectGrid}>
                {prospects.map((item, index) => {
                  const rawUsername = firstString(item, [
                    "username",
                    "userName",
                    "handle",
                  ]);
                  const username = rawUsername || `Perfil ${index + 1}`;
                  const email = firstString(item, ["email", "publicEmail"]);
                  const phone = firstString(item, [
                    "phone_number",
                    "phone",
                    "phoneNumber",
                  ]);
                  const instagram =
                    firstString(item, ["profile_url", "profileUrl"]) ||
                    instagramUrl(rawUsername);
                  const whatsapp = firstString(item, [
                    "whatsapp_url",
                    "whatsappUrl",
                  ]);
                  return (
                    <article
                      key={firstString(item, ["id", "prospectId"]) || index}
                    >
                      <div>
                        <strong>
                          {rawUsername
                            ? `@${rawUsername.replace(/^@/, "")}`
                            : username}
                        </strong>
                        <span>
                          {firstString(item, [
                            "full_name",
                            "fullName",
                            "name",
                          ]) || "Perfil público"}
                        </span>
                        {email && (
                          <a className={styles.email} href={`mailto:${email}`}>
                            {email}
                          </a>
                        )}
                        {phone && <span>{phone}</span>}
                      </div>
                      <div className={styles.contactActions}>
                        {instagram && (
                          <a
                            className={styles.contactButton}
                            href={instagram}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`Abrir Instagram de ${username}`}
                          >
                            <AtSign />
                            Instagram
                          </a>
                        )}
                        {whatsapp && (
                          <a
                            className={`${styles.contactButton} ${styles.whatsappButton}`}
                            href={whatsapp}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`Enviar WhatsApp para ${username}`}
                          >
                            <MessageCircleMore />
                            WhatsApp
                          </a>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className={styles.empty}>
                <CheckCircle2 />
                <p>Nenhum prospecto disponível.</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
