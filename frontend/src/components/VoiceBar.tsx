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

  // Auto-read the current text when it (or the language) changes, unless muted.
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
