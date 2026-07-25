# Voce del Kiosk — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the voice layer to the kiosk SPA — read the current screen's text aloud (TTS) and let the person dictate answers (STT) — consuming the S8 voice API, with graceful voice↔text degradation.

**Architecture:** A `voiceClient` (fail-closed HTTP over `/kiosk/voice/*`), two hooks that isolate the browser APIs (`useSpeech` for playback, `useRecorder` for capture), a `VoiceProvider` context carrying `{language, muted, client}`, and a `VoiceBar` component embedded in the screens. The interview state machine is untouched — voice fills the existing answer field and reads `step.text`.

**Tech Stack:** React 18 + Vite + TypeScript + react-i18next, Vitest + @testing-library/react. Browser-native APIs (`getUserMedia`/`MediaRecorder`/`Audio`) — NO new dependencies.

## Global Constraints

- **Local/offline, open-source permissive only; no new dependencies** — voice uses browser-native APIs (`CLAUDE.md` §3).
- **Voice is an enhancement over a text base that always works; degradation never blocks** (§3/§7.1): `transcribe` 503/network or mic denied/absent → the text field stays and the person writes; `synthesize` 204/network → no audio, text stays; autoplay blocked → text stays. No path throws to the UI. «✕ Ferma» stays available.
- **The interview state machine is NOT modified.** Dictation writes into the existing answer field for review; the person submits explicitly (never auto-submit) — §5.
- **Auto-read on each new step** (if not muted); a session **mute** toggle; «Ascolta» replays on demand (works even when muted — explicit request).
- **All user-facing strings externalized via i18n** in ALL 5 catalogs with identical keys (parity test must hold); code/identifiers in English (§11).
- **`X-Kiosk-Token` on every voice call** (build-time `VITE_KIOSK_TOKEN`), like `kioskClient`.
- **The language passed to both voice endpoints is the interview language** (`state.language`).
- **TDD; only synthetic data.** Browser APIs (`getUserMedia`/`MediaRecorder`/`Audio`/`URL.createObjectURL`) are absent in jsdom — mock them; the `voiceClient` is injected via `VoiceProvider` so tests default to a silent no-op client. Test output must be pristine (no act() warnings).
- **Arabic read-aloud is expected to be absent** (S7 has no `ar` voice → `synthesize` 204 → text); Arabic dictation (Whisper) works. This is the §8 fallback, handled by the normal 204→null path — no special-casing.

---

## File Structure

```
frontend/src/
  voice/
    voiceClient.ts        (Task 1)  transcribe/synthesize, fail-closed
    voiceClient.test.ts
    useSpeech.ts          (Task 2)  TTS playback hook
    useSpeech.test.tsx
    VoiceContext.tsx      (Task 3)  VoiceProvider {language,muted,setMuted,client} + useVoice
    useRecorder.ts        (Task 4)  STT capture hook
    useRecorder.test.tsx
  components/
    VoiceBar.tsx          (Task 3 read-aloud+mute → Task 5 adds dictation)
    VoiceBar.test.tsx
    AnswerPrompt.tsx      (Task 6 — embeds VoiceBar, dictation→field)
    ConfirmCorrect.tsx    (Task 6 — embeds VoiceBar)
    VoicePlaceholder.tsx  (Task 7 — DELETED)
  screens/
    Consent.tsx, Unavailable.tsx, Completed.tsx, Unauthorized.tsx  (Task 7 — add read-only VoiceBar)
  i18n/locales/{it,en,fr,es,ar}.ts   (Task 1 — add voice.* keys; Task 7 — remove voice.placeholder)
  test/utils.tsx          (Task 3 — wrap VoiceProvider, accept overrides)
  test/fakeClient.ts      (Task 1 — add noopVoiceClient + makeVoiceClient)
  App.tsx / main.tsx      (Task 7 — VoiceProvider(language), remove VoicePlaceholder)
  styles/theme.css        (Task 7 — .voice-bar styles)
```

---

## Task 1: `voiceClient` + voice i18n keys

**Files:**
- Create: `frontend/src/voice/voiceClient.ts`
- Test: `frontend/src/voice/voiceClient.test.ts`
- Modify: `frontend/src/i18n/locales/{it,en,fr,es,ar}.ts` (add a `voice.*` key block — keep the existing `voice.placeholder` for now)
- Modify: `frontend/src/test/fakeClient.ts` (add `noopVoiceClient` + `makeVoiceClient`)

**Interfaces:**
- Produces:
  - `interface VoiceClient { transcribe(blob: Blob, language: string): Promise<{ status: 'ok'; text: string } | { status: 'unavailable' }>; synthesize(text: string, language: string): Promise<Blob | null> }`
  - `const voiceClient: VoiceClient`
  - `noopVoiceClient: VoiceClient` (synthesize→null, transcribe→unavailable) and `makeVoiceClient(opts)` in test/fakeClient.ts
  - i18n keys under `voice`: `speak, stop, listening, transcribing, listen, audioOn, audioOff, muteToggle, micDenied`

- [ ] **Step 1: Write the failing test**

