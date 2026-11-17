# Aprendizado da Kiara + cofre do Obsidian

A cada 6 horas o timer `kiara-learning.timer` chama a API:

1. `POST /v1/learning/internal/tick`: para cada empresa, a Kiara olha as buscas de leads (o que virou lead, o que avançou,
   o que não deu certo) e guarda até 5 lições na memória daquela empresa; e atualiza os padrões gerais (só números por
   nicho e cidade, sem nomes nem telefones; um padrão só aparece com pelo menos 2 empresas).
2. `GET /v1/learning/internal/vault`: as notas do Obsidian com os padrões gerais, gravadas em `/var/lib/kiara-vault`.

Nenhum dado de uma empresa vai para o cofre: ele tem só os padrões gerais. Abra a pasta como cofre no Obsidian
(por sincronização, ex.: Syncthing). As notas são reescritas a cada execução; não edite.

Instalação (segredos em `/opt/kiara/learning/.env`, root 0600: `KIARA_API_URL` e `KIARA_WORKER_TOKEN`, os mesmos do SDR):

```sh
sudo install -m 0755 kiara-learning-tick.sh /usr/local/lib/kiara/
sudo install -m 0644 kiara-learning.service kiara-learning.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now kiara-learning.timer
sudo systemctl start kiara-learning.service && journalctl -u kiara-learning -n 5
```
