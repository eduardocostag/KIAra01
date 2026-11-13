"use client"

import { useEffect, useRef } from "react"

const VERTEX = `attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }`

// Living plasma around Kiara's orb: a noisy ring whose radius, turbulence and glow follow the voice level.
const FRAGMENT = `#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
uniform vec2 res; uniform float time; uniform float level; uniform float mode;
float hash(vec2 p) { p = fract(p * vec2(0.1031, 0.1030)); p += dot(p, p.yx + 33.33); return fract((p.x + p.y) * p.x); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }
void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * res) / min(res.x, res.y);
  float r = length(uv), a = atan(uv.y, uv.x);
  float speed = mode > 1.5 ? 1.8 : mode > 0.5 ? 1.1 : 0.45;
  // Noise sampled on the circle (cos, sin) so there is no seam where the angle wraps.
  vec2 around = vec2(cos(a), sin(a)) * 1.7;
  float n = fbm(around + vec2(time * 0.22 * speed, r * 2.5 - time * 0.5 * speed));
  float edge = 0.33 + level * 0.07 + (n - 0.5) * (0.05 + level * 0.12);
  float ring = smoothstep(0.08 + level * 0.05, 0.0, abs(r - edge));
  float halo = smoothstep(0.5, edge, r) * 0.35;
  vec3 violet = vec3(0.56, 0.32, 1.0), pink = vec3(0.98, 0.45, 0.85), cyan = vec3(0.35, 0.8, 1.0);
  vec3 tint = mix(violet, mode > 1.5 ? pink : cyan, 0.5 + 0.5 * sin(a * 2.0 + time * 0.7));
  float glow = (ring * (0.55 + level * 0.9) + halo * (0.4 + level)) * smoothstep(0.62, 0.42, r);
  gl_FragColor = vec4(tint * glow, glow);
}`

const modes: Record<string, number> = { idle: 0, thinking: 1, listening: 1, speaking: 2, error: 0 }

/**
 * WebGL aura drawn behind the voice orb. It reads the `--level` and `data-state` the voice loop
 * already writes on the orb stage, so it adds no React work per frame. Without WebGL it draws nothing.
 */
export function VoiceAura() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    const stage = canvas?.parentElement
    const gl = canvas?.getContext("webgl", { premultipliedAlpha: false, alpha: true })
    if (!canvas || !stage || !gl) return
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    function shader(type: number, source: string) {
      const item = gl!.createShader(type)!
      gl!.shaderSource(item, source); gl!.compileShader(item)
      return item
    }
    const program = gl.createProgram()!
    gl.attachShader(program, shader(gl.VERTEX_SHADER, VERTEX))
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FRAGMENT))
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return
    gl.useProgram(program)
    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
    const position = gl.getAttribLocation(program, "p")
    gl.enableVertexAttribArray(position)
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE)
    const uniforms = { res: gl.getUniformLocation(program, "res"), time: gl.getUniformLocation(program, "time"), level: gl.getUniformLocation(program, "level"), mode: gl.getUniformLocation(program, "mode") }

    let frame = 0, smooth = 0
    const started = performance.now()
    function draw(now: number) {
      const size = Math.round(canvas!.clientWidth * Math.min(2, window.devicePixelRatio || 1))
      if (canvas!.width !== size) { canvas!.width = size; canvas!.height = size }
      gl!.viewport(0, 0, size, size)
      smooth += ((Number(stage!.style.getPropertyValue("--level")) || 0) - smooth) * .25
      gl!.uniform2f(uniforms.res, size, size)
      gl!.uniform1f(uniforms.time, reduced ? 0 : (now - started) / 1000)
      gl!.uniform1f(uniforms.level, Math.min(1, smooth))
      gl!.uniform1f(uniforms.mode, modes[stage!.dataset.state ?? "idle"] ?? 0)
      gl!.clearColor(0, 0, 0, 0); gl!.clear(gl!.COLOR_BUFFER_BIT)
      gl!.drawArrays(gl!.TRIANGLE_STRIP, 0, 4)
      if (!reduced) frame = requestAnimationFrame(draw)
    }
    frame = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(frame); gl.deleteProgram(program); gl.deleteBuffer(buffer) }
  }, [])
  return <canvas ref={canvasRef} aria-hidden="true" style={{ position: "absolute", inset: "-22%", width: "144%", height: "144%", pointerEvents: "none", zIndex: 0 }} />
}