`frontend/src/voice/voiceClient.test.ts`:
```ts
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { voiceClient } from './voiceClient'

afterEach(() => vi.unstubAllGlobals())

test('transcribe posts multipart audio+language with the kiosk token and maps 200', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ text: 'so cucinare' }),
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
  const blob = new Blob(['x'], { type: 'audio/webm' })
  const res = await voiceClient.transcribe(blob, 'it')
  expect(res).toEqual({ status: 'ok', text: 'so cucinare' })
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/voice/transcribe')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  const body = (init as RequestInit).body as FormData
  expect(body).toBeInstanceOf(FormData)
  expect(body.get('language')).toBe('it')
  expect(body.get('audio')).toBeInstanceOf(Blob)
})

test('transcribe maps 503 and a thrown fetch to unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 } as Response))
  expect(await voiceClient.transcribe(new Blob(), 'it')).toEqual({ status: 'unavailable' })
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await voiceClient.transcribe(new Blob(), 'it')).toEqual({ status: 'unavailable' })
})

test('synthesize posts json and returns the audio blob on 200', async () => {
  const audio = new Blob(['wav'], { type: 'audio/wav' })
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    blob: async () => audio,
  } as unknown as Response)
  vi.stubGlobal('fetch', fetchMock)
  const res = await voiceClient.synthesize('Sai cucinare?', 'it')
  expect(res).toBe(audio)
  const [url, init] = fetchMock.mock.calls[0]
  expect(String(url)).toContain('/kiosk/voice/synthesize')
  expect((init!.headers as Record<string, string>)['X-Kiosk-Token']).toBeDefined()
  expect(JSON.parse((init as RequestInit).body as string)).toEqual({ text: 'Sai cucinare?', language: 'it' })
})

test('synthesize maps 204 and a thrown fetch to null', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 204 } as Response))
  expect(await voiceClient.synthesize('x', 'it')).toBeNull()
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
  expect(await voiceClient.synthesize('x', 'it')).toBeNull()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- voiceClient`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `voiceClient.ts`**

```ts
const BASE = import.meta.env.VITE_API_BASE ?? ''
const TOKEN = import.meta.env.VITE_KIOSK_TOKEN ?? ''

export interface VoiceClient {
  transcribe(blob: Blob, language: string): Promise<{ status: 'ok'; text: string } | { status: 'unavailable' }>
  synthesize(text: string, language: string): Promise<Blob | null>
}

async function transcribe(
  blob: Blob,
  language: string,
): Promise<{ status: 'ok'; text: string } | { status: 'unavailable' }> {
  const form = new FormData()
  form.append('audio', blob, 'audio.webm')
  form.append('language', language)
  let res: Response
  try {
    // No Content-Type header: the browser sets the multipart boundary.
    res = await fetch(`${BASE}/kiosk/voice/transcribe`, {
      method: 'POST',
      headers: { 'X-Kiosk-Token': TOKEN },
      body: form,
    })
  } catch {
    return { status: 'unavailable' }
  }
  if (!res.ok) return { status: 'unavailable' } // 503 = voice unavailable, use text
  try {
    const data = (await res.json()) as { text: string }
    return { status: 'ok', text: data.text }
  } catch {
    return { status: 'unavailable' }
  }
}

async function synthesize(text: string, language: string): Promise<Blob | null> {
  let res: Response
  try {
    res = await fetch(`${BASE}/kiosk/voice/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Kiosk-Token': TOKEN },
      body: JSON.stringify({ text, language }),
    })
  } catch {
    return null
  }
  if (res.status === 204 || !res.ok) return null // 204 = no audio, read the text
  try {
    return await res.blob()
  } catch {
    return null
  }
}

export const voiceClient: VoiceClient = { transcribe, synthesize }
```

- [ ] **Step 4: Add the voice i18n keys to all 5 catalogs**

In each `frontend/src/i18n/locales/<lang>.ts`, add a `voice` sibling key block (KEEP the existing `voice.placeholder` — it is removed in Task 7; if `voice` is already an object with `placeholder`, ADD these keys into it). Use exactly:

`it.ts` — `voice: { placeholder: '…(existing)…', speak: 'Parla', stop: 'Stop', listening: 'sto ascoltando…', transcribing: 'sto trascrivendo…', listen: 'Ascolta', audioOn: 'Audio acceso', audioOff: 'Audio spento', muteToggle: 'Attiva o disattiva l\'audio', micDenied: 'Microfono non disponibile — scrivi pure.' }`

`en.ts` — `speak: 'Speak', stop: 'Stop', listening: 'listening…', transcribing: 'transcribing…', listen: 'Listen', audioOn: 'Audio on', audioOff: 'Audio off', muteToggle: 'Turn audio on or off', micDenied: 'Microphone unavailable — please type.'`

`fr.ts` — `speak: 'Parler', stop: 'Stop', listening: 'écoute…', transcribing: 'transcription…', listen: 'Écouter', audioOn: 'Audio activé', audioOff: 'Audio coupé', muteToggle: 'Activer ou couper le son', micDenied: 'Micro indisponible — écris, tout simplement.'`

`es.ts` — `speak: 'Hablar', stop: 'Parar', listening: 'escuchando…', transcribing: 'transcribiendo…', listen: 'Escuchar', audioOn: 'Audio activado', audioOff: 'Audio apagado', muteToggle: 'Activar o desactivar el audio', micDenied: 'Micrófono no disponible — escribe, por favor.'`

`ar.ts` — `speak: 'تحدّث', stop: 'إيقاف', listening: 'جارٍ الاستماع…', transcribing: 'جارٍ التفريغ…', listen: 'استمع', audioOn: 'الصوت مُفعّل', audioOff: 'الصوت مُطفأ', muteToggle: 'تشغيل الصوت أو إيقافه', micDenied: 'الميكروفون غير متاح — اكتب من فضلك.'`

(Each catalog's `voice` object must end up with the SAME keys — the existing `i18n.test.ts` parity test enforces this.)

- [ ] **Step 5: Add test voice-client fakes to `frontend/src/test/fakeClient.ts`**

Append:
```ts
import type { VoiceClient } from '../voice/voiceClient'

// Silent default for component tests: no audio, dictation unavailable.
export const noopVoiceClient: VoiceClient = {
  async transcribe() {
    return { status: 'unavailable' }
  },
  async synthesize() {
    return null
  },
}

