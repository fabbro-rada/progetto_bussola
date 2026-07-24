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
