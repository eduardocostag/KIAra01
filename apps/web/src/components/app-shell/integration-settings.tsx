"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle2,
  ExternalLink,
  KeyRound,
  Link2,
  Loader2,
  MessageCircle,
  Radar,
  SearchCheck,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type Provider =
  "google" | "instagram" | "instagram_session" | "hermes" | "mailerfind" | "postiz" | "chatwoot";
type Status = {
  provider: Provider;
  configured_fields: string[];
  status: string;
  updated_at: string;
  is_global?: boolean;
};
type Field = {
  name: string;
  label: string;
  secret?: boolean;
  required?: boolean;
  placeholder?: string;
};
type MailerFindResult =
  | "connected"
  | "denied"
  | "state_error"
  | "token_error"
  | "validation_error"
  | "save_error"
  | "error";
const fields: Record<Provider, Field[]> = {
  google: [
    {
      name: "developer_token",
      label: "Developer token",
      secret: true,
      required: true,
    },
    {
      name: "client_id",
      label: "OAuth Client ID",
      required: true,
      placeholder: "...apps.googleusercontent.com",
    },
    {
      name: "client_secret",
      label: "OAuth Client Secret",
      secret: true,
      required: true,
    },
    {
      name: "refresh_token",
      label: "Refresh token",
      secret: true,
      required: true,
    },
    {
      name: "customer_id",
      label: "ID da conta cliente",
      required: true,
      placeholder: "10 dígitos, sem hífens",
    },
    { name: "login_customer_id", label: "ID da conta gerente" },
    { name: "ga4_property_id", label: "ID da propriedade GA4" },
  ],
  instagram: [
    { name: "app_id", label: "Meta App ID", required: true },
    {
      name: "app_secret",
      label: "Meta App Secret",
      secret: true,
      required: true,
    },
    {
      name: "access_token",
      label: "Access token de longa duração",
      secret: true,
      required: true,
    },
    {
      name: "instagram_account_id",
      label: "Instagram Business Account ID",
      required: true,
    },
    { name: "page_id", label: "Facebook Page ID" },
    { name: "verify_token", label: "Webhook verify token", secret: true },
  ],
  instagram_session: [
    {
      name: "session_id",
      label: "Session ID do Instagram",
      secret: true,
      required: true,
      placeholder: "Cole o valor do cookie sessionid",
    },
    {
      name: "username",
      label: "Usuário da conta conectada",
      placeholder: "@conta",
    },
  ],
  hermes: [
    {
      name: "instance_id",
      label: "ID exclusivo da instância",
      required: true,
      placeholder: "cliente-kiara-01",
    },
    {
      name: "endpoint_url",
      label: "URL HTTPS da instância",
      required: true,
      placeholder: "https://hermes-cliente.example.com",
    },
    { name: "api_key", label: "API_SERVER_KEY", secret: true, required: true },
  ],
  mailerfind: [],
  chatwoot: [{ name: "endpoint_url", label: "URL HTTPS do Chatwoot", required: true, placeholder: "https://atendimento.suaempresa.com" }, { name: "account_id", label: "ID da conta", required: true }, { name: "api_access_token", label: "Token de acesso", secret: true, required: true }, { name: "webhook_secret", label: "Segredo do webhook (receber mensagens)", secret: true }],
  postiz: [
    {
      name: "endpoint_url",
      label: "URL da API Postiz",
      required: true,
      placeholder: "https://api.postiz.com",
    },
    {
      name: "api_key",
      label: "API Key da organização",
      secret: true,
      required: true,
      placeholder: "Copie em Settings > Developers > Access",
    },
  ],
};
const info = {
  google: {
    name: "Google Growth",
    detail: "Ads, Analytics e Data Manager",
    href: "https://ads.google.com/aw/apicenter",
    icon: BarChart3,
  },
  instagram: {
    name: "Instagram",
    detail: "Mensagens e conta profissional",
    href: "https://developers.facebook.com/apps/",
    icon: MessageCircle,
  },
  instagram_session: {
    name: "Instagram · Concorrência",
    detail: "Perfis, publicações e interações reais",
    href: "https://www.instagram.com/",
    icon: Radar,
  },
  hermes: {
    name: "Hermes Agent",
    detail: "Instância autônoma isolada por cliente",
    href: "https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server",
    icon: Bot,
  },
  mailerfind: {
    name: "MailerFind",
    detail: "Maps, Instagram, X e enriquecimento via MCP",
    href: "https://help.mailerfind.com/pt-br/article/conecte-o-mailerfind-ao-claude-wunaig/",
    icon: SearchCheck,
  },
  chatwoot: { name: "Chatwoot", detail: "Central de atendimento multicanal", href: "https://www.chatwoot.com", icon: MessageCircle },
  postiz: {
    name: "Postiz",
    detail: "Calendário, publicação e analytics sociais",
    href: "https://docs.postiz.com/public-api",
    icon: Send,
  },
};

