import { useCallback, useEffect, useRef, useState } from 'react'
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
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const busyRef = useRef(false)
  const mountedRef = useRef(true)

  useEffect(
    () => () => {
      // Release the mic if we unmount mid-capture (e.g. «Ferma» while recording).
      mountedRef.current = false
      if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop()
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
        streamRef.current = null
      }
    },
    [],
  )

  const start = useCallback(async () => {
    if (busyRef.current) return // re-entrancy guard
    if (!recorderSupported()) {
      setState('unavailable')
      return
    }
    busyRef.current = true
    setState('requesting')
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      busyRef.current = false
      setState('denied')
      return
    }
    streamRef.current = stream
    chunksRef.current = []
    const rec = new MediaRecorder(stream)
    recorderRef.current = rec
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }
    rec.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      if (!mountedRef.current) {
        busyRef.current = false
        return
      }
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
      setState('transcribing')
      const res = await client.transcribe(blob, language)
      busyRef.current = false
      if (!mountedRef.current) return
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