// Configurable fake for voice tests. `transcript` → transcribe result text;
// `audio` → a Blob for synthesize (null = 204/no audio).
export function makeVoiceClient(opts: { transcript?: string; audio?: Blob | null } = {}): VoiceClient & {
  calls: { transcribe: number; synthesize: Array<{ text: string; language: string }> }
} {
  const calls = { transcribe: 0, synthesize: [] as Array<{ text: string; language: string }> }
  return {
    calls,
    async transcribe() {
      calls.transcribe++
      return opts.transcript !== undefined
        ? { status: 'ok', text: opts.transcript }
        : { status: 'unavailable' }
    },
    async synthesize(text: string, language: string) {
      calls.synthesize.push({ text, language })
      return opts.audio ?? null
    },
  }
}
```

- [ ] **Step 6: Run the tests and the gate**

Run: `npm test -- voiceClient i18n && npm run typecheck && npm run lint`
Expected: PASS (voiceClient tests green; i18n parity still green with the new keys).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/voice/voiceClient.ts frontend/src/voice/voiceClient.test.ts frontend/src/i18n/locales frontend/src/test/fakeClient.ts
git commit -m "feat(kiosk-voice): fail-closed voiceClient (S8 /kiosk/voice/*) + voice i18n keys"
```

---

## Task 2: `useSpeech` — TTS playback hook

**Files:**
- Create: `frontend/src/voice/useSpeech.ts`
- Test: `frontend/src/voice/useSpeech.test.tsx`

**Interfaces:**
- Consumes: `useVoice()` from `./VoiceContext` (Task 3) — **NOTE:** this task is written before Task 3's context exists. To keep tasks independent, `useSpeech` takes the client as a parameter: `useSpeech(client: VoiceClient)`. Task 3's `VoiceBar` will call `useSpeech(useVoice().client)`.
- Produces: `function useSpeech(client: VoiceClient): { play(text: string, language: string): Promise<void>; stop(): void; speaking: boolean }`

- [ ] **Step 1: Write the failing test**

`frontend/src/voice/useSpeech.test.tsx`:
```tsx
import { renderHook, act } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { useSpeech } from './useSpeech'
import { makeVoiceClient } from '../test/fakeClient'

class MockAudio {
  static instances: MockAudio[] = []
  onended: (() => void) | null = null
  paused = true
  constructor(public src: string) {
    MockAudio.instances.push(this)
  }
  play() {
    this.paused = false
    return Promise.resolve()
  }
  pause() {
    this.paused = true
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  MockAudio.instances = []
})

function stubAudio() {
  vi.stubGlobal('Audio', MockAudio as unknown as typeof Audio)
  vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })
}

test('play synthesizes and plays the returned audio', async () => {
  stubAudio()
  const client = makeVoiceClient({ audio: new Blob(['wav']) })
  const { result } = renderHook(() => useSpeech(client))
  await act(async () => {
    await result.current.play('Sai cucinare?', 'it')
  })
  expect(client.calls.synthesize).toEqual([{ text: 'Sai cucinare?', language: 'it' }])
  expect(MockAudio.instances).toHaveLength(1)
  expect(MockAudio.instances[0].paused).toBe(false)
  expect(result.current.speaking).toBe(true)
})

test('play with no audio (204) is a silent no-op — no Audio created', async () => {
  stubAudio()
  const client = makeVoiceClient({ audio: null })
  const { result } = renderHook(() => useSpeech(client))
  await act(async () => {
    await result.current.play('x', 'it')
  })
  expect(MockAudio.instances).toHaveLength(0)
  expect(result.current.speaking).toBe(false)
})

test('stop pauses the current audio', async () => {
  stubAudio()
  const client = makeVoiceClient({ audio: new Blob(['wav']) })
  const { result } = renderHook(() => useSpeech(client))
  await act(async () => {
    await result.current.play('x', 'it')
  })
  act(() => result.current.stop())
  expect(MockAudio.instances[0].paused).toBe(true)
  expect(result.current.speaking).toBe(false)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- useSpeech`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `useSpeech.ts`**

```ts
import { useCallback, useRef, useState } from 'react'
import type { VoiceClient } from './voiceClient'

export function useSpeech(client: VoiceClient) {
  const [speaking, setSpeaking] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setSpeaking(false)
  }, [])

  const play = useCallback(
    async (text: string, language: string) => {
      stop()
      const blob = await client.synthesize(text, language)
      if (!blob) return // 204/no audio → stay on text, no state change
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        URL.revokeObjectURL(url)
        setSpeaking(false)
      }
      try {
        await audio.play()
        setSpeaking(true)
      } catch {
        setSpeaking(false) // autoplay blocked → text stays
      }
    },
    [client, stop],
  )

  return { play, stop, speaking }
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- useSpeech && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/voice/useSpeech.ts frontend/src/voice/useSpeech.test.tsx
git commit -m "feat(kiosk-voice): useSpeech playback hook (queue-of-one, 204→no-op)"
```

---

## Task 3: `VoiceContext` + `VoiceBar` (read-aloud + mute) + test-helper wiring

**Files:**
- Create: `frontend/src/voice/VoiceContext.tsx`
- Create: `frontend/src/components/VoiceBar.tsx`
- Test: `frontend/src/components/VoiceBar.test.tsx`
- Modify: `frontend/src/test/utils.tsx` (wrap `VoiceProvider`, accept overrides)

**Interfaces:**
- Consumes: `useSpeech` (Task 2), `voiceClient`/`VoiceClient` (Task 1).
- Produces:
  - `VoiceProvider(props: { language: string; muted?: boolean; client?: VoiceClient; children: ReactNode })`
  - `useVoice(): { language: string; muted: boolean; setMuted: (m: boolean) => void; client: VoiceClient }`
  - `VoiceBar(props: { text: string })` — auto-reads `text` on change (if not muted), «Ascolta» replay, mute toggle
  - `renderWithProviders(ui, opts?: { voiceClient?: VoiceClient; language?: string })`

