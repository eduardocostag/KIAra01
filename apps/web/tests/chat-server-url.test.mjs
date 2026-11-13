import assert from "node:assert/strict"
import { test } from "node:test"
import { chatServerUrl } from "../src/lib/chat-client.ts"

test("defaults to the bridge on this computer", () => {
  assert.equal(chatServerUrl(undefined), "http://127.0.0.1:3008")
  assert.equal(chatServerUrl(""), "http://127.0.0.1:3008")
})

test("accepts the always-on HTTPS server and trims trailing slashes", () => {
  assert.equal(chatServerUrl("https://kiara.example.com/"), "https://kiara.example.com")
  assert.equal(chatServerUrl("http://localhost:3008"), "http://localhost:3008")
})

test("rejects plain HTTP on the internet, credentials and junk", () => {
  for (const value of ["http://kiara.example.com", "https://user:pw@kiara.example.com", "https://kiara.example.com/?x=1", "javascript:alert(1)", "não é url"]) {
    assert.equal(chatServerUrl(value), "http://127.0.0.1:3008", value)
  }
})
