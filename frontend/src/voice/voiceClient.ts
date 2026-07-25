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