- [ ] **Step 1: Write the failing test**

`frontend/src/components/VoiceBar.test.tsx`:
```tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { renderWithProviders } from '../test/utils'
import { makeVoiceClient } from '../test/fakeClient'
import { VoiceBar } from './VoiceBar'
import i18n from '../i18n'

test('auto-reads the text on mount (calls synthesize with text + language)', async () => {
  await i18n.changeLanguage('it')
  const client = makeVoiceClient({ audio: null }) // null → no Audio, silent
  renderWithProviders(<VoiceBar text="Che lavoro sai fare?" />, { voiceClient: client, language: 'it' })
  await waitFor(() => expect(client.calls.synthesize).toEqual([{ text: 'Che lavoro sai fare?', language: 'it' }]))
})

test('mute toggle suppresses auto-read and is reflected in aria-pressed', async () => {
  await i18n.changeLanguage('it')
  const client = makeVoiceClient({ audio: null })
  renderWithProviders(<VoiceBar text="Domanda" />, { voiceClient: client, language: 'it' })
  await waitFor(() => expect(client.calls.synthesize.length).toBe(1))
  const mute = screen.getByRole('button', { name: /audio/i })
  await userEvent.click(mute)
  expect(mute).toHaveAttribute('aria-pressed', 'true')
})

test('«Ascolta» replays on demand', async () => {
  await i18n.changeLanguage('it')
  const client = makeVoiceClient({ audio: null })
  renderWithProviders(<VoiceBar text="Domanda" />, { voiceClient: client, language: 'it' })
  await waitFor(() => expect(client.calls.synthesize.length).toBe(1))
  await userEvent.click(screen.getByRole('button', { name: 'Ascolta' }))
  await waitFor(() => expect(client.calls.synthesize.length).toBe(2))
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- VoiceBar`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `VoiceContext.tsx`**

```tsx
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { voiceClient as realClient, type VoiceClient } from './voiceClient'

interface VoiceContextValue {
  language: string
  muted: boolean
  setMuted: (m: boolean) => void
  client: VoiceClient
}

const VoiceContext = createContext<VoiceContextValue | null>(null)

export function VoiceProvider({
  language,
  muted: initialMuted = false,
  client = realClient,
  children,
}: {
  language: string
  muted?: boolean
  client?: VoiceClient
  children: ReactNode
}) {
  const [muted, setMuted] = useState(initialMuted)
  const value = useMemo(() => ({ language, muted, setMuted, client }), [language, muted, client])
  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>
}

export function useVoice(): VoiceContextValue {
  const ctx = useContext(VoiceContext)
  if (!ctx) throw new Error('useVoice must be used within a VoiceProvider')
  return ctx
}
```

- [ ] **Step 4: Implement `VoiceBar.tsx` (read-aloud + mute)**

```tsx
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useVoice } from '../voice/VoiceContext'
import { useSpeech } from '../voice/useSpeech'

export function VoiceBar({ text }: { text: string }) {
  const { t } = useTranslation()
  const { language, muted, setMuted, client } = useVoice()
  const { play, stop } = useSpeech(client)

  // Auto-read the current text when it (or the language) changes, unless muted.
  useEffect(() => {
    if (!muted && text) void play(text, language)
    return () => stop()
  }, [text, language, muted, play, stop])

  function toggleMute() {
    if (!muted) stop()
    setMuted(!muted)
  }

  return (
    <div className="voice-bar">
      <button className="voice-btn" aria-label={t('voice.listen')} onClick={() => void play(text, language)}>
        🔊 {t('voice.listen')}
      </button>
      <button className="voice-btn" aria-pressed={muted} aria-label={t('voice.muteToggle')} onClick={toggleMute}>
        {muted ? '🔇' : '🔈'} {muted ? t('voice.audioOff') : t('voice.audioOn')}
      </button>
    </div>
  )
}
```

- [ ] **Step 5: Extend `test/utils.tsx` to provide `VoiceProvider`**

```tsx
import { render, type RenderResult } from '@testing-library/react'
import { type ReactElement } from 'react'
import { I18nextProvider } from 'react-i18next'
import i18n from '../i18n'
import { TextSizeProvider } from '../a11y/TextSize'
import { VoiceProvider } from '../voice/VoiceContext'
import { noopVoiceClient } from './fakeClient'
import type { VoiceClient } from '../voice/voiceClient'

export function renderWithProviders(
  ui: ReactElement,
  opts: { voiceClient?: VoiceClient; language?: string } = {},
): RenderResult {
  return render(
    <I18nextProvider i18n={i18n}>
      <TextSizeProvider>
        <VoiceProvider language={opts.language ?? 'it'} client={opts.voiceClient ?? noopVoiceClient}>
          {ui}
        </VoiceProvider>
      </TextSizeProvider>
    </I18nextProvider>,
  )
}
```

