import { Fragment, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { useFetchOnMount } from '../../hooks/useFetchOnMount'

export function SystemConfigPanel() {
  const { t } = useTranslation()
  const { client } = useAuth()
  const fetchConfig = useCallback(() => client.getSystemConfig(), [client])
  const { data: config, error } = useFetchOnMount(fetchConfig, (r) => r.config)

  return (
    <div className="system-config">
      <h1>{t('system.title')}</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {config === null && !error ? (
        <p>{t('common.loading')}</p>
      ) : (
        config && (
          <div className="config-sections">
            <section>
              <h2>{t('system.llm')}</h2>
              <dl>
                <dt>{t('system.llmModel')}</dt><dd>{config.llm_model}</dd>
                <dt>{t('system.llmEndpoint')}</dt><dd>{config.llm_base_url}</dd>
                <dt>{t('system.llmTimeout')}</dt><dd>{config.llm_timeout}</dd>
                <dt>{t('system.llmStatus')}</dt>
                <dd>
                  <span className={`badge-status ${config.llm_reachable ? 'st-approved' : ''}`.trim()}>
                    {config.llm_reachable ? t('system.reachable') : t('system.unreachable')}
                  </span>
                </dd>
              </dl>
            </section>
            <section>
              <h2>{t('system.languages')}</h2>
              <p>{config.languages.join(', ')}</p>
            </section>
            <section>
              <h2>{t('system.voice')}</h2>
              <dl>
                <dt>{t('system.sttModel')}</dt><dd>{config.stt_model}</dd>
                {config.languages.map((lang) => (
                  <Fragment key={lang}>
                    <dt>{lang}</dt>
                    <dd>{config.tts_voices[lang] ? t('system.ttsAvailable') : t('system.ttsTextOnly')}</dd>
                  </Fragment>
                ))}
              </dl>
            </section>
            <section>
              <h2>{t('system.session')}</h2>
              <dl>
                <dt>{t('system.sessionTtl')}</dt><dd>{config.session_ttl_seconds}</dd>
                <dt>{t('system.sessionIdle')}</dt><dd>{config.session_idle_seconds}</dd>
                <dt>{t('system.maxAttempts')}</dt><dd>{config.max_failed_attempts}</dd>
                <dt>{t('system.lockout')}</dt><dd>{config.lockout_seconds}</dd>
              </dl>
            </section>
          </div>
        )
      )}
    </div>
  )
}
