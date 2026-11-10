import assert from "node:assert/strict";
import { test } from "node:test";
import { filterProspects, prospectsCsv } from "../src/lib/competition/export.ts";
test("filters the exact exported subset by public contact and search", () => {
  const data = [{username:"ana", email:"ana@example.test"}, {username:"bia"}, {username:"carla",phone_number:"+5511999999999"}];
  assert.equal(filterProspects(data,"",true).length,2);
  assert.deepEqual(filterProspects(data,"ANA",true),[data[0]]);
  assert.equal(filterProspects(data,"bia",true).length,0);
});
test("CSV quotes multiline data and neutralizes spreadsheet formulas", () => {
  const csv=prospectsCsv([{username:"=HYPERLINK(1)",full_name:'Ana "A"',comment_text:"oi\nlinha",phone_number:"+5511"}]);
  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.includes('"\'=HYPERLINK(1)"'));
  assert.ok(csv.includes('"Ana ""A"""'));
  assert.ok(csv.includes('"oi\nlinha"'));
  assert.ok(csv.includes('"\'+5511"'));
});