(All existing tests keep passing — they don't consume the voice context, and the default `noopVoiceClient` produces no audio.)

- [ ] **Step 6: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS (VoiceBar tests green; full suite still green — the new `VoiceProvider` in `renderWithProviders` is inert for non-voice components).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/voice/VoiceContext.tsx frontend/src/components/VoiceBar.tsx frontend/src/components/VoiceBar.test.tsx frontend/src/test/utils.tsx
git commit -m "feat(kiosk-voice): VoiceProvider + VoiceBar auto-read & mute; test helper wiring"
```

---

## Task 4: `useRecorder` — STT capture hook

**Files:**
- Create: `frontend/src/test/media.ts` (shared browser-media mock, imported by Tasks 4/5/6 tests)
- Create: `frontend/src/voice/useRecorder.ts`
- Test: `frontend/src/voice/useRecorder.test.tsx`

**Interfaces:**
- Consumes: `useVoice()` (Task 3) for `{ client, language }`.
- Produces:
  - `type RecorderState = 'idle' | 'requesting' | 'recording' | 'transcribing' | 'denied' | 'unavailable'`
  - `function recorderSupported(): boolean`
  - `function useRecorder(opts: { onText: (text: string) => void }): { state: RecorderState; start(): Promise<void>; stop(): void; supported: boolean }`
  - `src/test/media.ts` exports `MockMediaRecorder` and `stubMedia(granted?: boolean)`.

- [ ] **Step 1: Create the shared media mock `frontend/src/test/media.ts`**

```ts
import { vi } from 'vitest'

// Browser media APIs are absent in jsdom; this stubs getUserMedia + MediaRecorder.
export class MockMediaRecorder {
  static instances: MockMediaRecorder[] = []
  state: 'inactive' | 'recording' = 'inactive'
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  mimeType = 'audio/webm'
  constructor(public stream: MediaStream) {
    MockMediaRecorder.instances.push(this)
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['chunk'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}

export function stubMedia(granted = true): void {
  const stream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream
  vi.stubGlobal('navigator', {
    mediaDevices: {
      getUserMedia: granted
        ? vi.fn().mockResolvedValue(stream)
        : vi.fn().mockRejectedValue(new Error('denied')),
    },
  })
  vi.stubGlobal('MediaRecorder', MockMediaRecorder as unknown as typeof MediaRecorder)
}
```

- [ ] **Step 2: Write the failing test**

`frontend/src/voice/useRecorder.test.tsx`:
```tsx
import { renderHook, act, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { type ReactNode } from 'react'
import { useRecorder } from './useRecorder'
import { VoiceProvider } from './VoiceContext'
import { makeVoiceClient } from '../test/fakeClient'
import { stubMedia, MockMediaRecorder } from '../test/media'
import type { VoiceClient } from './voiceClient'

function wrapper(client: VoiceClient) {
  return ({ children }: { children: ReactNode }) => (
    <VoiceProvider language="it" client={client}>
      {children}
    </VoiceProvider>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  MockMediaRecorder.instances = []
})

test('record → stop → transcribe fills text via onText and returns to idle', async () => {
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'so cucinare' })
  const onText = vi.fn()
  const { result } = renderHook(() => useRecorder({ onText }), { wrapper: wrapper(client) })
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('recording')
  await act(async () => {
    result.current.stop()
  })
  await waitFor(() => expect(onText).toHaveBeenCalledWith('so cucinare'))
  expect(result.current.state).toBe('idle')
})

test('permission denied → state denied, onText never called', async () => {
  stubMedia(false)
  const onText = vi.fn()
  const { result } = renderHook(() => useRecorder({ onText }), { wrapper: wrapper(makeVoiceClient({})) })
  await act(async () => {
    await result.current.start()
  })
  expect(result.current.state).toBe('denied')
  expect(onText).not.toHaveBeenCalled()
})

test('transcribe unavailable (503) → state unavailable', async () => {
  stubMedia(true)
  const client = makeVoiceClient({}) // transcript undefined → unavailable
  const onText = vi.fn()
  const { result } = renderHook(() => useRecorder({ onText }), { wrapper: wrapper(client) })
  await act(async () => {
    await result.current.start()
  })
  await act(async () => {
    result.current.stop()
  })
  await waitFor(() => expect(result.current.state).toBe('unavailable'))
  expect(onText).not.toHaveBeenCalled()
})
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npm test -- useRecorder`
Expected: FAIL (module not found).

- [ ] **Step 4: Implement `useRecorder.ts`**

```ts
import { useCallback, useRef, useState } from 'react'
import { useVoice } from './VoiceContext'

export type RecorderState = 'idle' | 'requesting' | 'recording' | 'transcribing' | 'denied' | 'unavailable'

export function recorderSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined'
  )
}

export function useRecorder({ onText }: { onText: (text: string) => void }) {
  const { client, language } = useVoice()
  const [state, setState] = useState<RecorderState>('idle')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const start = useCallback(async () => {
    if (!recorderSupported()) {
      setState('unavailable')
      return
    }
    setState('requesting')
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setState('denied')
      return
    }
    chunksRef.current = []
    const rec = new MediaRecorder(stream)
    recorderRef.current = rec
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }
    rec.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop())
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
      setState('transcribing')
      const res = await client.transcribe(blob, language)
      if (res.status === 'ok') {
        onText(res.text)
        setState('idle')
      } else {
        setState('unavailable')
      }
    }
    rec.start()
    setState('recording')
  }, [client, language, onText])

  const stop = useCallback(() => {
    const rec = recorderRef.current
    if (rec && rec.state !== 'inactive') rec.stop()
  }, [])

  return { state, start, stop, supported: recorderSupported() }
}
```

- [ ] **Step 5: Run the tests and the gate**

Run: `npm test -- useRecorder && npm run typecheck && npm run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/test/media.ts frontend/src/voice/useRecorder.ts frontend/src/voice/useRecorder.test.tsx
git commit -m "feat(kiosk-voice): useRecorder capture hook (denied/unavailable degrade) + media test mock"
```

---

## Task 5: `VoiceBar` dictation (Parla + recording/transcribing states)

**Files:**
- Modify: `frontend/src/components/VoiceBar.tsx`
- Modify: `frontend/src/components/VoiceBar.test.tsx` (add dictation tests)

**Interfaces:**
- Consumes: `useRecorder` (Task 4).
- Produces: `VoiceBar(props: { text: string; canDictate?: boolean; onDictated?: (text: string) => void })`. Parla shown only when `canDictate && supported && state !== 'denied' && onDictated` is set. States: idle → «🎤 Parla» (start); recording → «⏹ Stop» + `t('voice.listening')`; transcribing → disabled + `t('voice.transcribing')`; unavailable/denied → `t('voice.micDenied')` note, no Parla.

- [ ] **Step 1: Write the failing dictation tests (append to VoiceBar.test.tsx)**

```tsx
import { vi } from 'vitest'
import { stubMedia } from '../test/media' // shared mock created in Task 4

