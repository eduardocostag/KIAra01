type VideoState = { status: "running" | "queued" | "done" | "failed" }

/** Poll an existing job only. A transient error must never create another video. */
export function pollVideoJob<T extends VideoState>({
  read, onUpdate, onError, onPaused,
  intervalMs = 4000, maxFailures = 4,
  schedule = (callback, delay) => setTimeout(callback, delay),
  cancel = (timer) => clearTimeout(timer),
}: {
  read: (signal: AbortSignal) => Promise<T>
  onUpdate: (job: T) => void
  onError: (error: unknown) => void
  onPaused: () => void
  intervalMs?: number
  maxFailures?: number
  schedule?: (callback: () => void, delay: number) => ReturnType<typeof setTimeout>
  cancel?: (timer: ReturnType<typeof setTimeout>) => void
}): () => void {
  const controller = new AbortController()
  let stopped = false
  let failures = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  function stop() {
    stopped = true
    controller.abort()
    if (timer !== undefined) cancel(timer)
  }

  async function tick() {
    if (stopped) return
    try {
      const job = await read(controller.signal)
      if (stopped) return
      failures = 0
      onUpdate(job)
      if (job.status === "done" || job.status === "failed") {
        stop()
        return
      }
      timer = schedule(() => { void tick() }, intervalMs)
    } catch (error) {
      if (stopped) return
      failures += 1
      onError(error)
      if (failures >= maxFailures) {
        stop()
        onPaused()
        return
      }
      timer = schedule(() => { void tick() }, Math.min(30_000, intervalMs * 2 ** failures))
    }
  }

  timer = schedule(() => { void tick() }, intervalMs)
  return stop
}
