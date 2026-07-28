import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useApiError } from './useApiError'

type Fetchable = { status: 'ok' | 'unauthorized' | 'forbidden' | 'error' }

// Centralizes the fetch-on-mount + degrade pattern shared by the read-only
// panels: 401 → useApiError (redirect), 403/error → i18n message, unmount guard.
export function useFetchOnMount<R extends Fetchable, T>(
  fetcher: () => Promise<R>,
  onOk: (r: Extract<R, { status: 'ok' }>) => T,
): { data: T | null; error: string } {
  const { t } = useTranslation()
  const handleError = useApiError()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const onOkRef = useRef(onOk)
  onOkRef.current = onOk

  useEffect(() => {
    let active = true
    void fetcher().then((r) => {
      if (!active) return
      if (r.status === 'ok') {
        setData(onOkRef.current(r as Extract<R, { status: 'ok' }>))
      } else {
        const outcome = handleError(r.status)
        if (outcome !== 'handled') {
          setError(t(outcome === 'forbidden' ? 'errors.forbidden' : 'errors.generic'))
        }
      }
    })
    return () => {
      active = false
    }
  }, [fetcher, handleError, t])

  return { data, error }
}