test('dictation: Parla → Stop → onDictated fires with the transcript (field, not auto-submit)', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'so cucinare', audio: null })
  const onDictated = vi.fn()
  renderWithProviders(<VoiceBar text="Domanda" canDictate onDictated={onDictated} />, {
    voiceClient: client,
    language: 'it',
  })
  await userEvent.click(await screen.findByRole('button', { name: /Parla/ }))
  await userEvent.click(await screen.findByRole('button', { name: /Stop/ }))
  await waitFor(() => expect(onDictated).toHaveBeenCalledWith('so cucinare'))
  vi.unstubAllGlobals()
})

test('no Parla when canDictate is false', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  renderWithProviders(<VoiceBar text="Domanda" />, { voiceClient: makeVoiceClient({ audio: null }), language: 'it' })
  expect(screen.queryByRole('button', { name: /Parla/ })).not.toBeInTheDocument()
  vi.unstubAllGlobals()
})
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `npm test -- VoiceBar`
Expected: FAIL (no Parla button / `canDictate` prop yet).

- [ ] **Step 3: Update `VoiceBar.tsx` to add dictation**

```tsx
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useVoice } from '../voice/VoiceContext'
import { useSpeech } from '../voice/useSpeech'
import { useRecorder } from '../voice/useRecorder'

export function VoiceBar({
  text,
  canDictate = false,
  onDictated,
}: {
  text: string
  canDictate?: boolean
  onDictated?: (text: string) => void
}) {
  const { t } = useTranslation()
  const { language, muted, setMuted, client } = useVoice()
  const { play, stop } = useSpeech(client)
  const recorder = useRecorder({ onText: (txt) => onDictated?.(txt) })

  useEffect(() => {
    if (!muted && text) void play(text, language)
    return () => stop()
  }, [text, language, muted, play, stop])

  function toggleMute() {
    if (!muted) stop()
    setMuted(!muted)
  }

  const dictationOn = canDictate && recorder.supported && !!onDictated
  const denied = recorder.state === 'denied' || recorder.state === 'unavailable'

  function renderParla() {
    if (!dictationOn) return null
    if (denied) return <span className="voice-note">{t('voice.micDenied')}</span>
    if (recorder.state === 'recording')
      return (
        <>
          <button className="voice-btn danger" onClick={recorder.stop}>
            ⏹ {t('voice.stop')}
          </button>
          <span className="voice-note recording" role="status" aria-live="polite">
            ● {t('voice.listening')}
          </span>
        </>
      )
    if (recorder.state === 'transcribing')
      return (
        <span className="voice-note" role="status" aria-live="polite">
          ⏳ {t('voice.transcribing')}
        </span>
      )
    return (
      <button className="voice-btn primary" onClick={() => void recorder.start()}>
        🎤 {t('voice.speak')}
      </button>
    )
  }

  return (
    <div className="voice-bar">
      {renderParla()}
      <button className="voice-btn" aria-label={t('voice.listen')} onClick={() => void play(text, language)}>
        🔊 {t('voice.listen')}
      </button>
      <button className="voice-btn" aria-pressed={muted} aria-label={t('voice.muteToggle')} onClick={toggleMute}>
        {muted ? '🔇' : '🔈'} {muted ? t('voice.audioOff') : t('voice.audioOn')}
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Run the tests and the gate**

Run: `npm test -- VoiceBar && npm run typecheck && npm run lint`
Expected: PASS (auto-read/mute tests still green; dictation tests green).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/VoiceBar.tsx frontend/src/components/VoiceBar.test.tsx
git commit -m "feat(kiosk-voice): VoiceBar dictation (Parla/Stop, recording & transcribing states)"
```

---

## Task 6: Embed `VoiceBar` in `AnswerPrompt` + `ConfirmCorrect`

**Files:**
- Modify: `frontend/src/components/AnswerPrompt.tsx`
- Modify: `frontend/src/components/ConfirmCorrect.tsx`
- Test: extend `AnswerPrompt.test.tsx`, `ConfirmCorrect.test.tsx`

**Interfaces:**
- `AnswerPrompt`: renders `<VoiceBar text={text} canDictate onDictated={setValue} />` above the textarea (dictation replaces the field value for review). Signature unchanged.
- `ConfirmCorrect`: renders `<VoiceBar text={text} />` (read-only) in the confirm branch; `<VoiceBar text={text} canDictate onDictated={setValue} />` in the correcting branch. Signature unchanged.

- [ ] **Step 1: Write the failing tests (append)**

`AnswerPrompt.test.tsx`:
```tsx
import { makeVoiceClient } from '../test/fakeClient'
import { stubMedia } from '../test/media'

test('dictated text lands in the field for review (does not auto-submit)', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  const client = makeVoiceClient({ transcript: 'ho lavorato in cucina', audio: null })
  const onSubmit = vi.fn()
  renderWithProviders(<AnswerPrompt text="Che lavoro sai fare?" onSubmit={onSubmit} />, { voiceClient: client })
  await userEvent.click(await screen.findByRole('button', { name: /Parla/ }))
  await userEvent.click(await screen.findByRole('button', { name: /Stop/ }))
  await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('ho lavorato in cucina'))
  expect(onSubmit).not.toHaveBeenCalled() // review, not auto-submit
  vi.unstubAllGlobals()
})
```
`ConfirmCorrect.test.tsx`:
```tsx
test('confirm branch shows read-aloud but no Parla; correcting branch enables Parla', async () => {
  await i18n.changeLanguage('it')
  stubMedia(true)
  renderWithProviders(<ConfirmCorrect text="Ho capito: sai cucinare" onSubmit={vi.fn()} />, {
    voiceClient: makeVoiceClient({ audio: null }),
  })
  expect(screen.getByRole('button', { name: 'Ascolta' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Parla/ })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'No, correggi qualcosa' }))
  expect(await screen.findByRole('button', { name: /Parla/ })).toBeInTheDocument()
  vi.unstubAllGlobals()
})
```
(Import `stubMedia` from `../test/media` — the shared mock created in Task 4. `ConfirmCorrect.test.tsx` needs `import { stubMedia } from '../test/media'` and `import { makeVoiceClient } from '../test/fakeClient'`.)

