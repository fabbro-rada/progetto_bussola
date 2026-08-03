import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useVoice } from '../voice/VoiceContext'
import { useSpeech } from '../voice/useSpeech'
import { useRecorder } from '../voice/useRecorder'

export function VoiceBar({
  text,
  canDictate = false,
  onDictated,
  onBusyChange,
  disabled = false,
}: {
  text: string
  canDictate?: boolean
  onDictated?: (text: string) => void
  onBusyChange?: (busy: boolean) => void
  // The surrounding form is busy (e.g. a submitted answer is being processed):
  // the whole voice bar goes inert so nothing is started/played mid-request.
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const { language, muted, setMuted, client } = useVoice()
  const { play, stop } = useSpeech(client)
  const recorder = useRecorder({ onText: (txt) => onDictated?.(txt) })

  // Voice is "busy" from the moment we ask for the mic until the transcript is
  // in: the field and the other controls must be inert during this window, so
  // nothing gets typed/played over a dictation in progress. Surfaced upward so
  // the surrounding form can disable its textarea and submit (§7.1).
  const voiceBusy =
    recorder.state === 'requesting' ||
    recorder.state === 'recording' ||
    recorder.state === 'transcribing'

  useEffect(() => {
    onBusyChange?.(voiceBusy)
  }, [voiceBusy, onBusyChange])

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
    if (recorder.state === 'requesting')
      return (
        <span className="voice-note" role="status" aria-live="polite">
          … {t('voice.requesting')}
        </span>
      )
    return (
      <button className="voice-btn primary" disabled={disabled} onClick={() => void recorder.start()}>
        🎤 {t('voice.speak')}
      </button>
    )
  }

  return (
    <div className="voice-bar">
      {renderParla()}
      <button
        className="voice-btn"
        aria-label={t('voice.listen')}
        disabled={disabled || voiceBusy}
        onClick={() => void play(text, language)}
      >
        🔊 {t('voice.listen')}
      </button>
      <button
        className="voice-btn"
        aria-pressed={muted}
        aria-label={t('voice.muteToggle')}
        disabled={disabled || voiceBusy}
        onClick={toggleMute}
      >
        {muted ? '🔇' : '🔈'} {muted ? t('voice.audioOff') : t('voice.audioOn')}
      </button>
    </div>
  )
}
