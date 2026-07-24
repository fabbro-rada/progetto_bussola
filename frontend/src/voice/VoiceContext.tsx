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