export function IntegrationSettings({
  adminMode = false,
  mailerFindResult,
}: {
  adminMode?: boolean;
  mailerFindResult?: MailerFindResult;
}) {
  const configurationRef = useRef<HTMLDivElement>(null);
  const [statuses, setStatuses] = useState<Status[]>([]),
    [selected, setSelected] = useState<Provider | null>(() =>
      mailerFindResult ? "mailerfind" : null,
    );
  const [saving, setSaving] = useState<Provider | null>(null),
    [message, setMessage] = useState<{
      type: "ok" | "error";
      text: string;
    } | null>(() => {
      if (mailerFindResult === "connected")
        return {
          type: "ok",
          text: "MailerFind conectado, validado e liberado para todos os usuários. Os tokens foram guardados no cofre criptografado da Kiara.",
        };
      if (mailerFindResult === "denied")
        return {
          type: "error",
          text: "A autorização do MailerFind foi cancelada. Nenhuma credencial foi salva.",
        };
      if (mailerFindResult === "state_error")
        return {
          type: "error",
          text: "A sessão de autorização expirou ou voltou incompleta. Clique em Conectar para todos e conclua o acesso em até 10 minutos.",
        };
      if (mailerFindResult === "token_error")
        return {
          type: "error",
          text: "O MailerFind autorizou o acesso, mas não entregou o token. Entre novamente no MailerFind e repita a conexão.",
        };
      if (mailerFindResult === "validation_error")
        return {
          type: "error",
          text: "O token foi recebido, mas o endpoint MCP do MailerFind recusou a validação. Confirme que sua conta possui acesso ao MCP e tente novamente.",
        };
      if (mailerFindResult === "save_error")
        return {
          type: "error",
          text: "A autorização foi concluída, mas a API da Kiara não conseguiu salvar a conexão global. Aguarde a atualização do serviço e tente novamente.",
        };
      if (mailerFindResult === "error")
        return {
          type: "error",
          text: "A Kiara não conseguiu iniciar a autorização. Verifique sua sessão de administrador e tente novamente.",
        };
      return null;
    });
  const providers: Provider[] = adminMode
    ? ["mailerfind", "postiz", "chatwoot", "google", "instagram", "hermes"]
    : ["postiz", "chatwoot", "google", "instagram", "hermes"];
  useEffect(() => {
    if (selected) {
      configurationRef.current?.scrollIntoView({ block: "nearest" });
      configurationRef.current?.focus({ preventScroll: true });
    }
  }, [selected]);
  useEffect(() => {
    fetch("/api/integrations", { cache: "no-store" })
      .then(async (response) =>
        response.ok
          ? setStatuses((await response.json()).items ?? [])
          : undefined,
      )
      .catch(() => undefined);
  }, []);
  async function save(provider: Provider, form: HTMLFormElement) {
    setSaving(provider);
    setMessage(null);
    const credentials = Object.fromEntries(
      Array.from(new FormData(form).entries())
        .map(([key, value]) => [key, String(value)])
        .filter(([, value]) => value.trim()),
    );
    try {
      const response = await fetch(`/api/integrations/${provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credentials }),
      });
      const body = await response.json();
      if (!response.ok)
        throw new Error(
          body?.error?.message ?? "Não foi possível salvar a integração.",
        );
      setStatuses((current) => [
        ...current.filter((item) => item.provider !== provider),
        body,
      ]);
      form.reset();
      setMessage({
        type: "ok",
        text: "Credenciais criptografadas e salvas para este workspace.",
      });
    } catch (error) {
      setMessage({
        type: "error",
        text: error instanceof Error ? error.message : "Falha ao salvar.",
      });
    } finally {
      setSaving(null);
    }
  }
  async function verifyHermes() {
    setSaving("hermes");
    setMessage(null);
    try {
      const response = await fetch("/api/integrations/hermes/capabilities", {
        cache: "no-store",
      });
      const body = await response.json();
      if (!response.ok || body?.platform !== "hermes-agent")
        throw new Error(
          body?.error?.message ?? "A instância Hermes não respondeu.",
        );
      setMessage({
        type: "ok",
        text: `Instância ${body.instance_id} respondeu. A conexão está pronta; nenhuma automação foi iniciada.`,
      });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error instanceof Error ? error.message : "Falha ao verificar Hermes.",
      });
    } finally {
      setSaving(null);
    }
  }
  async function verifyInstagramSession() {
    setSaving("instagram_session");
    setMessage(null);
    try {
      const response = await fetch(
        "/api/integrations/instagram-session/status",
        { cache: "no-store" },
      );
      const body = await response.json();
      if (!response.ok || !body?.connected)
        throw new Error(
          body?.error?.message ?? "A sessão do Instagram não respondeu.",
        );
      setMessage({
        type: "ok",
        text: `Instagram conectado${body.username ? ` como @${body.username}` : ""}. A coleta de interações reais está pronta.`,
      });
    } catch (error) {
      setMessage({
        type: "error",
        text:
          error instanceof Error
            ? error.message
            : "Falha ao verificar o Instagram.",
      });
    } finally {
      setSaving(null);
    }
  }
  function renderField(field: Field) {
    return (
      <div className="grid gap-2" key={field.name}>
        <Label htmlFor={`${selected}-${field.name}`}>
          {field.label}
          {field.required ? (
            <span className="text-primary"> *</span>
          ) : (
            <span className="font-normal text-muted-foreground">
              {" "}
              · opcional
            </span>
          )}
        </Label>
        <div className="relative">
          <Input
            className="bg-background pr-10"
            id={`${selected}-${field.name}`}
            name={field.name}
            type={field.secret ? "password" : "text"}
            required={field.required}
            placeholder={
              statuses
                .find((item) => item.provider === selected)
                ?.configured_fields.includes(field.name)
                ? "Já configurado — digite para substituir"
                : field.placeholder
            }
            autoComplete="new-password"
          />
          {field.secret && (
            <KeyRound className="absolute right-3 top-2.5 size-4 text-muted-foreground" />
          )}
        </div>
      </div>

    );
  }
  return (
    <section className="space-y-4" aria-label="Conexões disponíveis">
      <div className="divide-y overflow-hidden rounded-2xl border bg-card">
        {providers.map((provider) => {
          const providerInfo = info[provider],
            Icon = providerInfo.icon,
            status = statuses.find((item) => item.provider === provider);
          return (
            <button
              key={provider}
              type="button"
              onClick={() => {
                setSelected(provider);
                setMessage(null);
              }}
              className={cn(
                "group flex w-full flex-wrap items-center gap-3 p-4 text-left transition-colors hover:bg-muted/40 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring sm:gap-4 sm:p-5",
                selected === provider &&
                  "bg-primary/5",
              )}
              aria-expanded={selected === provider}
              aria-controls="integration-configuration"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground" aria-hidden="true">
                <Icon className="size-4" />
              </span>
              <span className="min-w-0 flex-1 basis-[calc(100%-4rem)] sm:basis-0">
                <span className="block text-sm font-semibold">{providerInfo.name}</span>
                <span className="mt-1 block text-xs text-muted-foreground">{providerInfo.detail}</span>
              </span>
              <span className="ml-12 flex items-center gap-3 sm:ml-auto">
                <Badge
                  variant={status ? "secondary" : "outline"}
                  className="rounded-full"
                >
                  {provider === "mailerfind" && status?.is_global
                    ? "Ativo para todos"
                    : status
                      ? "Configurado"
                      : "Não conectado"}
                </Badge>
                <span className="flex items-center gap-2 text-xs font-medium text-primary">
                  {status ? "Configurar" : "Conectar"}
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                </span>
              </span>
            </button>
          );
        })}
      </div>
      {selected && (
        <div id="integration-configuration" ref={configurationRef} tabIndex={-1} role="region" aria-label={`Configurar ${info[selected].name}`} className="overflow-hidden rounded-2xl border bg-card focus-visible:outline-2 focus-visible:outline-ring">
          <header className="flex items-center justify-between gap-3 border-b p-5">
            <div>
              <h2 className="text-base font-semibold">
                {info[selected].name}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">Configure os dados da conexão.</p>
            </div>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setSelected(null)}
              aria-label="Fechar configuração"
            >
              <X />
            </Button>
          </header>
          <div className="p-5">
            {message && (
              <Alert
                variant={message.type === "error" ? "destructive" : "default"}
                className="mb-6"
              >
                <ShieldCheck />
                <AlertTitle>
                  {message.type === "ok" ? "Tudo certo" : "Revise os dados"}
                </AlertTitle>
                <AlertDescription>{message.text}</AlertDescription>
              </Alert>
            )}
            {selected === "mailerfind" ? (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
                      <Link2 className="size-5" />
                    </span>
                    <div>
                      <p className="font-semibold">Conexão global por OAuth</p>
                      <p className="text-sm text-muted-foreground">
                        Endpoint MCP verificado: mcp.mailerfind.com
                      </p>
                    </div>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">Autorize uma conta administrativa para disponibilizar as pesquisas a todos os usuários.</p>
                  <details className="mt-4 text-xs text-muted-foreground"><summary className="cursor-pointer font-medium">Permissões da conexão</summary><div className="mt-3 flex flex-wrap gap-2">
                    <Badge variant="outline">Todos os usuários</Badge>
                    <Badge variant="outline">mailerfind:read</Badge>
                    <Badge variant="outline">mailerfind:write</Badge>
                    <Badge variant="outline">PKCE</Badge>
                  </div></details>
                </div>
                <div className="flex flex-col gap-2">
                  <Button asChild size="lg">
                    <a href="/api/admin/integrations/mailerfind/connect">
                      <Link2 />
                      {statuses.some((item) => item.provider === "mailerfind")
                        ? "Reconectar para todos"
                        : "Conectar para todos"}
                    </a>
                  </Button>
                  <Button asChild variant="ghost" size="sm">
                    <a
                      href={info.mailerfind.href}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Ver documentação oficial
                      <ExternalLink />
                    </a>
                  </Button>
                </div>
              </div>
            ) : (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void save(selected, event.currentTarget);
                }}
                autoComplete="off"
              >
                <div className="grid gap-5 md:grid-cols-2">
                  {fields[selected].filter((field) => field.required).map(renderField)}
                  {fields[selected].some((field) => !field.required) && <details className="rounded-xl border p-4 md:col-span-2">
                    <summary className="cursor-pointer text-sm font-medium">Opções adicionais</summary>
                    <div className="mt-4 grid gap-5 md:grid-cols-2">{fields[selected].filter((field) => !field.required).map(renderField)}</div>
                  </details>}
                </div>
                <div className="mt-5 flex flex-wrap justify-end gap-3 border-t pt-5">
                  <div className="flex flex-wrap gap-2">
                    {selected === "hermes" &&
                      statuses.some((item) => item.provider === "hermes") && (
                        <Button
                          type="button"
                          variant="outline"
                          disabled={saving !== null}
                          onClick={() => void verifyHermes()}
                        >
                          Verificar instância
                        </Button>
                      )}
                    {selected === "instagram_session" &&
                      statuses.some(
                        (item) => item.provider === "instagram_session",
                      ) && (
                        <Button
                          type="button"
                          variant="outline"
                          disabled={saving !== null}
                          onClick={() => void verifyInstagramSession()}
                        >
                          Testar conexão
                        </Button>
                      )}
                    <Button type="submit" disabled={saving !== null}>
                      {saving ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <CheckCircle2 />
                      )}
                      Salvar conexão
                    </Button>
                  </div>
                </div>
              </form>
            )}
            <details className="mt-5 border-t pt-4 text-xs text-muted-foreground">
              <summary className="cursor-pointer font-medium">Ajuda para conectar</summary>
              <a href={info[selected].href} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 text-primary underline underline-offset-4">Gerar credenciais oficiais<ExternalLink className="size-3.5" /></a>
            {selected === "hermes" && (
              <p className="mt-4 text-xs leading-5 text-muted-foreground">
                Uma instância exclusiva por cliente. A chave dá acesso ao agente
                e às ferramentas dele; configure permissões na própria
                instância. Salvar ou verificar não inicia tarefas.
              </p>
            )}
            {selected === "postiz" && (
              <p className="mt-4 text-xs leading-5 text-muted-foreground">
                A chave fica criptografada no cofre da Kiara e é usada somente pelo servidor da aba Conteúdo. Para Postiz Cloud, use https://api.postiz.com. Para instalação própria, use https://seu-dominio/api.
              </p>
            )}
            </details>
          </div>
        </div>
      )}
    </section>
  );
}
