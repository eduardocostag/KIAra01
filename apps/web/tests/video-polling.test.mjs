import assert from "node:assert/strict"
import { test } from "node:test"
import { pollVideoJob } from "../src/lib/video-polling.ts"

function clock() {
  let next = 0
  const timers = new Map()
  const delays = []
  return {
    timers, delays,
    schedule(callback, delay) { const id = ++next; timers.set(id, callback); delays.push(delay); return id },
    cancel(id) { timers.delete(id) },
    async tick() {
      const [id, callback] = timers.entries().next().value
      timers.delete(id)
      callback()
      await new Promise(setImmediate)
    },
  }
}

test("a failed status request recovers and reaches the completed video", async () => {
  const time = clock(), updates = [], errors = []
  let requests = 0, paused = false
  pollVideoJob({ ...time, read: async () => {
    requests += 1
    if (requests === 1) throw new Error("Temporary connection failure")
    return { status: requests === 2 ? "running" : "done" }
  }, onUpdate: (job) => updates.push(job.status), onError: (error) => errors.push(error.message), onPaused: () => { paused = true } })
  await time.tick()
  await time.tick()
  await time.tick()
  assert.deepEqual(updates, ["running", "done"])
  assert.equal(errors.length, 1)
  assert.deepEqual(time.delays, [4000, 8000, 4000])
  assert.equal(time.timers.size, 0)
  assert.equal(paused, false)
})

test("repeated failures pause after bounded retries and a fresh status subscription can resume", async () => {
  const time = clock()
  let reads = 0, paused = false, completed = false
  const options = { ...time, maxFailures: 3, onUpdate() {}, onError() {}, onPaused: () => { paused = true } }
  pollVideoJob({ ...options, read: async () => { reads += 1; throw new Error("offline") } })
  await time.tick(); await time.tick(); await time.tick()
  assert.equal(reads, 3)
  assert.equal(paused, true)
  assert.equal(time.timers.size, 0)
  pollVideoJob({ ...options, read: async () => ({ status: "done" }), onUpdate: () => { completed = true } })
  await time.tick()
  assert.equal(completed, true)
  assert.equal(time.timers.size, 0)
})

test("unmount cancels the timer and aborts or ignores an in-flight response", async () => {
  const time = clock()
  let finish, signal, updates = 0, errors = 0
  const stop = pollVideoJob({ ...time, read: async (activeSignal) => {
    signal = activeSignal
    return new Promise((resolve) => { finish = resolve })
  }, onUpdate: () => { updates += 1 }, onError: () => { errors += 1 }, onPaused() {} })
  await time.tick()
  stop()
  assert.equal(signal.aborted, true)
  finish({ status: "done" })
  await new Promise(setImmediate)
  assert.equal(updates, 0)
  assert.equal(errors, 0)
  assert.equal(time.timers.size, 0)

  const cancel = pollVideoJob({ ...time, read: async () => { throw new Error("Must not be read") }, onUpdate() {}, onError() {}, onPaused() {} })
  cancel()
  assert.equal(time.timers.size, 0)
})

test("terminal failed jobs do not continue polling", async () => {
  const time = clock()
  const updates = []
  pollVideoJob({ ...time, read: async () => ({ status: "failed" }), onUpdate: (job) => updates.push(job.status), onError() {}, onPaused() {} })
  await time.tick()
  assert.deepEqual(updates, ["failed"])
  assert.equal(time.timers.size, 0)
})