- [ ] **Step 2: Run to verify the new tests fail**

Run: `npm test -- AnswerPrompt ConfirmCorrect`
Expected: FAIL (no Parla; VoiceBar not embedded yet).

- [ ] **Step 3: Embed `VoiceBar` in `AnswerPrompt.tsx`**

Add the import and render `<VoiceBar>` above the textarea:
```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'
import { VoiceBar } from './VoiceBar'

export function AnswerPrompt({
  text,
  onSubmit,
  banner,
  busy,
}: {
  text: string
  onSubmit: (answer: string) => void
  banner?: string
  busy?: boolean
}) {
  const { t } = useTranslation()
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  return (
    <div>
      {banner && <div className="banner-warn">{banner}</div>}
      <p className="prompt-text">{text}</p>
      <VoiceBar text={text} canDictate onDictated={setValue} />
      <textarea
        aria-label={t('prompt.placeholder')}
        placeholder={t('prompt.placeholder')}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <BigButton
        variant="confirm"
        disabled={!trimmed || busy}
        onClick={() => {
          onSubmit(trimmed)
          setValue('')
        }}
      >
        {t('prompt.next')}
      </BigButton>
    </div>
  )
}
```

- [ ] **Step 4: Embed `VoiceBar` in `ConfirmCorrect.tsx`**

```tsx
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BigButton } from './BigButton'
import { VoiceBar } from './VoiceBar'

export function ConfirmCorrect({
  text,
  onSubmit,
  busy,
}: {
  text: string
  onSubmit: (answer: string) => void
  busy?: boolean
}) {
  const { t } = useTranslation()
  const [correcting, setCorrecting] = useState(false)
  const [value, setValue] = useState('')
  const trimmed = value.trim()
  return (
    <div>
      <p className="prompt-text">{text}</p>
      {!correcting ? (
        <>
          <VoiceBar text={text} />
          <BigButton variant="confirm" disabled={busy} onClick={() => onSubmit(t('confirm.yes'))}>
            {t('confirm.yes')}
          </BigButton>
          <BigButton variant="secondary" onClick={() => setCorrecting(true)}>
            {t('confirm.no')}
          </BigButton>
        </>
      ) : (
        <>
          <VoiceBar text={text} canDictate onDictated={setValue} />
          <textarea
            aria-label={t('confirm.correctPlaceholder')}
            placeholder={t('confirm.correctPlaceholder')}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <BigButton variant="confirm" disabled={!trimmed || busy} onClick={() => onSubmit(trimmed)}>
            {t('confirm.send')}
          </BigButton>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Run the tests and the gate**

Run: `npm test && npm run typecheck && npm run lint`
Expected: PASS. (Existing AnswerPrompt/ConfirmCorrect tests still pass — the default `noopVoiceClient` keeps the embedded VoiceBar silent and, with no media stubbed, `recorder.supported` is false so Parla is hidden unless a test stubs media.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AnswerPrompt.tsx frontend/src/components/ConfirmCorrect.tsx frontend/src/components/AnswerPrompt.test.tsx frontend/src/components/ConfirmCorrect.test.tsx frontend/src/test
git commit -m "feat(kiosk-voice): embed VoiceBar in AnswerPrompt & ConfirmCorrect (dictation → field)"
```

---

## Task 7: Wire screens + App `VoiceProvider`, remove `VoicePlaceholder`, integration tests

**Files:**
- Modify: `frontend/src/screens/Consent.tsx`, `Unavailable.tsx`, `Completed.tsx`, `Unauthorized.tsx` (add read-only `VoiceBar`)
- Modify: `frontend/src/App.tsx` (wrap screen area in `VoiceProvider`, add `voiceClient` prop, remove `VoicePlaceholder`)
- Modify: `frontend/src/main.tsx` (no VoicePlaceholder; App self-wraps VoiceProvider — no change needed unless it imported VoicePlaceholder)
- Delete: `frontend/src/components/VoicePlaceholder.tsx` + `frontend/src/components/VoicePlaceholder.test.tsx`
- Modify: `frontend/src/i18n/locales/{it,en,fr,es,ar}.ts` (remove `voice.placeholder`)
- Modify: `frontend/src/styles/theme.css` (add `.voice-bar` styles)
- Test: extend `frontend/src/App.test.tsx`

**Interfaces:**
- `App({ client = kioskClient, voiceClient = realVoiceClient })` — renders `<VoiceProvider language={state.language ?? 'it'} client={voiceClient}>` around `<main>{renderScreen()}</main>`.
- Consent/Unavailable/Completed/Unauthorized each render a read-only `<VoiceBar text={...} />`.

- [ ] **Step 1: Write the failing integration tests (append to App.test.tsx)**

