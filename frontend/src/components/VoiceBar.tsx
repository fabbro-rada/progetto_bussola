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
