type Prospect = Record<string, unknown>;
function text(item: Prospect, keys: string[]) {
  for (const key of keys) if (typeof item[key] === "string" && item[key]) return item[key] as string;
  return "";
}
export function hasPublicContact(item: Prospect) {
  return Boolean(text(item, ["email", "publicEmail", "public_email"]) || text(item, ["phone_number", "phone", "phoneNumber"]));
}
export function filterProspects(items: Prospect[], query: string, contactsOnly: boolean) {
  const search = query.trim().toLocaleLowerCase("pt-BR");
  return items.filter((item) => (!contactsOnly || hasPublicContact(item)) && (!search || ["username", "userName", "handle", "full_name", "fullName", "name", "email", "publicEmail", "public_email", "phone_number", "phone", "comment_text"].some((key) => typeof item[key] === "string" && (item[key] as string).toLocaleLowerCase("pt-BR").includes(search))));
}
function cell(value: string) {
  // Spreadsheet applications execute formula prefixes even inside quoted cells.
  const safe = /^[\s]*[=+@-]/.test(value) || /^[\t\r\n]/.test(value) ? "'" + value : value;
  return '"' + safe.replaceAll('"', '""') + '"';
}
export function prospectsCsv(items: Prospect[]) {
  const rows = [["Usuário", "Nome", "Email público", "Telefone público", "Perfil", "Comentário"]];
  for (const item of items) rows.push([
    text(item, ["username", "userName", "handle"]), text(item, ["full_name", "fullName", "name"]),
    text(item, ["email", "publicEmail", "public_email"]), text(item, ["phone_number", "phone", "phoneNumber"]),
    text(item, ["profile_url", "profileUrl"]), text(item, ["comment_text"]),
  ]);
  return "\uFEFF" + rows.map((row) => row.map(cell).join(";")).join("\r\n");
}
