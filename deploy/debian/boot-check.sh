#!/usr/bin/env bash
# Checks that everything the Kiara needs comes back by itself after the server is switched on.
#
#   sudo bash deploy/debian/boot-check.sh          # report only, changes nothing
#   sudo bash deploy/debian/boot-check.sh --fix    # also turns on start-at-boot where it is missing
#
# --fix only: enables docker/containerd/tailscaled and the kiara-* units, and gives containers without a
# restart policy "unless-stopped". It never stops, recreates or deletes anything and never touches .env files.
set -u
FIX=0; [ "${1:-}" = "--fix" ] && FIX=1
problems=0
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$1"; }
bad()  { printf '  \033[31mFALHA\033[0m %s\n' "$1"; problems=$((problems + 1)); }
fixed(){ printf '  \033[33mAJUSTE\033[0m %s\n' "$1"; }

echo "== Serviços do sistema que precisam subir sozinhos"
units="docker containerd tailscaled"
for unit in $(systemctl list-unit-files --no-legend 'kiara-*' 2>/dev/null | awk '{print $1}'); do
  case "$unit" in *.service)
    # a service started by its timer does not need to be enabled itself
    [ -n "$(systemctl list-unit-files --no-legend "${unit%.service}.timer" 2>/dev/null)" ] && continue ;;
  esac
  units="$units $unit"
done
for unit in $units; do
  state=$(systemctl is-enabled "$unit" 2>/dev/null || true)
  case "$state" in
    enabled|static|alias|indirect) ok "$unit ($state)" ;;
    *) if [ $FIX = 1 ] && systemctl enable "$unit" >/dev/null 2>&1; then fixed "$unit: ligado para subir no boot"
       else bad "$unit não sobe sozinho no boot (estado: ${state:-desconhecido})"; fi ;;
  esac
  case "$unit" in *.timer|*.service|docker|containerd|tailscaled)
    systemctl is-active --quiet "$unit" || bad "$unit está parado agora" ;;
  esac
done

echo "== Contêineres (devem voltar sozinhos)"
if command -v docker >/dev/null; then
  for id in $(docker ps -aq); do
    name=$(docker inspect -f '{{.Name}}' "$id" | sed 's#^/##')
    policy=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$id")
    status=$(docker inspect -f '{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}' "$id")
    case "$policy" in
      always|unless-stopped) ok "$name ($policy, $status)" ;;
      *) if [ $FIX = 1 ] && docker update --restart unless-stopped "$id" >/dev/null; then fixed "$name: agora volta sozinho (unless-stopped)"
         else bad "$name não volta sozinho (política: ${policy:-nenhuma}, $status)"; fi ;;
    esac
    case "$status" in running|running/healthy|running/starting) ;; *) bad "$name não está rodando bem agora ($status)" ;; esac
  done
else
  bad "docker não encontrado"
fi

echo "== Acesso de fora (Tailscale Funnel)"
if command -v tailscale >/dev/null; then
  tailscale status >/dev/null 2>&1 && ok "tailscale conectado" || bad "tailscale desconectado"
  if tailscale funnel status 2>/dev/null | grep -q "Funnel on"; then ok "funnel ligado"; else bad "funnel desligado: a nuvem não alcança o servidor"; fi
else
  bad "tailscale não encontrado"
fi

echo "== Respostas dos serviços (local)"
probe() { # name url expected-codes
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$2" || true)
  case " $3 " in *" $code "*) ok "$1 (HTTP $code)" ;; *) bad "$1 não respondeu como esperado (HTTP ${code:-sem resposta})" ;; esac
}
probe "gateway"            http://127.0.0.1:8088/healthz      "200"
probe "vídeo"              http://127.0.0.1:8891/healthz      "200"
probe "navegador do Maps"  http://127.0.0.1:8892/healthz      "200"
probe "voz (Kokoro)"       http://127.0.0.1:8880/health       "200 404"
probe "OmniRoute"          http://127.0.0.1:20128/            "200 301 302 307 401 404"

echo "== Energia"
systemctl is-enabled sleep.target 2>/dev/null | grep -q masked && ok "suspensão desligada" || bad "o servidor pode entrar em suspensão"
echo "   (Ligar sozinho depois de uma queda de energia é uma opção da BIOS: 'Restore on AC Power Loss' = Power On.)"

echo
if [ $problems = 0 ]; then echo "Tudo certo: o servidor volta sozinho depois de ligado."; else echo "$problems problema(s) encontrado(s)."; fi
exit $((problems > 0))