```tsx
import { makeVoiceClient, noopVoiceClient } from './test/fakeClient'

// NOTE: existing App tests must pass voiceClient={noopVoiceClient} to stay silent —
// update each existing `renderWithProviders(<App .../>)` to include it.

test('auto-reads the interview question via synthesize when a step appears', async () => {
  const fakeVoice = makeVoiceClient({ audio: null })
  const client = makeFakeClient({
    start: { status: 'ok', sessionToken: 'tok', step: step('question', 'Che lavoro sai fare?') },
  })
  renderWithProviders(<App client={client} voiceClient={fakeVoice} />)
  await userEvent.click(screen.getByRole('button', { name: 'Italiano' }))
  await userEvent.click(await screen.findByRole('button', { name: 'Ho capito, iniziamo' }))
  await screen.findByText('Che lavoro sai fare?')
  await waitFor(() =>
    expect(fakeVoice.calls.synthesize.some((c) => c.text === 'Che lavoro sai fare?' && c.language === 'it')).toBe(true),
  )
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- App`
Expected: FAIL (App has no `voiceClient` prop / auto-read not wired).

- [ ] **Step 3: Add read-only `VoiceBar` to the four text screens**

`Consent.tsx` — after the `<ul>` of points, before the buttons, add a VoiceBar reading title+points:
```tsx
import { VoiceBar } from '../components/VoiceBar'
// ...inside the component, build the spoken text:
const spoken = [t('consent.title'), ...POINTS.map((p) => t(`consent.point.${p}`))].join('. ')
// ...in JSX, right after </ul>:
<VoiceBar text={spoken} />
```
`Unavailable.tsx`, `Completed.tsx`, `Unauthorized.tsx` — render `<VoiceBar text={t('<the message key>')} />` inside the `Notice` (as a child, before/after the existing children). Example for `Unauthorized.tsx`:
```tsx
import { VoiceBar } from '../components/VoiceBar'
export function Unauthorized() {
  const { t } = useTranslation()
  return (
    <Notice tone="error" text={t('unauthorized.text')}>
      <VoiceBar text={t('unauthorized.text')} />
    </Notice>
  )
}
```
(For `Unavailable`/`Completed`, add `<VoiceBar text={t('unavailable.text')} />` / `<VoiceBar text={t('completed.text')} />` alongside their existing retry/finish buttons.)

- [ ] **Step 4: Update `App.tsx` — VoiceProvider + voiceClient prop, remove VoicePlaceholder**

```tsx
import { voiceClient as realVoiceClient } from './voice/voiceClient'
import { VoiceProvider } from './voice/VoiceContext'
import type { VoiceClient } from './voice/voiceClient'
// remove: import { VoicePlaceholder } from './components/VoicePlaceholder'

export function App({
  client = kioskClient,
  voiceClient = realVoiceClient,
}: { client?: KioskClient; voiceClient?: VoiceClient } = {}) {
  // ...unchanged reducer/handlers...
  const inSession = state.screen !== 'language'
  return (
    <div className="app">
      <header className="chrome">
        {inSession ? <StopButton onStop={stop} /> : <span />}
        {state.pending && (
          <div className="pending" role="status" aria-live="polite">
            {t('pending.text')}
          </div>
        )}
        <TextSizeControl />
      </header>
      <VoiceProvider language={state.language ?? 'it'} client={voiceClient}>
        <main>{renderScreen()}</main>
      </VoiceProvider>
    </div>
  )
}
```
(Remove the `<VoicePlaceholder />` from the chrome. The VoiceBar now lives inside each screen.)

- [ ] **Step 5: Delete VoicePlaceholder, remove the i18n key, update existing App tests, add theme**

- Delete `frontend/src/components/VoicePlaceholder.tsx` and `frontend/src/components/VoicePlaceholder.test.tsx`.
- Remove `placeholder` from the `voice` object in all 5 catalogs (keep the Task-1 voice keys; parity still holds).
- Update every existing `renderWithProviders(<App ... />)` in `App.test.tsx` to pass `voiceClient={noopVoiceClient}` (keeps them silent/pristine).
- Add to `frontend/src/styles/theme.css`:
```css
.voice-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-block: 12px; padding: 10px 12px; background: #f3f4f6; border-radius: 12px; }
.voice-btn { font: inherit; font-size: calc(16px * var(--text-scale)); font-weight: 700; padding: 12px 16px; border-radius: 10px; border: 2px solid #2563eb; background: #fff; color: #2563eb; cursor: pointer; }
.voice-btn.primary { background: #2563eb; color: #fff; }
.voice-btn.danger { background: var(--danger); color: #fff; border-color: var(--danger); }
.voice-btn[aria-pressed='true'] { background: #e5e7eb; color: #374151; border-color: #9ca3af; }
.voice-note { color: var(--muted); font-weight: 600; }
.voice-note.recording { color: var(--danger); }
```

- [ ] **Step 6: Run the FULL suite and the gate**

Run: `npm test && npm run typecheck && npm run lint && npm run build`
Expected: all PASS / exit 0; output pristine (no act() warnings). Confirm `i18n.test.ts` parity still green after removing `voice.placeholder`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git rm frontend/src/components/VoicePlaceholder.tsx frontend/src/components/VoicePlaceholder.test.tsx
git commit -m "feat(kiosk-voice): wire VoiceBar into screens + App VoiceProvider; remove placeholder"
```

---

## After all tasks

- **Manual/optional real round-trip (WebM decode risk):** with the real backend up (`llama`/voice not needed for STT decode itself, but the voice libs + models must be installed), record a short WebM clip in a Chromium kiosk session and confirm `/kiosk/voice/transcribe` returns text (validates faster-whisper/PyAV decoding of WebM/Opus, never exercised before — only WAV). If it fails, fall back to recording WAV via WebAudio or add a backend decode step. Log the result.
- Update `STATO_TECNICO.md`: the frontend voice layer (`voice/` client + hooks, `VoiceBar`, `VoiceProvider`), the decisions (auto-read+mute, reviewable dictation, contextual bar), the audio-unlock/degradation, and the §14 follow-ups (WebM round-trip to validate; Arabic TTS voice still absent).
- Run the final whole-branch review (opus), then `superpowers:finishing-a-development-branch`.
```
