import { useCallback, useRef, useState } from 'react'
import type { VoiceClient } from './voiceClient'

export function useSpeech(client: VoiceClient) {
  const [speaking, setSpeaking] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const urlRef = useRef<string | null>(null)
  const genRef = useRef(0)

  const stop = useCallback(() => {
    genRef.current++ // invalidate any in-flight play()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
    setSpeaking(false)
  }, [])

  const play = useCallback(
    async (text: string, language: string) => {
      stop()
      const gen = genRef.current
      const blob = await client.synthesize(text, language)
      // 204/no audio, or a newer stop()/play() superseded this one → drop (no Audio, no URL)
      if (!blob || gen !== genRef.current) return
      const url = URL.createObjectURL(blob)
      urlRef.current = url
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = () => {
        URL.revokeObjectURL(url)
        urlRef.current = null
        setSpeaking(false)
      }
      try {
        await audio.play()
        if (gen !== genRef.current) return // stopped while play() was resolving
        setSpeaking(true)
      } catch {
        URL.revokeObjectURL(url)
        if (gen !== genRef.current) return // superseded → don't clobber the newer generation
        urlRef.current = null
        audioRef.current = null
        setSpeaking(false)
      }
    },
    [client, stop],
  )

  return { play, stop, speaking }
}
