import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

type ErrorStatus = 'unauthorized' | 'forbidden' | 'not-found' | 'error'

export function useApiError(): (status: ErrorStatus) => 'forbidden' | 'not-found' | 'error' | 'handled' {
  const { onUnauthorized } = useAuth()
  const navigate = useNavigate()
  return useCallback(
    (status: ErrorStatus) => {
      if (status === 'unauthorized') {
        onUnauthorized() // sets the S11 sessionExpired flag; Login renders the notice
        navigate('/login', { replace: true })
        return 'handled' as const
      }
      return status
    },
    [onUnauthorized, navigate],
  )
}
